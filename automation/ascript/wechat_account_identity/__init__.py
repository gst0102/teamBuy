# -*- coding: utf-8 -*-
"""Read the stable identity of both Android dual-WeChat instances.

This is the first device-side control-plane slice. It deliberately does not
search Xiaohongshu, join groups, read chats, or send messages.

The dual-app chooser exposes two identical "微信" labels. The script therefore
uses the observed chooser rectangles only to distinguish the two temporary
slots, then uses the unique WeChat ID read from WeChat's own profile page as
identity. The nickname is retained only as display metadata.
"""

from __future__ import print_function

import json
import re
import time
import urllib.request

from ascript.android import node
from ascript.android.screen import Ocr
from ascript.android.system import Device
from ascript.android.system import open as open_app


DEVICE_ID = "android-01"
DEVICE_NAME = "安卓双开微信手机"
INPUT_MODE = "official_esp32_hid"
BACKEND_URL = ""
DEVICE_TOKEN = ""
# HID mode uses the mode-6 accessibility tree for perception.
UI_MODE = 6
WECHAT_PACKAGE = "com.tencent.mm"
DUAL_APP_PACKAGE = "com.zte.cn.doubleapp"
INSTANCE_SLOTS = ("wechat-instance-1", "wechat-instance-2")
HID_DEVICE = None


def _keep_screen_awake():
    """Prevent Android screen sleep while this automation task is active."""
    try:
        Device.wake_up()
        Device.keep_screen_on()
        print("已开启屏幕常亮")
    except Exception as exc:
        print("开启屏幕常亮失败:", exc)


_keep_screen_awake()


def _hid():
    """Load and connect the official ESP32 HID device once per run."""
    global HID_DEVICE
    if HID_DEVICE is not None:
        return HID_DEVICE
    from ascript.android import plug

    plug.load("esp32")
    from esp32 import BleDevice

    HID_DEVICE = BleDevice()
    if not HID_DEVICE.is_conncted():
        try:
            HID_DEVICE.re_connect()
        except Exception:
            pass
    if not HID_DEVICE.is_conncted():
        raise RuntimeError("官方 ESP32 HID 未连接")
    print("HID_READY", HID_DEVICE.get_name(), HID_DEVICE.get_mac_address())
    return HID_DEVICE


def _device_size():
    display = Device.display()
    return int(display.widthPixels), int(display.heightPixels)


def _dump(mode=None):
    mode = UI_MODE if mode is None else mode
    node.Selector.refresh(mode)
    raw = node.Selector.dump(mode)
    if isinstance(raw, str):
        return json.loads(raw)
    return raw


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
    # Selector.dump() returns the actual roots under ``views`` on the device;
    # keep those paths so the dual-app chooser can be resolved from live data.
    for view in value.get("views", []) or []:
        for found in _walk(view, parents):
            yield found
    for child in value.get("childs", []) or []:
        for found in _walk(child, current):
            yield found


def _visible_text_nodes(tree):
    result = []
    for path in _walk(tree):
        item = path[-1]
        text = item.get("text")
        rect = item.get("rect") or {}
        if (
            item.get("visible") is not False
            and isinstance(text, str)
            and text.strip()
            and isinstance(rect, dict)
            and rect.get("right", 0) > rect.get("left", 0)
            and rect.get("bottom", 0) > rect.get("top", 0)
        ):
            result.append(item)
    return result


def _wait_for(predicate, timeout=10, interval=0.5):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            value = predicate()
            if value:
                return value
        except Exception as exc:
            print("等待界面状态失败:", exc)
        time.sleep(interval)
    return None


def _tap(x, y):
    width, height = _device_size()
    x, y = int(x), int(y)
    if not (0 <= x < width and 0 <= y < height):
        raise RuntimeError("控件树坐标超出 HID 触控范围：({}, {})".format(x, y))
    _hid().click(x, y, dur=35)
    time.sleep(0.6)


def _tree_rect(item):
    rect = item.get("rect") or {}
    if isinstance(rect, dict):
        return (
            int(rect.get("left", 0)),
            int(rect.get("top", 0)),
            int(rect.get("right", 0)),
            int(rect.get("bottom", 0)),
        )
    if isinstance(rect, (list, tuple)) and len(rect) >= 4:
        return tuple(int(value) for value in rect[:4])
    return 0, 0, 0, 0


def _valid_rect(rect):
    return rect[2] > rect[0] and rect[3] > rect[1]


def _chooser_item_rect(path):
    """Return the single GridView item rect, never the shared GridView rect."""
    width, _ = _device_size()
    grid_index = None
    for index in range(len(path) - 1, -1, -1):
        if str(path[index].get("type") or "") == "GridView":
            grid_index = index
            break
    if grid_index is None or grid_index + 1 >= len(path):
        return None
    item = path[grid_index + 1]
    if str(item.get("type") or "") == "GridView":
        return None
    rect = _tree_rect(item)
    if not _valid_rect(rect) or rect[2] - rect[0] >= int(width * 0.75):
        return None
    return rect


def _chooser_points():
    points = []
    # Use the live mode-6 tree. OCR and fixed coordinates are not action
    # fallbacks because the two identical labels must remain unambiguous.
    try:
        tree = _dump(UI_MODE)
        width, _ = _device_size()
        chooser_marker = any(
            str(path[-1].get("text") or "").strip()
            in ("请选择要使用的应用", "取消")
            for path in _walk(tree)
        )
        for path in _walk(tree):
            item = path[-1]
            if (
                item.get("text") == "微信"
                and item.get("visible") is not False
            ):
                # Android's native resolver can report a system package
                # rather than com.zte.cn.doubleapp.  Keep the action target
                # tree-derived and require the chooser marker for that case.
                if item.get("packageName") != DUAL_APP_PACKAGE and not chooser_marker:
                    continue
                rect = _chooser_item_rect(path)
                if _valid_rect(rect):
                    points.append(
                        (
                            (rect[0] + rect[2]) // 2,
                            (rect[1] + rect[3]) // 2,
                        )
                    )
    except Exception as exc:
        print("双开选择器控件树读取失败:", exc)
    points = sorted(set(points), key=lambda point: point[0])
    return points if len(points) == 2 else []


def _select_dual_instance(slot_index):
    points = _wait_for(lambda: _chooser_points(), timeout=8)
    if not points or len(points) < 2:
        raise RuntimeError("未找到双开微信选择器的两个微信入口")
    if slot_index >= len(points):
        raise RuntimeError("双开微信入口数量不足")
    # The two labels are identical and their clickable parent did not expose a
    # reliable selector on this phone. Coordinates are derived from this live
    # UI tree, not hardcoded screen positions.
    _tap(*points[slot_index])


def _home_tab_point():
    _, height = _device_size()
    # Action coordinates must come from the live mode-6 tree. OCR is allowed
    # only when reading/confirming page state, never as a HID action target.
    try:
        tree = _dump()
    except Exception:
        return None
    for path in _walk(tree):
        item = path[-1]
        if (
            item.get("text") != "我"
            or item.get("packageName") != WECHAT_PACKAGE
            or _tree_rect(item)[1] < height - 520
        ):
            continue
        for ancestor in reversed(path[:-1]):
            rect = ancestor.get("rect") or {}
            if (
                ancestor.get("clickable") is True
                and rect.get("right", 0) > rect.get("left", 0)
                and rect.get("bottom", 0) > rect.get("top", 0)
            ):
                return (
                    (rect.get("left", 0) + rect.get("right", 0)) // 2,
                    (rect.get("top", 0) + rect.get("bottom", 0)) // 2,
                )
    return None


def _profile_texts():
    try:
        tree = _dump()
    except Exception:
        return []
    return [item for item in _visible_text_nodes(tree) if item.get("packageName") == WECHAT_PACKAGE]


def _read_nickname():
    texts = _profile_texts()
    # OCR and accessibility expose the separator differently on this device:
    # the same profile has appeared as both "微信号：" and "微信号:".
    anchors = [
        item
        for item in texts
        if str(item.get("text", "")).startswith(("微信号：", "微信号:"))
    ]
    if anchors:
        anchor = anchors[0]
        anchor_rect = anchor.get("rect") or {}
        candidates = []
        for item in texts:
            text = str(item.get("text", "")).strip()
            rect = item.get("rect") or {}
            if (
                text
                and not text.startswith(("微信号：", "微信号:"))
                and rect.get("bottom", 0) <= anchor_rect.get("top", 0)
                and rect.get("bottom", 0) > 100
                and len(text) <= 80
            ):
                candidates.append(item)
        if candidates:
            nickname = max(candidates, key=lambda item: (item.get("rect") or {}).get("bottom", 0))
            value = str(nickname.get("text", "")).strip()
            if value:
                return value

    # The profile page is visible to OCR even when the filtered Selector tree
    # is temporarily empty during a dual-app resume.
    ocr_matches = Ocr.find_all(rect=[0, 150, _device_size()[0], 650]) or []
    ocr_anchor = next(
        (
            item
            for item in ocr_matches
            if "微信号：" in str(item.get("text", ""))
            or "微信号:" in str(item.get("text", ""))
        ),
        None,
    )
    if ocr_anchor:
        text = str(ocr_anchor.get("text", "")).strip()
        anchor_rect = ocr_anchor.get("rect") or [0, 0, 0, 0]
        candidates = sorted(
            ocr_matches,
            key=lambda item: (item.get("rect") or [0, 0, 0, 0])[3],
            reverse=True,
        )
        for candidate in candidates:
            candidate_text = str(candidate.get("text", "")).strip()
            candidate_rect = candidate.get("rect") or [0, 0, 0, 0]
            if (
                candidate_text
                and candidate_text != text
                and "微信号" not in candidate_text
                and candidate_rect[0] >= 150
                and candidate_rect[2] <= 900
                and candidate_rect[1] >= 120
                and candidate_rect[3] <= anchor_rect[1]
                and len(candidate_text) <= 80
            ):
                return candidate_text
    return None


def _normalize_wechat_id(value):
    value = re.sub(r"\s+", "", str(value or "").strip())
    value = re.sub(r"^微信号[:：]?", "", value)
    if not re.match(r"^[A-Za-z][A-Za-z0-9_-]{2,63}$", value):
        return None
    return value.lower()


def _read_wechat_id():
    """Read one stable WeChat ID; return None for absent or ambiguous state."""
    try:
        texts = _profile_texts()
    except Exception:
        texts = []
    candidates = set()
    anchors = []
    for item in texts:
        text = str(item.get("text") or "").strip()
        if text.startswith(("微信号：", "微信号:")):
            anchors.append(item)
            value = _normalize_wechat_id(text)
            if value:
                candidates.add(value)
    for anchor in anchors:
        anchor_rect = _tree_rect(anchor)
        for item in texts:
            rect = _tree_rect(item)
            if rect[1] < anchor_rect[3] or rect[1] > anchor_rect[3] + 180:
                continue
            value = _normalize_wechat_id(item.get("text"))
            if value:
                candidates.add(value)

    try:
        ocr_matches = Ocr.find_all(rect=[0, 150, _device_size()[0], 650]) or []
    except Exception:
        ocr_matches = []
    for item in ocr_matches:
        text = str(item.get("text") or "").strip()
        if "微信号" in text:
            value = _normalize_wechat_id(text)
            if value:
                candidates.add(value)
    return next(iter(candidates)) if len(candidates) == 1 else None


def _account_id(wechat_id):
    wechat_id = _normalize_wechat_id(wechat_id)
    if not wechat_id:
        raise RuntimeError("微信号格式无效，拒绝使用昵称生成账号 ID")
    return "wechat-id-" + wechat_id


def _read_one(slot_index, slot_name):
    # Opening the package while a cloned WeChat instance is still alive may
    # resume that instance directly instead of showing the system chooser.
    # Return to the system launcher through AScript's native Home key, then
    # launch it so the observed dual-app picker is presented for every slot.
    _hid().home()
    time.sleep(0.8)
    open_app(WECHAT_PACKAGE)
    _select_dual_instance(slot_index)
    if not _wait_for(lambda: _home_tab_point(), timeout=20):
        raise RuntimeError("微信首页未出现“我”入口")
    _tap(*_home_tab_point())
    nickname = _wait_for(_read_nickname, timeout=10)
    if not nickname:
        raise RuntimeError("微信“我”页未读到登录昵称")
    wechat_id = _wait_for(_read_wechat_id, timeout=10)
    if not wechat_id:
        raise RuntimeError("微信“我”页未读到唯一微信号")
    return {
        "slot": slot_name,
        "nickname": nickname,
        "wechatId": wechat_id,
        "accountId": _account_id(wechat_id),
        "identitySource": "wechat_profile_id",
        "verifiedAt": int(time.time()),
        "status": "verified",
    }


def _post_heartbeat(accounts, errors):
    if not BACKEND_URL or not DEVICE_TOKEN:
        return {"sent": False, "reason": "backend_not_configured"}
    active = accounts[-1].get("accountId") if accounts else None
    status = "ready" if len(accounts) == len(INSTANCE_SLOTS) and not errors else "degraded"
    payload = {
        "deviceId": DEVICE_ID,
        "name": DEVICE_NAME,
        "hidDeviceId": None,
        "status": status,
        "activeWechatAccountId": active,
        "capabilities": ["ascript", "official-esp32-hid", "double-wechat", "profile-id"],
        "metadata": {
            "identitySource": "wechat_profile_id",
            "wechatAccounts": accounts,
            "identityErrors": errors,
            "inputMode": INPUT_MODE,
        },
    }
    request = urllib.request.Request(
        BACKEND_URL.rstrip("/") + "/api/automation/devices/heartbeat",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "X-Automation-Device-Token": DEVICE_TOKEN,
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=8) as response:
        return {"sent": True, "status": response.status}


accounts = []
errors = []
for index, slot in enumerate(INSTANCE_SLOTS):
    try:
        account = _read_one(index, slot)
        accounts.append(account)
        print("已识别", slot, account["nickname"], account["accountId"])
    except Exception as exc:
        errors.append({"slot": slot, "error": str(exc)})
        print("识别失败", slot, exc)

# A nickname may legitimately be shared by both instances. Only the stable
# WeChat ID is an account boundary.
account_slots = {}
for account in accounts:
    account_slots.setdefault(account["accountId"], []).append(account["slot"])
for account_id, slots in account_slots.items():
    if len(slots) > 1:
        for account in accounts:
            if account["accountId"] == account_id:
                account["status"] = "ambiguous"
        errors.append(
            {
                "slots": slots,
                "error": "重复微信号，无法安全区分账号",
            }
        )

heartbeat = {"sent": False, "reason": "not_attempted"}
try:
    heartbeat = _post_heartbeat(accounts, errors)
except Exception as exc:
    heartbeat = {"sent": False, "reason": "heartbeat_failed", "error": str(exc)}

_result = json.dumps(
    {
        "deviceId": DEVICE_ID,
        "accounts": accounts,
        "errors": errors,
        "status": "ready" if len(accounts) == len(INSTANCE_SLOTS) and not errors else "degraded",
        "heartbeat": heartbeat,
        "inputMode": INPUT_MODE,
    },
    ensure_ascii=False,
)
print(_result)
