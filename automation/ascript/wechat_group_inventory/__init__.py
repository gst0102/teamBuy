# -*- coding: utf-8 -*-
"""Read-only inventory of native WeChat group chats for both dual-app slots.

The script reads both WeChat's built-in ``通讯录 -> 群聊`` list and the
scrollable home conversation list. The latter is needed for groups that were
not saved into Contacts. It never opens a group, reads messages, sends a
message, joins a group, or changes a group remark.

Native WeChat groups do not expose an invitation QR in this list. The PC API
therefore receives ``source=wechat_native`` and a null ``groupQRCode``.
"""

from __future__ import print_function

import hashlib
import json
import re
import time
import urllib.request

import cv2
import numpy as np
from ascript.android import action, node
from ascript.android.screen import Ocr, capture_cv
from ascript.android.system import Device
from ascript.android.system import open as open_app


DEVICE_ID = "android-01"
DEVICE_NAME = "安卓双开微信手机"
INPUT_MODE = "ascript_native"
try:
    from . import local_config as _local_config
except Exception:
    _local_config = None

BACKEND_URL = getattr(_local_config, "BACKEND_URL", "")
DEVICE_TOKEN = getattr(_local_config, "DEVICE_TOKEN", "")
WECHAT_PACKAGE = "com.tencent.mm"
DUAL_APP_PACKAGE = "com.zte.cn.doubleapp"
INSTANCE_SLOTS = tuple(
    getattr(
        _local_config,
        "INSTANCE_SLOTS",
        ("wechat-instance-1", "wechat-instance-2"),
    )
)
UI_MODE = 2
MAX_SCROLLS = 60
MAX_CHAT_SCROLLS = 180
MAX_CHAT_RESET_SCROLLS = 12
GROUP_AVATAR_GRID_MIN = 6.0
GROUP_AVATAR_GRID_MAX_SEAM_MIN = 30.0
GROUP_NAME_HINTS = (
    "群",
    "交流群",
    "同好会",
    "集会",
    "后援会",
    "家族",
    "团队",
    "基地",
    "资源",
    "房源",
    "宠物",
    "租房",
    "培训",
    "贸易",
    "进出口",
    "行业",
    "水产",
    "冻品",
    "创业",
    "俱乐部",
    "同城",
    "答疑",
    "领养",
    "寻宠",
    "铲屎官",
    "毛孩子",
    "社区",
)
NON_GROUP_NAMES = {"服务号", "公众号", "微信团队"}


def _keep_screen_awake():
    try:
        Device.wake_up()
        Device.keep_screen_on()
        print("已开启屏幕常亮")
    except Exception as exc:
        print("开启屏幕常亮失败:", exc)


_keep_screen_awake()


def _device_size():
    display = Device.display()
    return int(display.widthPixels), int(display.heightPixels)


def _dump(mode=None):
    mode = UI_MODE if mode is None else mode
    node.Selector.refresh(mode)
    raw = node.Selector.dump(mode)
    return json.loads(raw) if isinstance(raw, str) else raw


def _walk(value, parents=None):
    parents = parents or []
    if isinstance(value, list):
        for item in value:
            for found in _walk(item, parents):
                yield found
        return
    if not isinstance(value, dict):
        return
    current = parents + [value]
    yield current
    # Device-side Selector.dump() returns {config, views}; views are the
    # actual roots and are not nested under ``childs``.
    for view in value.get("views", []) or []:
        for found in _walk(view, parents):
            yield found
    for child in value.get("childs", []) or []:
        for found in _walk(child, current):
            yield found


def _rect(item):
    rect = item.get("rect") or {}
    if isinstance(rect, dict):
        return (
            int(rect.get("left", 0)),
            int(rect.get("top", 0)),
            int(rect.get("right", 0)),
            int(rect.get("bottom", 0)),
        )
    return 0, 0, 0, 0


def _valid_rect(rect):
    return rect[2] > rect[0] and rect[3] > rect[1]


def _wait_for(predicate, timeout=10, interval=0.5):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            value = predicate()
            if value:
                return value
        except Exception as exc:
            print("等待微信界面失败:", exc)
        time.sleep(interval)
    return None


def _tap(x, y):
    action.click(int(x), int(y), dur=30)
    time.sleep(0.7)


def _swipe(x, y, x1, y1):
    action.swipe(int(x), int(y), int(x1), int(y1), dur=450)
    time.sleep(1.0)


def _clickable_ancestor(path):
    for item in reversed(path[:-1]):
        rect = _rect(item)
        if item.get("clickable") is True and _valid_rect(rect):
            return rect
    return None


def _point_for_text(text, package=WECHAT_PACKAGE, min_top=0, max_top=None):
    try:
        tree = _dump()
    except Exception:
        tree = None
    for path in _walk(tree):
        item = path[-1]
        if item.get("packageName") != package or item.get("text") != text:
            continue
        rect = _clickable_ancestor(path) or _rect(item)
        if not _valid_rect(rect):
            continue
        if rect[1] < min_top or (max_top is not None and rect[1] > max_top):
            continue
        return (int((rect[0] + rect[2]) / 2), int((rect[1] + rect[3]) / 2))
    return None


def _point_for_id(resource_id, package=WECHAT_PACKAGE, min_top=0, max_top=None):
    try:
        tree = _dump()
    except Exception:
        tree = None
    for path in _walk(tree):
        item = path[-1]
        if item.get("packageName") != package or item.get("id") != resource_id:
            continue
        rect = _clickable_ancestor(path) or _rect(item)
        if not _valid_rect(rect):
            continue
        if rect[1] < min_top or (max_top is not None and rect[1] > max_top):
            continue
        return (int((rect[0] + rect[2]) / 2), int((rect[1] + rect[3]) / 2))
    return None


def _chooser_points():
    width, height = _device_size()
    points = []
    try:
        tree = _dump(0)
        for path in _walk(tree):
            item = path[-1]
            if (
                item.get("text") == "微信"
                and item.get("visible") is not False
                and item.get("packageName") == DUAL_APP_PACKAGE
            ):
                rect = _clickable_ancestor(path)
                if rect:
                    points.append(
                        (int((rect[0] + rect[2]) / 2), int((rect[1] + rect[3]) / 2))
                    )
    except Exception as exc:
        print("微信双开选择器读取失败:", exc)
    if len(points) >= 2:
        return sorted(set(points), key=lambda point: point[0])

    for match in Ocr.find_all("微信", rect=[0, int(height * 0.65), width, height]) or []:
        rect = _rect(match)
        if _valid_rect(rect):
            points.append(
                (
                    int(match.get("center_x") or (rect[0] + rect[2]) / 2),
                    int(match.get("center_y") or (rect[1] + rect[3]) / 2),
                )
            )
    return sorted(points, key=lambda point: point[0])


def _select_wechat_instance(slot_index):
    points = _wait_for(_chooser_points, timeout=10)
    if not points or len(points) <= slot_index:
        raise RuntimeError("未找到双开微信选择器的两个微信入口")
    _tap(*points[slot_index])


def _open_wechat(slot_index):
    action.Key.home()
    time.sleep(1.0)
    open_app(WECHAT_PACKAGE)
    _select_wechat_instance(slot_index)
    for _ in range(5):
        home = _point_for_text("我", min_top=1800)
        if home:
            return home
        # WeChat restores the last child page for each clone. Prefer the
        # observed action-bar up button, then use the native back key. This
        # never opens a group conversation.
        up = _point_for_id("com.tencent.mm:id/actionbar_up_indicator", max_top=320)
        if up:
            _tap(*up)
        else:
            action.Key.back()
            time.sleep(0.8)
    raise RuntimeError("微信首页未出现“我”入口")


def _read_nickname():
    try:
        tree = _dump()
    except Exception:
        tree = None
    texts = []
    for path in _walk(tree):
        item = path[-1]
        if item.get("packageName") != WECHAT_PACKAGE or item.get("visible") is False:
            continue
        rect = _rect(item)
        text = str(item.get("text") or "").strip()
        if text and _valid_rect(rect):
            texts.append((text, rect))
    anchors = [(text, rect) for text, rect in texts if text.startswith(("微信号：", "微信号:"))]
    if anchors:
        _, anchor_rect = anchors[0]
        candidates = [
            (text, rect)
            for text, rect in texts
            if not text.startswith(("微信号：", "微信号:"))
            and rect[3] <= anchor_rect[1]
            and rect[3] > 100
            and len(text) <= 80
        ]
        if candidates:
            return max(candidates, key=lambda item: item[1][3])[0]

    matches = Ocr.find_all(rect=[0, 150, _device_size()[0], 650]) or []
    anchor = next(
        (
            item
            for item in matches
            if "微信号：" in str(item.get("text", ""))
            or "微信号:" in str(item.get("text", ""))
        ),
        None,
    )
    if not anchor:
        return None
    anchor_rect = _rect(anchor)
    for candidate in sorted(matches, key=lambda item: _rect(item)[3], reverse=True):
        text = str(candidate.get("text") or "").strip()
        rect = _rect(candidate)
        if (
            text
            and text != str(anchor.get("text") or "").strip()
            and "微信号" not in text
            and rect[2] <= 850
            and rect[3] <= anchor_rect[1]
        ):
            return text
    return None


def _account_id(nickname):
    digest = hashlib.sha256(("wechat:" + nickname).encode("utf-8")).hexdigest()[:20]
    return "wechat-nickname-" + digest


def _open_group_chat_list():
    contacts = _wait_for(lambda: _point_for_text("通讯录", min_top=1800), timeout=10)
    if not contacts:
        raise RuntimeError("未找到通讯录入口")
    _tap(*contacts)
    group_entry = _wait_for(lambda: _point_for_text("群聊", min_top=300, max_top=900), timeout=10)
    if not group_entry:
        raise RuntimeError("通讯录中未找到群聊入口")
    _tap(*group_entry)
    if not _wait_for(lambda: _group_names_and_total()[0], timeout=10):
        raise RuntimeError("群聊页面未出现群名")


def _open_chat_list():
    """Open the home conversation list without opening any conversation."""
    back = _point_for_text("微信", min_top=1800)
    if not back:
        up = _point_for_id("com.tencent.mm:id/actionbar_up_indicator", max_top=320)
        if up:
            _tap(*up)
        else:
            action.Key.back()
            time.sleep(0.8)
    chat_tab = _wait_for(lambda: _point_for_text("微信", min_top=1800), timeout=10)
    if not chat_tab:
        raise RuntimeError("未找到微信聊天 Tab")
    _tap(*chat_tab)
    if not _wait_for(lambda: len(_chat_rows()) >= 3, timeout=15):
        raise RuntimeError("微信聊天页未出现会话列表")


def _first_descendant_text(value, target_id):
    if isinstance(value, list):
        for item in value:
            found = _first_descendant_text(item, target_id)
            if found:
                return found
        return None
    if not isinstance(value, dict):
        return None
    if value.get("id") == target_id and value.get("text"):
        return str(value.get("text")).strip()
    found = _first_descendant_text(value.get("views", []) or [], target_id)
    if found:
        return found
    return _first_descendant_text(value.get("childs", []) or [], target_id)


def _chat_rows():
    try:
        tree = _dump()
    except Exception:
        return []
    rows = []
    seen = set()
    for path in _walk(tree):
        item = path[-1]
        if (
            item.get("packageName") != WECHAT_PACKAGE
            or item.get("id") != WECHAT_PACKAGE + ":id/cj1"
            or item.get("clickable") is not True
        ):
            continue
        rect = _rect(item)
        name = _first_descendant_text(item, WECHAT_PACKAGE + ":id/kbq")
        if not name or not _valid_rect(rect):
            continue
        key = (name, rect[1], rect[3])
        if key in seen:
            continue
        seen.add(key)
        rows.append({"name": name, "rect": rect})
    return sorted(rows, key=lambda item: item["rect"][1])


def _group_avatar_features(bitmap, row_rect):
    """Return grid evidence for WeChat's multi-avatar group tile."""
    if bitmap is None:
        return 0.0, 0.0, 0.0, 0.0, 0.0
    height, width = bitmap.shape[:2]
    left = max(0, min(width, 40))
    right = max(left, min(width, 195))
    top = max(0, row_rect[1] + 20)
    bottom = min(height, row_rect[1] + 175)
    if right - left < 80 or bottom - top < 80:
        return 0.0, 0.0, 0.0, 0.0, 0.0
    crop = bitmap[top:bottom, left:right]
    if crop is None or crop.size == 0:
        return 0.0, 0.0, 0.0, 0.0, 0.0
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY).astype(np.float32)
    vertical_seams = np.abs(np.diff(gray, axis=1)).mean(axis=0)
    horizontal_seams = np.abs(np.diff(gray, axis=0)).mean(axis=1)
    internal = horizontal_seams[12:140]
    if len(internal) < 3:
        return 0.0, 0.0, 0.0, 0.0, 0.0
    top_three = sorted(internal)[-3:]
    grid_vertical = list(vertical_seams[45:57]) + list(vertical_seams[96:108])
    grid_horizontal = list(horizontal_seams[45:57]) + list(horizontal_seams[96:108])
    return (
        float(max(internal)),
        float(sum(top_three) / 3.0),
        float(sum(grid_vertical) / len(grid_vertical)) if grid_vertical else 0.0,
        float(sum(grid_horizontal) / len(grid_horizontal)) if grid_horizontal else 0.0,
        float(max(grid_horizontal)) if grid_horizontal else 0.0,
    )


def _chat_group_names_for_frame(bitmap, rows=None):
    names = []
    for row in rows or _chat_rows():
        row_rect = row["rect"]
        # Do not classify a partially visible avatar; it can produce a false
        # seam at the screen edge. The next scroll will revisit the row.
        if row_rect[1] < 0 or row_rect[1] + 175 > _device_size()[1]:
            continue
        h_max, h_top_three, grid_v, grid_h, grid_h_max = _group_avatar_features(bitmap, row_rect)
        strong_avatar_grid = (
            grid_v >= GROUP_AVATAR_GRID_MIN
            and grid_h >= GROUP_AVATAR_GRID_MIN
            and grid_h_max >= GROUP_AVATAR_GRID_MAX_SEAM_MIN
        )
        name_hint = any(token in row["name"] for token in GROUP_NAME_HINTS)
        if row["name"] in NON_GROUP_NAMES or not (strong_avatar_grid or name_hint):
            continue
        names.append(row["name"])
    return names


def _chat_list_signature(rows=None):
    """Capture visible names and positions so a swipe must move the list."""
    rows = _chat_rows() if rows is None else rows
    return tuple(
        (row["name"], int(row["rect"][1]), int(row["rect"][3]))
        for row in rows
    )


def _chat_list_moved(previous_signature):
    current = _chat_list_signature()
    return current if current and current != previous_signature else None


def _reset_chat_list_to_top():
    previous = None
    unchanged_rounds = 0
    for _ in range(MAX_CHAT_RESET_SCROLLS):
        current = _chat_list_signature()
        if current and current == previous:
            unchanged_rounds += 1
        else:
            unchanged_rounds = 0
        if unchanged_rounds >= 2:
            return
        previous = current
        left, top, right, bottom = _scroll_bounds()
        if bottom - top < 300:
            return
        x = int((left + right) / 2)
        _swipe(x, top + 400, x, bottom - 300)


def _scan_chat_group_names():
    _reset_chat_list_to_top()
    collected = []
    seen = set()
    bottom_unchanged_rounds = 0
    stop_reason = "scroll_guard"
    scroll_count = 0
    for scroll_index in range(MAX_CHAT_SCROLLS + 1):
        rows = _chat_rows()
        signature = _chat_list_signature(rows)
        if not signature:
            stop_reason = "empty_list"
            break
        bitmap = capture_cv()
        for name in _chat_group_names_for_frame(bitmap, rows):
            if name not in seen:
                seen.add(name)
                collected.append(name)
        if scroll_index % 10 == 0:
            print(
                "会话列表扫描",
                scroll_index,
                "屏幕会话",
                len(rows),
                "已识别群",
                len(collected),
            )
        left, top, right, bottom = _scroll_bounds()
        if bottom - top < 300:
            stop_reason = "invalid_scroll_bounds"
            break
        x = int((left + right) / 2)
        _swipe(x, bottom - 260, x, top + 500)
        scroll_count += 1
        moved = _wait_for(
            lambda: _chat_list_moved(signature),
            timeout=3,
            interval=0.25,
        )
        if moved:
            bottom_unchanged_rounds = 0
            continue
        bottom_unchanged_rounds += 1
        print(
            "会话列表滑动后内容未位移",
            bottom_unchanged_rounds,
            "次；当前可见最后一个会话和底部位置保持不变",
        )
        if bottom_unchanged_rounds >= 2:
            stop_reason = "bottom_stable"
            break
    else:
        stop_reason = "scroll_guard"
    print(
        "会话列表扫描结束",
        "stopReason=",
        stop_reason,
        "scrolls=",
        scroll_count,
        "groups=",
        len(collected),
    )
    return collected, stop_reason, scroll_count


def _group_names_and_total():
    try:
        tree = _dump()
    except Exception:
        return [], None
    names = []
    seen = set()
    total = None
    for path in _walk(tree):
        item = path[-1]
        if item.get("packageName") != WECHAT_PACKAGE:
            continue
        text = str(item.get("text") or "").strip()
        rect = _rect(item)
        total_match = re.search(r"(\d+)\s*个群聊", text)
        if total_match:
            total = int(total_match.group(1))
        if item.get("id") != WECHAT_PACKAGE + ":id/cg1" or not _valid_rect(rect):
            continue
        if text and text not in seen:
            seen.add(text)
            names.append(text)
    return names, total


def _scroll_bounds():
    try:
        tree = _dump()
    except Exception:
        tree = None
    candidates = []
    for path in _walk(tree):
        item = path[-1]
        rect = _rect(item)
        if item.get("scrollable") is True and _valid_rect(rect):
            area = (rect[2] - rect[0]) * (rect[3] - rect[1])
            candidates.append((area, rect))
    if candidates:
        return max(candidates, key=lambda item: item[0])[1]
    width, height = _device_size()
    return 0, int(height * 0.16), width, int(height * 0.8)


def _scan_all_group_names():
    collected = []
    seen = set()
    unchanged_rounds = 0
    for _ in range(MAX_SCROLLS + 1):
        names, total = _group_names_and_total()
        before = len(seen)
        for name in names:
            if name not in seen:
                seen.add(name)
                collected.append(name)
        if total is not None and len(collected) >= total:
            break
        if len(seen) == before:
            unchanged_rounds += 1
        else:
            unchanged_rounds = 0
        if unchanged_rounds >= 3:
            break
        left, top, right, bottom = _scroll_bounds()
        if bottom - top < 300:
            break
        x = int((left + right) / 2)
        _swipe(x, bottom - 180, x, top + 180)
    return collected


def _post_json(path, payload):
    request = urllib.request.Request(
        BACKEND_URL.rstrip("/") + path,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "X-Automation-Device-Token": DEVICE_TOKEN,
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=8) as response:
        body = response.read().decode("utf-8")
        return json.loads(body) if body else {}


def _heartbeat(account_id, nickname):
    if not BACKEND_URL or not DEVICE_TOKEN:
        return {"sent": False, "reason": "backend_not_configured"}
    return _post_json(
        "/api/automation/devices/heartbeat",
        {
            "deviceId": DEVICE_ID,
            "name": DEVICE_NAME,
            "hidDeviceId": None,
            "status": "busy",
            "activeWechatAccountId": account_id,
            "capabilities": [
                "ascript",
                "native-input",
                "double-wechat",
                "wechat-native-group-inventory",
            ],
            "metadata": {
                "identitySource": "wechat_profile_nickname",
                "nickname": nickname,
                "inputMode": INPUT_MODE,
            },
        },
    )


def _post_group(account_id, nickname, group_name):
    payload = {
        "deviceId": DEVICE_ID,
        "wechatAccountId": account_id,
        "wechatAccountName": nickname,
        "source": "wechat_native",
        "groupName": group_name,
        "joinStatus": "success",
        "canSend": None,
        "lastSeenAt": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "idempotencyKey": "group:wechat_native:{}:{}".format(
            account_id,
            hashlib.sha256(group_name.encode("utf-8")).hexdigest()[:24],
        ),
    }
    return _post_json("/api/automation/group-candidates", payload)


accounts = []
errors = []
seen_account_ids = set()
for slot_index, slot_name in enumerate(INSTANCE_SLOTS):
    try:
        home_point = _open_wechat(slot_index)
        _tap(*home_point)
        nickname = _wait_for(_read_nickname, timeout=10)
        if not nickname:
            raise RuntimeError("微信“我”页未读到登录昵称")
        account_id = _account_id(nickname)
        if account_id in seen_account_ids:
            raise RuntimeError("两个微信实例登录昵称相同，拒绝把群记录串到同一账号")
        seen_account_ids.add(account_id)
        _heartbeat(account_id, nickname)
        _open_group_chat_list()
        contacts_group_names = _scan_all_group_names()
        print("通讯录群聊扫描完成", slot_name, len(contacts_group_names))
        _open_chat_list()
        chat_group_names, chat_scan_stop_reason, chat_scan_scrolls = _scan_chat_group_names()
        print("微信会话列表群扫描完成", slot_name, len(chat_group_names))
        group_names = []
        for group_name in contacts_group_names + chat_group_names:
            if group_name not in group_names:
                group_names.append(group_name)
        prepared = []
        posted = []
        post_errors = []
        for group_name in group_names:
            try:
                if BACKEND_URL and DEVICE_TOKEN:
                    posted.append(_post_group(account_id, nickname, group_name))
                else:
                    prepared.append({"groupName": group_name})
            except Exception as exc:
                post_errors.append({"groupName": group_name, "error": str(exc)})
        accounts.append(
            {
                "slot": slot_name,
                "nickname": nickname,
                "accountId": account_id,
                "groupCount": len(group_names),
                "groupNames": group_names,
                "contactsGroupCount": len(contacts_group_names),
                "chatListGroupCount": len(chat_group_names),
                "chatListScanStopReason": chat_scan_stop_reason,
                "chatListScanScrolls": chat_scan_scrolls,
                "preparedCount": len(prepared),
                "postedCount": len(posted),
                "backendWriteConfirmed": bool(BACKEND_URL and DEVICE_TOKEN),
                "postErrors": post_errors,
                "status": "success" if not post_errors else "degraded",
            }
        )
        print(
            "已扫描",
            slot_name,
            nickname,
            len(group_names),
            "个微信群（通讯录",
            len(contacts_group_names),
            "，会话列表",
            len(chat_group_names),
            "）",
        )
    except Exception as exc:
        errors.append({"slot": slot_name, "error": str(exc)})
        print("扫描失败", slot_name, exc)

_result = json.dumps(
    {
        "deviceId": DEVICE_ID,
        "functionId": "wechat.scan_native_groups",
        "source": "wechat_native",
        "accounts": accounts,
        "errors": errors,
        "status": "success" if accounts and not errors else "degraded" if accounts else "failed",
        "inputMode": INPUT_MODE,
    },
    ensure_ascii=False,
)
print(_result)
