"""Regression tests for compact scan traces sent by the AScript entry."""
import ast
import json
import os
from pathlib import Path
import time

import pytest


@pytest.fixture
def compact_trace():
    source = Path(__file__).resolve().parents[2] / "automation/ascript/__init__.py"
    module = ast.parse(source.read_text())
    module.body = [
        item
        for item in module.body
        if isinstance(item, ast.FunctionDef)
        and item.name == "_compact_preflight_trace"
    ]
    namespace = {}
    exec(compile(module, str(source), "exec"), namespace)
    return namespace["_compact_preflight_trace"]


@pytest.fixture
def completion_trace_functions():
    source = Path(__file__).resolve().parents[2] / "automation/ascript/__init__.py"
    module = ast.parse(source.read_text())
    selected = {
        "_completion_callback_summary",
        "_write_run_phase",
    }
    module.body = [
        item
        for item in module.body
        if isinstance(item, ast.FunctionDef) and item.name in selected
    ]
    namespace = {
        "json": json,
        "os": os,
        "time": time,
        "_RUN_STATUS_FILE": ".wechat_assistant_status.json",
        "_RUN_COMPLETION_REPORT": None,
    }
    exec(compile(module, str(source), "exec"), namespace)
    return namespace


def test_scan_trace_keeps_each_prefix_result_and_reconcile_counts(compact_trace):
    trace = compact_trace(
        0,
        {
            "status": "degraded",
            "scanConfig": {"searchPrefixes": ["c10", "g10"]},
            "accounts": [
                {
                    "accountId": "wechat-id-test",
                    "status": "degraded",
                    "groupCount": 3,
                    "prefixRuns": [
                        {
                            "prefix": "c10",
                            "status": "success",
                            "groupCount": 2,
                            "uniqueGroupCount": 2,
                            "scrollCount": 1,
                            "stopReason": "targeted_bottom_stable",
                        },
                        {
                            "prefix": "g10",
                            "status": "failed",
                            "groupCount": 0,
                            "uniqueGroupCount": 0,
                            "scrollCount": 1,
                            "stage": "wait_scroll_result",
                            "groupCountBeforeFailure": 2,
                            "stopReason": "exception",
                            "error": "IME inactive",
                        },
                    ],
                    "reconcile": {
                        "data": {
                            "scanId": "scan-test",
                            "wechatAccountId": "wechat-id-test",
                            "createdCount": 1,
                            "updatedCount": 2,
                            "missingCount": 0,
                        },
                    },
                }
            ],
        },
        [{"stage": "scan_prefix", "prefix": "g10", "error": "IME inactive"}],
    )

    assert trace["slot"] == 0
    assert trace["status"] == "degraded"
    assert trace["searchPrefixes"] == ["c10", "g10"]
    account = trace["accounts"][0]
    assert [run["status"] for run in account["prefixRuns"]] == ["success", "failed"]
    assert account["prefixRuns"][0]["uniqueGroups"] == 2
    assert account["prefixRuns"][1]["error"] == "IME inactive"
    assert account["prefixRuns"][1]["stage"] == "wait_scroll_result"
    assert account["prefixRuns"][1]["scrolls"] == 1
    assert account["prefixRuns"][1]["groupsBeforeFailure"] == 2
    assert account["reconcile"] == {
        "confirmed": True,
        "created": 1,
        "updated": 2,
        "missing": 0,
    }
    assert trace["errors"][0]["prefix"] == "g10"


def test_scan_trace_exposes_reconcile_error_without_claiming_zero_writes(compact_trace):
    trace = compact_trace(
        0,
        {
            "status": "degraded",
            "accounts": [
                {
                    "accountId": "wechat-id-test",
                    "status": "degraded",
                    "groupCount": 9,
                    "reconcile": {},
                    "postErrors": [
                        {"stage": "reconcile", "error": "PC 请求失败 HTTP 409: duplicate group"}
                    ],
                }
            ],
        },
        [],
    )

    account = trace["accounts"][0]
    assert account["reconcile"] == {
        "confirmed": False,
        "created": None,
        "updated": None,
        "missing": None,
    }
    assert account["postErrors"] == [
        {"stage": "reconcile", "error": "PC 请求失败 HTTP 409: duplicate group"}
    ]


def test_scan_trace_records_failure_even_when_module_has_no_scan_result(compact_trace):
    trace = compact_trace(
        1,
        {},
        [{"error": "ImportError"}],
    )

    assert trace["slot"] == 1
    assert trace["status"] == "unavailable"
    assert trace["accounts"] == []
    assert trace["errors"] == [{"stage": "", "prefix": "", "error": "ImportError"}]


def test_completion_callback_summary_preserves_email_failure_reason(completion_trace_functions):
    summarize = completion_trace_functions["_completion_callback_summary"]
    result = summarize(
        {"runId": "wechat-assistant-batch:123", "status": "degraded"},
        {
            "sent": False,
            "reason": "completion_callback_failed",
            "errorType": "TimeoutError",
            "email": {"sent": False, "reason": "smtp_timeout"},
        },
        attempted=True,
    )

    assert result["runId"] == "wechat-assistant-batch:123"
    assert result["requestAttempted"] is True
    assert result["notifierResultAvailable"] is True
    assert result["notificationSent"] is False
    assert result["emailSent"] is False
    assert result["reason"] == "smtp_timeout"
    assert result["errorType"] == "TimeoutError"


def test_completion_callback_summary_distinguishes_missing_result(completion_trace_functions):
    summarize = completion_trace_functions["_completion_callback_summary"]
    result = summarize(
        {"runId": "run-456", "status": "failed"},
        attempted=False,
        reason_override="completion_notification_missing",
    )

    assert result["requestAttempted"] is False
    assert result["notifierResultAvailable"] is False
    assert result["emailSent"] is None
    assert result["reason"] == "completion_notification_missing"


def test_completion_callback_survives_later_terminal_phase(completion_trace_functions, tmp_path):
    namespace = completion_trace_functions
    namespace["_RUN_COMPLETION_REPORT"] = {
        "runId": "run-789",
        "emailSent": True,
        "reason": "",
    }
    write_phase = namespace["_write_run_phase"]
    write_phase(str(tmp_path), "completion_report_result")
    write_phase(str(tmp_path), "run_stopped_after_batch")

    saved = json.loads((tmp_path / ".wechat_assistant_status.json").read_text())
    assert saved["phase"] == "run_stopped_after_batch"
    assert saved["completionReport"]["runId"] == "run-789"
    assert saved["completionReport"]["emailSent"] is True
