# -*- coding: utf-8 -*-
"""微信助手：AScript 统一入口。

AScript 设备端只启动这个入口工程。手机端只负责扫描和执行 PC 已配置的
批次，群、文字和小程序卡片内容不在手机端重复配置。

Android AScript runtime is Python 3.8. Keep this file compatible with 3.8.
"""

from __future__ import print_function

import json
import importlib.util
import os
import queue
import sys
import threading
import time

from ascript.android.ui import Dialog, WebWindow
from ascript.android.system import Device


FEATURES = {
    "send_batches": {
        "title": "群发微信",
        "subtitle": "先同步 g10 群台账，再按批次转发卡片",
        "module": "wechat_marketing_sender",
        "preflight_scan": True,
    },
}


def _keep_screen_awake():
    try:
        Device.wake_up()
        Device.keep_screen_on()
    except Exception as exc:
        print("开启屏幕常亮失败:", exc)


_HID_REQUEST_FILE = ".codex_hid_request.json"
_HID_RESULT_FILE = ".codex_hid_result.json"
_RUN_STATUS_FILE = ".wechat_assistant_status.json"
_RUN_COMPLETION_STATE = None
_RUN_COMPLETION_REPORT = None


def _write_run_phase(project_root, phase, detail=None):
    """记录统一入口阶段，不在关键流程线程调用可能阻塞的 Android UI。"""
    payload = {
        "phase": str(phase),
        "timestamp": int(time.time()),
    }
    if detail:
        payload["detail"] = str(detail)
    # Keep the final callback outcome on every later phase write so the
    # run_stopped_after_batch marker cannot erase the email result.
    if isinstance(_RUN_COMPLETION_REPORT, dict):
        payload["completionReport"] = dict(_RUN_COMPLETION_REPORT)
    path = os.path.join(project_root, _RUN_STATUS_FILE)
    temp_path = path + ".tmp"
    try:
        with open(temp_path, "w") as handle:
            json.dump(payload, handle, ensure_ascii=False)
        os.replace(temp_path, path)
    except Exception as exc:
        print("RUN_PHASE_FILE_ERROR", type(exc).__name__)
    print("WECHAT_ASSISTANT_PHASE", json.dumps(payload, ensure_ascii=False))


def _completion_callback_summary(
    report,
    response=None,
    attempted=False,
    reason_override="",
    error_type="",
):
    """Persist only safe, actionable completion-callback and email fields."""
    report = report if isinstance(report, dict) else {}
    response = response if isinstance(response, dict) else None
    email = response.get("email") if response else None
    email = email if isinstance(email, dict) else {}
    reason = (
        email.get("reason")
        or (response or {}).get("reason")
        or reason_override
        or ""
    )
    error_type = error_type or (response or {}).get("errorType")
    email_sent = email.get("sent")
    notification_sent = (response or {}).get("sent")
    summary = {
        "runId": str(report.get("runId") or "")[:160],
        "reportStatus": str(report.get("status") or "")[:24],
        "requestAttempted": bool(attempted),
        "notifierResultAvailable": response is not None,
        "notificationSent": (
            notification_sent if isinstance(notification_sent, bool) else None
        ),
        "emailSent": email_sent if isinstance(email_sent, bool) else None,
        "reason": str(reason or "")[:240],
        "recordedAt": int(time.time()),
    }
    if error_type:
        summary["errorType"] = str(error_type)[:80]
    return summary


def _record_completion_callback(
    project_root,
    report,
    response=None,
    attempted=False,
    reason_override="",
    error_type="",
):
    """Save the callback result before the launcher writes its terminal phase."""
    global _RUN_COMPLETION_REPORT
    _RUN_COMPLETION_REPORT = _completion_callback_summary(
        report,
        response=response,
        attempted=attempted,
        reason_override=reason_override,
        error_type=error_type,
    )
    email_sent = _RUN_COMPLETION_REPORT.get("emailSent")
    email_label = str(email_sent).lower() if isinstance(email_sent, bool) else "unknown"
    _write_run_phase(
        project_root,
        "completion_report_result",
        "requestAttempted={} emailSent={} reason={}".format(
            _RUN_COMPLETION_REPORT["requestAttempted"],
            email_label,
            _RUN_COMPLETION_REPORT["reason"] or "none",
        ),
    )
    print(
        "BATCH_COMPLETION_REPORT_RESULT",
        json.dumps(_RUN_COMPLETION_REPORT, ensure_ascii=False),
    )


def _merge_scan_config(state, scan_config):
    """Merge the PC safety switch without ever allowing it to be cleared."""
    config = scan_config if isinstance(scan_config, dict) else {}
    scan_only = bool(state.get("scanOnly") or config.get("scanOnly") is True)
    if config:
        state["scanConfig"] = {
            "searchPrefixes": [
                str(value)[:24] for value in config.get("searchPrefixes") or []
            ],
            "scanOnly": scan_only,
        }
    state["scanOnly"] = scan_only


def _compact_preflight_trace(slot_index, scan_result, scan_errors):
    """Keep per-prefix scan and reconcile facts in the combined run report."""
    result = scan_result if isinstance(scan_result, dict) else {}
    scan_config = result.get("scanConfig")
    scan_config = scan_config if isinstance(scan_config, dict) else {}
    accounts = []
    for account in result.get("accounts") or []:
        if not isinstance(account, dict):
            continue
        prefix_runs = []
        for run in account.get("prefixRuns") or []:
            if not isinstance(run, dict):
                continue
            prefix_row = {
                "prefix": str(run.get("prefix") or "")[:24],
                "status": str(run.get("status") or "unknown")[:24],
                "groups": run.get("groupCount", 0),
                "uniqueGroups": run.get("uniqueGroupCount", 0),
                "scrolls": run.get("scrollCount", 0),
                "stage": str(run.get("stage") or "")[:32],
                "groupsBeforeFailure": run.get("groupCountBeforeFailure", 0),
                "stop": str(run.get("stopReason") or "")[:48],
            }
            if run.get("error"):
                prefix_row["error"] = str(run.get("error"))[:120]
            prefix_runs.append(prefix_row)

        reconcile = account.get("reconcile")
        reconcile = reconcile if isinstance(reconcile, dict) else {}
        reconcile_data = reconcile.get("data")
        reconcile_data = reconcile_data if isinstance(reconcile_data, dict) else reconcile
        reconcile_confirmed = bool(
            isinstance(reconcile_data, dict)
            and reconcile_data.get("scanId")
            and reconcile_data.get("wechatAccountId") == account.get("accountId")
        )
        post_errors = []
        for error in account.get("postErrors") or []:
            if not isinstance(error, dict):
                post_errors.append({"error": str(error)[:180]})
                continue
            post_errors.append({
                "stage": str(error.get("stage") or "")[:40],
                "error": str(error.get("error") or "")[:240],
            })
        accounts.append({
            "accountId": str(account.get("accountId") or "")[:80],
            "status": str(account.get("status") or "unknown")[:24],
            "groups": account.get("groupCount", 0),
            "prefixRuns": prefix_runs,
            "reconcile": {
                "confirmed": reconcile_confirmed,
                "created": reconcile_data.get("createdCount") if reconcile_confirmed else None,
                "updated": reconcile_data.get("updatedCount") if reconcile_confirmed else None,
                "missing": reconcile_data.get("missingCount") if reconcile_confirmed else None,
            },
            "postErrors": post_errors,
        })

    errors = []
    for error in scan_errors or []:
        if not isinstance(error, dict):
            errors.append({"error": str(error)[:120]})
            continue
        errors.append({
            "stage": str(error.get("stage") or "")[:32],
            "prefix": str(error.get("prefix") or "")[:24],
            "error": str(error.get("error") or "")[:120],
        })
    return {
        "slot": slot_index,
        "status": str(result.get("status") or "unavailable")[:24],
        "searchPrefixes": [str(value)[:24] for value in scan_config.get("searchPrefixes") or []],
        "accounts": accounts,
        "errors": errors,
    }


def _write_hid_result(project_root, result):
    """写入 MCP HID 桥回执；回执只含状态，不含账号或凭证。"""
    path = os.path.join(project_root, _HID_RESULT_FILE)
    temp_path = path + ".tmp"
    try:
        with open(temp_path, "w") as handle:
            json.dump(result, handle, ensure_ascii=False)
        os.replace(temp_path, path)
    except Exception as exc:
        print("HID_BRIDGE_RESULT_WRITE_ERROR", type(exc).__name__)


def _process_hid_request(project_root):
    """处理 MCP 写入的实时控件矩形，动作只走官方 ESP32 BleDevice。"""
    request_path = os.path.join(project_root, _HID_REQUEST_FILE)
    if not os.path.isfile(request_path):
        return

    try:
        with open(request_path, "r") as handle:
            request = json.load(handle)
        os.remove(request_path)
    except (IOError, OSError, ValueError):
        # 上传尚未完成或文件内容仍在写入时，留给下一轮重试。
        return

    request_id = str(request.get("request_id", ""))
    result = {"request_id": request_id, "ok": False}
    try:
        if request.get("action") == "cleanup":
            try:
                os.remove(os.path.join(project_root, _HID_RESULT_FILE))
            except OSError:
                pass
            return
        if request.get("action") != "click":
            raise ValueError("不支持的 HID 动作")
        # AScript 自己的 Dialog 在 mode=6 辅助树中会被 WebWindow 遮住，
        # 但 mode=2/3 的实时树仍提供准确矩形；微信页面本身仍只接受
        # mode=6。所有模式最终都由同一个官方 BleDevice 执行。
        if request.get("mode") not in (2, 3, 6):
            raise ValueError("HID 动作必须来自实时控件树 mode=2/3/6")

        rect = request.get("rect")
        if isinstance(rect, dict):
            left = int(rect.get("left"))
            top = int(rect.get("top"))
            right = int(rect.get("right"))
            bottom = int(rect.get("bottom"))
        elif isinstance(rect, list) and len(rect) == 4:
            left, top, right, bottom = [int(value) for value in rect]
        else:
            raise ValueError("HID 请求缺少有效 rect")
        if right <= left or bottom <= top:
            raise ValueError("HID 请求 rect 为空")

        display = Device.display()
        width = int(getattr(display, "widthPixels", 0))
        height = int(getattr(display, "heightPixels", 0))
        x = (left + right) // 2
        y = (top + bottom) // 2
        if width <= 0 or height <= 0 or not (0 <= x < width and 0 <= y < height):
            raise ValueError("HID 请求中心点超出当前屏幕")

        from ascript.android import plug
        plug.load("esp32")
        from esp32 import BleDevice
        ble = BleDevice()
        if not ble.is_conncted():
            ble.re_connect()
        if not ble.is_conncted():
            raise RuntimeError("官方 ESP32 HID 未连接")
        ble.click(x, y, dur=int(request.get("duration", 35)))
        result.update({"ok": True, "center": [x, y]})
        print("HID_BRIDGE_CLICK_OK", request_id, x, y)
    except Exception as exc:
        result["error"] = "{}: {}".format(type(exc).__name__, exc)
        print("HID_BRIDGE_CLICK_ERROR", request_id, result["error"])
    _write_hid_result(project_root, result)


def _hid_bridge_loop(project_root, stop_event):
    print("HID_BRIDGE_READY mode=6 official=BleDevice")
    # The bridge is scoped to one AScript launcher run.  Event.wait keeps the
    # file-poll interval interruptible so the worker does not outlive the UI.
    while not stop_event.is_set():
        _process_hid_request(project_root)
        stop_event.wait(0.2)
    print("HID_BRIDGE_STOPPED")


def _load_feature_module(module_name):
    # AScript runs this file as the project entry, but the feature folders are
    # not top-level import paths. Load each feature as a synthetic package so
    # its local relative imports (for example .local_config) still work.
    project_root = os.path.dirname(os.path.abspath(__file__))
    module_dir = os.path.join(project_root, module_name)
    module_file = os.path.join(module_dir, "__init__.py")
    if not os.path.isfile(module_file):
        raise ImportError("找不到功能模块文件: {}".format(module_file))
    package_name = "_team_buy_ascript_{}".format(module_name)
    spec = importlib.util.spec_from_file_location(
        package_name,
        module_file,
        submodule_search_locations=[module_dir],
    )
    if spec is None or spec.loader is None:
        raise ImportError("无法加载功能模块: {}".format(module_name))
    module = importlib.util.module_from_spec(spec)
    sys.modules[package_name] = module
    spec.loader.exec_module(module)
    return module


def _run_module(feature):
    global _RUN_COMPLETION_STATE
    module_name = feature.get("module")
    project_root = os.path.dirname(os.path.abspath(__file__))
    _write_run_phase(project_root, "feature_started", feature.get("title", ""))

    if module_name == "wechat_marketing_sender":
        labels = ["第{}批".format(number) for number in range(1, 11)]
        _write_run_phase(project_root, "batch_dialog_open")
        choice = Dialog.select(
            labels,
            msg="第一次默认第1批；再次打开可重新选择任意批次。内容和目标群均读取 PC 配置。",
            title="群发微信",
            submit="开始执行",
            cancel="返回九宫格",
        )
        index = _menu_choice_index(choice, labels)
        if index is None:
            if choice is None:
                _write_run_phase(project_root, "batch_cancelled")
                return
            choice_type = type(choice).__name__
            _write_run_phase(
                project_root,
                "batch_selection_unrecognized",
                "type={}".format(choice_type),
            )
            raise RuntimeError("发送批次选择结果无法识别")
        os.environ["TEAMBUY_SEND_BATCH_NO"] = str(index + 1)
        _write_run_phase(project_root, "batch_selected", "batch={}".format(index + 1))

    if feature.get("preflight_scan"):
        # Scan and reconcile both configured WeChat slots before starting the
        # independent sender module. Any incomplete scan blocks the whole send
        # phase so no account runs with a partially prepared target set.
        os.environ["TEAMBUY_SCAN_MODE"] = "targeted"
        os.environ.pop("TEAMBUY_PREFLIGHT_ONLY", None)
        os.environ.pop("TEAMBUY_SEND_GROUP_CODES", None)
        os.environ.pop("TEAMBUY_SCAN_SLOT_INDICES", None)
        os.environ.pop("TEAMBUY_SEND_ACCOUNT_IDS", None)
        os.environ.pop("TEAMBUY_SEND_ACCOUNT_SLOT", None)
        os.environ.pop("TEAMBUY_PREFLIGHT_REPORT_JSON", None)
        _RUN_COMPLETION_STATE = {
            "reporter": None,
            "batchNo": int(os.environ.get("TEAMBUY_SEND_BATCH_NO") or "1"),
            "accounts": [],
            "scanSummaries": [],
            "scanErrors": [],
            "queueSummary": {
                "runIds": [],
                "createdCount": 0,
                "targetCount": 0,
                "skippedCount": 0,
                "accountRuns": [],
                "workflowFailureCount": 0,
                "cleanupFailureCount": 0,
            },
            # The PC owns this safety switch.  Keep it in the combined state
            # so the unified launcher can stop before loading the sender.
            "scanOnly": False,
            "scanConfig": {
                "searchPrefixes": [],
                "scanOnly": False,
            },
            "groupCodes": [],
            "forwardSummary": {
                "durationSeconds": 0.0,
                "successCount": 0,
                "actionSentCount": 0,
                "unconfirmedCount": 0,
                "failureCount": 0,
                "cleanupFailureCount": 0,
                "workflowFailureCount": 0,
                "targetCount": 0,
                "targetResults": [],
            },
            "runError": "",
        }
        # The scanner validates each slot against its live chooser and returns
        # the real WeChat ID before the separate send phase.
        for slot_index in (0, 1):
            os.environ["TEAMBUY_SCAN_SLOT_INDICES"] = str(slot_index)
            _write_run_phase(
                project_root,
                "preflight_started",
                "slot={}".format(slot_index),
            )
            try:
                preflight = _load_feature_module("wechat_group_inventory")
                if preflight is not None:
                    _RUN_COMPLETION_STATE["reporter"] = preflight
                preflight_errors = getattr(preflight, "errors", []) or []
            except Exception as exc:
                preflight = None
                preflight_errors = [{"error": "{}".format(type(exc).__name__)}]

            # Capture SCAN_RESULT before applying the failure gate: a scanner
            # can fail after one prefix/account has produced useful evidence.
            # Recording first makes the completion email explain where it
            # stopped without weakening the rule that any scan error blocks send.
            scan_result = getattr(preflight, "SCAN_RESULT", {}) or {}
            scan_config = scan_result.get("scanConfig")
            scan_config = scan_config if isinstance(scan_config, dict) else {}
            _merge_scan_config(_RUN_COMPLETION_STATE, scan_config)
            scan_accounts = [
                account
                for account in scan_result.get("accounts", [])
                if isinstance(account, dict)
            ]
            scan_errors = list(scan_result.get("errors", []) or [])
            for error in preflight_errors:
                if error not in scan_errors:
                    scan_errors.append(error)
            _RUN_COMPLETION_STATE["accounts"].extend(
                dict(account) for account in scan_accounts
            )
            trace = _compact_preflight_trace(slot_index, scan_result, scan_errors)
            trace["summary"] = scan_result.get("scanSummary", {})
            _RUN_COMPLETION_STATE["scanSummaries"].append(trace)
            _RUN_COMPLETION_STATE["scanErrors"].extend(scan_errors)
            print("PREFLIGHT_DIAGNOSTICS", json.dumps(trace, ensure_ascii=False))
            if preflight_errors or scan_errors:
                print(
                    "PREFLIGHT_ATTEMPT_FAILED",
                    "slot={}".format(slot_index),
                    json.dumps(scan_errors, ensure_ascii=False),
                )
                _write_run_phase(
                    project_root,
                    "preflight_failed",
                    "slot={} errors={}".format(slot_index, len(scan_errors)),
                )
                raise RuntimeError("微信群前置扫描未完成：{}".format(scan_errors))
            incomplete_accounts = [
                account
                for account in scan_accounts
                if account.get("status") != "success"
                or not str(account.get("accountId") or "").strip()
            ]
            if scan_errors or incomplete_accounts or len(scan_accounts) != 1:
                raise RuntimeError(
                    "当前微信账号前置扫描未完成，禁止进入该账号发送：slot={} accounts={} errors={} incomplete={}".format(
                        slot_index,
                        len(scan_accounts),
                        len(scan_errors),
                        len(incomplete_accounts),
                    )
                )
            account = scan_accounts[0]
            account_id = str(account.get("accountId") or "").strip()
            if not account_id:
                raise RuntimeError("前置扫描没有返回当前微信真实账号 ID")
            if account_id in {
                str(row.get("accountId") or "").strip()
                for row in _RUN_COMPLETION_STATE["accounts"][:-1]
                if isinstance(row, dict)
            }:
                raise RuntimeError("双开槽位读取到重复微信号，停止避免跨账号重复执行")

            _write_run_phase(
                project_root,
                "preflight_finished",
                "slot={} account={}".format(slot_index, account_id),
            )
            # Keep the scan phase and forwarding phase separate: the sender
            # receives both verified accounts and claims the complete account
            # set in one batch run, as required by TEST_ONLY queue validation.
        if len(_RUN_COMPLETION_STATE["accounts"]) != 2:
            raise RuntimeError("双账号扫描结果数量不完整，禁止启动群发")
        if _RUN_COMPLETION_STATE.get("scanOnly") is True:
            # A scan-only run is intentionally complete without creating or
            # claiming any send task.  Returning here keeps the sender from
            # turning the PC safety switch into a normal batch run.
            _RUN_COMPLETION_STATE["queueSummary"]["skipped"] = (
                "scan_only_configuration"
            )
            _RUN_COMPLETION_STATE["queueSummary"]["reason"] = (
                "PC 配置为仅扫描并同步，不创建发送任务"
            )
            _write_run_phase(
                project_root,
                "scan_only_completed",
                "accounts={}".format(len(_RUN_COMPLETION_STATE["accounts"])),
            )
            return
        scan_summary = {
            "accounts": _RUN_COMPLETION_STATE["scanSummaries"],
            "errors": [],
        }
        os.environ["TEAMBUY_PREFLIGHT_REPORT_JSON"] = json.dumps(
            {
                "accounts": _RUN_COMPLETION_STATE["accounts"],
                "errors": [],
                "scanSummary": scan_summary,
            },
            ensure_ascii=False,
        )
        os.environ.pop("TEAMBUY_SEND_ACCOUNT_IDS", None)
        os.environ.pop("TEAMBUY_SEND_ACCOUNT_SLOT", None)
        os.environ.pop("TEAMBUY_REUSE_SCANNED_ACCOUNT", None)
        os.environ.pop("TEAMBUY_DEFER_COMPLETION_REPORT", None)
        _write_run_phase(
            project_root,
            "all_preflight_finished",
            "accounts={}".format(len(_RUN_COMPLETION_STATE["accounts"])),
        )
        _write_run_phase(project_root, "sender_started", "accounts=2")
        sender = _load_feature_module(module_name)
        sender_result = getattr(sender, "run_result", {}) or {}
        if not isinstance(sender_result, dict):
            raise RuntimeError("发送器未返回可核验的运行结果")
        _write_run_phase(
            project_root,
            "sender_finished",
            "status={}".format(sender_result.get("status") or "unknown"),
        )
        completion_notification = sender_result.get("completionNotification")
        completion_report = getattr(sender, "completion_report", {}) or {}
        if isinstance(completion_notification, dict):
            # A configured request gets exactly one sender-owned callback;
            # retain its response for inspection without sending a duplicate.
            reason = str(completion_notification.get("reason") or "")
            _record_completion_callback(
                project_root,
                completion_report,
                response=completion_notification,
                attempted=reason not in {
                    "backend_not_configured",
                    "deferred_to_unified_run_report",
                },
            )
        else:
            _record_completion_callback(
                project_root,
                completion_report,
                attempted=False,
                reason_override="completion_notification_missing",
            )
        # The sender has sent the single combined run report containing the
        # two-account scan report; avoid emitting a second partial email here.
        _RUN_COMPLETION_STATE = None
        os.environ.pop("TEAMBUY_SCAN_SLOT_INDICES", None)
        os.environ.pop("TEAMBUY_SEND_ACCOUNT_IDS", None)
        os.environ.pop("TEAMBUY_SEND_ACCOUNT_SLOT", None)
        os.environ.pop("TEAMBUY_PREFLIGHT_REPORT_JSON", None)


def _record_sender_result(account_id, sender_result):
    state = _RUN_COMPLETION_STATE
    if not isinstance(state, dict):
        return
    result = sender_result if isinstance(sender_result, dict) else {}
    queue = result.get("queue") if isinstance(result.get("queue"), dict) else {}
    queue_summary = state["queueSummary"]
    run_id = str(queue.get("runId") or "").strip()
    if run_id and run_id not in queue_summary["runIds"]:
        queue_summary["runIds"].append(run_id)
    for key in ("createdCount", "targetCount", "skippedCount"):
        try:
            queue_summary[key] += int(queue.get(key) or 0)
        except (TypeError, ValueError):
            pass
    queue_summary["accountRuns"].append({
        "wechatAccountId": account_id,
        "status": str(result.get("status") or "unknown"),
        "createdCount": queue.get("createdCount", 0),
        "targetCount": queue.get("targetCount", 0),
        "skippedCount": queue.get("skippedCount", 0),
        "reason": str(queue.get("reason") or result.get("idleReason") or ""),
        "workflowFailureCount": result.get("workflowFailureCount", 0),
        "cleanupFailureCount": result.get("cleanupFailureCount", 0),
    })

    forward = state["forwardSummary"]
    try:
        forward["durationSeconds"] += float(result.get("forwardDurationSeconds") or 0)
    except (TypeError, ValueError):
        pass
    try:
        forward["successCount"] += int(result.get("forwardSuccessCount") or 0)
        action_sent_count = int(result.get("forwardActionSentCount") or 0)
        forward["actionSentCount"] += action_sent_count
        forward["unconfirmedCount"] += int(
            result.get("forwardUnconfirmedCount") or action_sent_count
        )
        # Recipient failures are derived from target outcomes. A task-level
        # error after sending (for example, failing to leave the chat) must not
        # be counted as a failed recipient.
        target_results = [
            item for item in result.get("targetResults") or []
            if isinstance(item, dict)
        ]
        if target_results:
            failure_count = sum(
                1 for item in target_results
                if item.get("status") not in {
                    "sent_ui_confirmed",
                    "send_action_sent_unverified",
                }
            )
        else:
            failure_count = int(result.get("forwardFailureCount") or 0)
        forward["targetCount"] += int(queue.get("targetCount") or 0)
    except (TypeError, ValueError):
        failure_count = 0
    forward["failureCount"] += failure_count
    cleanup_failures = int(result.get("cleanupFailureCount") or 0)
    workflow_failures = int(result.get("workflowFailureCount") or 0)
    forward["cleanupFailureCount"] += cleanup_failures
    forward["workflowFailureCount"] += workflow_failures
    queue_summary["cleanupFailureCount"] += cleanup_failures
    queue_summary["workflowFailureCount"] += workflow_failures
    for target in result.get("targetResults") or []:
        if not isinstance(target, dict):
            continue
        row = dict(target)
        row.setdefault("wechatAccountId", account_id)
        forward["targetResults"].append(row)
    error = str(result.get("lastError") or result.get("error") or "").strip()
    if error:
        queue_summary.setdefault("errors", []).append({
            "wechatAccountId": account_id,
            "stage": str(result.get("lastErrorStage") or "workflow"),
            "error": error[:500],
        })


def _flush_run_completion():
    state = _RUN_COMPLETION_STATE
    if not isinstance(state, dict):
        return
    project_root = os.path.dirname(os.path.abspath(__file__))
    scan_complete = len(state["accounts"]) == 2 and not state["scanErrors"]
    forward = state["forwardSummary"]
    if (
        state.get("scanOnly") is True
        and scan_complete
        and not state["runError"]
    ):
        # A scan-only run intentionally has no forwarding outcomes; its
        # successful terminal state means both account scans completed.
        status = "success"
    elif (
        scan_complete
        and forward["successCount"] > 0
        and forward["failureCount"] == 0
        and forward["unconfirmedCount"] == 0
        and forward["cleanupFailureCount"] == 0
        and not state["runError"]
    ):
        status = "success"
    elif forward["successCount"] > 0 or forward["actionSentCount"] > 0:
        status = (
            "unverified"
            if forward["successCount"] == 0
            and forward["failureCount"] == 0
            and forward["actionSentCount"] > 0
            and forward["cleanupFailureCount"] == 0
            and not state["runError"]
            else "degraded"
        )
    else:
        status = "failed"
    queue_summary = dict(state["queueSummary"])
    if state["runError"]:
        queue_summary["runError"] = state["runError"][:800]
    report = {
        "deviceId": "android-01",
        "runId": "wechat-assistant-batch:{}".format(int(time.time() * 1000)),
        "status": status,
        "batchNo": state["batchNo"],
        # A preflight-only or failed run may not have a selected batch code;
        # do not invent the test code in its completion report.
        "groupCodes": list(state.get("groupCodes") or []),
        "scanConfig": dict(state.get("scanConfig") or {}),
        "accounts": state["accounts"],
        "scanSummary": {
            "accounts": state["scanSummaries"],
            "errors": state["scanErrors"],
        },
        "queueSummary": queue_summary,
        "forwardSummary": forward,
    }
    reporter = state.get("reporter")
    notify = getattr(reporter, "_notify_preflight_completion", None)
    if not callable(notify):
        _record_completion_callback(
            project_root,
            report,
            attempted=False,
            reason_override="reporter_unavailable",
        )
        print("BATCH_COMPLETION_REPORT_FAILED reporter_unavailable")
        return
    try:
        response = notify(report)
        reason = str(response.get("reason") or "") if isinstance(response, dict) else ""
        _record_completion_callback(
            project_root,
            report,
            response=response,
            attempted=reason != "backend_not_configured",
        )
        email = response.get("email") if isinstance(response, dict) else None
        sent = email.get("sent") if isinstance(email, dict) else None
        print(
            "BATCH_COMPLETION_REPORT status={} emailSent={}".format(
                status,
                str(sent).lower() if isinstance(sent, bool) else "unknown",
            )
        )
    except Exception as exc:
        _record_completion_callback(
            project_root,
            report,
            attempted=True,
            reason_override="completion_callback_exception",
            error_type=type(exc).__name__,
        )
        print("BATCH_COMPLETION_REPORT_FAILED {}".format(type(exc).__name__))


def _run_module_with_completion(feature):
    global _RUN_COMPLETION_STATE
    _RUN_COMPLETION_STATE = None
    try:
        return _run_module(feature)
    except Exception as exc:
        if isinstance(_RUN_COMPLETION_STATE, dict):
            _RUN_COMPLETION_STATE["runError"] = str(exc)[:800]
        raise
    finally:
        for name in (
            "TEAMBUY_SCAN_SLOT_INDICES",
            "TEAMBUY_SEND_ACCOUNT_IDS",
            "TEAMBUY_SEND_ACCOUNT_SLOT",
            "TEAMBUY_PREFLIGHT_REPORT_JSON",
            "TEAMBUY_REUSE_SCANNED_ACCOUNT",
            "TEAMBUY_DEFER_COMPLETION_REPORT",
        ):
            os.environ.pop(name, None)
        # This is the sole combined notification point: sender-level notices
        # are deferred, and _run_module has now finished (or stopped) its
        # per-account scan -> c1001 card-forward workflow.
        _flush_run_completion()
        _RUN_COMPLETION_STATE = None


def _menu_choice_index(choice, labels):
    """Normalize Dialog.select's result across AScript 4.x builds."""
    if isinstance(choice, int):
        if 0 <= choice < len(labels):
            return choice
        if 1 <= choice <= len(labels):
            return choice - 1
    if isinstance(choice, str):
        value = choice.strip()
        if value in labels:
            return labels.index(value)
        if value.isdigit():
            number = int(value)
            if 1 <= number <= len(labels):
                return number - 1
            if 0 <= number < len(labels):
                return number
    if isinstance(choice, dict):
        for key in ("index", "selectedIndex", "position", "value", "text", "item"):
            if key in choice:
                index = _menu_choice_index(choice[key], labels)
                if index is not None:
                    return index
    if isinstance(choice, (list, tuple)) and len(choice) == 1:
        return _menu_choice_index(choice[0], labels)
    return None


def _native_menu():
    """原生菜单兜底也只允许启动一笔批次，结束后让 AScript 进程返回。"""
    labels = ["群发微信"]
    feature_ids = list(FEATURES.keys())
    choice = Dialog.select(
        labels,
        msg="请选择要运行的功能",
        title="微信助手",
        submit="打开",
        cancel="退出",
    )
    if choice is None:
        return
    index = _menu_choice_index(choice, labels)
    if index is None or index < 0 or index >= len(feature_ids):
        Dialog.alert("未识别菜单选择：{}".format(choice), submit="关闭")
        return
    feature = FEATURES[feature_ids[index]]
    try:
        _run_module_with_completion(feature)
    except Exception as exc:
        Dialog.alert(
            "{} 执行失败：\n{}".format(feature["title"], exc),
            submit="关闭",
        )


def _run_launcher(project_root):
    state = {
        "window": None,
        "closing_for_feature": False,
        "feature_consumed": False,
    }
    events = queue.Queue()

    def tunnel(key, value):
        if key == "window_closed":
            if state["closing_for_feature"]:
                state["closing_for_feature"] = False
                return
            events.put(("closed", None))
            return
        if key != "feature":
            return
        feature = FEATURES.get(str(value))
        if not feature:
            events.put(("unknown_feature", str(value)))
            return
        # One launcher invocation may start only one batch workflow. This
        # drops duplicate/late callbacks so the just-finished run cannot
        # silently start another scan/send cycle from a stale tap event.
        if state["feature_consumed"]:
            return
        state["feature_consumed"] = True
        # Keep the WebWindow callback non-blocking: status-file I/O, Toast and
        # close() may wait on Android UI dispatch. The launcher thread owns
        # those operations after consuming this event.
        events.put(("feature", feature))

    def show_launcher():
        # A fresh id avoids reusing a stale WebWindow after the previous run.
        window_id = 10000 + (int(time.time()) % 90000)
        # Resolve the launcher from this project so the copied "微信助手"
        # project never falls back to the legacy 资料整理助手 UI.
        launcher_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "res",
            "ui",
            "launcher.html",
        )
        # Use the documented constructor-level tunnel.  On Android 15 the
        # page is visible in the accessibility tree, but named handlers can be
        # dropped after an HID tap; registering both paths also duplicates
        # events.  The constructor tunnel is the single callback path.
        window = WebWindow(launcher_path, tunnel=tunnel, id=window_id)
        state["window"] = window
        # Keep the full-screen WebWindow visible while all device actions are
        # still dispatched through the official HID bridge.
        window.mode(0)
        window.background("#080d1d")
        window.dim_amount(0)
        window.size("100vw", "100vh")
        window.show(wait=False)
        _write_run_phase(project_root, "launcher_ready")
        print("微信助手九宫格已显示，等待用户选择")

    try:
        show_launcher()
    except Exception as exc:
        print("九宫格窗口不可用，切换原生菜单:", exc)
        _native_menu()
        return

    try:
        # 一个入口进程只展示一次九宫格并消费一次用户动作；批次结束后
        # 自动退出，避免跑完仍停留在常驻等待循环或重复执行旧点击事件。
        event_type, payload = events.get(timeout=300)
    except queue.Empty:
        print("九宫格 300 秒未收到点击回调，关闭窗口并退出")
        window = state.get("window")
        state["window"] = None
        if window is not None:
            try:
                window.close()
            except Exception:
                pass
        _write_run_phase(project_root, "run_stopped_idle_timeout")
        return

    window = state.get("window")
    state["window"] = None
    if event_type == "closed":
        if window is not None:
            try:
                window.close()
            except Exception:
                pass
        _write_run_phase(project_root, "run_stopped_by_user")
        return
    if event_type == "unknown_feature":
        _write_run_phase(project_root, "unknown_feature", payload)
        print("收到未知九宫格功能，停止本次入口:", payload)
        return
    if event_type != "feature":
        print("收到未知九宫格事件，停止本次入口:", event_type)
        return

    # The callback only queues the selection. Close the overlay here, on the
    # launcher thread, so a blocked WebWindow callback cannot prevent scanning.
    _write_run_phase(project_root, "feature_event_received", payload.get("module"))
    state["closing_for_feature"] = True
    if window is not None:
        try:
            window.close()
        except Exception as exc:
            state["closing_for_feature"] = False
            detail = "{}: {}".format(type(exc).__name__, str(exc)[:500])
            _write_run_phase(project_root, "launcher_close_failed", detail)
            print("LAUNCHER_CLOSE_FAILED", detail)
            return

    try:
        _run_module_with_completion(payload)
    except Exception as exc:
        failure_detail = str(exc)[:1400]
        _write_run_phase(
            project_root,
            "feature_failed",
            "{}: {}".format(type(exc).__name__, failure_detail),
        )
        # Do not block the one-shot launcher on a modal alert: the combined
        # run report and this log/phase already preserve the error, and the
        # finally block must be able to mark the run stopped and return.
        print(
            "FEATURE_FAILED title={} error={}".format(
                payload["title"],
                failure_detail,
            )
        )
    else:
        _write_run_phase(project_root, "feature_returned")
    finally:
        # _run_module_with_completion 已在 finally 发送整笔报告；现在让
        # AScript 正式入口返回，不再重开九宫格，也不等待下一轮批次。
        _write_run_phase(project_root, "run_stopped_after_batch", payload["title"])


def main():
    global _RUN_COMPLETION_REPORT
    _keep_screen_awake()
    project_root = os.path.dirname(os.path.abspath(__file__))
    # A new launcher invocation must not carry the previous run's mail result.
    _RUN_COMPLETION_REPORT = None
    for stale_name in (_HID_REQUEST_FILE, _HID_RESULT_FILE):
        try:
            os.remove(os.path.join(project_root, stale_name))
        except OSError:
            pass
    _write_run_phase(project_root, "launcher_start")
    stop_event = threading.Event()
    bridge_thread = threading.Thread(
        target=_hid_bridge_loop,
        args=(project_root, stop_event),
        daemon=True,
    )
    bridge_thread.start()
    try:
        _run_launcher(project_root)
    finally:
        # Stop the polling worker on every launcher exit path, including
        # timeout, user close, native-menu fallback, and completed batches.
        stop_event.set()
        bridge_thread.join(timeout=2.0)
        if bridge_thread.is_alive():
            print("HID_BRIDGE_STOP_TIMEOUT worker still active")
        else:
            print("HID_BRIDGE_STOP_CONFIRMED")


# AScript loads an Android project entry file as a module rather than relying
# on the CPython __main__ name. This file is the dedicated project entry, so
# invoke the launcher unconditionally; otherwise the project reports success
# while showing only the AScript host screen.
main()
