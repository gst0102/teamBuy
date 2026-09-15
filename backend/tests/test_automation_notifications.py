from __future__ import annotations

import asyncio
import smtplib

import pytest

from app.api import dependencies
from app.core.config import settings
from app.services import automation_notification_service


class _FakeSmtp:
    message = None

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def login(self, username, password):
        assert username == "smtp-user"
        assert password == "server-only-password"

    def send_message(self, message):
        _FakeSmtp.message = message


def test_completion_mail_uses_server_smtp_and_safe_report(monkeypatch):
    monkeypatch.setattr(settings, "automation_completion_email_enabled", True)
    monkeypatch.setattr(settings, "automation_completion_email_to", "250667571@qq.com")
    monkeypatch.setattr(settings, "automation_smtp_host", "smtp.example.test")
    monkeypatch.setattr(settings, "automation_smtp_port", 465)
    monkeypatch.setattr(settings, "automation_smtp_username", "smtp-user")
    monkeypatch.setattr(settings, "automation_smtp_password", "server-only-password")
    monkeypatch.setattr(settings, "automation_smtp_from", "smtp-user@example.test")
    monkeypatch.setattr(settings, "automation_smtp_use_ssl", True)
    monkeypatch.setattr(settings, "automation_smtp_timeout_seconds", 10)
    monkeypatch.setattr(automation_notification_service.smtplib, "SMTP_SSL", _FakeSmtp)

    result = automation_notification_service.send_automation_completion_email(
        {
            "deviceId": "android-01",
            "runId": "preflight-c1001",
            "status": "success",
            "batchNo": 1,
            "groupCodes": ["c1001"],
            "scanConfig": {"searchPrefixes": ["g10", "c1001"], "scanOnly": True},
            "accounts": [{"wechatId": "qq673105954", "nickname": "leo", "groupCount": 2, "status": "success"}],
            "scanSummary": {"accountCount": 1},
            "queueSummary": {"createdCount": 1, "targetCount": 2},
            "forwardSummary": {
                "durationSeconds": 52.0,
                "successCount": 2,
                "actionSentCount": 0,
                "unconfirmedCount": 0,
                "failureCount": 0,
                "targetResults": [
                    {"wechatAccountId": "qq673105954", "groupName": "互助群", "status": "sent_ui_confirmed"},
                    {"wechatAccountId": "qq673105954", "groupName": "测试群", "status": "sent_ui_confirmed"},
                ],
            },
        }
    )

    assert result["configured"] is True
    assert result["sent"] is True
    assert result["smtpAccepted"] is True
    assert result["messageId"].startswith("<teambuy-")
    assert len(result["recipientFingerprint"]) == 16
    assert _FakeSmtp.message["Message-ID"] == result["messageId"]
    body = _FakeSmtp.message.get_content()
    assert "preflight-c1001" in body
    assert "c1001" in body
    assert "扫描范围：g10, c1001；运行方式：仅扫描并同步，不创建发送任务" in body
    assert "转发汇总：耗时 52.0 秒，PC目标 2 个（收到结果 2 个），UI确认送达 2 个，发送动作已发出待确认 0 个，目标未发送/失败 0 个，结果未回报 0 个" in body
    assert "互助群" in body
    assert "测试群" in body
    assert "server-only-password" not in body


def test_completion_mail_reports_smtp_recipient_refusal(monkeypatch):
    class RejectingSmtp(_FakeSmtp):
        def send_message(self, message):
            _FakeSmtp.message = message
            return {"250667571@qq.com": (550, b"mailbox unavailable")}

    monkeypatch.setattr(settings, "automation_completion_email_enabled", True)
    monkeypatch.setattr(settings, "automation_completion_email_to", "250667571@qq.com")
    monkeypatch.setattr(settings, "automation_smtp_host", "smtp.example.test")
    monkeypatch.setattr(settings, "automation_smtp_port", 465)
    monkeypatch.setattr(settings, "automation_smtp_username", "smtp-user")
    monkeypatch.setattr(settings, "automation_smtp_password", "server-only-password")
    monkeypatch.setattr(settings, "automation_smtp_from", "smtp-user@example.test")
    monkeypatch.setattr(settings, "automation_smtp_use_ssl", True)
    monkeypatch.setattr(settings, "automation_smtp_timeout_seconds", 10)
    monkeypatch.setattr(automation_notification_service.smtplib, "SMTP_SSL", RejectingSmtp)

    result = automation_notification_service.send_automation_completion_email(
        {"deviceId": "android-01", "runId": "run-refused", "status": "failed"}
    )

    assert result["sent"] is False
    assert result["smtpAccepted"] is False
    assert result["reason"] == "smtp_recipient_rejected"
    assert result["refusedCount"] == 1
    assert result["refused"] == [{"code": 550, "message": "mailbox unavailable"}]
    assert "250667571@qq.com" not in str(result["refused"])


def test_completion_mail_redacts_refusal_details(monkeypatch):
    class RejectingSmtp(_FakeSmtp):
        def send_message(self, message):
            return {
                "250667571@qq.com": (
                    550,
                    b"smtp.example.test smtp-user 250667571@qq.com rejected",
                )
            }

    monkeypatch.setattr(settings, "automation_completion_email_enabled", True)
    monkeypatch.setattr(settings, "automation_completion_email_to", "250667571@qq.com")
    monkeypatch.setattr(settings, "automation_smtp_host", "smtp.example.test")
    monkeypatch.setattr(settings, "automation_smtp_port", 465)
    monkeypatch.setattr(settings, "automation_smtp_username", "smtp-user")
    monkeypatch.setattr(settings, "automation_smtp_password", "server-only-password")
    monkeypatch.setattr(settings, "automation_smtp_from", "smtp-user@example.test")
    monkeypatch.setattr(settings, "automation_smtp_use_ssl", True)
    monkeypatch.setattr(settings, "automation_smtp_timeout_seconds", 10)
    monkeypatch.setattr(automation_notification_service.smtplib, "SMTP_SSL", RejectingSmtp)

    result = automation_notification_service.send_automation_completion_email(
        {"deviceId": "android-01", "runId": "run-refused-details", "status": "failed"}
    )

    assert result["reason"] == "smtp_recipient_rejected"
    assert result["refused"] == [{
        "code": 550,
        "message": "<redacted> <redacted> <redacted> rejected",
    }]


def test_completion_mail_handles_all_recipient_refusal_exception(monkeypatch):
    class RejectingSmtp(_FakeSmtp):
        def send_message(self, message):
            raise smtplib.SMTPRecipientsRefused({
                "250667571@qq.com": (550, b"250667571@qq.com mailbox unavailable")
            })

    monkeypatch.setattr(settings, "automation_completion_email_enabled", True)
    monkeypatch.setattr(settings, "automation_completion_email_to", "250667571@qq.com")
    monkeypatch.setattr(settings, "automation_smtp_host", "smtp.example.test")
    monkeypatch.setattr(settings, "automation_smtp_port", 465)
    monkeypatch.setattr(settings, "automation_smtp_username", "smtp-user")
    monkeypatch.setattr(settings, "automation_smtp_password", "server-only-password")
    monkeypatch.setattr(settings, "automation_smtp_from", "smtp-user@example.test")
    monkeypatch.setattr(settings, "automation_smtp_use_ssl", True)
    monkeypatch.setattr(settings, "automation_smtp_timeout_seconds", 10)
    monkeypatch.setattr(automation_notification_service.smtplib, "SMTP_SSL", RejectingSmtp)

    result = automation_notification_service.send_automation_completion_email(
        {"deviceId": "android-01", "runId": "run-all-refused", "status": "failed"}
    )

    assert result["reason"] == "smtp_recipient_rejected"
    assert result["smtpAccepted"] is False
    assert result["refused"] == [{
        "code": 550,
        "message": "<redacted> mailbox unavailable",
    }]


def test_completion_mail_redacts_smtp_details_from_exception(monkeypatch):
    class FailingSmtp(_FakeSmtp):
        def send_message(self, message):
            raise RuntimeError(
                "smtp.example.test smtp-user server-only-password 250667571@qq.com"
            )

    monkeypatch.setattr(settings, "automation_completion_email_enabled", True)
    monkeypatch.setattr(settings, "automation_completion_email_to", "250667571@qq.com")
    monkeypatch.setattr(settings, "automation_smtp_host", "smtp.example.test")
    monkeypatch.setattr(settings, "automation_smtp_port", 465)
    monkeypatch.setattr(settings, "automation_smtp_username", "smtp-user")
    monkeypatch.setattr(settings, "automation_smtp_password", "server-only-password")
    monkeypatch.setattr(settings, "automation_smtp_from", "smtp-user@example.test")
    monkeypatch.setattr(settings, "automation_smtp_use_ssl", True)
    monkeypatch.setattr(settings, "automation_smtp_timeout_seconds", 10)
    monkeypatch.setattr(automation_notification_service.smtplib, "SMTP_SSL", FailingSmtp)

    result = automation_notification_service.send_automation_completion_email(
        {"deviceId": "android-01", "runId": "run-error", "status": "failed"}
    )

    assert result["sent"] is False
    assert result["reason"] == "smtp_send_failed"
    assert result["smtpAccepted"] is None
    assert result["error"] == "<redacted> <redacted> <redacted> <redacted>"


def test_completion_mail_separates_sent_actions_from_post_send_cleanup_failure(monkeypatch):
    monkeypatch.setattr(settings, "automation_completion_email_enabled", True)
    monkeypatch.setattr(settings, "automation_completion_email_to", "250667571@qq.com")
    monkeypatch.setattr(settings, "automation_smtp_host", "smtp.example.test")
    monkeypatch.setattr(settings, "automation_smtp_port", 465)
    monkeypatch.setattr(settings, "automation_smtp_username", "smtp-user")
    monkeypatch.setattr(settings, "automation_smtp_password", "server-only-password")
    monkeypatch.setattr(settings, "automation_smtp_from", "smtp-user@example.test")
    monkeypatch.setattr(settings, "automation_smtp_use_ssl", True)
    monkeypatch.setattr(settings, "automation_smtp_timeout_seconds", 10)
    monkeypatch.setattr(automation_notification_service.smtplib, "SMTP_SSL", _FakeSmtp)

    automation_notification_service.send_automation_completion_email(
        {
            "deviceId": "android-01",
            "runId": "wechat-assistant-batch:1789272421252",
            "status": "degraded",
            "batchNo": 1,
            "groupCodes": ["c1001"],
            "accounts": [],
            "scanSummary": {},
            # Legacy failureCount included the later HID-home-reset error.
            "queueSummary": {
                "targetCount": 2,
                "createdCount": 1,
                "errors": [{
                    "wechatAccountId": "wechat-id-qq673105954",
                    "error": "HID返回后仍未确认微信会话列表：state=chat query=",
                }],
            },
            "forwardSummary": {
                "durationSeconds": 139.212,
                "successCount": 0,
                "unconfirmedCount": 2,
                "failureCount": 1,
                "targetResults": [
                    {
                        "wechatAccountId": "wechat-id-qq673105954",
                        "groupName": "互助群",
                        "status": "send_action_sent_unverified",
                    },
                    {
                        "wechatAccountId": "wechat-id-qq673105954",
                        "groupName": "测试群",
                        "status": "send_action_sent_unverified",
                    },
                ],
            },
        }
    )

    body = _FakeSmtp.message.get_content()
    assert "状态：degraded（微信页面收尾未确认；不计为目标群发送失败）" in body
    assert "转发汇总：耗时 139.212 秒，PC目标 2 个（收到结果 2 个），UI确认送达 0 个，发送动作已发出待确认 2 个，目标未发送/失败 0 个，结果未回报 0 个" in body
    assert "微信页面收尾：1 项未确认（不计入目标群发送失败）。" in body
    assert "目标未发送/失败 1 个" not in body
    assert "互助群" in body
    assert "测试群" in body


def test_completion_mail_lists_per_account_push_outcomes(monkeypatch):
    monkeypatch.setattr(settings, "automation_completion_email_enabled", True)
    monkeypatch.setattr(settings, "automation_completion_email_to", "250667571@qq.com")
    monkeypatch.setattr(settings, "automation_smtp_host", "smtp.example.test")
    monkeypatch.setattr(settings, "automation_smtp_port", 465)
    monkeypatch.setattr(settings, "automation_smtp_username", "smtp-user")
    monkeypatch.setattr(settings, "automation_smtp_password", "server-only-password")
    monkeypatch.setattr(settings, "automation_smtp_from", "smtp-user@example.test")
    monkeypatch.setattr(settings, "automation_smtp_use_ssl", True)
    monkeypatch.setattr(settings, "automation_smtp_timeout_seconds", 10)
    monkeypatch.setattr(automation_notification_service.smtplib, "SMTP_SSL", _FakeSmtp)

    automation_notification_service.send_automation_completion_email(
        {
            "deviceId": "android-01",
            "runId": "run-per-account",
            "status": "unverified",
            "batchNo": 1,
            "accounts": [
                {"accountId": "wechat-id-a", "nickname": "账号A"},
                {"accountId": "wechat-id-b", "nickname": "账号B"},
            ],
            "queueSummary": {
                "targetCount": 4,
                "accountRuns": [
                    {"wechatAccountId": "wechat-id-a", "targetCount": 2},
                    {"wechatAccountId": "wechat-id-b", "targetCount": 2},
                ],
            },
            "forwardSummary": {
                "targetResults": [
                    {"wechatAccountId": "wechat-id-a", "status": "sent_ui_confirmed"},
                    {"wechatAccountId": "wechat-id-a", "status": "search_no_results"},
                    {"wechatAccountId": "wechat-id-b", "status": "sent_ui_confirmed"},
                    {"wechatAccountId": "wechat-id-b", "status": "send_action_sent_unverified"},
                ],
            },
        }
    )

    body = _FakeSmtp.message.get_content()
    assert "账号推送统计：" in body
    assert "账号A：计划推送 2 个，收到结果 2 个，UI确认成功 1 个，发送动作待确认 0 个，失败/未发送 1 个，结果未回报 0 个" in body
    assert "账号B：计划推送 2 个，收到结果 2 个，UI确认成功 1 个，发送动作待确认 1 个，失败/未发送 0 个，结果未回报 0 个" in body


def test_completion_mail_worker_retries_when_delivery_is_not_confirmed(monkeypatch):
    monkeypatch.setattr(
        dependencies,
        "send_automation_completion_email",
        lambda report: {"configured": True, "sent": False, "reason": "smtp_send_failed"},
    )

    with pytest.raises(RuntimeError, match="smtp_send_failed"):
        asyncio.run(dependencies._run_automation_completion_email_task({"report": {"runId": "run-001"}}))

    monkeypatch.setattr(
        dependencies,
        "send_automation_completion_email",
        lambda report: {"configured": True, "sent": True},
    )
    result = asyncio.run(dependencies._run_automation_completion_email_task({"report": {"runId": "run-001"}}))

    assert result == {"syncStatus": "success", "email": {"configured": True, "sent": True}}
    assert "automation-completion-email" in dependencies.BACKGROUND_TASK_NAMES
