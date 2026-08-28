# -*- coding: utf-8 -*-
"""Read the logged-in nickname of both Android dual-WeChat instances.

This is the first device-side control-plane slice. It deliberately does not
search Xiaohongshu, join groups, read chats, or send messages.

The dual-app chooser exposes two identical "微信" labels. The script therefore
uses the observed chooser rectangles only to distinguish the two temporary
slots, then uses the nickname read from WeChat's own profile page as identity.
"""

from __future__ import print_function

import hashlib
import json
import time
import urllib.request

from ascript.android import action, node
from ascript.android.screen import Ocr
from ascript.android.system import Device
from ascript.android.system import open as open_app


DEVICE_ID = "android-01"
DEVICE_NAME = "安卓双开微信手机"
INPUT_MODE = "ascript_native"
BACKEND_URL = ""
DEVICE_TOKEN = ""
UI_MODE = 2
WECHAT_PACKAGE = "com.tencent.mm"
DUAL_APP_PACKAGE = "com.zte.cn.doubleapp"
INSTANCE_SLOTS = ("wechat-instance-1", "wechat-instance-2")


def _keep_screen_awake():
    """Prevent Android screen sleep while this automation task is active."""
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
    action.click(int(x), int(y), dur=30)
    time.sleep(0.6)


def _chooser_points():
    width, height = _device_size()
    points = []
    # The system dual-app chooser is exposed by the accessibility engine in
    # mode 0/1, while mode 2 filters it out. Use the live clickable parent
    # bounds so the tap targets the option container rather than its label.
    try:
        tree = _dump(0)
        for path in _walk(tree):
            item = path[-1]
            if (
                item.get("text") == "微信"
                and item.get("visible") is not False
                and item.get("packageName") == DUAL_APP_PACKAGE
            ):
                for ancestor in reversed(path[:-1]):
                    rect = ancestor.get("rect") or {}
                    if (
                        ancestor.get("clickable") is True
                        and rect.get("right", 0) > rect.get("left", 0)
                        and rect.get("bottom", 0) > rect.get("top", 0)
                    ):
                        points.append(
                            (
                                (rect.get("left", 0) + rect.get("right", 0)) // 2,
                                (rect.get("top", 0) + rect.get("bottom", 0)) // 2,
                            )
                        )
                        break
    except Exception as exc:
        print("双开选择器控件树读取失败，改用 OCR:", exc)
    if len(points) >= 2:
        return sorted(set(points), key=lambda point: point[0])

    points = []
    # The system chooser is visible to MCP's selector test but is omitted by
    # some device-side selector modes. OCR remains the observed fallback; the
    # two identical labels are still distinguished by x-order.
    matches = Ocr.find_all("微信", rect=[0, int(height * 0.65), width, height]) or []
    for match in matches:
        rect = match.get("rect") or []
        if isinstance(rect, dict):
            left, top, right, bottom = (
                rect.get("left", 0),
                rect.get("top", 0),
                rect.get("right", 0),
                rect.get("bottom", 0),
            )
        else:
            left, top, right, bottom = rect[:4]
        if right > left and bottom > top:
            points.append(
                (
                    int(match.get("center_x") or (left + right) // 2),
                    int(match.get("center_y") or (top + bottom) // 2),
                )
            )
    return sorted(points, key=lambda point: point[0])


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
    width, height = _device_size()
    # On this phone the bottom-tab text is visible to OCR but can disappear
    # from the device-side Selector.dump after the dual-app switch. Restrict
    # OCR to the lower-right tab area so a chat/profile message containing
    # “我” cannot be mistaken for the tab.
    match = Ocr.find("我", rect=[int(width * 0.70), int(height * 0.82), width, height])
    if match:
        rect = match.get("rect") or []
        if isinstance(rect, dict):
            left, top, right, bottom = (
                rect.get("left", 0),
                rect.get("top", 0),
                rect.get("right", 0),
                rect.get("bottom", 0),
            )
        else:
            left, top, right, bottom = rect[:4]
        if right > left and bottom > top:
            return (
                int(match.get("center_x") or (left + right) // 2),
                int(match.get("center_y") or (top + bottom) // 2),
            )
    try:
        tree = _dump()
    except Exception:
        return None
    for path in _walk(tree):
        item = path[-1]
        if item.get("text") != "我" or item.get("id") != WECHAT_PACKAGE + ":id/icon_tv":
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
        separator = "：" if "微信号：" in text else ":" if "微信号:" in text else None
        if separator:
            value = text.split("微信号" + separator, 1)[1].strip()
            if value:
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
                        and candidate_rect[2] <= 850
                        and candidate_rect[3] <= ocr_anchor.get("rect", [0, 0, 0, 0])[1]
                        and all(char.isalnum() or char in "_-" for char in candidate_text)
                    ):
                        return candidate_text
    return None


def _account_id(nickname):
    digest = hashlib.sha256(("wechat:" + nickname).encode("utf-8")).hexdigest()[:20]
    return "wechat-nickname-" + digest


def _read_one(slot_index, slot_name):
    # Opening the package while a cloned WeChat instance is still alive may
    # resume that instance directly instead of showing the system chooser.
    # Return to the system launcher through AScript's native Home key, then
    # launch it so the observed dual-app picker is presented for every slot.
    action.Key.home()
    time.sleep(0.8)
    open_app(WECHAT_PACKAGE)
    _select_dual_instance(slot_index)
    if not _wait_for(lambda: _home_tab_point(), timeout=20):
        raise RuntimeError("微信首页未出现“我”入口")
    _tap(*_home_tab_point())
    nickname = _wait_for(_read_nickname, timeout=10)
    if not nickname:
        raise RuntimeError("微信“我”页未读到登录昵称")
    return {
        "slot": slot_name,
        "nickname": nickname,
        "accountId": _account_id(nickname),
        "identitySource": "wechat_profile_nickname",
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
        "capabilities": ["ascript", "native-input", "double-wechat", "profile-nickname"],
        "metadata": {
            "identitySource": "wechat_profile_nickname",
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

# Nickname is the currently observed identity source. If two instances ever
# expose the same nickname, do not let the same derived accountId silently
# bind two slots to one PC task stream.
nickname_slots = {}
for account in accounts:
    nickname_slots.setdefault(account["nickname"], []).append(account["slot"])
for nickname, slots in nickname_slots.items():
    if len(slots) > 1:
        for account in accounts:
            if account["nickname"] == nickname:
                account["status"] = "ambiguous"
        errors.append(
            {
                "slots": slots,
                "error": "重复微信昵称，无法安全区分账号",
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
