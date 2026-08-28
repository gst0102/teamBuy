# -*- coding: utf-8 -*-
"""Execute exactly one approved WeChat mini-program-card task.

This project deliberately starts with a hard preflight boundary.  The current
development input channel is AScript native input; ESP32 is not loaded or
required. After a task is claimed it verifies the task shape and the live
WeChat group header before any send UI is touched. The actual mini-program
share flow will be enabled only after the target card has a current published
share snapshot and the device-side flow has been observed on this phone.

Android AScript runs Python 3.8 on the device.  Do not run this file with the
workstation Python interpreter.
"""

from __future__ import print_function

import json
import time
import urllib.request

from ascript.android.screen import Ocr
from ascript.android.system import Device


DEVICE_ID = "android-01"
DEVICE_NAME = "安卓双开微信手机"
INPUT_MODE = "ascript_native"
UI_MODE = 2

# Runtime configuration is intentionally local-only.  Copy the values into
# an ignored local_config.py on the device project when the executor is
# enabled; never commit a device token to this source file.
BACKEND_URL = ""
DEVICE_TOKEN = ""
ACTIVE_WECHAT_ACCOUNT_ID = ""
try:
    from . import local_config as _local_config
except Exception:
    _local_config = None

if _local_config is not None:
    BACKEND_URL = getattr(_local_config, "BACKEND_URL", BACKEND_URL)
    DEVICE_TOKEN = getattr(_local_config, "DEVICE_TOKEN", DEVICE_TOKEN)
    ACTIVE_WECHAT_ACCOUNT_ID = getattr(
        _local_config,
        "ACTIVE_WECHAT_ACCOUNT_ID",
        ACTIVE_WECHAT_ACCOUNT_ID,
    )


def _json_request(path, payload):
    if not BACKEND_URL or not DEVICE_TOKEN:
        raise RuntimeError("AScript 发送器未配置后端地址或设备令牌")
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
    response = _json_request(
        "/api/automation/tasks/claim",
        {
            "deviceId": DEVICE_ID,
            "activeWechatAccountId": ACTIVE_WECHAT_ACCOUNT_ID or None,
            "leaseSeconds": 120,
        },
    )
    return (response.get("data") or None) if isinstance(response, dict) else None


def _finish_task(task, result):
    return _json_request(
        "/api/automation/tasks/{}/complete".format(task["id"]),
        {
            "deviceId": DEVICE_ID,
            "leaseToken": task["leaseToken"],
            "activeWechatAccountId": ACTIVE_WECHAT_ACCOUNT_ID or None,
            "result": result,
        },
    )


def _fail_task(task, error_message, result=None):
    return _json_request(
        "/api/automation/tasks/{}/fail".format(task["id"]),
        {
            "deviceId": DEVICE_ID,
            "leaseToken": task["leaseToken"],
            "activeWechatAccountId": ACTIVE_WECHAT_ACCOUNT_ID or None,
            "errorMessage": error_message,
            "result": result or {"source": "wechat.marketing_sender"},
        },
    )


def _load_input_channel():
    """Return the current input mode without loading the optional ESP32 plug-in."""
    return INPUT_MODE, None


def _ocr_has_group(group_name):
    expected = " ".join(str(group_name or "").split())
    if not expected:
        return False
    width = int(Device.display().widthPixels)
    height = int(Device.display().heightPixels)
    matches = Ocr.find_all(expected, rect=[0, 0, width, int(height * 0.18)]) or []
    for item in matches:
        text = " ".join(str(item.get("text") or "").split())
        if expected in text:
            return True
    return False


def _validate_task(task):
    if not task:
        return None
    if task.get("functionId") != "wechat.send_miniapp_card":
        raise RuntimeError("领取到非 wechat.send_miniapp_card 任务，已拒绝执行")
    payload = task.get("payload") or {}
    required = (
        "candidateId",
        "noteId",
        "cardId",
        "cardRevision",
        "groupName",
        "shareSnapshotUrl",
        "sharePath",
    )
    missing = [key for key in required if not str(payload.get(key) or "").strip()]
    if missing:
        raise RuntimeError("发送任务缺少字段：" + "、".join(missing))
    if payload.get("noteId") != payload.get("cardId"):
        raise RuntimeError("发送任务 noteId/cardId 不一致")
    if not str(payload.get("shareSnapshotUrl") or "").startswith("https://"):
        raise RuntimeError("分享图不是 HTTPS 地址，已拒绝发送")
    if not str(payload.get("sharePath") or "").startswith("/pages/note-preview/index?"):
        raise RuntimeError("分享路径不是资料预览页，已拒绝发送")
    return payload


def _result(status, **extra):
    data = {
        "deviceId": DEVICE_ID,
        "functionId": "wechat.send_miniapp_card",
        "status": status,
        "source": "wechat.marketing_sender",
        "inputMode": INPUT_MODE,
    }
    data.update(extra)
    return data


Device.wake_up()
try:
    Device.keep_screen_on()
except Exception:
    pass

task = None
result = _result("failed")
input_mode, input_error = _load_input_channel()
if input_error:
    result.update({"error": "AScript 输入通道不可用", "inputError": input_error})
else:
    try:
        task = _claim_task()
        if not task:
            result = _result("idle", message="没有可领取的单群单卡任务")
        else:
            payload = _validate_task(task)
            if not _ocr_has_group(payload["groupName"]):
                raise RuntimeError("当前微信群标题与任务目标不一致，已拒绝发送")
            # This boundary is intentional.  The WeChat mini-program share
            # UI is not enabled until a real published card/share snapshot has
            # been observed on the device.  Claiming and then failing here is
            # safer than clicking an unverified share path.
            raise RuntimeError("微信小程序卡片发送 UI 尚未完成设备验收")
    except Exception as exc:
        result["error"] = str(exc)
        if task:
            try:
                result["backend"] = _fail_task(task, str(exc), result)
            except Exception as backend_exc:
                result["backendError"] = str(backend_exc)

print(json.dumps(result, ensure_ascii=False))
