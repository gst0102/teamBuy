# -*- coding: utf-8 -*-
"""PC-plan driven WeChat sender for the standalone ``微信助手`` project.

The PC is the source of truth for group-code plans, card ids and text.  This
module only performs the explicitly queued task on the phone:

* ask the PC to materialize the user-selected batch;
* process one grouped task per WeChat account and group code;
* locate the exact ``卡片素材群`` chat and use WeChat's normal long-press →
  forward flow;
* search the configured group code, uniquely resolve and tap each saved real
  group-name row, then confirm, annotate, and send one native forward per group;
* write each per-group result back to the PC.

The mode-6 UI tree is perception only: every actionable rectangle is resolved
from that tree and executed through the official ESP32 HID device.  OCR is
reserved for post-action/state confirmation.  Card scrolling waits for a live
tree after each gesture and stops on confirmed lack of progress.

The default mode is dry-run.  A real send is enabled only by a local runtime
configuration whose ``TEST_MODE`` is exactly ``TEST_SINGLE`` or ``TEST_ONLY``.
That gate is deliberately not a source-code switch and is never sent to the
PC or printed in logs.

Android AScript runs Python 3.8.  Keep this file compatible with 3.8.
"""

from __future__ import print_function

import json
import os
import re
import time
import urllib.request

import cv2
from ascript.android.action import Ime
from ascript.android import node
from ascript.android.screen import Ocr, capture_cv
from ascript.android.system import Clipboard, Device
from ascript.android.system import open as open_app


DEVICE_ID = "android-01"
DEVICE_NAME = "安卓双开微信手机"
INPUT_MODE = "official_esp32_hid"
# Android HID exposes the assistant/accessibility tree as mode 6.  Mode 2 is
# not used by this sender while the phone is in HID mode.
UI_MODE = 6
WECHAT_PACKAGE = "com.tencent.mm"
DUAL_APP_PACKAGE = "com.zte.cn.doubleapp"
HID_POST_ACTION_SETTLE_SECONDS = 1.5
GROUP_BATCH_FUNCTION_ID = "wechat.send_group_batch"
MATERIAL_GROUP_NAME = "卡片素材群"
MATERIAL_CHAT_SEARCH_ALLOWED_SECTIONS = ("群聊", "最常使用", "最近使用")
MATERIAL_CHAT_SEARCH_SECTION_HEADERS = MATERIAL_CHAT_SEARCH_ALLOWED_SECTIONS + (
    "最近搜索",
    "更多群聊",
    "聊天记录",
    "搜索网络结果",
)
MAX_TASKS_PER_RUN = 50
# A grouped task can contain several native <=9-recipient chunks.  Keep its
# lease long enough for a normal long batch; a future renewal endpoint is still
# needed for batches that genuinely exceed this upper bound.
TASK_LEASE_SECONDS = 900
# 素材扫描预算由实时 act-x 的数字决定；不再保留固定 12 次最低值。
# 预算是整次查找的总上限，找到卡片或确认无进展时提前结束。
MAX_CHAT_LIST_TOP_SWIPES = 24
CHAT_TREE_WAIT_TIMEOUT_SECONDS = 8
CHAT_TREE_POLL_INTERVAL_SECONDS = 0.8
# A failed account flow stops immediately.  Re-entering the material chat can
# duplicate navigation, reopen the chooser, and hide the first actionable UI
# error behind a later cleanup failure.
MAX_ACCOUNT_FLOW_ATTEMPTS = 1
# Returning to the WeChat chat-list home is navigation, not content scrolling.
# Use the official HID back key only after the live mode-6 tree identifies a
# known WeChat child page.
MAX_HOME_BACKS = 5
WECHAT_ROOT_TAB_STATES = ("contacts", "discover", "profile")
SEARCH_PAGE_MARKER = "页面设置"
SEARCH_PAGE_KEYWORDS = ("搜索指定内容", "朋友圈", "公众号", "小程序", "视频号")
SEARCH_PAGE_RESULT_KEYWORDS = (
    "最近使用",
    "最近搜索",
    "群聊",
    "更多群聊",
    "聊天记录",
    "搜索网络结果",
)
GROUP_NOT_FOUND_MARKERS = (
    "你已被移出群聊",
    "已退出群聊",
    "群聊不存在",
    "群聊已解散",
    "无法找到该群聊",
    # When a stale group row remains selectable in native forwarding, WeChat
    # reports this only after the send action. Treat it as explicit evidence
    # that the account can no longer send to that group.
    "无法在已退出的群聊中发送消息",
)


def _capture_blocker_screenshot(stage, error=None):
    """Save a device screenshot for a blocked run without exposing secrets."""
    safe_stage = re.sub(r"[^A-Za-z0-9_-]+", "_", str(stage or "blocked"))[:80]
    path = "sdcard/airscript/screen/gp/teamBuy_blocker_{}_{}.jpg".format(
        safe_stage,
        int(time.time()),
    )
    try:
        bitmap = capture_cv()
        saved = bool(bitmap is not None and cv2.imwrite(path, bitmap))
        print(
            "BLOCKER_SCREENSHOT path={} saved={} error={}".format(
                path,
                saved,
                str(error or "")[:240],
            )
        )
        return path if saved else None
    except Exception as exc:
        print("BLOCKER_SCREENSHOT_FAILED stage={} error={}".format(safe_stage, str(exc)[:240]))
        return None

BACKEND_URL = ""
DEVICE_TOKEN = ""
ACTIVE_WECHAT_ACCOUNT_ID = ""
TEST_MODE = ""
TEST_GROUP_CODE = ""
TEST_CARD_ID = ""
ACCOUNT_SLOTS = {}
WECHAT_ACCOUNT_IDS = ()
WECHAT_ACCOUNT_NAMES = {}
try:
    from . import local_config as _local_config
except Exception:
    _local_config = None

if _local_config is not None:
    configured_device_id = getattr(_local_config, "DEVICE_ID", DEVICE_ID)
    if " ".join(str(configured_device_id or "").split()):
        DEVICE_ID = " ".join(str(configured_device_id).split())[:128]
    BACKEND_URL = getattr(_local_config, "BACKEND_URL", BACKEND_URL)
    DEVICE_TOKEN = getattr(_local_config, "DEVICE_TOKEN", DEVICE_TOKEN)
    ACTIVE_WECHAT_ACCOUNT_ID = getattr(
        _local_config,
        "ACTIVE_WECHAT_ACCOUNT_ID",
        ACTIVE_WECHAT_ACCOUNT_ID,
    )
    TEST_MODE = str(getattr(_local_config, "TEST_MODE", TEST_MODE) or "").strip()
    TEST_GROUP_CODE = str(getattr(_local_config, "TEST_GROUP_CODE", TEST_GROUP_CODE) or "").strip()
    TEST_CARD_ID = " ".join(
        str(getattr(_local_config, "TEST_CARD_ID", TEST_CARD_ID) or "").split()
    )
    ACCOUNT_SLOTS = getattr(_local_config, "ACCOUNT_SLOTS", ACCOUNT_SLOTS) or {}
    WECHAT_ACCOUNT_NAMES = getattr(
        _local_config,
        "WECHAT_ACCOUNT_NAMES",
        WECHAT_ACCOUNT_NAMES,
    ) or {}
    configured_account_ids = getattr(_local_config, "WECHAT_ACCOUNT_IDS", ()) or ()
    if isinstance(configured_account_ids, str):
        configured_account_ids = re.split(r"[,，\n]", configured_account_ids)
    WECHAT_ACCOUNT_IDS = tuple(
        " ".join(str(value).split())
        for value in configured_account_ids
        if " ".join(str(value).split())
    )


def _selected_batch_no():
    value = str(os.environ.get("TEAMBUY_SEND_BATCH_NO") or "1").strip()
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = 1
    return max(1, min(number, 100))


def _configured_account_ids():
    scoped = str(os.environ.get("TEAMBUY_SEND_ACCOUNT_IDS", "") or "").strip()
    if scoped:
        values = [value.strip() for value in scoped.split(",") if value.strip()]
    else:
        values = list(WECHAT_ACCOUNT_IDS)
    if not values and ACTIVE_WECHAT_ACCOUNT_ID:
        values = [ACTIVE_WECHAT_ACCOUNT_ID]
    normalized = tuple(dict.fromkeys(" ".join(str(value).split()) for value in values if " ".join(str(value).split())))
    if any(value.startswith("wechat-nickname-") for value in normalized):
        raise RuntimeError("发送器仍配置昵称派生账号 ID，必须改为唯一微信号 ID")
    return normalized


def _send_mode_enabled():
    """Only the explicit single/test-only modes may create send tasks."""
    return TEST_MODE in {"TEST_SINGLE", "TEST_ONLY"}


def _reuse_scanned_account():
    """Continue in the account selected by the immediately preceding scan."""
    return str(os.environ.get("TEAMBUY_REUSE_SCANNED_ACCOUNT") or "").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def _validate_test_configuration(account_ids):
    if TEST_MODE != "TEST_ONLY":
        return
    # The c-prefixed group code is the explicit test scope. Recipient names
    # and candidate IDs come from the PC's eligible task, not a second local
    # allowlist that becomes stale when a group is added to that code.
    if not TEST_GROUP_CODE or not TEST_GROUP_CODE.lower().startswith("c") or not TEST_CARD_ID:
        raise RuntimeError("TEST_ONLY 必须使用 c 开头测试群编号并配置卡片 ID")
    if not account_ids or len(account_ids) != len(set(account_ids)):
        raise RuntimeError("TEST_ONLY 必须配置至少一个且不重复的微信账号 ID")
    print(
        "TEST_ONLY_CONFIG",
        "groupCode={}".format(TEST_GROUP_CODE),
        "cardId={}".format(TEST_CARD_ID),
        "accountCount={}".format(len(account_ids)),
    )
    slots = {}
    for account_id in account_ids:
        if account_id not in ACCOUNT_SLOTS:
            raise RuntimeError("TEST_ONLY 缺少账号双开槽位配置：{}".format(account_id))
        try:
            slot = int(ACCOUNT_SLOTS[account_id])
        except (TypeError, ValueError):
            raise RuntimeError("TEST_ONLY 账号双开槽位配置无效：{}".format(account_id))
        if slot not in (0, 1) or slot in slots:
            raise RuntimeError("TEST_ONLY 双开槽位必须使用唯一的 0/1 槽位")
        slots[slot] = account_id


class SenderStop(Exception):
    def __init__(
        self,
        message,
        group_not_found=False,
        ambiguous=False,
        target_results=None,
        send_attempted=False,
        retryable=True,
        skip_target=False,
        stage=None,
    ):
        super().__init__(message)
        self.group_not_found = group_not_found
        self.ambiguous = ambiguous
        self.target_results = list(target_results or [])
        # A verified query with no visible row may be skipped so later
        # recipients can still be selected, but it is not proof that the
        # account left the group.  Only explicit WeChat membership markers
        # set group_not_found and can update the PC candidate state.
        self.skip_target = bool(skip_target)
        # Once the native send button has been tapped, a missing confirmation
        # is not safe to retry because the message may already have gone out.
        self.send_attempted = bool(send_attempted)
        self.retryable = bool(retryable)
        # Keep workflow cleanup failures separate from recipient-send outcomes.
        self.stage = str(stage or "").strip()


class StepLog(object):
    def __init__(self):
        self.items = []

    def add(self, step, action, state="", detail=""):
        self.items.append({
            "step": step,
            "action": action,
            "state": state,
            "detail": str(detail or "")[:300],
        })
        print("SEND_STEP", step, action, state, detail)


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


def _preflight_report():
    raw = str(os.environ.get("TEAMBUY_PREFLIGHT_REPORT_JSON") or "").strip()
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def _notify_run_completion(report):
    if not BACKEND_URL or not DEVICE_TOKEN:
        return {"sent": False, "reason": "backend_not_configured"}
    try:
        response = _json_request("/api/automation/runs/complete", report)
        result = response.get("data") if isinstance(response, dict) else None
        return result if isinstance(result, dict) else {"sent": False, "reason": "empty_response"}
    except Exception as exc:
        print("运行完成通知回传失败：{}".format(exc))
        # Return a safe error class so the launcher can persist why the email
        # callback failed without storing credentials or full request headers.
        return {
            "sent": False,
            "reason": "completion_callback_failed",
            "errorType": type(exc).__name__,
        }


def _claim_task(run_id=None):
    response = _json_request(
        "/api/automation/tasks/claim",
        {
            "deviceId": DEVICE_ID,
            "activeWechatAccountId": ACTIVE_WECHAT_ACCOUNT_ID or None,
            "runId": run_id,
            "leaseSeconds": TASK_LEASE_SECONDS,
            "functionIds": [GROUP_BATCH_FUNCTION_ID],
        },
    )
    return (response.get("data") or None) if isinstance(response, dict) else None


def _request_device_batch_run(account_ids, batch_no):
    _validate_test_configuration(account_ids)
    group_codes = []
    if TEST_MODE in {"TEST_SINGLE", "TEST_ONLY"}:
        if not TEST_GROUP_CODE:
            raise RuntimeError("单次测试未配置 TEST_GROUP_CODE")
        # Keep the test run bounded by its c-code, while letting the PC decide
        # which eligible groups under that code are actual recipients.
        group_codes = [TEST_GROUP_CODE]
    run_id = "{}-{}".format(DEVICE_ID, int(time.time() * 1000))
    payload = {
        "deviceId": DEVICE_ID,
        "batchNo": batch_no,
        "wechatAccountIds": list(account_ids),
        "groupCodes": group_codes,
        # Do not silently truncate PC-approved recipients by a local count or
        # name list. Native forwarding is chunked by the sender at nine rows.
        "maxTargets": 1000,
        "runId": run_id,
    }
    response = _json_request("/api/automation/group-content-plans/device-run", payload)
    data = (response.get("data") or {}) if isinstance(response, dict) else {}
    print(
        "BATCH_RUN_QUEUED",
        batch_no,
        data.get("createdCount", 0),
        data.get("targetCount", 0),
        data.get("skippedCount", 0),
    )
    # skippedCount 包含群资格、目标上限和方案配置跳过；逐条输出才能定位原因。
    for skipped in data.get("skippedItems") or []:
        print("QUEUE_SKIPPED", json.dumps(skipped, ensure_ascii=False))
    if data.get("skippedCount") and "skippedItems" not in data:
        print("QUEUE_SKIP_DETAILS_UNAVAILABLE backend_response_has_count_only=true")
    for task in data.get("tasks") or []:
        task_payload = task.get("payload") or {}
        target_rows = task_payload.get("targets") or []
        print(
            "QUEUE_TASK",
            task.get("id"),
            task.get("targetWechatAccountId"),
            task_payload.get("groupCode"),
            task_payload.get("cardId"),
            [row.get("groupName") for row in target_rows if isinstance(row, dict)],
    )
    if TEST_MODE == "TEST_ONLY":
        tasks = data.get("tasks") or []
        try:
            created_count = int(data.get("createdCount") or 0)
            target_count = int(data.get("targetCount") or 0)
        except (TypeError, ValueError):
            raise RuntimeError("TEST_ONLY 任务队列计数格式无效")
        if not tasks and created_count == 0 and target_count == 0:
            # A per-account scan may find no mapping for the configured test
            # code instance. A skipped row is still an empty account queue,
            # not a task-shape error; let the runner continue to the next
            # account and let _queue_empty_reason classify the aggregate run.
            print(
                "TEST_ONLY_ACCOUNT_NO_TARGET groupCode={} skipped={}".format(
                    TEST_GROUP_CODE,
                    data.get("skippedCount", 0),
                )
            )
            data["_clientRunId"] = run_id
            return data
        if not tasks or len(tasks) > len(account_ids):
            raise RuntimeError(
                "TEST_ONLY 任务映射不符合当前测试范围：created={}, targets={}, tasks={}".format(
                    created_count, target_count, len(tasks)
                )
            )
        seen_accounts = set()
        for task in tasks:
            account_id = str(task.get("targetWechatAccountId") or "").strip()
            payload = task.get("payload") or {}
            targets = payload.get("targets") or []
            if account_id not in account_ids or account_id in seen_accounts:
                raise RuntimeError("TEST_ONLY 任务未按两个账号各自创建")
            if payload.get("groupCode") != TEST_GROUP_CODE or payload.get("cardId") != TEST_CARD_ID:
                raise RuntimeError("TEST_ONLY 任务群编号或卡片 ID 与本地测试范围不一致")
            try:
                physical_target_count = sum(
                    int(target.get("groupOccurrenceCount") or 1)
                    for target in targets
                )
            except (TypeError, ValueError):
                raise RuntimeError("TEST_ONLY 任务目标重复数量无效")
            if not targets or physical_target_count > 1000:
                raise RuntimeError("TEST_ONLY 任务目标数量无效")
            for target in targets:
                if target.get("targetWechatAccountId") != account_id:
                    raise RuntimeError("TEST_ONLY 目标群归属账号与任务账号不一致")
            seen_accounts.add(account_id)
    data["_clientRunId"] = run_id
    return data


def _complete_task(task, result):
    return _json_request(
        "/api/automation/tasks/{}/complete".format(task["id"]),
        {
            "deviceId": DEVICE_ID,
            "leaseToken": task["leaseToken"],
            "activeWechatAccountId": ACTIVE_WECHAT_ACCOUNT_ID or None,
            "result": result,
        },
    )


def _fail_task(task, error_message, result):
    return _json_request(
        "/api/automation/tasks/{}/fail".format(task["id"]),
        {
            "deviceId": DEVICE_ID,
            "leaseToken": task["leaseToken"],
            "activeWechatAccountId": ACTIVE_WECHAT_ACCOUNT_ID or None,
            "errorMessage": error_message,
            "result": result,
        },
    )


def _heartbeat():
    """Refresh the device lease before asking the PC for a task."""
    response = _json_request(
        "/api/automation/devices/heartbeat",
        {
            "deviceId": DEVICE_ID,
            "name": DEVICE_NAME,
            "hidDeviceId": None,
            "status": "busy",
            "activeWechatAccountId": ACTIVE_WECHAT_ACCOUNT_ID or None,
            "capabilities": [
                "ascript",
                "official-esp32-hid",
                "double-wechat",
                "wechat-native-ui",
            ],
            "metadata": {
                "identitySource": "wechat_profile_id",
                "wechatAccountId": ACTIVE_WECHAT_ACCOUNT_ID or None,
                "inputMode": INPUT_MODE,
            },
        },
    )
    print("DEVICE_HEARTBEAT", "ok" if response else "empty")
    return response


def _load_hid():
    from ascript.android import plug

    plug.load("esp32")
    from esp32 import BleDevice

    ble = BleDevice()
    if not ble.is_conncted():
        try:
            ble.re_connect()
        except Exception:
            pass
    if not ble.is_conncted():
        raise RuntimeError("官方 ESP32 HID 未连接")
    print("HID_READY", ble.get_name(), ble.get_mac_address())
    return ble


def _device_size():
    display = Device.display()
    return int(display.widthPixels), int(display.heightPixels)


def _rect(item):
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
    for view in value.get("views", []) or []:
        for found in _walk(view, current):
            yield found
    for child in value.get("childs", []) or []:
        for found in _walk(child, current):
            yield found


def _dump():
    node.Selector.refresh(UI_MODE)
    raw = node.Selector.dump(UI_MODE)
    return json.loads(raw) if isinstance(raw, str) else raw


def _wait_for(predicate, timeout=10, interval=0.35):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            value = predicate()
            if value:
                return value
        except Exception as exc:
            print("WAIT_STATE_ERROR", str(exc)[:160])
        time.sleep(interval)
    return None


def _wait_for_stable_wechat_home(timeout=8, interval=0.5, confirmations=2):
    """Require repeated live-tree home matches to avoid trusting one stale frame."""
    deadline = time.time() + timeout
    consecutive = 0
    while time.time() < deadline:
        if _is_wechat_chat_list():
            consecutive += 1
            if consecutive >= confirmations:
                return True
        else:
            consecutive = 0
        time.sleep(interval)
    return False


def _clickable_ancestor(path):
    item = path[-1] if path else {}
    item_rect = _rect(item)
    if item.get("clickable") is True and _valid_rect(item_rect):
        return item_rect
    for item in reversed(path[:-1]):
        rect = _rect(item)
        if item.get("clickable") is True and _valid_rect(rect):
            return rect
    return None


def _popup_offset(path, anchor_text):
    """Translate a local PopupWindow tree rect into screen coordinates.

    WeChat's long-press menu is exposed as a small local window by mode 6;
    its tree rects are not screen-global.  OCR supplies only the live window
    offset by matching the same visible label.  The action rectangle and its
    size remain from the tree, and an unresolved offset is unsafe to tap.
    """
    width, height = _device_size()
    local_window = None
    for item in path:
        rect = _rect(item)
        if not _valid_rect(rect):
            continue
        # The first valid ancestor is the window root.  Do not inspect later
        # message rows: normal full-screen trees naturally contain small
        # child rects as well.
        window_width = rect[2] - rect[0]
        window_height = rect[3] - rect[1]
        if window_width < int(width * 0.9) or window_height < int(height * 0.5):
            local_window = rect
            break
        return 0, 0
    if not local_window:
        return 0, 0
    try:
        ocr_items = Ocr.find_all(
            re.escape(str(anchor_text).strip()),
            rect=[0, 0, width, height],
        ) or []
    except Exception as exc:
        print("POPUP_OFFSET_OCR_ERROR", str(exc)[:160])
        return None
    anchor_rect = None
    for item in ocr_items:
        value = " ".join(str(item.get("text") or "").split())
        rect = _rect(item)
        if value == str(anchor_text).strip() and _valid_rect(rect):
            anchor_rect = rect
            break
    if not anchor_rect:
        return None
    local_anchor = _rect(path[-1])
    if not _valid_rect(local_anchor):
        return None
    return (
        int(((anchor_rect[0] + anchor_rect[2]) - (local_anchor[0] + local_anchor[2])) / 2),
        int(((anchor_rect[1] + anchor_rect[3]) - (local_anchor[1] + local_anchor[3])) / 2),
    )


def _translate_popup_rect(path, rect, anchor_text):
    offset = _popup_offset(path, anchor_text)
    if offset is None:
        return None
    return (
        rect[0] + offset[0],
        rect[1] + offset[1],
        rect[2] + offset[0],
        rect[3] + offset[1],
    )


def _find_text_rect(
    text,
    package=WECHAT_PACKAGE,
    top=0,
    bottom=None,
    allow_ocr=True,
):
    matches = []
    try:
        tree = _dump()
    except Exception:
        tree = None
    for path in _walk(tree):
        item = path[-1]
        if package and item.get("packageName") != package:
            continue
        if item.get("visible") is False:
            continue
        if str(item.get("text") or "").strip() != str(text).strip():
            continue
        item_rect = _rect(item)
        rect = _clickable_ancestor(path) or item_rect
        if _valid_rect(rect):
            rect = _translate_popup_rect(path, rect, text)
            if rect is None:
                continue
        # Bounds are evaluated against the text node's local rect.  A
        # translated popup button can legitimately sit below the screen
        # region used by the caller's local-window query.
        bounds_rect = item_rect if _valid_rect(item_rect) else rect
        if not _valid_rect(rect) or not _valid_rect(bounds_rect) or bounds_rect[1] < top:
            continue
        if bottom is not None and bounds_rect[3] > bottom:
            continue
        matches.append(rect)
    if matches or not allow_ocr:
        return sorted(set(matches))
    for item in Ocr.find_all(
        re.escape(str(text)),
        rect=[0, top, _device_size()[0], bottom or _device_size()[1]],
    ) or []:
        rect = _rect(item)
        if _valid_rect(rect):
            matches.append(rect)
    return sorted(set(matches))


def _find_text_contains_rect(
    fragment,
    package=WECHAT_PACKAGE,
    top=0,
    bottom=None,
    allow_ocr=True,
):
    """Find a visible label whose text contains a stable fragment.

    WeChat renders the multi-select action as ``完成`` or ``完成(n)`` depending
    on the build, so exact text matching is not sufficient there.  The same
    tree/OCR priority is kept as the exact-text helper.
    """
    needle = str(fragment or "").strip()
    if not needle:
        return []
    matches = []
    try:
        tree = _dump()
    except Exception:
        tree = None
    for path in _walk(tree):
        item = path[-1]
        if package and item.get("packageName") != package:
            continue
        if item.get("visible") is False:
            continue
        if needle not in str(item.get("text") or ""):
            continue
        rect = _clickable_ancestor(path) or _rect(item)
        if not _valid_rect(rect) or rect[1] < top:
            continue
        if bottom is not None and rect[3] > bottom:
            continue
        matches.append(rect)
    if matches or not allow_ocr:
        return sorted(set(matches))
    try:
        for item in Ocr.find_all(
            re.escape(needle),
            rect=[0, top, _device_size()[0], bottom or _device_size()[1]],
        ) or []:
            rect = _rect(item)
            if _valid_rect(rect):
                matches.append(rect)
    except Exception as exc:
        print("TEXT_CONTAINS_OCR_ERROR", str(exc)[:160])
    return sorted(set(matches))


def _find_action_text_rect(text, package=WECHAT_PACKAGE, top=0, bottom=None):
    """Resolve an action target from the mode-6 UI tree only.

    OCR remains available to state verification, but it must not provide the
    coordinates for a HID action.  This keeps perception and execution
    separate and makes an unexposed/ambiguous control a visible stop reason.
    """
    return _find_text_rect(
        text,
        package=package,
        top=top,
        bottom=bottom,
        allow_ocr=False,
    )


def _find_action_text_contains_rect(
    fragment,
    package=WECHAT_PACKAGE,
    top=0,
    bottom=None,
):
    return _find_text_contains_rect(
        fragment,
        package=package,
        top=top,
        bottom=bottom,
        allow_ocr=False,
    )


def _native_forward_multi_state():
    """Read the native multi-select counter and its real Complete button.

    WeChat can expose the same ``完成(n)`` control as both a clickable Button
    and an overlapping TextView.  Generic text lookup returns both rectangles
    and falsely reports an ambiguous action.  Prefer the live clickable
    Button's mode-6 rectangle; OCR may confirm the counter only, never the
    action coordinates.
    """
    width, height = _device_size()
    label_pattern = re.compile(r"^完成\s*(?:\(\s*(\d+)\s*\))?$")
    tree_counts = set()
    button_rects = []
    fallback_rects = []
    try:
        tree = _dump()
    except Exception as exc:
        tree = None
        print("FORWARD_MULTI_TREE_ERROR", str(exc)[:160])

    for path in _walk(tree):
        item = path[-1]
        if item.get("packageName") != WECHAT_PACKAGE:
            continue
        if any(parent.get("visible") is False for parent in path):
            continue
        match = label_pattern.fullmatch(" ".join(str(item.get("text") or "").split()))
        if not match:
            continue
        label_rect = _rect(item)
        if (
            not _valid_rect(label_rect)
            or label_rect[1] < 0
            or label_rect[3] > 420
            or label_rect[0] < int(width * 0.55)
        ):
            continue
        tree_counts.add(int(match.group(1) or 0))

        if item.get("type") == "Button" and item.get("clickable") is True:
            action_rect = _rect(item)
            if _valid_rect(action_rect) and action_rect[3] <= 420:
                button_rects.append(action_rect)
            continue
        action_rect = _clickable_ancestor(path)
        if (
            action_rect
            and _valid_rect(action_rect)
            and action_rect[3] <= 420
            and action_rect[0] >= int(width * 0.55)
        ):
            fallback_rects.append(action_rect)

    selected_count = next(iter(tree_counts)) if len(tree_counts) == 1 else None
    count_source = "mode6_tree" if selected_count is not None else "unavailable"
    if selected_count is None:
        try:
            ocr_items = Ocr.find_all(
                r"完成\s*(?:\(\s*\d+\s*\))?",
                rect=[int(width * 0.55), 0, width, min(height, 420)],
            ) or []
            ocr_counts = set()
            for item in ocr_items:
                match = label_pattern.fullmatch(
                    " ".join(str(item.get("text") or "").split())
                )
                if match:
                    ocr_counts.add(int(match.group(1) or 0))
            if len(ocr_counts) == 1:
                selected_count = next(iter(ocr_counts))
                count_source = "ocr_confirmation"
        except Exception as exc:
            print("FORWARD_MULTI_OCR_CONFIRM_ERROR", str(exc)[:160])

    action_rects = sorted(set(button_rects or fallback_rects))
    return {
        "selected_count": selected_count,
        "count_source": count_source,
        "rects": action_rects,
    }


def _find_desc_or_id_rect(descs=(), ids=(), top=0, bottom=None):
    try:
        tree = _dump()
    except Exception:
        tree = None
    for path in _walk(tree):
        item = path[-1]
        if item.get("packageName") != WECHAT_PACKAGE:
            continue
        item_desc = str(item.get("desc") or item.get("contentDesc") or "").strip()
        item_id = str(item.get("id") or "").strip()
        short_id = item_id.rsplit("/", 1)[-1]
        wanted_short_ids = set(str(value).rsplit("/", 1)[-1] for value in ids)
        if item_desc not in descs and item_id not in ids and short_id not in wanted_short_ids:
            continue
        is_input = (
            item.get("type") in ("EditText", "AutoCompleteTextView")
            or item.get("editable") is True
            or short_id in {"f8", "search_src_text"}
        )
        # The clickable ancestor of an EditText can be the whole toolbar. Use
        # the editor's own live rect so HID click actually gives it focus.
        rect = _rect(item) if is_input else (_clickable_ancestor(path) or _rect(item))
        if _valid_rect(rect) and rect[1] >= top and (bottom is None or rect[3] <= bottom):
            return rect
    return None


def _find_editable_rect(top=0, bottom=None):
    """Find the current WeChat EditText when its generated id changes."""
    try:
        tree = _dump()
    except Exception:
        tree = None
    for path in _walk(tree):
        item = path[-1]
        if item.get("packageName") != WECHAT_PACKAGE:
            continue
        if item.get("type") not in ("EditText", "AutoCompleteTextView") and item.get("editable") is not True:
            continue
        # Never promote an editor to its clickable toolbar ancestor.
        rect = _rect(item)
        if _valid_rect(rect) and rect[1] >= top and (
            bottom is None or rect[3] <= bottom
        ):
            return rect
    return None


def _search_icon_rect():
    """Locate a search control from the mode-6 UI tree only.

    There is intentionally no OCR or fixed-coordinate fallback here.  If a
    WeChat build exposes a custom-drawn icon without a tree node, the caller
    stops instead of guessing a tap position.
    """
    width, _ = _device_size()
    candidates = []
    try:
        tree = _dump()
    except Exception as exc:
        print("SEARCH_ICON_TREE_ERROR", str(exc)[:160])
        return None
    for path in _walk(tree):
        item = path[-1]
        if item.get("packageName") != WECHAT_PACKAGE:
            continue
        rect = _clickable_ancestor(path) or _rect(item)
        if not _valid_rect(rect) or rect[1] >= 360 or rect[0] < int(width * 0.55):
            continue
        label = " ".join(
            str(item.get(key) or "").strip()
            for key in ("text", "desc", "contentDesc", "id")
        )
        if "搜索" in label or "search" in label.lower():
            candidates.append(rect)
    candidates = sorted(set(candidates))
    return candidates[0] if len(candidates) == 1 else None


def _search_input_rect():
    rect = _find_desc_or_id_rect(
        ids=(WECHAT_PACKAGE + ":id/f8", WECHAT_PACKAGE + ":id/search_src_text"),
        top=0,
        bottom=420,
    )
    return rect or _find_editable_rect(top=100, bottom=420)


def _search_input_item(tree):
    """Return the live search input path and its own rectangle."""
    preferred = []
    editable = []
    placeholder = []
    for path in _walk(tree):
        item = path[-1]
        if not any(node.get("packageName") == WECHAT_PACKAGE for node in path):
            continue
        if any(node.get("visible") is False for node in path):
            continue
        item_id = str(item.get("id") or "").rsplit("/", 1)[-1]
        is_known = item_id in {"f8", "search_src_text"}
        is_editable = item.get("type") in ("EditText", "AutoCompleteTextView") or item.get("editable") is True
        label = " ".join(
            str(item.get(key) or "").strip()
            for key in ("text", "desc", "contentDesc", "hint", "id")
        )
        is_placeholder = "搜索本地或网络结果" in label
        rect = _rect(item)
        if not _valid_rect(rect) or rect[1] >= 460 or not (
            is_known or is_editable or is_placeholder
        ):
            continue
        if is_known:
            preferred.append((path, rect))
        if is_editable:
            editable.append((path, rect))
        if is_placeholder:
            placeholder.append((path, rect))
    if preferred:
        preferred_with_text = [
            value
            for value in preferred
            if str(value[0][-1].get("text") or "").strip()
        ]
        if len(preferred_with_text) == 1:
            return preferred_with_text[0]
        return sorted(preferred, key=lambda value: (value[1][1], value[1][0]))[0]
    labeled = [
        value
        for value in editable
        if "搜索" in " ".join(
            str(value[0][-1].get(key) or "").strip()
            for key in ("text", "desc", "contentDesc", "hint", "id")
        )
    ]
    if len(labeled) == 1:
        return labeled[0]
    if len(editable) == 1:
        return editable[0]
    placeholder_rects = sorted(set(value[1] for value in placeholder))
    if len(placeholder_rects) == 1:
        return next(value for value in placeholder if value[1] == placeholder_rects[0])
    # Android 15/HID may expose a visible editor and a background editor with
    # generated IDs.  The editor carrying the non-empty query is the safe
    # search target when it is unique.
    with_text = [
        value
        for value in editable
        if str(value[0][-1].get("text") or "").strip()
    ]
    if len(with_text) == 1:
        return with_text[0]
    return None


def _search_input_focused():
    """Confirm that a visible search editor, not its toolbar, owns focus."""
    try:
        tree = _dump()
    except Exception:
        return False
    item = _search_input_item(tree)
    if item and item[0][-1].get("focused") is True:
        return True
    for path in _walk(tree):
        node_item = path[-1]
        if not any(node.get("packageName") == WECHAT_PACKAGE for node in path):
            continue
        if any(node.get("visible") is False for node in path):
            continue
        rect = _rect(node_item)
        if not _valid_rect(rect) or rect[1] >= 460:
            continue
        is_editable = (
            node_item.get("type") in ("EditText", "AutoCompleteTextView")
            or node_item.get("editable") is True
        )
        if is_editable and node_item.get("focused") is True:
            return True
    return False


def _tree_has_exact_text(tree, value, min_top=0, max_bottom=None):
    """Check a visible WeChat text marker without using it as an action rect."""
    expected = str(value or "").strip()
    if not expected:
        return False
    for path in _walk(tree):
        item = path[-1]
        if item.get("packageName") != WECHAT_PACKAGE or item.get("visible") is False:
            continue
        if str(item.get("text") or "").strip() != expected:
            continue
        rect = _rect(item)
        if not _valid_rect(rect) or rect[1] < min_top:
            continue
        if max_bottom is not None and rect[3] > max_bottom:
            continue
        return True
    return False


def _search_page_signature(tree, search_item):
    """Recognize WeChat search from the requested page marker and context."""
    if not search_item:
        return False
    # The empty search page has the unique “页面设置” DOM marker and the
    # visible search-category keywords.  The marker is only a state signal;
    # actions still use the live search input rectangle.
    if _tree_has_exact_text(tree, SEARCH_PAGE_MARKER) and any(
        _tree_has_exact_text(tree, keyword)
        for keyword in SEARCH_PAGE_KEYWORDS
    ):
        return True
    # Once a query is entered, WeChat may hide the category panel, result
    # section and marker from mode 6 even though they are visibly rendered.
    # A non-empty live editor plus the top cancel action is already a unique
    # search-page signature; do not downgrade this page to ``unknown`` and
    # block the bounded right-swipe reset.
    query = str(search_item[0][-1].get("text") or "").strip()
    if not query:
        return False
    if _tree_has_exact_text(tree, "取消", max_bottom=420):
        return True
    # Returning from a searched material-group chat lands on WeChat's results
    # list, whose toolbar uses a back arrow rather than “取消”. A non-empty,
    # live top search editor plus one unique WeChat action-bar back node is the
    # positive search-page signature for that intermediate page.
    return len(_wechat_actionbar_back_rects(tree)) == 1


def _wechat_tree_fingerprint(tree):
    """Summarize visible WeChat tree content to verify a HID swipe changed it."""
    observed = []
    for path in _walk(tree):
        item = path[-1]
        if item.get("packageName") != WECHAT_PACKAGE or item.get("visible") is False:
            continue
        rect = _rect(item)
        if not _valid_rect(rect):
            continue
        text = " ".join(
            str(item.get(key) or "").strip()
            for key in ("text", "desc", "contentDesc", "hint")
        ).strip()
        if not text and item.get("scrollable") is not True:
            continue
        observed.append(
            (
                text,
                str(item.get("type") or ""),
                str(item.get("id") or ""),
                rect,
                bool(item.get("scrollable")),
            )
        )
    return tuple(sorted(observed, key=repr))


def _tree_has_top_text(tree, value, max_bottom=520):
    expected = str(value or "").strip()
    for path in _walk(tree):
        item = path[-1]
        if item.get("packageName") != WECHAT_PACKAGE or item.get("visible") is False:
            continue
        if str(item.get("text") or "").strip() != expected:
            continue
        rect = _rect(item)
        if _valid_rect(rect) and rect[1] <= max_bottom:
            return True
    return False


def _truthy_tree_value(value):
    return str(value).strip().lower() in {"1", "true", "yes", "selected", "checked"}


def _tree_tab_is_selected(path):
    """Prefer an explicit selected marker when this WeChat tree exposes one."""
    for item in reversed(path):
        for key in ("selected", "isSelected", "activated", "checked"):
            if _truthy_tree_value(item.get(key)):
                return True
        marker = " ".join(
            str(item.get(key) or "").strip()
            for key in ("stateDescription", "desc", "contentDesc")
        )
        if re.search(r"(?:已)?选中|selected", marker, re.IGNORECASE):
            return True
    return False


def _wechat_home_tree_signature(tree):
    """Prefer a selected WeChat tab; fall back to its tab/search structure."""
    if not tree or _search_input_item(tree):
        return False
    # Bottom-tab nodes survive on Contacts/Discover/Profile pages.  Their
    # top-level title is the negative signal that prevents a false home match.
    if any(_tree_has_top_text(tree, title) for title in ("通讯录", "发现", "我")):
        return False
    _, height = _device_size()
    chat_tabs = []
    me_tabs = []
    chat_tab_selected = []
    me_tab_selected = []
    top_search = False
    for path in _walk(tree):
        item = path[-1]
        if item.get("packageName") != WECHAT_PACKAGE or item.get("visible") is False:
            continue
        rect = _rect(item)
        if not _valid_rect(rect):
            continue
        if rect[1] >= int(height * 0.72):
            text = str(item.get("text") or "").strip()
            if text == "微信":
                chat_tabs.append(item)
                chat_tab_selected.append(_tree_tab_is_selected(path))
            elif text == "我":
                me_tabs.append(item)
                me_tab_selected.append(_tree_tab_is_selected(path))
        if rect[1] <= 260:
            label = " ".join(
                str(item.get(key) or "").strip()
                for key in ("text", "desc", "contentDesc", "hint", "id")
            )
            if "搜索" in label or "search" in label.lower():
                top_search = True
    if not chat_tabs or not me_tabs or not top_search:
        return False
    # A positive WeChat-tab marker is strongest. This build can expose
    # checked=false on ordinary tabs, so when neither tab has a positive
    # marker use the visible bottom tabs + top search entry as the fallback.
    # A positive “我” marker always rules out chat-list home.
    if any(chat_tab_selected):
        return not any(me_tab_selected)
    if any(me_tab_selected):
        return False
    # No positive selection marker is exposed by this tree snapshot. The
    # required visible WeChat/Me tabs and top search entry above are the
    # fallback signature; other root pages and the search editor were excluded.
    return True


def _wechat_page_state(tree=None):
    """Classify the visible WeChat page from one live mode-6 tree snapshot."""
    if tree is None:
        try:
            tree = _dump()
        except Exception:
            return "unknown", ""
    if not any(
        item.get("packageName") == WECHAT_PACKAGE
        and item.get("visible") is not False
        for path in _walk(tree)
        for item in (path[-1],)
    ):
        return "unknown", ""

    search_item = _search_input_item(tree)
    if _search_page_signature(tree, search_item):
        return "search", str(search_item[0][-1].get("text") or "").strip()

    # Confirm the positive home signature before interpreting a stale
    # action-bar container as a child-page back button.
    if _wechat_home_tree_signature(tree):
        return "home", ""

    _, height = _device_size()
    has_message_editor = False
    top_texts = []
    has_up = False
    for path in _walk(tree):
        item = path[-1]
        if item.get("packageName") != WECHAT_PACKAGE or item.get("visible") is False:
            continue
        rect = _rect(item)
        if not _valid_rect(rect):
            continue
        text = str(item.get("text") or "").strip()
        if text and rect[3] <= 360:
            top_texts.append(text)
        if rect[1] >= int(height * 0.62) and (
            item.get("type") in ("EditText", "AutoCompleteTextView")
            or item.get("editable") is True
        ):
            has_message_editor = True
        item_id = str(item.get("id") or "").rsplit("/", 1)[-1]
        label = " ".join(
            str(item.get(key) or "").strip()
            for key in ("text", "desc", "contentDesc", "id")
        )
        if (
            item_id == "actionbar_up_indicator"
            or "actionbar_up_indicator" in label
        ) and rect[1] <= 320:
            has_up = True

    if has_up:
        if has_message_editor and any(
            re.search(r"[（(]\s*\d{1,5}\s*[)）]", text)
            for text in top_texts
        ):
            return "group_chat", ""
        if has_message_editor:
            return "chat", ""
        return "child", ""

    # Root tabs have no action-bar back button. Navigate only through the
    # live bottom “微信” tab, then confirm the actual chat-list signature.
    for title, state in (("通讯录", "contacts"), ("发现", "discover"), ("我", "profile")):
        if _tree_has_top_text(tree, title):
            return state, ""
    return "unknown", ""


def _generic_wechat_gesture_rect():
    """Find a clipped live WeChat content rectangle after search controls vanish."""
    try:
        tree = _dump()
    except Exception:
        return None
    width, height = _device_size()
    candidates = []
    broad = []
    for path in _walk(tree):
        item = path[-1]
        if item.get("packageName") != WECHAT_PACKAGE or item.get("visible") is False:
            continue
        raw_rect = _rect(item)
        rect = (
            max(0, min(width, raw_rect[0])),
            max(0, min(height, raw_rect[1])),
            max(0, min(width, raw_rect[2])),
            max(0, min(height, raw_rect[3])),
        )
        if not _valid_rect(rect):
            continue
        if rect[2] - rect[0] < int(width * 0.70) or rect[3] - rect[1] < 300:
            continue
        # Do not use the root WeChat wrapper as a gesture target.  It can
        # produce a HID log entry without delivering the swipe to the visible
        # page, which is indistinguishable from a missing swipe to the user.
        is_generic_fullscreen = (
            rect[0] <= 16
            and rect[1] <= 160
            and rect[2] >= width - 16
            and rect[3] >= int(height * 0.92)
        )
        if is_generic_fullscreen:
            continue
        broad.append(rect)
        label = " ".join(
            str(item.get(key) or "").strip().lower()
            for key in ("type", "className", "id", "resourceName")
        )
        if item.get("scrollable") is True or any(
            marker in label for marker in ("listview", "recyclerview", "scrollview")
        ):
            candidates.append(rect)
    if candidates:
        return max(candidates, key=lambda rect: (rect[2] - rect[0]) * (rect[3] - rect[1]))
    if broad:
        return (
            min(rect[0] for rect in broad),
            min(rect[1] for rect in broad),
            max(rect[2] for rect in broad),
            max(rect[3] for rect in broad),
        )
    return None


def _material_chat_history_rect(tree=None):
    """Resolve the visible material-chat history from live tree anchors.

    WeChat's mode-6 tree does not consistently expose message history as a
    ListView/RecyclerView. Prefer that semantic node when present; otherwise
    use the visible parent chain of a live act-* message marker, clipped to
    the area between this chat's title and composer. OCR may supply a missing
    title boundary; the gesture body still comes from a live history node,
    never a whole-screen WeChat wrapper or an OCR message text box.
    """
    try:
        if tree is None:
            tree = _dump()
    except Exception as exc:
        return None, "实时 mode=6 控件树读取失败：{}".format(str(exc)[:160])

    width, height = _device_size()
    headers, composers, lists, markers = {}, {}, [], []
    for path in _walk(tree):
        item = path[-1]
        if any(node_item.get("visible") is False for node_item in path):
            continue
        if not any(node_item.get("packageName") == WECHAT_PACKAGE for node_item in path):
            continue
        raw = _rect(item)
        if not _valid_rect(raw) or raw[2] <= 0 or raw[0] >= width or raw[3] <= 0 or raw[1] >= height:
            continue
        rect = (max(0, raw[0]), max(0, raw[1]), min(width, raw[2]), min(height, raw[3]))
        label = " ".join(str(item.get("text") or "").split())
        center_y = (rect[1] + rect[3]) / 2.0
        if MATERIAL_GROUP_NAME in label and center_y < height * 0.24:
            if rect not in headers or len(path) > len(headers[rect]):
                headers[rect] = path
        if (
            item.get("type") in ("EditText", "AutoCompleteTextView")
            or item.get("editable") is True
        ) and center_y > height * 0.60:
            if rect not in composers or len(path) > len(composers[rect]):
                composers[rect] = path
        if re.fullmatch(r"act-\d+", label):
            markers.append(path)
        classes = " ".join(
            str(item.get(key) or "").lower() for key in ("type", "className")
        )
        if "listview" in classes or "recyclerview" in classes:
            lists.append((path, rect, classes))

    # 标题确认与 _header_has 共用同一规则和本次树快照；树漏标题时接受实时 OCR。
    # OCR 只补标题边界，滑动区域仍必须来自微信历史列表或 act-* 的实际父容器。
    header_rects = _chat_header_rects(MATERIAL_GROUP_NAME, tree)
    if len(header_rects) != 1 or len(composers) != 1:
        return None, "素材群标题/聊天输入框无法唯一确认：header={} composer={}".format(
            len(header_rects), len(composers)
        )
    header_rect = header_rects[0]
    header_path = headers.get(header_rect)
    composer_rect, composer_path = next(iter(composers.items()))
    common_path = []
    if header_path:
        for first, second in zip(header_path, composer_path):
            if first is not second:
                break
            common_path.append(first)
    else:
        # OCR 标题没有控件父链，用本次微信输入框所属的微信根节点隔离页面。
        for index, item in enumerate(composer_path):
            if item.get("packageName") == WECHAT_PACKAGE:
                common_path = composer_path[:index + 1]
                break
    if not common_path:
        return None, "素材群标题与输入框不属于同一可见微信页面"

    same_page_markers = [
        path
        for path in markers
        if len(path) >= len(common_path)
        and all(path[index] is common_path[index] for index in range(len(common_path)))
    ]
    candidates = [
        (path, rect, classes)
        for path, rect, classes in lists
        if len(path) >= len(common_path)
        and all(path[index] is common_path[index] for index in range(len(common_path)))
        and rect[2] - rect[0] >= width * 0.70
        and rect[3] - rect[1] >= height * 0.40
    ]
    if same_page_markers:
        candidates = [
            candidate
            for candidate in candidates
            if any(
                len(marker) > len(candidate[0])
                and all(candidate[0][index] is marker[index] for index in range(len(candidate[0])))
                for marker in same_page_markers
            )
        ]
    unique_rects = sorted(set(item[1] for item in candidates))
    if len(unique_rects) == 1:
        list_rect = unique_rects[0]
        selected_evidence = "list={} class={}".format(
            list_rect,
            next(item[2] for item in candidates if item[1] == list_rect),
        )
    elif len(unique_rects) > 1:
        return None, "素材群历史 ListView/RecyclerView 候选不唯一：{} 个".format(
            len(unique_rects)
        )
    else:
        # Some WeChat builds expose message cells and generic FrameLayout /
        # RelativeLayout parents, but no scrollable class. Anchor the fallback
        # to a visible act-* node in the same page, then choose the deepest
        # wide ancestor whose clipped body still spans a substantial history
        # region. This preserves structural evidence without requiring a
        # particular Android widget class.
        ancestor_candidates = {}
        for marker_path in same_page_markers:
            for depth in range(len(common_path), len(marker_path) - 1):
                item = marker_path[depth]
                package_name = item.get("packageName")
                if package_name and package_name != WECHAT_PACKAGE:
                    continue
                raw = _rect(item)
                if not _valid_rect(raw):
                    continue
                rect = (
                    max(0, raw[0]),
                    max(0, raw[1]),
                    min(width, raw[2]),
                    min(height, raw[3]),
                )
                region = (
                    rect[0],
                    max(rect[1], header_rect[3]),
                    rect[2],
                    min(rect[3], composer_rect[1]),
                )
                if (
                    rect[2] - rect[0] < width * 0.70
                    or not _valid_rect(region)
                    or region[3] - region[1] < height * 0.35
                ):
                    continue
                item_class = " ".join(
                    str(item.get(key) or "") for key in ("type", "className")
                ).strip()
                item_id = str(item.get("id") or "").rsplit("/", 1)[-1]
                area = (region[2] - region[0]) * (region[3] - region[1])
                key = (depth, area, region)
                ancestor_candidates[key] = (item_class, item_id, rect)

        if not ancestor_candidates:
            return None, (
                "素材群历史无 ListView/RecyclerView，且 act-* 可见父容器无法唯一确认"
            )
        deepest = max(key[0] for key in ancestor_candidates)
        deepest_candidates = [
            (key, value)
            for key, value in ancestor_candidates.items()
            if key[0] == deepest
        ]
        regions = sorted(set(key[2] for key, _ in deepest_candidates))
        if len(regions) != 1:
            return None, "act-* 可见父容器候选不唯一：{} 个".format(len(regions))
        region = regions[0]
        _, selected_value = min(
            (pair for pair in deepest_candidates if pair[0][2] == region),
            key=lambda pair: pair[0][1],
        )
        list_rect = selected_value[2]
        marker_texts = sorted(
            set(" ".join(str(path[-1].get("text") or "").split()) for path in same_page_markers)
        )
        selected_evidence = (
            "ancestor_fallback=true marker={} parent_type={} parent_id={} parent_rect={}".format(
                marker_texts,
                selected_value[0],
                selected_value[1],
                list_rect,
            )
        )

    region = (
        list_rect[0],
        max(list_rect[1], header_rect[3]),
        list_rect[2],
        min(list_rect[3], composer_rect[1]),
    )
    if not _valid_rect(region) or region[3] - region[1] < height * 0.35:
        return None, "实时历史列表与标题/输入框之间无可用区域"
    return region, "header={} composer={} {} region={}".format(
        header_rect, composer_rect, selected_evidence, region
    )


def _reset_from_search_page(ble, step_log):
    """Return to chat-list home with bounded official HID right swipes."""
    page_state, query = _wechat_page_state()
    if page_state != "search":
        raise SenderStop(
            "当前页面不是微信搜索页，禁止执行右滑复位：state={} query={}".format(
                page_state,
                query,
            ),
            ambiguous=True,
        )
    if _wait_for_stable_wechat_home(timeout=2.0, interval=0.5):
        step_log.add(
            len(step_log.items) + 1,
            "确认微信首页（会话列表）",
            "verified",
            "right_swipes=0 home_signature_already_true",
        )
        return
    step_log.add(
        len(step_log.items) + 1,
        "准备直接右滑返回微信首页",
        "home_not_confirmed",
        "page_classification_observational_only",
    )
    for attempt in range(2):
        if _wait_for_stable_wechat_home(timeout=2.0, interval=0.5):
            step_log.add(
                len(step_log.items) + 1,
                "确认微信首页（会话列表）",
                "verified",
                "right_swipes={}".format(attempt),
            )
            return
        gesture_rect = _generic_wechat_gesture_rect()
        if not gesture_rect:
            _capture_blocker_screenshot(
                "return_home_search_no_gesture",
                "state=search query={}".format(query),
            )
            raise SenderStop(
                "微信返回前未找到实时滑动区域",
                ambiguous=True,
            )
        left, top, right, bottom = gesture_rect
        # Search-page return uses the requested live-area left-to-middle
        # gesture.  This path is only for leaving search/results; profile
        # return uses the bottom “微信” tab instead.
        content_width = right - left
        start_x = int(left + content_width * 0.00)
        end_x = int(left + content_width * 0.50)
        start_y = int(top + (bottom - top) * 0.50)
        width, height = _device_size()
        if not (
            0 <= start_x < width
            and 0 <= end_x < width
            and 0 <= start_y < height
            and start_x < end_x
        ):
            raise SenderStop("微信右滑实时区域超出 HID 范围", ambiguous=True)
        _hid_swipe(
            ble,
            start_x,
            start_y,
            end_x,
            start_y,
            step_log,
            "右滑返回微信首页 {}/2".format(attempt + 1),
        )
        if _wait_for_stable_wechat_home(timeout=5, interval=0.5):
            step_log.add(
                len(step_log.items) + 1,
                "确认微信首页（会话列表）",
                "verified",
                "right_swipes={}".format(attempt + 1),
            )
            return
    raise SenderStop(
        "微信返回后两次右滑仍未稳定确认首页",
        ambiguous=True,
    )


def _action_scene_matches(expected, detail="", point=None):
    """Check the fresh live page before a state-changing HID action."""
    page_state, _ = _wechat_page_state()
    if expected == "chooser":
        current = _chooser_rects()
        if point is None:
            return bool(current)
        return any(
            abs((_center(rect)[0]) - int(point[0])) <= 4
            and abs((_center(rect)[1]) - int(point[1])) <= 4
            for rect in current
        )
    if expected in ("home", "chat_list"):
        return _is_wechat_chat_list()
    if expected == "profile":
        return bool(_read_profile_wechat_id())
    if expected == "search":
        return page_state == "search" and bool(_search_input_rect())
    if expected == "material":
        return _header_has(MATERIAL_GROUP_NAME)
    if expected == "chat":
        return page_state in ("group_chat", "chat") and not _search_input_rect()
    if expected == "target_chat":
        return (
            bool(detail)
            and not _search_input_rect()
            and _header_has(detail)
        )
    if expected == "card_menu":
        return len(_find_action_text_rect("转发", top=0, bottom=420)) == 1
    if expected == "forward_page":
        return (
            not _find_action_text_rect("转发", top=0, bottom=420)
            and len(_find_action_text_rect("多选", top=0, bottom=420)) == 1
        )
    if expected == "forward_multi":
        return bool(_search_input_rect())
    if expected == "forward_preview":
        return bool(_find_text_contains_rect("发送给", top=700, bottom=1300)) and len(
            _find_action_text_rect("发送", top=1700)
        ) == 1
    if expected == "mini_program":
        return bool(
            _find_action_text_rect("最近", top=80, bottom=270)
            and _find_action_text_rect("搜索小程序", top=230, bottom=420)
        )
    return page_state == expected


def _before_action(ble, step_log, expected, action_name, detail="", rect=None):
    """Keep page classification observational; never gate a live target action."""
    step_log.add(
        len(step_log.items) + 1,
        "跳过动作前页面判定：{}".format(action_name),
        "page_gate_skipped",
        "expected={} reason=live_target_only".format(expected),
    )


def _center(rect):
    return int((rect[0] + rect[2]) / 2), int((rect[1] + rect[3]) / 2)


def _hid_point(rect, action_name):
    width, height = _device_size()
    x, y = _center(rect)
    if not (0 <= x < width and 0 <= y < height):
        raise SenderStop(
            "控件树坐标超出 HID 触控范围：{} ({}, {})".format(action_name, x, y),
            ambiguous=True,
        )
    return x, y


def _settle_after_hid(step_log, action_name, seconds=HID_POST_ACTION_SETTLE_SECONDS):
    """Wait 1–2 seconds after one complete HID action before reading the tree."""
    delay = max(1.0, min(2.0, float(seconds)))
    step_log.add(len(step_log.items) + 1, "动作后等待：{}".format(action_name), "settling", str(delay))
    time.sleep(delay)


def _hid_swipe(ble, start_x, start_y, end_x, end_y, step_log, action_name):
    """Send one explicit official HID swipe as down, move, and up."""
    start = (int(start_x), int(start_y))
    end = (int(end_x), int(end_y))
    ble.touch_down(start[0], start[1], dur=20)
    try:
        ble.touch_move(end[0], end[1], dur=450)
    finally:
        ble.touch_up(end[0], end[1], dur=20)
    step_log.add(
        len(step_log.items) + 1,
        action_name,
        "hid_swipe_down_move_up_sent",
        "start={} end={}".format(start, end),
    )
    _settle_after_hid(step_log, action_name)


def _hid_history_scroll(ble, start_x, start_y, end_x, end_y, step_log, action_name):
    """Scroll chat history with the ESP32 plugin's timed, multi-report slide."""
    start = (int(start_x), int(start_y))
    end = (int(end_x), int(end_y))
    ble.slide(
        start[0],
        start[1],
        end[0],
        end[1],
        dur=700,
        down_dur=30,
        up_dur=30,
        easing_mode=0,
        easing_power=1,
        report_interval=30,
    )
    step_log.add(
        len(step_log.items) + 1,
        action_name,
        "official_ble_slide_invoked",
        "start={} end={} dur=700ms report_interval=30ms".format(start, end),
    )
    _settle_after_hid(step_log, action_name)


def _hid_back(ble, step_log, action_name="返回"):
    ble.back()
    step_log.add(len(step_log.items) + 1, action_name, "hid_back_sent")
    _settle_after_hid(step_log, action_name)


def _hid_clear(ble, step_log, action_name="清空输入框", settle_seconds=None):
    ble.clear()
    step_log.add(len(step_log.items) + 1, action_name, "hid_clear_sent")
    if settle_seconds is None:
        _settle_after_hid(step_log, action_name)
    else:
        delay = float(settle_seconds)
        step_log.add(
            len(step_log.items) + 1,
            "动作后等待：{}".format(action_name),
            "settling_assumed_empty",
            str(delay),
        )
        time.sleep(delay)


def _tap(ble, rect, step_log, action_name, expected=None, detail=""):
    if not rect:
        raise SenderStop("未找到可点击目标：{}".format(action_name))
    if expected:
        _before_action(ble, step_log, expected, action_name, detail=detail, rect=rect)
    ble.click(*_hid_point(rect, action_name), dur=35)
    step_log.add(len(step_log.items) + 1, action_name, "hid_action_sent")
    _settle_after_hid(step_log, action_name)


def _focus_search_input(ble, step_log, action_name="聚焦搜索框", expected=None):
    """Tap the editor's own live rect and require a mode-6 focus signal."""
    for attempt in range(2):
        rect = _wait_for(_search_input_rect, timeout=5, interval=0.25)
        if not rect:
            raise SenderStop("未找到唯一的微信搜索输入框", ambiguous=True)
        _tap(
            ble,
            rect,
            step_log,
            action_name if attempt == 0 else "再次" + action_name,
            expected=expected,
        )
        if _wait_for(_search_input_focused, timeout=3, interval=0.25):
            step_log.add(
                len(step_log.items) + 1,
                "确认搜索框获得焦点",
                "focused",
                "attempt={}".format(attempt + 1),
            )
            return rect
    raise SenderStop("搜索输入框点击后未确认获得焦点", ambiguous=True)


def _search_input_has_value(value):
    expected = str(value or "").strip()
    if not expected:
        return False
    try:
        tree = _dump()
    except Exception:
        return False
    for path in _walk(tree):
        item = path[-1]
        if not any(node.get("packageName") == WECHAT_PACKAGE for node in path):
            continue
        if any(node.get("visible") is False for node in path):
            continue
        if item.get("type") not in ("EditText", "AutoCompleteTextView") and item.get(
            "editable"
        ) is not True:
            continue
        rect = _rect(item)
        if not _valid_rect(rect) or rect[1] >= 460 or rect[3] > 520:
            continue
        if str(item.get("text") or "").strip() == expected:
            return True
    return False


def _search_input_has_value_ocr(value):
    """Confirm typed text visually, but never use OCR to choose an action target."""
    expected = "".join(str(value or "").split())
    if not expected:
        return False
    rect = _search_input_rect()
    if not _valid_rect(rect):
        return False
    try:
        items = Ocr.find_all(rect=list(rect)) or []
    except Exception as exc:
        print("SEARCH_INPUT_OCR_ERROR", str(exc)[:160])
        return False
    observed = "".join(
        "".join(str(item.get("text") or "").split())
        for item in items
        if isinstance(item, dict)
    )
    return expected in observed


def _search_submit_rect():
    """Return the live WeChat search-submit button, if this build exposes it."""
    return _find_desc_or_id_rect(
        descs=("搜索", "Search"),
        ids=(WECHAT_PACKAGE + ":id/mdg",),
        top=150,
        bottom=360,
    )


def _commit_search_input(ble, step_log, value, action_name="提交微信搜索"):
    """Verify the query before submitting so Enter cannot hide the evidence."""
    if _wait_for(lambda: _search_input_has_value(value), timeout=3, interval=0.25):
        step_log.add(
            len(step_log.items) + 1,
            "核验搜索输入内容",
            "verified_by_tree",
            value[:80],
        )
    elif _search_input_has_value_ocr(value):
        step_log.add(
            len(step_log.items) + 1,
            "核验搜索输入内容",
            "verified_by_ocr_in_live_input_rect",
            value[:80],
        )
    else:
        raise SenderStop(
            "搜索框控件树与输入框区域 OCR 均未核验到文本：{}".format(value[:80]),
            ambiguous=True,
        )
    submit = _wait_for(_search_submit_rect, timeout=3, interval=0.25)
    if submit:
        _tap(
            ble,
            submit,
            step_log,
            "点击微信搜索",
        )
    else:
        # Only submit after the exact query was observed in the live editor.
        # Do not send Enter as a speculative attempt to commit unverified text.
        ble.enter()
        step_log.add(
            len(step_log.items) + 1,
            action_name,
            "hid_enter_sent_after_query_verification",
            value[:80],
        )
        _settle_after_hid(step_log, action_name)


def _long_press(ble, rect, step_log, action_name, expected=None, detail=""):
    if not rect:
        raise SenderStop("未找到长按目标：{}".format(action_name))
    if expected:
        _before_action(ble, step_log, expected, action_name, detail=detail, rect=rect)
    x, y = _hid_point(rect, action_name)
    ble.touch_down(x, y, dur=30)
    time.sleep(1.15)
    ble.touch_up(x, y, dur=30)
    step_log.add(len(step_log.items) + 1, action_name, "hid_long_press_sent")
    _settle_after_hid(step_log, action_name)


def _paste(
    ble,
    text,
    step_log,
    action_name,
    expected=None,
    detail="",
    commit_search=True,
):
    value = str(text or "")
    if not value:
        raise SenderStop("尝试输入空文本：{}".format(action_name))
    if expected:
        _before_action(ble, step_log, expected, action_name, detail=detail)
    if expected in ("search", "forward_multi", "forward_preview"):
        # Use AScript's official IME for recipient searches and the forwarding
        # caption. Clipboard paste can leave text out of WeChat's EditText on
        # this Android 15 build. UI actions remain official HID.
        if not Ime.is_active():
            raise SenderStop("AScript 输入法未处于激活状态", ambiguous=True)
        Ime.input(value)
        step_log.add(
            len(step_log.items) + 1,
            action_name,
            "ascript_ime_input_sent",
            value,
        )
    else:
        Clipboard.put(value)
        ble.paste()
        step_log.add(len(step_log.items) + 1, action_name, "clipboard_paste_sent")
    _settle_after_hid(step_log, action_name)
    if expected in ("search", "forward_multi") and commit_search:
        _commit_search_input(ble, step_log, value)


def _send_enter(ble, step_log, expected="chat"):
    if expected:
        _before_action(ble, step_log, expected, "发送输入文字")
    ble.enter()
    step_log.add(len(step_log.items) + 1, "发送输入文字", "hid_enter_sent")
    _settle_after_hid(step_log, "发送输入文字")


def _chat_header_rects(group_name, tree=None):
    """统一标题证据：同一次 mode=6 树优先，缺失时读取实时标题栏 OCR。"""
    expected = " ".join(str(group_name or "").split())
    if not expected:
        return []
    if tree is None:
        tree = _dump()
    pattern = re.compile(re.escape(expected) + r"\s*(?:[（(]\s*\d+\s*[)）])?")

    def title_rect(item):
        label = " ".join(str(item.get("text") or "").split())
        rect = _rect(item)
        if pattern.fullmatch(label) and _valid_rect(rect) and 80 <= (rect[1] + rect[3]) / 2 <= 250:
            return rect
        return None

    rects = set()
    for path in _walk(tree):
        if any(item.get("visible") is False for item in path):
            continue
        if not any(item.get("packageName") == WECHAT_PACKAGE for item in path):
            continue
        rect = title_rect(path[-1])
        if rect:
            rects.add(rect)
    if rects:
        return sorted(rects)
    try:
        items = Ocr.find_all(rect=[0, 80, _device_size()[0], 250]) or []
    except Exception:
        return []
    return sorted(set(rect for rect in (title_rect(item) for item in items) if rect))


def _header_has(group_name):
    return len(_chat_header_rects(group_name)) == 1


def _wait_header(group_name, timeout=10):
    return _wait_for(lambda: _header_has(group_name), timeout=timeout)


def _is_wechat_chat_list():
    """Confirm the top-level WeChat chat list before starting a new search."""
    try:
        # _dump 内部已固定 mode=6；传入参数会抛 TypeError 并使首页始终判为 False。
        tree = _dump()
    except Exception:
        return False
    return _wechat_home_tree_signature(tree)


def _wechat_actionbar_back_rects(tree=None):
    """Resolve unique live WeChat chat-page back controls from mode-6 nodes."""
    if tree is None:
        try:
            tree = _dump()
        except Exception:
            return []
    width, _ = _device_size()
    candidates = []
    for path in _walk(tree):
        item = path[-1]
        if item.get("packageName") != WECHAT_PACKAGE or item.get("visible") is False:
            continue
        short_id = str(item.get("id") or "").rsplit("/", 1)[-1]
        if short_id != "actionbar_up_indicator":
            continue
        rect = _clickable_ancestor(path)
        if not rect and item.get("clickable") is True:
            rect = _rect(item)
        if (
            _valid_rect(rect)
            and rect[1] <= 360
            and rect[3] <= 420
            and rect[0] <= int(width * 0.25)
        ):
            candidates.append(tuple(rect))
    return sorted(set(candidates))


def _return_to_chat_list(ble, step_log):
    """Leave a chat/search result and confirm the top-level WeChat list."""
    if _is_wechat_chat_list():
        step_log.add(
            len(step_log.items) + 1,
            "确认微信首页（会话列表）",
            "verified",
            "home_signature_already_true",
        )
        return
    step_log.add(
        len(step_log.items) + 1,
        "读取微信收尾页面状态",
        "home_not_confirmed",
        "page_classification_observational_only",
    )
    page_state, query = _wechat_page_state()
    if page_state == "home":
        # The immediately preceding chat-list signature read can race a UI
        # tree refresh. A fresh positive home signature is already sufficient;
        # do not swipe, back out, or misroute an existing home page.
        step_log.add(
            len(step_log.items) + 1,
            "复核当前页已是微信首页会话列表",
            "verified",
            "page_state_home",
        )
        return
    known_material_chat = _header_has(MATERIAL_GROUP_NAME)
    known_forward_page = bool(
        _find_action_text_rect("多选", top=0, bottom=420)
        or _find_action_text_contains_rect("完成", top=0, bottom=420)
        or _find_text_contains_rect("发送给", top=700, bottom=1300)
    )

    # A chat page exposes WeChat's live action-bar back node. Prefer one
    # uniquely resolved HID tap and confirm the list; this avoids repeated
    # back-key presses being mistaken for proof of a successful reset.
    if page_state in ("chat", "group_chat") and not known_forward_page:
        back_rects = _wechat_actionbar_back_rects()
        if len(back_rects) == 1:
            _tap(
                ble,
                back_rects[0],
                step_log,
                "点击微信聊天页实时返回按钮",
                expected="chat",
                detail="mode6_actionbar_up_indicator",
            )
            # When the material chat was opened from WeChat search, its first
            # back action returns to the search-results page, not the chat
            # list. Wait for either safe destination instead of treating that
            # expected intermediate page as a failed home reset.
            next_page = _wait_for(
                _wechat_chat_or_search_state,
                timeout=8,
                interval=0.25,
            )
            if next_page and next_page[0] == "home":
                step_log.add(
                    len(step_log.items) + 1,
                    "确认微信首页（会话列表）",
                    "verified",
                    "chat_back_control=mode6_actionbar_up_indicator",
                )
                return
            if next_page and next_page[0] == "search":
                step_log.add(
                    len(step_log.items) + 1,
                    "聊天页返回后到达微信搜索结果页",
                    "intermediate_page_confirmed",
                    "query={}".format(next_page[1]),
                )
                _return_from_search_results_to_chat_list(ble, step_log)
                return
            next_state, next_query = _wechat_page_state()
            _capture_blocker_screenshot(
                "return_home_chat_back_unconfirmed",
                "state={} query={}".format(next_state, next_query),
            )
            raise SenderStop(
                "点击微信聊天页实时返回按钮后未确认会话列表：state={} query={}".format(
                    next_state,
                    next_query,
                ),
                ambiguous=True,
            )

    # Native forwarding pages and child pages without a unique live back
    # control use the official HID back key. They never enter right-swipe
    # recovery, which is reserved for WeChat search/results pages.
    if known_material_chat or known_forward_page or page_state in (
        "chat",
        "group_chat",
        "child",
    ):
        for attempt in range(MAX_HOME_BACKS):
            if _is_wechat_chat_list():
                return
            _hid_back(
                ble,
                step_log,
                "HID返回微信会话列表 {}/{}".format(attempt + 1, MAX_HOME_BACKS),
            )
            if _wait_for(_is_wechat_chat_list, timeout=5, interval=0.25):
                return
        _capture_blocker_screenshot(
            "return_home_child_page",
            "state={} query={}".format(page_state, query),
        )
        raise SenderStop(
            "HID返回后仍未确认微信会话列表：state={} query={}".format(
                page_state,
                query,
            ),
            ambiguous=True,
        )

    # Search/results pages are the only pages that use the bounded right
    # swipe requested for this device.
    if page_state == "search":
        _reset_from_search_page(ble, step_log)
        if _is_wechat_chat_list():
            return
    elif page_state in WECHAT_ROOT_TAB_STATES:
        _return_from_profile_to_chat_home(ble, step_log)
        return
    else:
        _capture_blocker_screenshot(
            "return_home_unknown_page",
            "state={} query={}".format(page_state, query),
        )
        raise SenderStop(
            "微信收尾页面状态不明，禁止盲滑或盲退：state={} query={}".format(
                page_state,
                query,
            ),
            ambiguous=True,
        )

    raise SenderStop("微信右滑返回后无法确认微信会话列表", ambiguous=True)


def _wechat_chat_or_search_state():
    """Return only a confirmed safe post-back destination for bounded polling."""
    state, query = _wechat_page_state()
    if state in ("home", "search"):
        return state, query
    return None


def _return_from_search_results_to_chat_list(ble, step_log):
    """Exit the confirmed material-group search results with its live back node."""
    state, query = _wechat_page_state()
    back_rects = _wechat_actionbar_back_rects()
    if state != "search" or len(back_rects) != 1:
        _capture_blocker_screenshot(
            "return_home_search_result_unconfirmed",
            "state={} query={} back_candidates={}".format(
                state,
                query,
                len(back_rects),
            ),
        )
        raise SenderStop(
            "微信搜索结果页未能唯一确认返回按钮：state={} query={} back_candidates={}".format(
                state,
                query,
                len(back_rects),
            ),
            ambiguous=True,
        )
    _tap(
        ble,
        back_rects[0],
        step_log,
        "退出卡片素材群搜索结果返回微信会话列表",
        expected="search",
        detail="unique_mode6_actionbar_up_indicator query={}".format(query),
    )
    if _wait_for(_is_wechat_chat_list, timeout=8, interval=0.25):
        step_log.add(
            len(step_log.items) + 1,
            "确认微信首页（会话列表）",
            "verified",
            "search_result_back_control=mode6_actionbar_up_indicator",
        )
        return
    next_state, next_query = _wechat_page_state()
    _capture_blocker_screenshot(
        "return_home_search_result_back_unconfirmed",
        "state={} query={}".format(next_state, next_query),
    )
    raise SenderStop(
        "退出微信搜索结果后仍未确认会话列表：state={} query={}".format(
            next_state,
            next_query,
        ),
        ambiguous=True,
    )


def _reset_to_wechat_home(ble, step_log, reason):
    """Return to and confirm WeChat's top-level chat-list home.

    The next account or task must never inherit the material chat, a native
    forwarding page, or a search result. Back navigation is an official HID
    action; the live mode-6 tree only confirms the resulting page.
    """
    _return_to_chat_list(ble, step_log)
    if not _wait_for_stable_wechat_home(timeout=8, interval=0.5):
        raise SenderStop(
            "{}后未确认微信首页（会话列表）".format(reason),
            ambiguous=True,
        )
    step_log.add(
        len(step_log.items) + 1,
        "确认微信首页（会话列表）",
        "verified",
        reason,
    )


def _reset_after_card_forward(ble, step_log):
    """Use up to three HID right swipes only after a completed card forward.

    The send action is the authorization for this navigation path. Each
    gesture uses the current WeChat content rectangle, waits for the HID
    action to settle, then requires two consecutive mode-6 home signatures.
    Other return/navigation paths continue to use their existing controls.
    """
    if _wait_for_stable_wechat_home(timeout=2.0, interval=0.5):
        step_log.add(
            len(step_log.items) + 1,
            "卡片转发后已在微信首页",
            "verified",
            "right_swipes=0 stable_home_signature=true",
        )
        return

    for attempt in range(3):
        gesture_rect = _generic_wechat_gesture_rect()
        if not gesture_rect:
            _capture_blocker_screenshot(
                "post_forward_no_live_gesture_region",
                "right_swipes={} home=unconfirmed".format(attempt),
            )
            raise SenderStop(
                "卡片转发后未找到实时微信滑动区域，停止复位",
                ambiguous=True,
                stage="post_send_cleanup",
            )
        left, top, right, bottom = gesture_rect
        width, height = _device_size()
        start_x = int(left + (right - left) * 0.00)
        end_x = int(left + (right - left) * 0.50)
        start_y = int(top + (bottom - top) * 0.50)
        if not (
            _valid_rect(gesture_rect)
            and 0 <= start_x < width
            and 0 <= end_x < width
            and 0 <= start_y < height
            and start_x < end_x
        ):
            _capture_blocker_screenshot(
                "post_forward_invalid_gesture_region",
                "rect={} start=({}, {}) end=({}, {})".format(
                    gesture_rect, start_x, start_y, end_x, start_y
                ),
            )
            raise SenderStop(
                "卡片转发后实时右滑区域超出 HID 屏幕范围",
                ambiguous=True,
                stage="post_send_cleanup",
            )
        _hid_swipe(
            ble,
            start_x,
            start_y,
            end_x,
            start_y,
            step_log,
            "卡片转发后右滑复位 {}/3".format(attempt + 1),
        )
        if _wait_for_stable_wechat_home(timeout=6, interval=0.5):
            step_log.add(
                len(step_log.items) + 1,
                "确认卡片转发后微信首页",
                "verified",
                "right_swipes={} stable_home_reads=2".format(attempt + 1),
            )
            return

    page_state, query = _wechat_page_state()
    _capture_blocker_screenshot(
        "post_forward_home_unconfirmed",
        "right_swipes=3 state={} query={}".format(page_state, query),
    )
    raise SenderStop(
        "卡片转发后最多三次右滑仍未稳定确认微信首页：state={} query={}".format(
            page_state, query
        ),
        ambiguous=True,
        stage="post_send_cleanup",
    )


def _normalize_wechat_id(value):
    value = re.sub(r"\s+", "", str(value or "").strip())
    value = re.sub(r"^微信号[:：]?", "", value)
    if not re.match(r"^[A-Za-z][A-Za-z0-9_-]{2,63}$", value):
        return None
    return value.lower()


def _read_profile_wechat_id():
    """Read exactly one stable WeChat ID from the live mode-6 tree."""
    candidates = set()
    try:
        tree = _dump()
    except Exception:
        return None
    for path in _walk(tree):
        item = path[-1]
        if item.get("packageName") != WECHAT_PACKAGE or item.get("visible") is False:
            continue
        text = str(item.get("text") or "").strip()
        if not text.startswith(("微信号：", "微信号:")):
            continue
        value = _normalize_wechat_id(text)
        if value:
            candidates.add(value)
    # During a dual-app resume the mode-6 tree can briefly omit the profile
    # text even though it is already visible. OCR supplements perception; it
    # never supplies a HID action coordinate.
    try:
        ocr_matches = Ocr.find_all(
            rect=[0, 150, _device_size()[0], 650]
        ) or []
    except Exception:
        ocr_matches = []
    for item in ocr_matches:
        text = str(item.get("text") or "").strip()
        if "微信号" not in text:
            continue
        value = _normalize_wechat_id(text)
        if value:
            candidates.add(value)
    return next(iter(candidates)) if len(candidates) == 1 else None


def _return_from_profile_to_chat_home(ble, step_log):
    """Leave the verified profile by clicking the live bottom “微信” tab."""
    bottom = _device_size()[1]
    tab_rects = _find_action_text_rect("微信", top=bottom - 520)
    if len(tab_rects) != 1:
        raise SenderStop("微信“我”页未找到唯一的“微信”Tab，未执行滑动", ambiguous=True)
    _tap(
        ble,
        tab_rects[0],
        step_log,
        "点击微信Tab返回首页",
        expected="profile",
    )
    if not _wait_for(_is_wechat_chat_list, timeout=8, interval=0.25):
        raise SenderStop("点击微信Tab后未确认微信首页（会话列表）", ambiguous=True)
    step_log.add(
        len(step_log.items) + 1,
        "确认微信首页（会话列表）",
        "verified",
        "strategy=wechat_tab",
    )


def _verify_active_wechat_account(ble, payload, step_log):
    """Open “我” and verify the stable ID before touching the material group.

    The user-facing nickname is logged from configuration as display metadata,
    while the unique WeChat ID remains the hard account boundary. This device's
    mode-6 tree exposes the WeChat ID but may omit the large nickname label.
    """
    target_id = str(payload.get("targetWechatAccountId") or "").strip()
    if not target_id.startswith("wechat-id-"):
        raise SenderStop("任务账号不是稳定微信号 ID，拒绝继续")
    bottom = _device_size()[1]
    me_rects = _find_action_text_rect("我", top=bottom - 520)
    if len(me_rects) != 1:
        raise SenderStop("无法从控件树唯一定位微信“我”入口", ambiguous=True)
    _tap(
        ble,
        me_rects[0],
        step_log,
        "进入微信“我”页核验账号",
        expected="home",
    )
    actual_wechat_id = _wait_for(_read_profile_wechat_id, timeout=10)
    if not actual_wechat_id and _is_wechat_chat_list():
        # A dual-app resume can consume the first HID tap while the list is
        # settling. Retry only when the live tree still proves that we are on
        # the chat list; never repeat a tap on an unknown page.
        retry_rects = _find_action_text_rect("我", top=bottom - 520)
        if len(retry_rects) == 1:
            _tap(
                ble,
                retry_rects[0],
                step_log,
                "重试进入微信“我”页",
                expected="home",
            )
            actual_wechat_id = _wait_for(_read_profile_wechat_id, timeout=10)
    if not actual_wechat_id:
        raise SenderStop("微信“我”页未读到唯一微信号", ambiguous=True)
    actual_account_id = "wechat-id-" + actual_wechat_id
    if actual_account_id != target_id:
        raise SenderStop(
            "微信账号槽位不匹配：任务={}，实际={}".format(
                target_id,
                actual_account_id,
            ),
            ambiguous=True,
        )
    expected_name = " ".join(str(WECHAT_ACCOUNT_NAMES.get(target_id) or "").split())
    detail = actual_account_id + (" / " + expected_name if expected_name else "")
    step_log.add(len(step_log.items) + 1, "核验微信账号身份", "verified", detail)
    step_log.add(
        len(step_log.items) + 1,
        "读取微信号后等待页面稳定",
        "settling",
        str(HID_POST_ACTION_SETTLE_SECONDS),
    )
    time.sleep(HID_POST_ACTION_SETTLE_SECONDS)
    _return_from_profile_to_chat_home(ble, step_log)


def _wait_target_chat(group_name, group_code=None, timeout=10):
    expected_code = " ".join(str(group_code or "").split())
    expected_name = " ".join(str(group_name or "").split())

    def predicate():
        # The same EditText is present on WeChat's search results page.  Do
        # not accept a query-page label as the chat header.
        if _search_input_rect():
            return False
        if expected_code and _find_text_rect(
            expected_code, top=0, bottom=360
        ):
            return True
        return bool(expected_name and _find_text_rect(expected_name, top=0, bottom=360))

    return _wait_for(predicate, timeout=timeout)


def _ensure_wechat(ble, payload, step_log):
    Device.wake_up()
    try:
        Device.keep_screen_on()
    except Exception:
        pass
    if _reuse_scanned_account():
        if not _wait_for(
            lambda: _wechat_tree_visible() and not _chooser_rects(),
            timeout=8,
            interval=0.25,
        ):
            raise SenderStop(
                "扫描后未能复用当前微信实例，拒绝猜测账号槽位",
                ambiguous=True,
            )
        step_log.add(
            len(step_log.items) + 1,
            "复用刚扫描的微信实例",
            "verified",
            str(payload.get("targetWechatAccountId") or ""),
        )
        time.sleep(HID_POST_ACTION_SETTLE_SECONDS)
        return

    target_id = str(payload.get("targetWechatAccountId") or "").strip()
    raw_slot = str(os.environ.get("TEAMBUY_SEND_ACCOUNT_SLOT") or "").strip()
    try:
        configured_slot = int(ACCOUNT_SLOTS[target_id])
        # A unified sender run handles both scanned accounts; use the stable
        # account-to-slot map unless a caller explicitly scopes one account.
        slot_index = int(raw_slot) if raw_slot else configured_slot
    except (KeyError, TypeError, ValueError):
        raise SenderStop(
            "发送阶段缺少已扫描账号对应的有效双开槽位",
            ambiguous=True,
        )
    if slot_index not in (0, 1) or configured_slot != slot_index:
        raise SenderStop(
            "发送账号与扫描槽位映射不一致：account={} slot={} configured={}".format(
                target_id,
                slot_index,
                configured_slot,
            ),
            ambiguous=True,
        )

    # Explicitly re-open the native dual-app chooser after both scans. The
    # chooser rectangles are re-read from mode=6; no remembered coordinates.
    ble.home()
    _settle_after_hid(step_log, "返回系统桌面以切换微信槽位")
    open_app(WECHAT_PACKAGE)
    chooser_rects = _wait_for(_chooser_rects, timeout=10, interval=0.4)
    if not chooser_rects or len(chooser_rects) != 2:
        raise SenderStop(
            "发送前未能从实时控件树唯一识别双开选择器的两个微信入口",
            ambiguous=True,
        )
    _tap(
        ble,
        chooser_rects[slot_index],
        step_log,
        "扫描完成后选择微信槽位 {}".format(slot_index),
        expected="chooser",
    )
    if not _wait_for(
        lambda: _wechat_tree_visible() and not _chooser_rects(),
        timeout=12,
        interval=0.4,
    ):
        raise SenderStop(
            "选择双开槽位后未确认微信页面，停止账号发送",
            ambiguous=True,
        )
    step_log.add(
        len(step_log.items) + 1,
        "确认已进入指定微信槽位",
        "verified",
        "slot={} targetAccount={}".format(slot_index, target_id),
    )
    time.sleep(HID_POST_ACTION_SETTLE_SECONDS)


def _chooser_rects():
    """Read the two native dual-WeChat entries from the chooser UI."""
    rects = []
    try:
        node.Selector.refresh(UI_MODE)
        raw = node.Selector.dump(UI_MODE)
        tree = json.loads(raw) if isinstance(raw, str) else raw
        chooser_marker = any(
            str(path[-1].get("text") or "").strip()
            in ("请选择要使用的应用", "取消")
            for path in _walk(tree)
        )
        for path in _walk(tree):
            item = path[-1]
            if (
                item.get("visible") is not False
                and str(item.get("text") or "").strip() == "微信"
            ):
                # Accept the native system resolver package only when the
                # live tree itself identifies the chooser; keep rect/action
                # derivation strictly inside the mode-6 GridView subtree.
                if item.get("packageName") != DUAL_APP_PACKAGE and not chooser_marker:
                    continue
                # Both entries are non-clickable labels inside one clickable
                # GridView. Use the nearest single-item container below that
                # GridView; never use the shared GridView rectangle.
                grid_index = None
                for index in range(len(path) - 1, -1, -1):
                    if str(path[index].get("type") or "") == "GridView":
                        grid_index = index
                        break
                if grid_index is None or grid_index + 1 >= len(path):
                    continue
                item_container = path[grid_index + 1]
                if str(item_container.get("type") or "") == "GridView":
                    continue
                rect = _rect(item_container)
                if _valid_rect(rect) and rect[2] - rect[0] < int(_device_size()[0] * 0.75):
                    rects.append(rect)
    except Exception as exc:
        print("DUAL_CHOOSER_READ_ERROR", str(exc)[:160])
    rects = sorted(set(rects), key=lambda rect: rect[0])
    return rects if len(rects) == 2 else []


def _wechat_tree_visible():
    """Confirm that a visible WeChat view exists after the chooser closes."""
    try:
        tree = _dump()
    except Exception:
        return False
    for path in _walk(tree):
        item = path[-1]
        if item.get("packageName") != WECHAT_PACKAGE or item.get("visible") is False:
            continue
        if _valid_rect(_rect(item)):
            return True
    return False


def _select_account_if_needed(ble, payload, step_log):
    target_id = str(payload.get("targetWechatAccountId") or "").strip()
    if _chooser_rects() or DUAL_APP_PACKAGE in str(Device.current_appinfo()):
        raise SenderStop(
            "发送前双开选择器仍在前台，账号选择未完成",
            ambiguous=True,
        )
    if not _wechat_tree_visible():
        raise SenderStop(
            "发送前当前微信控件树不可见，未继续执行",
            ambiguous=True,
        )
    step_log.add(
        len(step_log.items) + 1,
        "确认发送目标微信账号",
        "verified",
        target_id,
    )


def _visible_chat_row_rects():
    """Resolve visible full-width conversation rows from the live mode-6 tree."""
    try:
        tree = _dump()
    except Exception:
        return []
    if not _wechat_home_tree_signature(tree):
        return []
    width, height = _device_size()
    has_list_container = any(
        item.get("packageName") == WECHAT_PACKAGE
        and item.get("visible") is not False
        and item.get("type") in ("ListView", "RecyclerView")
        and _valid_rect(_rect(item))
        and _rect(item)[2] - _rect(item)[0] >= int(width * 0.85)
        and _rect(item)[3] - _rect(item)[1] >= int(height * 0.50)
        for path in _walk(tree)
        for item in (path[-1],)
    )
    if not has_list_container:
        return []
    candidates = []
    for path in _walk(tree):
        item = path[-1]
        if (
            item.get("packageName") != WECHAT_PACKAGE
            or item.get("visible") is False
            or any(parent.get("visible") is False for parent in path[:-1])
            or item.get("clickable") is not True
        ):
            continue
        rect = _rect(item)
        if not _valid_rect(rect):
            continue
        if rect[0] > int(width * 0.03) or rect[2] < int(width * 0.97):
            continue
        if rect[1] < 180 or rect[3] > height - 120:
            continue
        if rect[3] - rect[1] < 100 or rect[3] - rect[1] > 500:
            continue
        candidates.append(rect)
    return sorted(set(candidates), key=lambda rect: (rect[1], rect[3]))


def _first_chat_row_rect():
    """Resolve the top fully visible conversation row from the live tree."""
    rows = _visible_chat_row_rects()
    return rows[0] if rows else None


def _chat_list_top_swipe_points():
    """Resolve a downward finger swipe inside the live conversation-list body."""
    rows = _visible_chat_row_rects()
    if len(rows) < 2:
        return None, "会话列表控件树未暴露至少两个可见整行"
    width, height = _device_size()
    top = max(220, rows[0][1])
    bottom = min(height - 160, rows[-1][3])
    if bottom - top < 500:
        return None, "会话列表实时行区域过短：top={} bottom={}".format(top, bottom)
    x = int(width * 0.50)
    start_y = int(top + (bottom - top) * 0.25)
    end_y = int(top + (bottom - top) * 0.78)
    if not (0 <= x < width and 0 <= start_y < end_y < height):
        return None, "会话列表实时滑动范围越界：{} {}→{}".format(x, start_y, end_y)
    return (x, start_y, end_y), "rows={} viewport=({}, {})".format(len(rows), top, bottom)


def _material_title_confirmed_in_first_row(row_rect):
    """Use OCR only to confirm the pinned title inside its tree-derived row."""
    if not _valid_rect(row_rect):
        return False
    left, top, right, bottom = row_rect
    try:
        items = Ocr.find_all(rect=[left, top, right, bottom]) or []
    except Exception as exc:
        print("MATERIAL_TITLE_OCR_ERROR", str(exc)[:160])
        return False
    for item in items:
        value = " ".join(str(item.get("text") or "").split())
        # OCR may confuse 素材 as 泰材 on this device; require the stable
        # surrounding words and 群 suffix. WeChat may append the unread count.
        normalized = re.sub(r"\s*(?:[（(]?\d+[)）]?)$", "", value)
        if (
            normalized.startswith("卡片")
            and "材" in normalized
            and normalized.endswith("群")
        ):
            return True
    return False


def _open_material_chat_first(ble, step_log, home_already_confirmed=False):
    """Find the material chat through WeChat search's live 群聊 result section."""
    # The sender may already be on the pinned material chat after account
    # switching or after the previous nine-group chunk.  In that state,
    # returning to the list is unnecessary and can race the list transition.
    material_chat_open = lambda: (
        not _search_input_rect() and _header_has(MATERIAL_GROUP_NAME)
    )
    if _wait_for(material_chat_open, timeout=1.5, interval=0.3):
        step_log.add(len(step_log.items) + 1, "当前已在卡片素材群", "verified")
        return
    if home_already_confirmed and _is_wechat_chat_list():
        step_log.add(
            len(step_log.items) + 1,
            "复核账号扫描后微信首页仍在会话列表",
            "verified",
            "strategy=wechat_tab_already_confirmed",
        )
    else:
        _return_to_chat_list(ble, step_log)
    if not _is_wechat_chat_list():
        page_state, query = _wechat_page_state()
        if page_state != "home":
            raise SenderStop(
                "打开卡片素材群前未确认微信首页会话列表：state={} query={}".format(
                    page_state,
                    query,
                ),
                ambiguous=True,
            )
        step_log.add(
            len(step_log.items) + 1,
            "使用新鲜页面快照确认微信首页",
            "verified",
            "state=home",
        )

    step_log.add(
        len(step_log.items) + 1,
        "通过微信搜索定位卡片素材群",
        "search_route_selected",
        "query={}".format(MATERIAL_GROUP_NAME),
    )
    _open_search(ble, step_log)
    _focus_search_input(
        ble,
        step_log,
        "聚焦素材群搜索框",
        expected="search",
    )
    _hid_clear(ble, step_log, "清空素材群搜索框")
    _paste(
        ble,
        MATERIAL_GROUP_NAME,
        step_log,
        "搜索卡片素材群",
        expected="search",
    )
    matches = _wait_for(
        _material_chat_search_result_rects,
        timeout=10,
        interval=0.4,
    ) or []
    if not matches:
        _capture_blocker_screenshot(
            "material_chat_search_no_result",
            "query={} sections={} results=0".format(
                MATERIAL_GROUP_NAME,
                "/".join(MATERIAL_CHAT_SEARCH_ALLOWED_SECTIONS),
            ),
        )
        raise SenderStop(
            "微信搜索已提交，但未在‘群聊/最常使用/最近使用’区域控件树中找到卡片素材群",
            ambiguous=True,
        )
    if len(matches) != 1:
        _capture_blocker_screenshot(
            "material_chat_search_ambiguous",
            "query={} sections={} matches={}".format(
                MATERIAL_GROUP_NAME,
                "/".join(MATERIAL_CHAT_SEARCH_ALLOWED_SECTIONS),
                len(matches),
            ),
        )
        raise SenderStop(
            "微信搜索‘群聊/最常使用/最近使用’区域的卡片素材群仍不唯一：{}".format(
                len(matches)
            ),
            ambiguous=True,
        )
    _tap(
        ble,
        matches[0],
        step_log,
        "点击搜索结果中的卡片素材群",
        expected="search",
    )
    if not _wait_for(material_chat_open, timeout=10):
        _capture_blocker_screenshot(
            "material_chat_search_header_unconfirmed",
            "query={} header_not_confirmed".format(MATERIAL_GROUP_NAME),
        )
        raise SenderStop(
            "点击卡片素材群搜索结果后未核验群聊标题",
            ambiguous=True,
        )
    step_log.add(
        len(step_log.items) + 1,
        "确认已进入卡片素材群",
        "verified",
        "route=wechat_search_result",
    )


def _open_search(ble, step_log):
    for attempt in range(2):
        rect = _find_desc_or_id_rect(
            descs=("搜索", "Search"),
            ids=(WECHAT_PACKAGE + ":id/actionbar_search",),
            top=0,
            bottom=360,
        )
        if not rect:
            rects = _find_action_text_rect("搜索", top=0, bottom=360)
            rect = rects[0] if len(rects) == 1 else None
        if not rect:
            rect = _search_icon_rect()
        if not rect:
            raise SenderStop("控件树未暴露唯一的微信搜索入口", ambiguous=True)
        _tap(
            ble,
            rect,
            step_log,
            "打开微信搜索",
            expected="chat_list",
        )
        if _wait_for(
            lambda: bool(_search_input_rect())
            or bool(_find_text_rect("搜索本地或网络结果", top=100, bottom=360)),
            timeout=8,
        ):
            return
        if attempt == 0:
            print("SEARCH_OPEN_RETRY", "search_input_not_visible")
            time.sleep(1.2)
    raise SenderStop("微信搜索框未出现")


def _group_search_result_rects(group_name):
    # When a chat's visible title is a routing code (for example c1001),
    # WeChat exposes the saved name as a "群聊名: ..." child.  Selecting that
    # row avoids accidentally opening a similarly named web-search result.
    labels = []
    for prefix in ("群聊名: ", "群聊名：", "昵称: ", "昵称："):
        labels.extend(_find_action_text_rect(prefix + group_name, top=300, bottom=1400))
    if labels:
        return sorted(set(labels))
    # Some WeChat builds expose recipient rows visually but omit their text
    # from the accessibility tree. Keep exact-name matching in this bounded
    # result-list region, then use OCR only as a coordinate fallback.
    return _find_text_rect(group_name, top=300, bottom=1400)


def _current_duplicate_result_rect(group_name, duplicate_index, expected_count):
    """Resolve one same-name row from a fresh tree snapshot before each tap.

    WeChat can remove an already-selected row from the live search results. In
    that case, the remaining rows are re-indexed from one; selection-count
    verification after the tap is the guard that confirms forward progress.
    """
    if expected_count < 1 or duplicate_index < 1 or duplicate_index > expected_count:
        raise SenderStop(
            "同名群实时结果序号越界：groupName={} index={} expected={}".format(
                group_name, duplicate_index, expected_count
            ),
            ambiguous=True,
        )
    fresh_rects = sorted(set(tuple(rect) for rect in _group_search_result_rects(group_name)))
    remaining_count = expected_count - duplicate_index + 1
    if len(fresh_rects) == expected_count:
        fresh_index = duplicate_index
    elif len(fresh_rects) == remaining_count:
        # The selected rows disappeared from the result list; this is now the
        # first unselected matching row, rather than a reason to abort.
        fresh_index = 1
    else:
        raise SenderStop(
            "同名群实时结果数与剩余未选目标不符，不能安全选择：groupName={} expected={} remaining={} observed={}".format(
                group_name,
                expected_count,
                remaining_count,
                len(fresh_rects),
            ),
            ambiguous=True,
        )
    if fresh_index > len(fresh_rects):
        raise SenderStop(
            "同名群实时结果序号越界：groupName={} index={} count={}".format(
                group_name,
                duplicate_index,
                len(fresh_rects),
            ),
            ambiguous=True,
        )
    return fresh_rects[fresh_index - 1]


def _same_name_result_count_options(duplicate_index, expected_count):
    """Allow either all duplicate rows or only the still-unselected rows.

    A fresh search is performed for each PC candidate. Some WeChat builds keep
    already-selected rows visible; others hide them. Any other count is
    ambiguous and must not be clicked.
    """
    if expected_count < 1 or duplicate_index < 1 or duplicate_index > expected_count:
        return ()
    remaining_count = expected_count - duplicate_index + 1
    return tuple(sorted({expected_count, remaining_count}))


def _expand_same_name_targets_to_observed_count(targets, group_name, observed_count):
    """Expand one route bundle when an exact live search proves PC undercounted.

    This is only used in an explicitly scoped c-code test. The approved
    low-granularity policy treats exact same-name rows as one route bundle.
    """
    normalized_name = " ".join(str(group_name or "").split())
    same_name_targets = [
        target
        for target in targets
        if " ".join(str(target.get("groupName") or "").split()) == normalized_name
    ]
    try:
        live_count = int(observed_count)
    except (TypeError, ValueError):
        return []
    if not same_name_targets or live_count <= len(same_name_targets):
        return []

    # Reuse the route package's IDs; never invent a PC candidate or persist a
    # fragile row position as a durable group identity.
    representative = same_name_targets[0]
    candidate_id = str(representative.get("candidateId") or "").strip()
    if not candidate_id:
        return []
    occurrence_values = []
    for target in same_name_targets:
        if str(target.get("candidateId") or "").strip() != candidate_id:
            continue
        try:
            occurrence_values.append(int(target.get("selectionOccurrence") or 1))
        except (TypeError, ValueError):
            occurrence_values.append(1)
    next_occurrence = max(occurrence_values or [1]) + 1
    expanded = []
    for offset in range(live_count - len(same_name_targets)):
        extra = dict(representative)
        extra["groupOccurrenceCount"] = live_count
        extra["selectionOccurrence"] = next_occurrence + offset
        extra["liveOccurrenceExpanded"] = True
        expanded.append(extra)
    return expanded


def _material_chat_search_result_rects():
    """Find the exact material-chat row in a supported WeChat result section.

    WeChat may place the chat under 群聊 or 最常使用/最近使用. Treat those
    sections as alternatives, while section headers from the same fresh mode-6
    tree bound each candidate and keep 搜索网络结果 out of click selection.
    """
    try:
        tree = _dump()
    except Exception as exc:
        print("MATERIAL_CHAT_SEARCH_TREE_ERROR", str(exc)[:160])
        return []

    section_headers = []
    candidate_paths = []
    for path in _walk(tree):
        item = path[-1]
        if item.get("packageName") != WECHAT_PACKAGE:
            continue
        if any(parent.get("visible") is False for parent in path):
            continue
        text = str(item.get("text") or "").strip()
        item_rect = _rect(item)
        if text in MATERIAL_CHAT_SEARCH_SECTION_HEADERS and _valid_rect(item_rect):
            section_headers.append((text, item_rect))
        elif text == MATERIAL_GROUP_NAME and _valid_rect(item_rect):
            candidate_paths.append((path, item_rect))

    section_headers = sorted(
        set(section_headers),
        key=lambda header: (header[1][1], header[1][0], header[0]),
    )
    if not section_headers:
        return []

    sections = []
    screen_bottom = _device_size()[1]
    for index, (header_text, header_rect) in enumerate(section_headers):
        if header_text not in MATERIAL_CHAT_SEARCH_ALLOWED_SECTIONS:
            continue
        section_top = header_rect[3]
        section_bottom = next(
            (
                next_rect[1]
                for _, next_rect in section_headers[index + 1 :]
                if next_rect[1] >= section_top
            ),
            screen_bottom,
        )
        if section_bottom > section_top:
            sections.append((section_top, section_bottom))
    if not sections:
        return []

    matches = []
    for path, text_rect in candidate_paths:
        containing_sections = [
            bounds
            for bounds in sections
            if text_rect[1] >= bounds[0] and text_rect[3] <= bounds[1]
        ]
        if not containing_sections:
            continue
        action_rect = _clickable_ancestor(path)
        if not _valid_rect(action_rect or (0, 0, 0, 0)) or not any(
            action_rect[1] >= section_top and action_rect[3] <= section_bottom
            for section_top, section_bottom in containing_sections
        ):
            action_rect = text_rect
        if (
            _valid_rect(action_rect)
            and any(
                action_rect[1] >= section_top and action_rect[3] <= section_bottom
                for section_top, section_bottom in containing_sections
            )
        ):
            matches.append(action_rect)
    return sorted(set(matches))


def _explicit_group_missing_message():
    """Return a live WeChat error marker for an exited/kicked group, if any."""
    for marker in GROUP_NOT_FOUND_MARKERS:
        if _find_text_contains_rect(marker, top=0, bottom=_device_size()[1]):
            return marker
    return None


def _forward_target_rects(group_code, group_name):
    """Resolve one result after searching the routing code.

    A single exact real group name wins.  If WeChat only exposes the code,
    accept it only when there is exactly one result; multiple same-code rows
    are ambiguous and must not be guessed.
    """
    name_matches = _group_search_result_rects(group_name)
    if len(name_matches) == 1:
        return name_matches
    code_matches = _find_action_text_rect(group_code, top=300, bottom=1450)
    if len(code_matches) == 1:
        return code_matches
    return []


def _search_forward_group_by_name(
    ble,
    group_name,
    step_log,
    target_trace,
    target_index,
    target_count,
    expected_match_count=1,
    allowed_match_counts=None,
    allow_live_occurrence_expansion=False,
):
    """Search by exact name and reject result counts outside the live contract."""
    _record_target_stage(
        step_log,
        target_trace,
        target_index,
        target_count,
        "聚焦搜索框",
        "started",
        "groupName={}".format(group_name),
    )
    try:
        input_rect = _focus_search_input(
            ble,
            step_log,
            "聚焦转发搜索框",
            expected="forward_multi",
        )
    except Exception as exc:
        _record_target_stage(
            step_log,
            target_trace,
            target_index,
            target_count,
            "聚焦搜索框",
            "failed",
            str(exc),
        )
        raise
    _record_target_stage(
        step_log,
        target_trace,
        target_index,
        target_count,
        "聚焦搜索框",
        "focused",
        "rect={}".format(input_rect),
    )

    _record_target_stage(
        step_log,
        target_trace,
        target_index,
        target_count,
        "清空搜索框",
        "started",
        "method=BleDevice.clear",
    )
    _before_action(ble, step_log, "forward_multi", "清空转发搜索框")
    try:
        _hid_clear(
            ble,
            step_log,
            "清空转发搜索框",
            settle_seconds=0.6,
        )
    except Exception as exc:
        _record_target_stage(
            step_log,
            target_trace,
            target_index,
            target_count,
            "清空搜索框",
            "failed",
            str(exc),
        )
        raise
    _record_target_stage(
        step_log,
        target_trace,
        target_index,
        target_count,
        "清空搜索框",
        "clear_sent_waited_0.6s",
    )

    # Selecting a recipient can dismiss the IME and drop editor focus.  Keep
    # the existing clear behavior for this test, then reacquire focus from the
    # live mode-6 editor before typing; if focus is not confirmed, stop here.
    _record_target_stage(
        step_log,
        target_trace,
        target_index,
        target_count,
        "清空后重新聚焦搜索框",
        "started",
        "groupName={}".format(group_name),
    )
    try:
        input_rect = _focus_search_input(
            ble,
            step_log,
            "清空后重新聚焦转发搜索框",
            expected="forward_multi",
        )
    except Exception as exc:
        _record_target_stage(
            step_log,
            target_trace,
            target_index,
            target_count,
            "清空后重新聚焦搜索框",
            "failed_stop_before_input",
            str(exc),
        )
        raise
    _record_target_stage(
        step_log,
        target_trace,
        target_index,
        target_count,
        "清空后重新聚焦搜索框",
        "focused",
        "rect={}".format(input_rect),
    )

    _record_target_stage(
        step_log,
        target_trace,
        target_index,
        target_count,
        "输入真实群名",
        "started",
        "method=AScript.Ime.input groupName={}".format(group_name),
    )
    try:
        _paste(
            ble,
            group_name,
            step_log,
            "按真实群名搜索：{}".format(group_name),
            expected="forward_multi",
            commit_search=False,
        )
    except Exception as exc:
        _record_target_stage(
            step_log,
            target_trace,
            target_index,
            target_count,
            "输入真实群名",
            "failed",
            str(exc),
        )
        raise
    _record_target_stage(
        step_log,
        target_trace,
        target_index,
        target_count,
        "输入真实群名",
        "ime_input_call_returned",
        "groupName={}".format(group_name),
    )

    tree_verified = _wait_for(
        lambda: _search_input_has_value(group_name),
        timeout=3,
        interval=0.25,
    )
    if tree_verified:
        query_source = "mode6_tree"
    else:
        _record_target_stage(
            step_log,
            target_trace,
            target_index,
            target_count,
            "核验搜索框文本",
            "not_found_in_tree",
            "query={}".format(group_name),
        )
        ocr_verified = _wait_for(
            lambda: _search_input_has_value_ocr(group_name),
            timeout=2,
            interval=0.25,
        )
        query_source = "ocr_in_live_input_rect" if ocr_verified else None
    if not query_source:
        _record_target_stage(
            step_log,
            target_trace,
            target_index,
            target_count,
            "核验搜索框文本",
            "unverified_stop",
            "query={} tree=false ocr=false; 不执行结果搜索/完成".format(group_name),
        )
        raise SenderStop(
            "转发搜索框未核验到真实群名，未把目标判为缺失且不会点击完成：{}".format(
                group_name
            ),
            ambiguous=True,
            retryable=False,
        )
    _record_target_stage(
        step_log,
        target_trace,
        target_index,
        target_count,
        "核验搜索框文本",
        "verified",
        "source={} query={}".format(query_source, group_name),
    )

    _record_target_stage(
        step_log,
        target_trace,
        target_index,
        target_count,
        "查找真实群名结果",
        "waiting",
        "timeout=8s",
    )
    matches = _wait_for(
        lambda: _group_search_result_rects(group_name),
        timeout=8,
        interval=0.4,
    ) or []
    _record_target_stage(
        step_log,
        target_trace,
        target_index,
        target_count,
        "查找真实群名结果",
        "results_observed",
        "query_verified=true count={}".format(len(matches)),
    )
    if not matches:
        marker = _explicit_group_missing_message()
        raise SenderStop(
            "搜索框已核验真实群名，但 8 秒内无匹配结果：{}{}".format(
                group_name,
                "（{}）".format(marker) if marker else "",
            ),
            group_not_found=bool(marker),
            skip_target=True,
        )
    expected_match_count = max(1, int(expected_match_count))
    if allowed_match_counts is None:
        accepted_match_counts = (expected_match_count,)
    else:
        accepted_match_counts = tuple(
            sorted({int(count) for count in allowed_match_counts if int(count) > 0})
        )
    live_count_expanded = (
        allow_live_occurrence_expansion
        and len(matches) > expected_match_count
    )
    if len(matches) not in accepted_match_counts and not live_count_expanded:
        raise SenderStop(
            "真实群名结果数与 PC 同名目标数/剩余目标数不一致：groupName={} expected={} allowed={} observed={}".format(
                group_name, expected_match_count, accepted_match_counts, len(matches)
            ),
            ambiguous=True,
        )
    _record_target_stage(
        step_log,
        target_trace,
        target_index,
        target_count,
        "定位真实群名结果",
        "live_count_expanded" if live_count_expanded else "exact_match_set",
        "expected={} allowed={} observed={} rects={}".format(
            expected_match_count, accepted_match_counts, len(matches), matches
        ),
    )
    return matches


def _search_and_open_group(ble, group_name, step_log, group_code=None):
    _return_to_chat_list(ble, step_log)
    _open_search(ble, step_log)
    _focus_search_input(
        ble,
        step_log,
        "聚焦群搜索框",
        expected="search",
    )
    query = str(group_code or group_name).strip()
    _paste(
        ble,
        query,
        step_log,
        "输入群编号" if group_code else "输入真实群名",
        expected="search",
    )
    if not _wait_for(
        lambda: bool(
            _forward_target_rects(group_code, group_name)
            if group_code
            else _group_search_result_rects(group_name)
        ),
        timeout=10,
    ):
        raise SenderStop("搜索不到 PC 记录的群编号或真实群名", group_not_found=True)
    matches = (
        _forward_target_rects(group_code, group_name)
        if group_code
        else _group_search_result_rects(group_name)
    )
    if len(matches) != 1:
        raise SenderStop("目标群匹配不唯一，停止避免误发", ambiguous=True)
    _tap(
        ble,
        matches[0],
        step_log,
        "进入目标群",
        expected="search",
    )
    if not _wait_target_chat(group_name, group_code=group_code, timeout=10):
        raise SenderStop("进入后顶部群名未核验", ambiguous=True)


def _find_input_rect():
    ids = (
        WECHAT_PACKAGE + ":id/aep",
        WECHAT_PACKAGE + ":id/ajw",
        WECHAT_PACKAGE + ":id/search_src_text",
    )
    rect = _find_desc_or_id_rect(ids=ids, top=1500)
    if rect:
        return rect
    rect = _find_editable_rect(top=1400)
    if rect:
        return rect
    for hint in ("输入消息", "说点什么", "搜索"):
        rects = _find_action_text_rect(hint, top=1400)
        if len(rects) == 1:
            return rects[0]
    return None


def _send_text(ble, text, step_log):
    input_rect = _find_input_rect()
    if not input_rect:
        keyboard_rect = _find_desc_or_id_rect(
            descs=("切换到键盘",),
            ids=(WECHAT_PACKAGE + ":id/bpe",),
            top=2000,
        )
        if keyboard_rect:
            _tap(
                ble,
                keyboard_rect,
                step_log,
                "切换到文字键盘",
                expected="chat",
            )
            input_rect = _wait_for(_find_input_rect, timeout=5)
    if not input_rect:
        raise SenderStop("未找到微信聊天输入框")
    _tap(
        ble,
        input_rect,
        step_log,
        "聚焦聊天输入框",
        expected="chat",
    )
    _paste(ble, text, step_log, "粘贴发送文字", expected="chat")
    if not _wait_for(lambda: bool(_find_text_rect(text, top=1450)), timeout=5):
        raise SenderStop("输入框中未核验到待发送文字")
    _send_enter(ble, step_log)
    if not _wait_for(lambda: bool(_find_text_rect(text, top=800)), timeout=8):
        raise SenderStop("发送后未在聊天窗口核验到文字")
    step_log.add(len(step_log.items) + 1, "验证文字气泡", "verified")


def _visible_tree_signature(tree=None):
    """Return a stable signature of visible WeChat text and rectangles."""
    if tree is None:
        tree = _dump()
    visible = []
    for path in _walk(tree):
        item = path[-1]
        if item.get("packageName") != WECHAT_PACKAGE:
            continue
        text = " ".join(str(item.get("text") or "").split())
        rect = _rect(item)
        if text and _valid_rect(rect):
            visible.append((text, rect))
    return tuple(sorted(set(visible))[:400])


def _scroll_chat_to_older(ble, step_log):
    """Swipe toward older chat history and wait for a readable live tree."""
    action_name = "向旧消息方向滑动素材群"
    _before_action(ble, step_log, "material", action_name)
    def history_snapshot():
        tree = _dump()
        signature = _visible_tree_signature(tree)
        region, evidence = _material_chat_history_rect(tree)
        return (signature, region, evidence) if signature and region else None

    # 在同一帧读取标题、输入框、历史区域，允许树在动作后的 0.8 秒轮询中恢复。
    snapshot = _wait_for(
        history_snapshot,
        timeout=CHAT_TREE_WAIT_TIMEOUT_SECONDS,
        interval=CHAT_TREE_POLL_INTERVAL_SECONDS,
    )
    if not snapshot:
        _, gesture_evidence = _material_chat_history_rect()
        step_log.add(
            len(step_log.items) + 1,
            "定位素材群历史列表",
            "stopped_unverified_region",
            gesture_evidence,
        )
        _capture_blocker_screenshot(
            "material_history_scroll_no_region",
            gesture_evidence,
        )
        raise SenderStop(
            "等待后仍无法确认素材群聊天历史区域：{}".format(
                gesture_evidence
            ),
            ambiguous=True,
        )
    before, gesture_rect, gesture_evidence = snapshot
    left, top, right, bottom = gesture_rect
    start_x = int(left + (right - left) * 0.50)
    start_y = int(top + (bottom - top) * 0.35)
    end_y = int(top + (bottom - top) * 0.78)
    width, height = _device_size()
    if not (
        0 <= start_x < width
        and 0 <= start_y < height
        and 0 <= end_y < height
    ):
        raise SenderStop("素材群实时滑动区域超出 HID 范围", ambiguous=True)
    step_log.add(
        len(step_log.items) + 1,
        "素材群历史滑动区域",
        "resolved_from_live_tree",
        gesture_evidence,
    )
    _hid_history_scroll(
        ble,
        start_x,
        start_y,
        start_x,
        end_y,
        step_log,
        action_name,
    )

    last_same_chat = {"signature": None}

    def readable_same_chat():
        tree = _dump()
        if len(_chat_header_rects(MATERIAL_GROUP_NAME, tree)) != 1:
            last_same_chat["signature"] = None
            return None
        after = _visible_tree_signature(tree)
        last_same_chat["signature"] = after or None
        # 刚滑完第一帧可能还是旧树；等待变化或观察窗口耗尽后才判定无进展。
        return after if after and after != before else None

    after = _wait_for(
        readable_same_chat,
        timeout=CHAT_TREE_WAIT_TIMEOUT_SECONDS,
        interval=CHAT_TREE_POLL_INTERVAL_SECONDS,
    )
    after = after or last_same_chat["signature"]
    if not after:
        raise SenderStop(
            "滑动后等待实时微信控件树超时，无法确认素材群页面（{}秒）".format(
                CHAT_TREE_WAIT_TIMEOUT_SECONDS
            ),
            ambiguous=True,
        )
    step_log.add(
        len(step_log.items) + 1,
        "滑动后控件树读取",
        "ready",
        "poll_interval={}s changed={}".format(
            CHAT_TREE_POLL_INTERVAL_SECONDS,
            after != before,
        ),
    )
    return after != before


def _card_marker_rects(card_id):
    """Read the unique card marker for perception only.

    The marker may be a custom-drawn chat bubble, so use the live mode-6 tree
    when it exposes text and OCR as the small perception fallback.  This
    rectangle is never sent to HID as an action target.
    """
    width, height = _device_size()
    tree_rects = []
    try:
        tree = _dump()
    except Exception:
        tree = None
    for path in _walk(tree):
        item = path[-1]
        if item.get("packageName") != WECHAT_PACKAGE or item.get("visible") is False:
            continue
        if str(item.get("text") or "").strip() != str(card_id).strip():
            continue
        rect = _rect(item)
        if _valid_rect(rect) and rect[1] >= 250 and rect[3] <= height - 260:
            tree_rects.append(rect)
    tree_rects = sorted(set(tree_rects))
    if tree_rects:
        return tree_rects
    try:
        items = Ocr.find_all(
            re.escape(str(card_id).strip()),
            rect=[0, 250, width, height - 260],
        ) or []
    except Exception as exc:
        print("CARD_MARKER_OCR_ERROR", str(exc)[:160])
        return []
    matches = []
    for item in items:
        marker = _rect(item)
        if not _valid_rect(marker):
            continue
        matches.append(marker)
    return sorted(set(matches))


def _visible_card_marker_ids():
    """Return card markers currently visible in the chat, for scroll gating."""
    values = set()
    try:
        tree = _dump()
    except Exception:
        tree = None
    for path in _walk(tree):
        item = path[-1]
        if item.get("packageName") != WECHAT_PACKAGE or item.get("visible") is False:
            continue
        value = str(item.get("text") or "").strip()
        if re.match(r"^act-[0-9A-Za-z_-]+$", value):
            values.add(value)
    try:
        items = Ocr.find_all(
            r"act-[0-9A-Za-z_-]+",
            rect=[0, 250, _device_size()[0], _device_size()[1] - 260],
        ) or []
    except Exception:
        return values
    for item in items:
        value = str(item.get("text") or "").strip()
        if re.match(r"^act-[0-9A-Za-z_-]+$", value):
            values.add(value)
    return values


def _card_scroll_budget(card_id, visible_markers):
    """可见 act-100 允许总共最多 100 次；无可见编号时以目标编号为预算。"""
    target_match = re.fullmatch(r"act-(\d+)", str(card_id or "").strip())
    if not target_match:
        return 0
    target_number = int(target_match.group(1))
    visible_numbers = []
    for marker_id in visible_markers or ():
        match = re.fullmatch(r"act-(\d+)", str(marker_id or "").strip())
        if match:
            visible_numbers.append(int(match.group(1)))
    return max([1, target_number] + visible_numbers)


def _locate_card(ble, card_id, card_title, step_log):
    """Resolve the card body from the marker's live tree neighborhood.

    ``cardTitle`` remains a PC-plan field, but it is not an action selector:
    WeChat changes punctuation and truncates card text between builds.  The
    unique marker identifies the message; the mode-6 tree supplies the
    nearby long-clickable card rectangle used by HID.
    """
    if not card_id:
        raise SenderStop("卡片目录缺少编号，无法安全定位现有卡片")
    marker_rects = _wait_for(
        lambda: _card_marker_rects(card_id),
        timeout=5,
        interval=0.4,
    ) or []
    visible_markers = _visible_card_marker_ids()
    print("CARD_MARKER_STATE", card_id, marker_rects, sorted(visible_markers))
    scrolls = 0
    scroll_budget = _card_scroll_budget(card_id, visible_markers)
    while not marker_rects and scrolls < scroll_budget:
        step_log.add(
            len(step_log.items) + 1,
            "扫描素材群卡片编号",
            "not_found_scroll_progress_bounded",
            "target={} visible={} scroll={}/{}".format(
                card_id,
                sorted(visible_markers),
                scrolls,
                scroll_budget,
            ),
        )
        try:
            # Card markers may be omitted by both mode-6 and OCR on a given
            # viewport.  Once the material-chat header is verified, use the
            # live tree-derived content rectangle for a bounded history scan;
            # never gate scrolling on OCR having recognized another act-* ID.
            tree_changed = _scroll_chat_to_older(ble, step_log)
        except SenderStop as exc:
            step_log.add(
                len(step_log.items) + 1,
                "滚动素材群查找卡片",
                "stopped",
                str(exc),
            )
            exc.steps = step_log.items[-40:]
            exc.retryable = False
            raise
        scrolls += 1
        marker_rects = _wait_for(
            lambda: _card_marker_rects(card_id),
            timeout=5,
            interval=0.4,
        ) or []
        visible_markers = _visible_card_marker_ids()
        step_log.add(
            len(step_log.items) + 1,
            "扫描素材群卡片编号",
            "found" if marker_rects else "not_found_after_scroll",
            "target={} matches={} visible={} scroll={}/{}".format(
                card_id,
                len(marker_rects),
                sorted(visible_markers),
                scrolls,
                scroll_budget,
            ),
        )
        print(
            "CARD_MARKER_SCAN",
            card_id,
            "scroll={}/{}".format(scrolls, scroll_budget),
            marker_rects,
            sorted(visible_markers),
        )
        scroll_budget = max(
            scroll_budget,
            _card_scroll_budget(card_id, visible_markers),
        )
        if not marker_rects and not tree_changed:
            step_log.add(
                len(step_log.items) + 1,
                "停止素材群卡片扫描",
                "confirmed_no_scroll_progress",
                "target={} visible={} scroll={}/{}".format(
                    card_id,
                    sorted(visible_markers),
                    scrolls,
                    scroll_budget,
                ),
            )
            exc = SenderStop(
                "控件树已恢复，但素材群滑动后内容未变化；为避免盲滑已停止",
                ambiguous=True,
            )
            exc.steps = step_log.items[-40:]
            exc.retryable = False
            raise exc
    if len(marker_rects) != 1:
        step_log.add(
            len(step_log.items) + 1,
            "定位素材卡片",
            "failed_not_unique",
            "target={} matches={} scrolls={}/{} visible={}".format(
                card_id,
                len(marker_rects),
                scrolls,
                scroll_budget,
                sorted(visible_markers),
            ),
        )
        exc = SenderStop(
            "素材群中未唯一识别卡片编号 {}".format(card_id),
            ambiguous=True,
        )
        exc.steps = step_log.items[-40:]
        exc.retryable = False
        raise exc
    marker = marker_rects[0]
    width, height = _device_size()
    candidates = []
    try:
        tree = _dump()
    except Exception:
        tree = None
    for path in _walk(tree):
        item = path[-1]
        if item.get("packageName") != WECHAT_PACKAGE or item.get("visible") is False:
            continue
        if item.get("clickable") is not True and item.get("longClickable") is not True:
            continue
        rect = _rect(item)
        if not _valid_rect(rect):
            continue
        if rect[1] < marker[3] - 30 or rect[1] - marker[3] > 420:
            continue
        if rect[2] <= marker[0] or rect[0] >= marker[2]:
            continue
        if rect[2] - rect[0] > int(width * 0.95):
            continue
        if rect[3] - rect[1] > int(height * 0.75):
            continue
        if rect[3] - rect[1] < 70:
            continue
        candidates.append((rect, item.get("longClickable") is True))
    long_candidates = sorted(set(rect for rect, is_long in candidates if is_long))
    clickable_candidates = sorted(set(rect for rect, is_long in candidates if not is_long))
    usable = long_candidates or clickable_candidates
    if not usable:
        raise SenderStop(
            "已识别卡片编号，但其下方没有可长按的微信控件树对象",
            ambiguous=True,
        )
    # Nested message containers can expose the same card more than once. Use
    # the nearest vertical band and its largest tree rect; do not use OCR as
    # the action coordinate.
    nearest_distance = min(abs(rect[1] - marker[3]) for rect in usable)
    nearest = [
        rect for rect in usable
        if abs(rect[1] - marker[3]) <= nearest_distance + 35
    ]
    card_rect = max(nearest, key=lambda rect: (rect[2] - rect[0]) * (rect[3] - rect[1]))
    step_log.add(
        len(step_log.items) + 1,
        "定位素材卡片",
        "marker_tree_card_verified",
        "{} marker={} card={}".format(card_id, marker, card_rect),
    )
    return card_rect


def _target_result(
    target,
    status,
    group_not_found=False,
    error="",
    target_index=None,
    requested_count=None,
    stage_trace=None,
):
    result = {
        "candidateId": target.get("candidateId"),
        "candidateIds": list(target.get("candidateIds") or [target.get("candidateId")]),
        "groupCode": target.get("groupCode"),
        "groupName": " ".join(str(target.get("groupName") or "").split()),
        "status": status,
        "groupNotFound": bool(group_not_found),
        "error": str(error or "")[:240],
    }
    if target.get("selectionOccurrence") is not None:
        result["selectionOccurrence"] = int(target["selectionOccurrence"])
    if target_index is not None:
        result["targetIndex"] = int(target_index)
    if requested_count is not None:
        result["requestedTargetCount"] = int(requested_count)
    if stage_trace is not None:
        result["stageTrace"] = [
            dict(item)
            for item in stage_trace[-24:]
            if isinstance(item, dict)
        ]
    return result


def _record_target_stage(
    step_log,
    stage_trace,
    target_index,
    target_count,
    stage,
    state,
    detail="",
):
    event = {
        "stage": str(stage or "")[:80],
        "state": str(state or "")[:80],
    }
    if detail:
        event["detail"] = str(detail)[:240]
    stage_trace.append(event)
    step_log.add(
        len(step_log.items) + 1,
        "目标群 {}/{} {}".format(target_index, target_count, stage),
        state,
        detail,
    )


def _forward_card(ble, card_id, card_title, group_code, targets, text, step_log):
    """Select up to nine real group names, then complete one native forward."""
    if not targets or len(targets) > 9:
        raise SenderStop("一次 PC 任务分组必须包含 1 至 9 个群", ambiguous=True)
    results_by_target = {}
    selected_targets = []

    def target_key(target):
        candidate_id = str(target.get("candidateId") or id(target))
        occurrence = target.get("selectionOccurrence")
        return (
            "{}#{}".format(candidate_id, int(occurrence))
            if occurrence is not None
            else candidate_id
        )

    target_indexes = {
        target_key(target): index
        for index, target in enumerate(targets, 1)
    }
    target_traces = {key: [] for key in target_indexes}
    selected_candidate_keys = set()

    def target_result(target, status, group_not_found=False, error=""):
        key = target_key(target)
        return _target_result(
            target,
            status,
            group_not_found=group_not_found,
            error=error,
            target_index=target_indexes[key],
            requested_count=len(targets),
            stage_trace=target_traces[key],
        )

    def ordered_results(selected_status=None, error=""):
        rows = dict(results_by_target)
        if selected_status:
            for target in selected_targets:
                key = target_key(target)
                if key not in rows:
                    rows[key] = target_result(target, selected_status, error=error)
        return [rows[target_key(target)] for target in targets if target_key(target) in rows]

    def open_native_forward_picker():
        # _run_one has already opened and selected the material chat. Reuse
        # that single chat and picker for every target in this <=9-group chunk.
        _before_action(ble, step_log, "material", "定位素材卡片")
        card_rect = _locate_card(ble, card_id, card_title, step_log)
        _long_press(
            ble,
            card_rect,
            step_log,
            "长按现有小程序卡片",
            expected="material",
        )
        forward_rects = _find_action_text_rect("转发", top=0, bottom=420)
        if len(forward_rects) != 1:
            raise SenderStop(
                "长按后未唯一找到微信原生转发入口",
                ambiguous=True,
            )
        _tap(
            ble,
            forward_rects[0],
            step_log,
            "进入微信原生转发",
            expected="card_menu",
        )

        def native_forward_multi_rect():
            rects = _find_action_text_rect("多选", top=0, bottom=420)
            return rects if len(rects) == 1 else None

        multi_rects = _wait_for(native_forward_multi_rect, timeout=8, interval=0.4)
        if not multi_rects:
            raise SenderStop("转发页未唯一找到多选入口", ambiguous=True)
        _tap(
            ble,
            multi_rects[0],
            step_log,
            "打开转发目标列表",
            expected="forward_page",
        )

    open_native_forward_picker()
    initial_multi_state = _native_forward_multi_state()
    if initial_multi_state["selected_count"] != 0:
        raise SenderStop(
            "进入原生多选后无法确认初始已选群数为 0",
            ambiguous=True,
            target_results=ordered_results("selected_not_sent"),
        )
    step_log.add(
        len(step_log.items) + 1,
        "确认原生多选初始状态",
        "selection_count_verified",
        "selected=0 source={}".format(initial_multi_state["count_source"]),
    )

    for target_index, target in enumerate(targets, 1):
        key = target_key(target)
        target_trace = target_traces[key]
        group_name = " ".join(str(target.get("groupName") or "").split())
        if key in selected_candidate_keys or key in results_by_target:
            continue
        _record_target_stage(
            step_log,
            target_trace,
            target_index,
            len(targets),
            "收到 PC 目标",
            "received",
            "candidateId={} groupName={} groupCode={} groupIdentity={}".format(
                target.get("candidateId"),
                group_name,
                group_code,
                target.get("groupIdentity") or "none",
            ),
        )
        step_log.add(
            len(step_log.items) + 1,
            "开始搜索第 {}/{} 个转发目标群".format(target_index, len(targets)),
            "target_search_started",
            "groupName={} groupCode={}".format(group_name, group_code),
        )
        if not group_name:
            _record_target_stage(
                step_log,
                target_trace,
                target_index,
                len(targets),
                "校验真实群名",
                "missing_stop",
            )
            results_by_target[key] = target_result(
                target,
                "target_name_missing",
                error="PC 任务没有提供真实群名",
            )
            exc = SenderStop(
                "转发任务目标缺少真实群名，停止避免误发",
                ambiguous=True,
            )
            exc.target_results = ordered_results("selected_not_sent", str(exc))
            raise exc
        selection_attempted = False
        active_target = target
        active_key = key
        active_index = target_index
        active_trace = target_trace
        try:
            same_name_targets = [
                candidate
                for candidate in targets
                if " ".join(str(candidate.get("groupName") or "").split()) == group_name
                and target_key(candidate) not in selected_candidate_keys
                and target_key(candidate) not in results_by_target
            ]
            same_name_count = len(same_name_targets)
            for duplicate_index, selected_target in enumerate(same_name_targets, 1):
                selected_key = target_key(selected_target)
                selected_index = target_indexes[selected_key]
                selected_trace = target_traces[selected_key]
                active_target = selected_target
                active_key = selected_key
                active_index = selected_index
                active_trace = selected_trace

                # Selecting a same-name recipient can dismiss search focus or
                # change the result list. Re-focus and search the exact group
                # name again for every distinct PC candidate before resolving
                # its tap rectangle from a fresh mode-6 tree.
                allowed_match_counts = _same_name_result_count_options(
                    duplicate_index, same_name_count
                )
                try:
                    match_rects = _search_forward_group_by_name(
                        ble,
                        group_name,
                        step_log,
                        selected_trace,
                        selected_index,
                        len(targets),
                        expected_match_count=same_name_count,
                        allowed_match_counts=allowed_match_counts,
                        # In a bounded c-code test, exact live search rows are
                        # the best available count when PC has a stale/low
                        # occurrenceCount. Production remains fail-closed.
                        allow_live_occurrence_expansion=(
                            TEST_MODE in {"TEST_SINGLE", "TEST_ONLY"}
                            and str(group_code or "").strip().lower().startswith("c")
                        ),
                    )
                except SenderStop as search_exc:
                    if (
                        (search_exc.group_not_found or search_exc.skip_target)
                        and not search_exc.ambiguous
                        and not search_exc.send_attempted
                    ):
                        target_status = (
                            "group_not_found"
                            if search_exc.group_not_found
                            else "search_no_results"
                        )
                        results_by_target[selected_key] = target_result(
                            selected_target,
                            target_status,
                            group_not_found=search_exc.group_not_found,
                            error=str(search_exc),
                        )
                        step_log.add(
                            len(step_log.items) + 1,
                            "记录目标群搜索结果",
                            target_status,
                            "target={}/{} candidateId={} groupName={} duplicateIndex={}".format(
                                selected_index,
                                len(targets),
                                selected_key,
                                group_name,
                                duplicate_index,
                            ),
                        )
                        continue
                    raise

                if len(match_rects) > same_name_count:
                    added_targets = _expand_same_name_targets_to_observed_count(
                        same_name_targets,
                        group_name,
                        len(match_rects),
                    )
                    if added_targets:
                        # WeChat permits at most nine recipients in this one
                        # native picker. Do not partly select a group bundle
                        # that cannot fit; stop before tapping any new row.
                        if len(targets) + len(added_targets) > 9:
                            raise SenderStop(
                                "实时同名群数高于 PC 计数，扩展后超过单次九群上限；未点击新增结果：groupName={} pcTargets={} liveRows={}".format(
                                    group_name, len(targets), len(match_rects)
                                ),
                                ambiguous=True,
                            )
                        for added_target in added_targets:
                            added_key = target_key(added_target)
                            if added_key in target_indexes:
                                raise SenderStop(
                                    "实时同名群扩展生成重复选择键，停止避免重复点选：{}".format(
                                        added_key
                                    ),
                                    ambiguous=True,
                                )
                            targets.append(added_target)
                            target_indexes[added_key] = len(targets)
                            target_traces[added_key] = []
                            same_name_targets.append(added_target)
                        same_name_count = len(same_name_targets)
                        _record_target_stage(
                            step_log,
                            selected_trace,
                            selected_index,
                            len(targets),
                            "校正 PC 同名群数量",
                            "expanded_to_live_exact_rows",
                            "pcOccurrenceCount={} liveExactRows={} added={}；仅用于 c 编号测试".format(
                                same_name_count - len(added_targets),
                                len(match_rects),
                                len(added_targets),
                            ),
                        )

                step_log.add(
                    len(step_log.items) + 1,
                    "重新搜索并匹配真实微信群名结果集",
                    "live_tree_match_set",
                    "groupName={} candidateId={} duplicateIndex={}/{} allowedCounts={} resultRects={}".format(
                        group_name,
                        selected_key,
                        duplicate_index,
                        same_name_count,
                        allowed_match_counts,
                        match_rects,
                    ),
                )
                # Re-read after each search too; never tap the rectangles
                # returned by an earlier candidate's result snapshot.
                current_rect = _current_duplicate_result_rect(
                    group_name,
                    duplicate_index,
                    same_name_count,
                )
                before_state = _native_forward_multi_state()
                if before_state["selected_count"] != len(selected_targets):
                    raise SenderStop(
                        "搜索目标前原生多选计数与已确认选择数不一致：{} != {}".format(
                            before_state["selected_count"], len(selected_targets)
                        ),
                        ambiguous=True,
                    )
                expected_selected_count = len(selected_targets) + 1
                _record_target_stage(
                    step_log,
                    selected_trace,
                    selected_index,
                    len(targets),
                    "读取点击前已选群数",
                    "verified",
                    "selected={} source={}".format(
                        before_state["selected_count"], before_state["count_source"]
                    ),
                )
                selection_attempted = True
                _tap(
                    ble,
                    current_rect,
                    step_log,
                    "点击真实群名目标：{}（同名第{}项）".format(
                        group_name, duplicate_index
                    ),
                    expected="forward_multi",
                )
                _record_target_stage(
                    step_log,
                    selected_trace,
                    selected_index,
                    len(targets),
                    "点击匹配群名",
                    "hid_action_sent",
                    "duplicateIndex={} rect={}".format(duplicate_index, current_rect),
                )

                def selected_count_incremented():
                    state = _native_forward_multi_state()
                    return state if state["selected_count"] == expected_selected_count else None

                after_state = _wait_for(
                    selected_count_incremented,
                    timeout=5,
                    interval=0.4,
                )
                if not after_state:
                    results_by_target[selected_key] = target_result(
                        selected_target,
                        "selection_unconfirmed",
                        error="完成计数未按同名目标逐个递增",
                    )
                    raise SenderStop(
                        "点击第 {}/{} 个同名目标后，完成计数未从 {} 增至 {}：{}".format(
                            selected_index,
                            len(targets),
                            len(selected_targets),
                            expected_selected_count,
                            group_name,
                        ),
                        ambiguous=True,
                    )
                selected_targets.append(selected_target)
                selected_candidate_keys.add(selected_key)
                _record_target_stage(
                    step_log,
                    selected_trace,
                    selected_index,
                    len(targets),
                    "核验点选后已选群数",
                    "incremented",
                    "selected={} source={}".format(
                        after_state["selected_count"], after_state["count_source"]
                    ),
                )
                step_log.add(
                    len(step_log.items) + 1,
                    "确认选择第 {}/{} 个原生转发目标".format(selected_index, len(targets)),
                    "recipient_selected_verified",
                    "candidateId={} groupName={} sameNameIndex={} selected={}".format(
                        selected_key,
                        group_name,
                        duplicate_index,
                        after_state["selected_count"],
                    ),
                )
        except SenderStop as exc:
            query_unverified = any(
                event.get("stage") == "核验搜索框文本"
                and event.get("state") == "unverified_stop"
                for event in active_trace
            )
            if active_key not in results_by_target:
                _record_target_stage(
                    step_log,
                    active_trace,
                    active_index,
                    len(targets),
                    "目标处理结果",
                    "stopped",
                    str(exc),
                )
                results_by_target[active_key] = target_result(
                    active_target,
                    "search_input_unverified"
                    if query_unverified
                    else "selection_unconfirmed"
                    if selection_attempted
                    else "search_unconfirmed",
                    error=str(exc),
                )
            exc.target_results = ordered_results("selected_not_sent", str(exc))
            raise

    if not selected_targets:
        return ordered_results()

    if TEST_MODE == "TEST_ONLY" and len(selected_targets) != len(targets):
        selected_keys = {target_key(target) for target in selected_targets}
        missing_targets = [
            target
            for target in targets
            if target_key(target) not in selected_keys
        ]
        uncertain_targets = [
            target
            for target in missing_targets
            if not _is_explicit_missing_target_status(
                (results_by_target.get(target_key(target)) or {}).get("status")
            )
        ]
        missing_labels = [
            "{} ({})".format(
                str(target.get("groupName") or ""),
                str(target.get("candidateId") or ""),
            )
            for target in missing_targets
        ]
        if uncertain_targets:
            # A failed focus, ambiguous row, or unconfirmed selection is not a
            # legitimate missing-group result; never press 完成 in that state.
            step_log.add(
                len(step_log.items) + 1,
                "TEST_ONLY 目标选择状态保护",
                "test_only_selection_uncertain_stop",
                "requested={} selected={} unresolved={}".format(
                    len(targets), len(selected_targets), missing_labels
                ),
            )
            raise SenderStop(
                "TEST_ONLY 有目标未选中且原因不是已确认的群缺失/无结果，停止点击完成：{}".format(
                    missing_labels
                ),
                target_results=ordered_results("selected_not_sent"),
            )
        # A kicked/absent target is an auditable recipient outcome, not a
        # reason to discard other groups that were successfully selected.
        step_log.add(
            len(step_log.items) + 1,
            "记录明确缺失目标并继续已选群",
            "explicit_missing_targets_continue",
            "requested={} selected={} missing={}".format(
                len(targets), len(selected_targets), missing_labels
            ),
        )

    final_multi_state = _native_forward_multi_state()
    if final_multi_state["selected_count"] != len(selected_targets):
        raise SenderStop(
            "点击完成前多选计数与已确认目标数不一致：{} != {}".format(
                final_multi_state["selected_count"], len(selected_targets)
            ),
            ambiguous=True,
            target_results=ordered_results("selected_not_sent"),
        )
    step_log.add(
        len(step_log.items) + 1,
        "汇总本次原生转发目标",
        "target_selection_summary",
        "requested={} selected={} missing={} countSource={}".format(
            len(targets),
            len(selected_targets),
            len(targets) - len(selected_targets),
            final_multi_state["count_source"],
        ),
    )

    complete_rects = final_multi_state["rects"]
    if len(complete_rects) != 1:
        raise SenderStop(
            "已选择 {} 个目标，但 mode=6 树未唯一定位原生转发‘完成’按钮：候选数={}".format(
                len(selected_targets), len(complete_rects)
            ),
            ambiguous=True,
            target_results=ordered_results("selected_not_sent"),
        )
    for target in selected_targets:
        _record_target_stage(
            step_log,
            target_traces[target_key(target)],
            target_indexes[target_key(target)],
            len(targets),
            "确认已选目标并点击完成",
            "started",
            "selected={} rect={}".format(len(selected_targets), complete_rects[0]),
        )
    _tap(
        ble,
        complete_rects[0],
        step_log,
        "确认本次已选择的转发群",
        expected="forward_multi",
    )
    for target in selected_targets:
        _record_target_stage(
            step_log,
            target_traces[target_key(target)],
            target_indexes[target_key(target)],
            len(targets),
            "确认已选目标并点击完成",
            "hid_action_sent",
            "selected={}".format(len(selected_targets)),
        )

    if text:
        input_rect = _find_input_rect()
        if not input_rect:
            raise SenderStop(
                "转发确认页未找到附加文字输入框",
                ambiguous=True,
                target_results=ordered_results("selected_not_sent"),
            )
        _tap(
            ble,
            input_rect,
            step_log,
            "聚焦转发附加文字",
            expected="forward_preview",
        )
        _paste(
            ble,
            text,
            step_log,
            "填写转发附加文字",
            expected="forward_preview",
        )
        if not _wait_for(lambda: bool(_find_text_rect(text, top=1450)), timeout=5):
            raise SenderStop(
                "转发确认页未核验到附加文字",
                ambiguous=True,
                target_results=ordered_results("selected_not_sent"),
            )

    send_rects = _find_action_text_rect("发送", top=1700)
    if not send_rects:
        # The preview's primary action is occasionally missing from mode=6;
        # use OCR's exact label only as a bounded coordinate fallback.
        send_rects = _find_text_rect("发送", top=1700)
    if len(send_rects) > 1:
        cancel_rects = _find_action_text_rect("取消", top=1700)
        if not cancel_rects:
            cancel_rects = _find_text_rect("取消", top=1700)
        if len(cancel_rects) == 1:
            cancel = cancel_rects[0]
            cancel_center_y = (cancel[1] + cancel[3]) / 2.0
            row_tolerance = max(60, cancel[3] - cancel[1])
            same_action_row = [
                rect for rect in send_rects
                if rect[0] >= cancel[2] - 20
                and abs((rect[1] + rect[3]) / 2.0 - cancel_center_y) <= row_tolerance
            ]
            if len(same_action_row) == 1:
                send_rects = same_action_row
                step_log.add(
                    len(step_log.items) + 1,
                    "区分转发预览中的发送按钮",
                    "send_button_disambiguated",
                    "paired_with_cancel rect={}".format(send_rects[0]),
                )
    if len(send_rects) != 1:
        raise SenderStop(
            "转发确认页未唯一找到发送按钮",
            ambiguous=True,
            target_results=ordered_results("selected_not_sent"),
        )
    try:
        _tap(
            ble,
            send_rects[0],
            step_log,
            "发送小程序卡片和文字到已选择目标群",
            expected="forward_preview",
        )
    except SenderStop as exc:
        exc.send_attempted = True
        for target in selected_targets:
            _record_target_stage(
                step_log,
                target_traces[target_key(target)],
                target_indexes[target_key(target)],
                len(targets),
                "发送卡片和文字",
                "unconfirmed",
                str(exc),
            )
        exc.target_results = ordered_results("send_unconfirmed", str(exc))
        raise

    # A kicked/removed group can remain visible in WeChat's native recipient
    # picker. In that case the send button is accepted, but WeChat shows a
    # post-send error such as “无法在已退出的群聊中发送消息！”. Read the live
    # error before recording any recipient as send_action_sent_unverified.
    missing_marker = _wait_for(
        _explicit_group_missing_message,
        timeout=2.5,
        interval=0.25,
    )
    if missing_marker:
        if len(selected_targets) != 1:
            # With a multi-recipient native send the UI does not identify
            # which selected row produced the error. Stop without marking all
            # rows removed; doing so would destroy valid recipients.
            detail = "{}；本次包含 {} 个目标，无法安全归属".format(
                missing_marker,
                len(selected_targets),
            )
            for target in selected_targets:
                key = target_key(target)
                results_by_target[key] = target_result(
                    target,
                    "send_error_unattributed",
                    error=detail,
                )
            step_log.add(
                len(step_log.items) + 1,
                "记录转发后微信群错误",
                "send_error_unattributed",
                detail,
            )
            raise SenderStop(
                "转发后微信明确报告目标群不可发送，但无法从多目标结果归属具体群：{}".format(
                    missing_marker
                ),
                ambiguous=True,
                target_results=ordered_results(),
                send_attempted=True,
                retryable=False,
            )
        target = selected_targets[0]
        key = target_key(target)
        results_by_target[key] = target_result(
            target,
            "group_not_found",
            group_not_found=True,
            error=missing_marker,
        )
        _record_target_stage(
            step_log,
            target_traces[key],
            target_indexes[key],
            len(targets),
            "发送卡片和文字",
            "group_not_found",
            missing_marker,
        )
        step_log.add(
            len(step_log.items) + 1,
            "记录转发后微信群错误",
            "group_not_found",
            missing_marker,
        )
        raise SenderStop(
            "转发后微信明确报告目标群已退出：{}".format(missing_marker),
            group_not_found=True,
            target_results=ordered_results("selected_not_sent"),
            send_attempted=True,
            retryable=False,
        )

    for target in selected_targets:
        key = target_key(target)
        _record_target_stage(
            step_log,
            target_traces[key],
            target_indexes[key],
            len(targets),
            "发送卡片和文字",
            "hid_action_sent_unverified",
            "UI/后端送达尚未核验",
        )
        results_by_target[key] = target_result(
            target,
            "send_action_sent_unverified",
        )
    step_log.add(
        len(step_log.items) + 1,
        "记录转发发送动作",
        "hid_action_sent_unverified",
        "selectedTargets={} uiDeliveryNotChecked=true".format(len(selected_targets)),
    )
    return ordered_results()


def _validate_task(task):
    if not task:
        return None
    if task.get("functionId") != GROUP_BATCH_FUNCTION_ID:
        raise RuntimeError("领取到非群编号批次任务，已拒绝执行")
    payload = task.get("payload") or {}
    required = ("groupCode", "batchNo", "cardId", "cardTitle")
    missing = [key for key in required if not str(payload.get(key) or "").strip()]
    if missing:
        raise RuntimeError("发送任务缺少字段：" + "、".join(missing))
    targets = payload.get("targets")
    if not isinstance(targets, list) or not targets:
        legacy_target = {
            "candidateId": payload.get("candidateId"),
            "groupCode": payload.get("groupCode"),
            "groupName": payload.get("groupName"),
            "targetWechatAccountId": payload.get("targetWechatAccountId"),
            "targetWechatAccountName": payload.get("targetWechatAccountName"),
        }
        targets = [legacy_target] if legacy_target.get("candidateId") and legacy_target.get("groupName") else []
    if not targets:
        raise RuntimeError("发送任务没有真实目标群")
    normalized_targets = []
    logical_candidate_ids = set()
    for target in targets:
        if not isinstance(target, dict):
            raise RuntimeError("发送任务目标群格式无效")
        missing_target = [
            key for key in ("candidateId", "groupName")
            if not str(target.get(key) or "").strip()
        ]
        if missing_target:
            raise RuntimeError("发送任务目标群缺少字段：" + "、".join(missing_target))
        if target.get("groupCode") and str(target.get("groupCode")).strip() != str(payload.get("groupCode")).strip():
            raise RuntimeError("发送任务目标群编号不一致")
        group_identity = str(target.get("groupIdentity") or "").strip().lower()
        if group_identity and not re.fullmatch(r"[0-9a-f]{64}", group_identity):
            raise RuntimeError("发送任务群身份指纹格式无效")
        candidate_id = str(target.get("candidateId") or "").strip()
        raw_candidate_ids = target.get("candidateIds")
        if not isinstance(raw_candidate_ids, list):
            raw_candidate_ids = [candidate_id]
        candidate_ids = list(dict.fromkeys(
            str(value or "").strip()
            for value in raw_candidate_ids
            if str(value or "").strip()
        ))
        if not candidate_ids or candidate_id not in candidate_ids:
            raise RuntimeError("发送任务群目标包缺少有效候选 ID")
        if logical_candidate_ids.intersection(candidate_ids):
            raise RuntimeError("发送任务含重复候选 ID：多个目标包重复引用同一候选 ID")
        logical_candidate_ids.update(candidate_ids)
        try:
            occurrence_count = int(target.get("groupOccurrenceCount") or 1)
        except (TypeError, ValueError):
            raise RuntimeError("发送任务群目标重复数量无效")
        if occurrence_count < 1 or occurrence_count > 10000:
            raise RuntimeError("发送任务群目标重复数量超出安全范围")
        # Expand one account/code/name route into one selection row per
        # observed WeChat result. Every occurrence will use a fresh live tree
        # rectangle and a verified 完成(n) increment; no row coordinate is
        # retained between occurrences.
        for occurrence in range(1, occurrence_count + 1):
            expanded = dict(target)
            expanded["candidateIds"] = candidate_ids
            expanded["groupOccurrenceCount"] = occurrence_count
            expanded["selectionOccurrence"] = occurrence
            normalized_targets.append(expanded)
    payload = dict(payload)
    payload["targets"] = normalized_targets
    task_account_id = str(task.get("targetWechatAccountId") or "").strip()
    if not task_account_id:
        raise RuntimeError("发送任务外层缺少目标微信账号 ID")
    payload["targetWechatAccountId"] = task_account_id
    if not payload.get("targetWechatAccountName") and normalized_targets:
        payload["targetWechatAccountName"] = normalized_targets[0].get(
            "targetWechatAccountName"
        )
    if TEST_MODE == "TEST_ONLY":
        if task_account_id != ACTIVE_WECHAT_ACCOUNT_ID:
            raise RuntimeError("TEST_ONLY 任务账号与当前微信账号槽位不一致")
        # Do not compare recipient names/IDs to a local list: the exact test
        # code bounds the request, and PC eligibility determines its targets.
        if not normalized_targets or len(normalized_targets) > 1000:
            raise RuntimeError("TEST_ONLY 任务目标数量无效")
    if TEST_MODE in {"TEST_SINGLE", "TEST_ONLY"}:
        if not TEST_GROUP_CODE:
            raise RuntimeError("单次测试未配置 TEST_GROUP_CODE")
        if str(payload.get("groupCode") or "").strip() != TEST_GROUP_CODE:
            raise RuntimeError("单次测试任务群编号与 TEST_GROUP_CODE 不一致")
    try:
        if int(payload.get("batchNo")) < 1:
            raise ValueError
    except (TypeError, ValueError):
        raise RuntimeError("发送任务批次号无效")
    return payload


def _result(status, step_log=None, **extra):
    data = {
        "deviceId": DEVICE_ID,
        "functionId": GROUP_BATCH_FUNCTION_ID,
        "status": status,
        "source": "wechat.marketing_sender",
        "inputMode": INPUT_MODE,
    }
    if step_log is not None:
        data["steps"] = step_log.items[-40:]
    data.update(extra)
    return data


def _forward_outcome_counts(target_results):
    """Count recipient outcomes without folding navigation cleanup into sends."""
    confirmed_count = 0
    action_sent_count = 0
    target_failure_count = 0
    for target in target_results or []:
        if not isinstance(target, dict):
            target_failure_count += 1
            continue
        status = str(target.get("status") or "").strip()
        if status == "sent_ui_confirmed":
            confirmed_count += 1
        elif status == "send_action_sent_unverified":
            action_sent_count += 1
        else:
            # A missing/failed recipient is a target outcome; a later failure
            # to return to the chat list is a workflow warning, not a send miss.
            target_failure_count += 1
    return confirmed_count, action_sent_count, target_failure_count


def _is_explicit_missing_target_status(status):
    """Only confirmed missing/no-result outcomes may be skipped in a multi-send.

    Search-focus, selection, and page-state failures are not evidence that a
    group is absent; those remain hard stops before the native 完成 action.
    """
    return str(status or "").strip() in {"group_not_found", "search_no_results"}


def _run_one(task, ble):
    step_log = StepLog()
    payload = _validate_task(task)
    step_log.add(1, "校验 PC 任务", "validated", payload.get("groupCode"))
    step_log.add(
        2,
        "读取 PC 批次映射",
        "resolved",
        "batch={} card={} targets={} names={} text={}".format(
            payload.get("batchNo"),
            payload.get("cardId"),
            len(payload.get("targets") or []),
            [target.get("groupName") for target in payload.get("targets") or []],
            bool(str(payload.get("text") or "").strip()),
        ),
    )
    _ensure_wechat(ble, payload, step_log)
    _select_account_if_needed(ble, payload, step_log)
    time.sleep(1.2)
    # The required order is: open WeChat -> click the live “我” tab -> read
    # the real WeChat ID -> click the live “微信” tab back to chat home.
    # Search/results pages use the separate bounded right-swipe path.
    if _reuse_scanned_account():
        # The scanner has just verified the real WeChat ID and returned to the
        # chat home. Reopening “我” here only repeats navigation and can make
        # the mode-6 tree lose the home/list rectangle before material lookup.
        step_log.add(
            len(step_log.items) + 1,
            "复用扫描阶段已核验的微信账号",
            "verified",
            str(payload.get("targetWechatAccountId") or "").strip(),
        )
    else:
        _verify_active_wechat_account(ble, payload, step_log)
    targets = payload["targets"]
    card_id = str(payload.get("cardId") or "").strip()
    card_title = str(payload.get("cardTitle") or "").strip()
    text = str(payload.get("text") or "").strip()
    print("SEND_CARD_REQUEST", card_id, card_title)
    if not _send_mode_enabled():
        # Never report an unattempted send as a completed task.  Keep the
        # runtime safety gate, but fail visibly before opening the material
        # chat so the operator can fix TEST_MODE instead of seeing a silent
        # scan-only run.
        raise SenderStop(
            "已领取群发任务，但 TEST_MODE 未启用 TEST_SINGLE/TEST_ONLY；"
            "为保护真实发送，已停止，尚未搜索卡片素材群",
            retryable=False,
            stage="send_safety_gate",
        )
    target_results = []
    # WeChat's native multi-select forward page accepts at most nine target
    # groups per confirmation.  Keep the PC-resolved target order and split
    # only at that native limit.
    chunk_size = 9
    need_material_chat = True
    for offset in range(0, len(targets), chunk_size):
        chunk = targets[offset:offset + chunk_size]
        if need_material_chat:
            _open_material_chat_first(
                ble,
                step_log,
                home_already_confirmed=(offset == 0),
            )
            need_material_chat = False
        elif _wait_for(
            lambda: not _search_input_rect() and _header_has(MATERIAL_GROUP_NAME),
            timeout=2,
            interval=0.4,
        ):
            step_log.add(
                len(step_log.items) + 1,
                "复用卡片素材群继续下一组",
                "verified",
                "chunk_start={} strategy=long_press_same_card".format(offset + 1),
            )
        else:
            # Normal WeChat send returns to the source material chat. Reuse it
            # for the next <=9 group chunk; navigate back through search only
            # if the live title/input tree proves that the source chat is gone.
            step_log.add(
                len(step_log.items) + 1,
                "后续分组复用素材群检查",
                "material_chat_not_current",
                "chunk_start={}；仅在来源聊天已离开时重新定位".format(offset + 1),
            )
            _open_material_chat_first(ble, step_log)
        try:
            forwarded_results = _forward_card(
                ble,
                card_id,
                card_title,
                str(payload["groupCode"]).strip(),
                chunk,
                text,
                step_log,
            )
            target_results.extend(forwarded_results)
        except SenderStop as exc:
            # Preserve the actual UI/gesture trace for the account-level
            # launcher error.  Without this, a card-location failure is
            # reduced to only slot/account and cannot show whether a swipe
            # was sent before the stop.
            if not getattr(exc, "steps", None):
                exc.steps = step_log.items[-40:]
            target_results.extend(exc.target_results)
            if not exc.group_not_found or exc.ambiguous:
                raise
            # A confirmed missing target is recorded and later chunks may
            # continue, but only after one bounded home reset. The next chunk
            # then opens the material chat once; successful chunks do not.
            try:
                _reset_to_wechat_home(ble, step_log, "目标群未找到后")
            except SenderStop as cleanup_exc:
                combined = SenderStop(
                    "{}；目标未找到后的页面复位也失败：{}".format(
                        str(exc),
                        str(cleanup_exc),
                    ),
                    group_not_found=exc.group_not_found,
                    ambiguous=True,
                    target_results=target_results,
                    send_attempted=exc.send_attempted,
                    retryable=False,
                )
                combined.steps = step_log.items[-40:]
                raise combined
            need_material_chat = True
            continue
        if offset + chunk_size < len(targets):
            # Let WeChat settle in the source chat before long-pressing the
            # same card again for the next native <=9-recipient selection.
            time.sleep(1.2)
    sent_action_exists = any(
        item.get("status") in {"sent_ui_confirmed", "send_action_sent_unverified"}
        for item in target_results
        if isinstance(item, dict)
    )
    try:
        if sent_action_exists:
            _reset_after_card_forward(ble, step_log)
        else:
            _reset_to_wechat_home(ble, step_log, "微信账号任务完成后")
    except SenderStop as exc:
        # The recipient actions have already been attempted. Preserve them in
        # the batch report and classify the page reset as workflow cleanup,
        # never as another failed recipient or a reason to resend.
        raise SenderStop(
            str(exc),
            ambiguous=True,
            target_results=target_results,
            send_attempted=bool(target_results),
            retryable=False,
            stage="post_send_cleanup",
        )
    sent_count = sum(1 for item in target_results if item.get("status") == "sent_ui_confirmed")
    action_sent_count = sum(
        1 for item in target_results
        if item.get("status") == "send_action_sent_unverified"
    )
    missing_count = sum(1 for item in target_results if item.get("groupNotFound") is True)
    search_miss_count = sum(
        1 for item in target_results if item.get("status") == "search_no_results"
    )
    if sent_count and not missing_count and not search_miss_count and not action_sent_count:
        status = "success"
    elif sent_count or (action_sent_count and (missing_count or search_miss_count)):
        status = "partial"
    elif action_sent_count:
        status = "send_action_unverified"
    elif search_miss_count:
        status = "search_no_results"
    else:
        status = "group_not_found"
    return _result(
        status,
        step_log,
        groupCode=payload.get("groupCode"),
        batchNo=payload.get("batchNo"),
        cardId=card_id or None,
        targetCount=len(targets),
        sentCount=sent_count,
        sendActionCount=action_sent_count,
        missingCount=missing_count,
        searchNoResultsCount=search_miss_count,
        targetResults=target_results,
        textIncluded=bool(text),
        cardForwarded=True,
        uiVerified=sent_count > 0,
        targetWechatAccountId=str(task.get("targetWechatAccountId") or "").strip() or None,
    )


def _run_one_with_recovery(task, ble):
    """Run one account task with two safe, home-reset retries.

    Retries are only for UI failures before any send attempt.  A failure after
    tapping the native send button is terminal for this task to prevent a
    duplicate message.
    """
    last_exc = None
    for attempt in range(1, MAX_ACCOUNT_FLOW_ATTEMPTS + 1):
        if attempt > 1:
            if last_exc is None or last_exc.send_attempted or last_exc.target_results:
                raise last_exc
            reset_log = StepLog()
            _reset_to_wechat_home(
                ble,
                reset_log,
                "第{}次账号流程尝试前复位".format(attempt),
            )
            _heartbeat()
            print(
                "TASK_RETRY",
                task.get("id"),
                "attempt={}".format(attempt),
                str(last_exc),
            )
        try:
            result = _run_one(task, ble)
            if attempt > 1:
                print("TASK_RETRY_SUCCEEDED", task.get("id"), "attempt={}".format(attempt))
            return result
        except SenderStop as exc:
            if (
                exc.send_attempted
                or exc.target_results
                or not exc.retryable
                or attempt >= MAX_ACCOUNT_FLOW_ATTEMPTS
            ):
                raise
            last_exc = exc
            print(
                "TASK_ATTEMPT_FAILED",
                task.get("id"),
                "attempt={}".format(attempt),
                "retryable_before_send",
                str(exc),
            )
    raise last_exc


def _queue_empty_reason(queued):
    """Classify a zero-task response without hiding queue creation defects."""
    try:
        target_count = int(queued.get("targetCount") or 0)
        skipped_count = int(queued.get("skippedCount") or 0)
    except (AttributeError, TypeError, ValueError):
        return {
            "status": "failed",
            "reason": "PC 未返回有效的目标/跳过计数",
        }
    if target_count < 0 or skipped_count < 0:
        return {
            "status": "failed",
            "reason": "PC 返回了负数的目标/跳过计数",
        }
    if target_count:
        return {
            "status": "failed",
            "reason": "PC 报告仍有 {} 个可发送目标，但没有创建任何发送任务".format(
                target_count,
            ),
        }
    if skipped_count:
        return {
            "status": "idle",
            "reason": "当前账号没有可发送目标；PC 跳过了 {} 项，详见 QUEUE_SKIPPED".format(
                skipped_count,
            ),
        }
    return {
        "status": "idle",
        "reason": "当前微信账号本批次没有可发送目标",
    }


def _run_queue(ble):
    processed = 0
    summary = {
        "processed": 0,
        "success": 0,
        "partial": 0,
        "failed": 0,
        "missingGroups": 0,
        "idle": False,
        "batchNo": _selected_batch_no(),
        "forwardDurationSeconds": None,
        "forwardSuccessCount": 0,
        "forwardActionSentCount": 0,
        "forwardUnconfirmedCount": 0,
        "forwardFailureCount": 0,
        "workflowFailureCount": 0,
        "cleanupFailureCount": 0,
        "lastErrorStage": "",
        "targetResults": [],
    }
    account_ids = _configured_account_ids()
    if not account_ids:
        raise RuntimeError("未配置可执行的微信账号 ID")
    _validate_test_configuration(account_ids)
    if not _send_mode_enabled():
        # Keep production in dry-run before the queue endpoint is called. A
        # task created before this gate could be claimed by this device and
        # would also leave misleading pending/failed rows in the outbox.
        reason = "生产发送未启用 TEST_SINGLE/TEST_ONLY，已保持 dry-run"
        print("SEND_SAFETY_GATE", reason)
        summary.update({
            "status": "degraded",
            "lastErrorStage": "send_safety_gate",
            "queue": {
                "runId": None,
                "groupCodes": [],
                "createdCount": 0,
                "targetCount": 0,
                "skippedCount": 0,
                "skippedItems": [],
                "reason": "production_send_disabled",
                "workflowFailureCount": 0,
            },
        })
        return summary
    _heartbeat()
    queued = _request_device_batch_run(account_ids, summary["batchNo"])
    try:
        created_count = int(queued.get("createdCount") or 0)
    except (AttributeError, TypeError, ValueError):
        raise RuntimeError("PC 群发队列 createdCount 无效")
    if created_count < 0:
        raise RuntimeError("PC 群发队列 createdCount 不能为负数")
    if created_count == 0:
        empty_outcome = _queue_empty_reason(queued)
        empty_status = empty_outcome["status"]
        empty_reason = empty_outcome["reason"]
        # An account with no PC-created task must not enter the material chat:
        # there is no authoritative card/recipient payload to forward.  This
        # is a normal per-account skip, but it is logged and surfaced by the
        # unified launcher before scanning the next WeChat instance.  An
        # eligible target without a created task is instead a hard queue error.
        print(
            "SEND_QUEUE_EMPTY",
            "accounts={}".format(account_ids),
            "batch={}".format(summary["batchNo"]),
            "createdCount=0",
            "targetCount={}".format(queued.get("targetCount", 0)),
            "skippedCount={}".format(queued.get("skippedCount", 0)),
            "status={}".format(empty_status),
            "reason={}".format(empty_reason),
        )
        summary["status"] = empty_status
        summary["idle"] = empty_status == "idle"
        if empty_status == "idle":
            summary["idleReason"] = empty_reason
        else:
            summary["lastError"] = empty_reason
            summary["lastErrorStage"] = "queue_creation"
            summary["workflowFailureCount"] = 1
        summary["queue"] = {
            "runId": queued.get("runId"),
            "groupCodes": queued.get("groupCodes", []),
            "createdCount": 0,
            "targetCount": queued.get("targetCount", 0),
            "skippedCount": queued.get("skippedCount", 0),
            "skippedItems": queued.get("skippedItems", []),
            "reason": empty_reason,
            "workflowFailureCount": summary["workflowFailureCount"],
        }
        return summary
    max_tasks = 1 if TEST_MODE in {"TEST_SINGLE", "TEST_ONLY"} else MAX_TASKS_PER_RUN
    run_id = queued.get("_clientRunId")
    forward_started_at = None
    previous_account_homed = False
    for account_id in account_ids:
        global ACTIVE_WECHAT_ACCOUNT_ID
        if previous_account_homed:
            switch_log = StepLog()
            _reset_to_wechat_home(ble, switch_log, "切换下一个微信账号前")
        ACTIVE_WECHAT_ACCOUNT_ID = account_id
        _heartbeat()
        stop_after_account = False
        for _ in range(max_tasks):
            task = _claim_task(run_id=run_id)
            if not task:
                # No task is a valid per-account outcome: this account has no
                # eligible target in the selected c-code. Do not treat it as
                # a workflow failure; the outer loop continues to the next
                # configured WeChat account.
                print(
                    "ACCOUNT_QUEUE_EMPTY_CONTINUE",
                    account_id,
                    "runId={}".format(run_id or ""),
                )
                break
            processed += 1
            try:
                if forward_started_at is None:
                    forward_started_at = time.time()
                result = _run_one_with_recovery(task, ble)
                status = result.get("status")
                if status == "success":
                    summary["success"] += 1
                elif status in {
                    "partial",
                    "group_not_found",
                    "search_no_results",
                    "send_action_unverified",
                }:
                    summary["partial"] += 1
                summary["missingGroups"] += int(result.get("missingCount") or 0)
                for target_result in result.get("targetResults") or []:
                    if isinstance(target_result, dict):
                        row = dict(target_result)
                        row["taskId"] = task.get("id")
                        row["wechatAccountId"] = task.get("targetWechatAccountId")
                        summary["targetResults"].append(row)
                completion = _complete_task(task, result)
                print(
                    "TASK_COMPLETED",
                    task.get("id"),
                    task.get("targetWechatAccountId"),
                    result.get("status"),
                    json.dumps(result.get("targetResults") or [], ensure_ascii=False),
                    bool(completion),
                )
                previous_account_homed = True
            except SenderStop as exc:
                payload = task.get("payload") or {}
                print(
                    "TASK_FAILED",
                    repr(exc),
                    "ambiguous",
                    bool(exc.ambiguous),
                    "group_not_found",
                    bool(exc.group_not_found),
                    "targetResults",
                    json.dumps(exc.target_results, ensure_ascii=False),
                )
                screenshot_path = _capture_blocker_screenshot(
                    "task_{}".format(task.get("id") or "unknown"),
                    exc,
                )
                summary["lastError"] = str(exc)[:400]
                summary["lastErrorStage"] = exc.stage or "task_workflow"
                summary["lastFailureSteps"] = list(
                    getattr(exc, "steps", []) or []
                )[-8:]
                summary["lastBlockerScreenshot"] = screenshot_path
                result = _result(
                    "failed",
                    groupNotFound=bool(exc.group_not_found),
                    ambiguous=bool(exc.ambiguous),
                    targetResults=exc.target_results,
                    error=str(exc),
                    steps=getattr(exc, "steps", []),
                    blockerScreenshot=screenshot_path,
                )
                for target_result in result.get("targetResults") or []:
                    if isinstance(target_result, dict):
                        row = dict(target_result)
                        row["taskId"] = task.get("id")
                        row["wechatAccountId"] = task.get("targetWechatAccountId")
                        summary["targetResults"].append(row)
                try:
                    failure = _fail_task(task, str(exc), result)
                    print("TASK_FAILED_RECORDED", task.get("id"), bool(failure))
                except Exception as backend_exc:
                    result["backendError"] = str(backend_exc)[:200]
                summary["failed"] += 1
                summary["workflowFailureCount"] += 1
                if exc.stage == "post_send_cleanup":
                    summary["cleanupFailureCount"] += 1
                # An unknown/ambiguous page must stop the run.  A confirmed
                # missing group is normally handled inside _run_one so other
                # groups can continue.
                stop_after_account = True
                previous_account_homed = False
                try:
                    cleanup_log = StepLog()
                    _reset_to_wechat_home(ble, cleanup_log, "任务失败收尾")
                    previous_account_homed = True
                except SenderStop as cleanup_exc:
                    print("TASK_HOME_RESET_FAILED", task.get("id"), str(cleanup_exc))
                    _capture_blocker_screenshot(
                        "task_cleanup_{}".format(task.get("id") or "unknown"),
                        cleanup_exc,
                    )
                break
            except Exception as exc:
                print("TASK_EXCEPTION", repr(exc))
                screenshot_path = _capture_blocker_screenshot("task_exception", exc)
                summary["lastError"] = str(exc)[:400]
                summary["lastErrorStage"] = "task_workflow"
                summary["lastFailureSteps"] = []
                summary["lastBlockerScreenshot"] = screenshot_path
                result = _result("failed", error=str(exc))
                try:
                    _fail_task(task, str(exc), result)
                except Exception as backend_exc:
                    result["backendError"] = str(backend_exc)[:200]
                summary["failed"] += 1
                summary["workflowFailureCount"] += 1
                stop_after_account = True
                break
        if stop_after_account and not previous_account_homed:
            break
    summary["processed"] = processed
    if forward_started_at is not None:
        summary["forwardDurationSeconds"] = round(time.time() - forward_started_at, 3)
    (
        summary["forwardSuccessCount"],
        summary["forwardActionSentCount"],
        summary["forwardFailureCount"],
    ) = _forward_outcome_counts(summary["targetResults"])
    summary["forwardUnconfirmedCount"] = summary["forwardActionSentCount"]
    summary["status"] = (
        "failed"
        if summary["failed"] > 0 and not previous_account_homed
        else "success"
        if summary["failed"] == 0
        and summary["forwardFailureCount"] == 0
        and summary["forwardUnconfirmedCount"] == 0
        and summary["forwardSuccessCount"] > 0
        else "unverified"
        if summary["failed"] == 0
        and summary["forwardFailureCount"] == 0
        and summary["forwardUnconfirmedCount"] > 0
        and summary["forwardSuccessCount"] == 0
        else "partial"
        if summary["forwardSuccessCount"] > 0 or summary["forwardActionSentCount"] > 0
        else "failed"
    )
    summary["queue"] = {
        "runId": queued.get("runId"),
        "groupCodes": queued.get("groupCodes", []),
        "createdCount": queued.get("createdCount", 0),
        "targetCount": queued.get("targetCount", 0),
        "skippedCount": queued.get("skippedCount", 0),
        "skippedItems": queued.get("skippedItems", []),
        "reason": summary.get("idleReason", ""),
        "workflowFailureCount": summary["workflowFailureCount"],
        "cleanupFailureCount": summary["cleanupFailureCount"],
    }
    return summary


Device.wake_up()
try:
    Device.keep_screen_on()
except Exception:
    pass

run_result = None
try:
    ble_device = _load_hid()
    run_result = _run_queue(ble_device)
except Exception as exc:
    print("SEND_EXCEPTION", repr(exc))
    _capture_blocker_screenshot("send_exception", exc)
    run_result = _result("failed", error=str(exc))

if not isinstance(run_result, dict):
    run_result = _result("failed", error="发送器未返回结构化结果")
queue_summary = run_result.get("queue") if isinstance(run_result.get("queue"), dict) else {}
scan_report = _preflight_report()
completion_report = {
    "deviceId": DEVICE_ID,
    "runId": queue_summary.get("runId") or "wechat-send:{}".format(int(time.time())),
    "status": run_result.get("status") or ("success" if not run_result.get("failed") else "failed"),
    "batchNo": run_result.get("batchNo") or queue_summary.get("batchNo"),
    "groupCodes": queue_summary.get("groupCodes", []),
    "accounts": scan_report.get("accounts", []),
    "scanSummary": scan_report.get("scanSummary", {}),
    "queueSummary": queue_summary,
    "forwardSummary": {
        "durationSeconds": run_result.get("forwardDurationSeconds"),
        "successCount": run_result.get("forwardSuccessCount", 0),
        "failureCount": run_result.get("forwardFailureCount", 0),
        "targetResults": run_result.get("targetResults", []),
    },
}
if str(os.environ.get("TEAMBUY_DEFER_COMPLETION_REPORT") or "").strip() == "1":
    run_result["completionNotification"] = {
        "sent": False,
        "reason": "deferred_to_unified_run_report",
    }
else:
    run_result["completionNotification"] = _notify_run_completion(completion_report)
print(json.dumps(run_result, ensure_ascii=False))
