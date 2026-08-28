# -*- coding: utf-8 -*-
"""Read-only Xiaohongshu group-search slice for one fixed XHS instance.

This project intentionally stops at search observations. It does not open a
note, save a QR image, join a WeChat group, or send any message. QR values are
decoded in memory only and are returned as invitation references.
"""

from __future__ import print_function

import json
import time
import urllib.request

from ascript.android import action, node, screen
from ascript.android.screen import CodeScanner, Ocr
from ascript.android.system import Device
from ascript.android.system import open as open_app


DEVICE_ID = "android-01"
INPUT_MODE = "ascript_native"
BACKEND_URL = ""
DEVICE_TOKEN = ""
LOCAL_SEARCH_KEYWORD = "微信群"
XHS_PACKAGE = "com.xingin.xhs"
XHS_SLOT_INDEX = 1  # The right-hand instance is the verified working slot.
UI_MODE = 2
MAX_OBSERVATIONS = 12


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


def _ocr_rect(item):
    rect = item.get("rect") or []
    if isinstance(rect, dict):
        return (
            int(rect.get("left", 0)),
            int(rect.get("top", 0)),
            int(rect.get("right", 0)),
            int(rect.get("bottom", 0)),
        )
    if len(rect) >= 4:
        return tuple(int(value) for value in rect[:4])
    return 0, 0, 0, 0


def _wait_for(predicate, timeout=10, interval=0.5):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            value = predicate()
            if value:
                return value
        except Exception as exc:
            print("等待小红书界面失败:", exc)
        time.sleep(interval)
    return None


def _tap(x, y):
    # Coordinates come from live OCR; the current development path uses
    # AScript native input and intentionally does not load ESP32.
    action.click(int(x), int(y), dur=30)
    time.sleep(0.6)


def _chooser_points():
    """Return live icon centers for the two XHS choices.

    The chooser exposes the app name twice: once on the icon and once under
    it. Prefer the upper icon OCR boxes, then use the lower labels only as a
    fallback. This avoids hardcoding a screen coordinate while keeping the
    input path on AScript's native action API.
    """
    width, height = _device_size()
    matches = Ocr.find_all("小红书", rect=[0, int(height * 0.62), width, height]) or []
    icons = []
    labels = []
    for match in matches:
        left, top, right, bottom = _ocr_rect(match)
        if right <= left or bottom <= top:
            continue
        point = ((left + right) // 2, (top + bottom) // 2)
        if top < int(height * 0.84):
            icons.append(point)
        else:
            labels.append((left, point))
    if len(icons) >= 2:
        return sorted(set(icons), key=lambda point: point[0])
    return [point for _, point in sorted(labels, key=lambda item: item[0])]


def _select_fixed_xhs_instance():
    points = _wait_for(lambda: _chooser_points(), timeout=10)
    if not points or len(points) <= XHS_SLOT_INDEX:
        raise RuntimeError("未找到两个小红书实例，拒绝猜测固定采集账号")
    _tap(*points[XHS_SLOT_INDEX])


def _open_fixed_xhs(keyword):
    action.Key.home()
    time.sleep(1.5)
    open_app(XHS_PACKAGE)
    _select_fixed_xhs_instance()
    state = _wait_for(lambda: _search_page_state(keyword), timeout=15)
    if not state:
        raise RuntimeError("固定小红书实例未出现搜索入口")
    return state


def _has_search_entry():
    return bool(node.Selector(mode=UI_MODE).desc("搜索").clickable(True).find())


def _has_search_results(keyword):
    # The search field is near the top edge on this device; start OCR at 0 so
    # its full box is included. Requiring both the keyword and group labels
    # prevents reusing a stale result page from another PC task.
    width, height = _device_size()
    keyword_found = bool(
        Ocr.find_all(keyword, rect=[0, 0, width, int(height * 0.22)])
    )
    return keyword_found and bool(_group_observations())


def _search_page_state(keyword):
    if _has_search_entry():
        return "search"
    if _has_search_results(keyword):
        return "results"
    return None


def _search(keyword):
    # Selector confirms the live search button. The search screen focuses its
    # input after this selector click, then AScript native input submits it.
    search_button = node.Selector(mode=UI_MODE).desc("搜索").clickable(True).find()
    if not search_button:
        raise RuntimeError("未找到小红书搜索按钮")
    node.Selector(mode=UI_MODE).desc("搜索").click()
    time.sleep(1)
    action.input(keyword)
    time.sleep(0.4)
    action.Ime.enter()
    if not _wait_for(lambda: _group_observations(), timeout=12):
        raise RuntimeError("小红书搜索后未观察到群聊结果")


def _group_observations(bitmap=None):
    width, height = _device_size()
    # Passing the text "群聊" returns only that token on this AScript build.
    # Full OCR preserves the complete line, which is needed for the group
    # name after the separator.
    matches = Ocr.find_all(
        rect=[0, int(height * 0.12), width, int(height * 0.82)],
        image=bitmap,
    ) or []
    observations = []
    seen = set()
    for match in matches:
        text = str(match.get("text", "")).strip()
        if not text.startswith(("群聊：", "群聊:")):
            continue
        separator = "：" if "：" in text else ":"
        group_name = text.split(separator, 1)[1].strip()
        if not group_name or group_name in seen:
            continue
        left, top, right, bottom = _ocr_rect(match)
        seen.add(group_name)
        observations.append(
            {
                "groupName": group_name,
                "label": text,
                "rect": [left, top, right, bottom],
                "qrStatus": "requires_decode",
                "groupQRCode": None,
            }
        )
        if len(observations) >= MAX_OBSERVATIONS:
            break
    return observations


def _qr_observations(bitmap=None):
    width, height = _device_size()
    raw = CodeScanner.scan(
        rect=[0, int(height * 0.13), width, int(height * 0.5)],
        bitmap=bitmap,
    ) or []
    observations = []
    for item in raw:
        value = str(item.get("value") or "").strip()
        if not value or not value.startswith(
            ("https://weixin.qq.com/g/", "http://weixin.qq.com/g/")
        ):
            continue
        left, top, right, bottom = _ocr_rect(item)
        if right <= left or bottom <= top:
            continue
        observations.append(
            {
                "value": value,
                "rect": [left, top, right, bottom],
                "format": item.get("format"),
                "type": item.get("type"),
            }
        )
    return observations


def _attach_qr_codes(observations, bitmap=None):
    available = _qr_observations(bitmap)
    for observation in observations:
        left, top, right, bottom = observation["rect"]
        center_x = (left + right) / 2.0
        below = [
            item
            for item in available
            if item["rect"][1] >= bottom
        ]
        candidates = below or available
        if not candidates:
            continue
        chosen = min(
            candidates,
            key=lambda item: abs(((item["rect"][0] + item["rect"][2]) / 2.0) - center_x),
        )
        available.remove(chosen)
        observation["groupQRCode"] = chosen["value"]
        observation["qrStatus"] = "decoded"
        observation["qrRect"] = chosen["rect"]
    return observations


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


def _claim_task():
    if not BACKEND_URL or not DEVICE_TOKEN:
        return None
    response = _post_json(
        "/api/automation/tasks/claim",
        {"deviceId": DEVICE_ID, "activeWechatAccountId": None},
    )
    return (response.get("data") or None) if isinstance(response, dict) else None


def _complete_task(task, result):
    if not task or not BACKEND_URL or not DEVICE_TOKEN:
        return {"sent": False, "reason": "backend_not_configured"}
    return _post_json(
        "/api/automation/tasks/{}/complete".format(task["id"]),
        {
            "deviceId": DEVICE_ID,
            "leaseToken": task["leaseToken"],
            "activeWechatAccountId": None,
            "result": result,
        },
    )


def _fail_task(task, error_message):
    if not task or not BACKEND_URL or not DEVICE_TOKEN:
        return {"sent": False, "reason": "backend_not_configured"}
    return _post_json(
        "/api/automation/tasks/{}/fail".format(task["id"]),
        {
            "deviceId": DEVICE_ID,
            "leaseToken": task["leaseToken"],
            "activeWechatAccountId": None,
            "errorMessage": error_message,
            "result": {"source": "xhs.find_group"},
        },
    )


task = None
result = {
    "deviceId": DEVICE_ID,
    "functionId": "xhs.find_group",
    "source": "xhs_search_observation",
    "fixedXhsSlot": XHS_SLOT_INDEX,
    "status": "failed",
    "keyword": None,
    "candidates": [],
    "qrDecode": "ascript_code_scanner",
    "inputMode": INPUT_MODE,
}
try:
    task = _claim_task()
    if BACKEND_URL and DEVICE_TOKEN:
        if not task:
            raise RuntimeError("PC 没有可领取的 xhs.find_group 任务")
        if task.get("functionId") != "xhs.find_group":
            raise RuntimeError("领取到非 xhs.find_group 任务，已拒绝执行")
        keyword = str((task.get("payload") or {}).get("keyword") or LOCAL_SEARCH_KEYWORD).strip()
    else:
        keyword = LOCAL_SEARCH_KEYWORD
    if not keyword:
        raise RuntimeError("搜索关键词为空")
    result["keyword"] = keyword
    page_state = _open_fixed_xhs(keyword)
    if page_state == "results" and _has_search_results(keyword):
        print("复用小红书当前同关键词结果页")
    else:
        if page_state != "search":
            raise RuntimeError("小红书当前不是可确认的搜索页，拒绝盲操作")
        _search(keyword)
    snapshot = screen.capture()
    result["candidates"] = _attach_qr_codes(_group_observations(snapshot), snapshot)
    result["status"] = "success" if result["candidates"] else "empty"
    if task:
        result["backend"] = _complete_task(task, result)
except Exception as exc:
    result["error"] = str(exc)
    if task:
        try:
            result["backend"] = _fail_task(task, str(exc))
        except Exception as backend_exc:
            result["backendError"] = str(backend_exc)

print(json.dumps(result, ensure_ascii=False))
