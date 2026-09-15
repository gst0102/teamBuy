from __future__ import annotations

import smtplib
import hashlib
from email.message import EmailMessage
from email.utils import parseaddr

from app.core.config import settings


def _one_line(value: object, limit: int = 300) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split())[:limit]


def _recipient(value: str) -> str | None:
    address = parseaddr(str(value or ""))[1].strip()
    if not address or "@" not in address or address.startswith("@") or address.endswith("@"):
        return None
    return address


def _nonnegative_int(value: object) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _recipient_fingerprint(recipient: str) -> str:
    """Return a short correlation key without persisting the address."""
    return hashlib.sha256(recipient.strip().lower().encode("utf-8")).hexdigest()[:16]


def _message_id(report: dict, sender: str) -> str:
    """Derive one stable Message-ID for retries of the same run."""
    run_key = "{}|{}".format(report.get("deviceId") or "", report.get("runId") or "")
    digest = hashlib.sha256(run_key.encode("utf-8")).hexdigest()[:32]
    domain = parseaddr(sender)[1].split("@", 1)[-1].strip() or "localhost"
    return "<teambuy-{}@{}>".format(digest, domain)


def _smtp_refusal_summary(refused: dict) -> list[dict]:
    """Keep SMTP refusal codes/text while dropping recipient addresses."""
    summary = []
    for response in (refused or {}).values():
        code = None
        message = ""
        if isinstance(response, (tuple, list)) and response:
            code = response[0]
            if len(response) > 1:
                message = response[1]
        else:
            message = response
        if isinstance(message, bytes):
            message = message.decode("utf-8", "replace")
        try:
            code = int(code) if code is not None else None
        except (TypeError, ValueError):
            code = None
        summary.append({
            "code": code,
            "message": _one_line(message, 240),
        })
    return summary


def _forward_outcome_counts(forward: dict, queue: dict) -> tuple[int, int, int, int, int, int]:
    """Derive recipient totals from per-target outcomes when they are present.

    Older device summaries could increment failureCount for a navigation error
    after sending. Per-target rows are the authority for recipient outcomes;
    workflow cleanup is rendered separately below.
    """
    targets = [item for item in forward.get("targetResults") or [] if isinstance(item, dict)]
    expected_count = max(
        len(targets),
        _nonnegative_int(forward.get("targetCount")),
        _nonnegative_int(queue.get("targetCount")),
    )
    if targets:
        confirmed = sum(item.get("status") == "sent_ui_confirmed" for item in targets)
        action_sent = sum(item.get("status") == "send_action_sent_unverified" for item in targets)
        failed = len(targets) - confirmed - action_sent
        return expected_count, len(targets), confirmed, action_sent, failed, max(0, expected_count - len(targets))

    confirmed = _nonnegative_int(forward.get("successCount"))
    action_sent = _nonnegative_int(
        forward.get("unconfirmedCount")
        if forward.get("unconfirmedCount") is not None
        else forward.get("actionSentCount")
    )
    failed = _nonnegative_int(forward.get("failureCount"))
    recorded_count = confirmed + action_sent + failed
    expected_count = expected_count or recorded_count
    return expected_count, recorded_count, confirmed, action_sent, failed, max(0, expected_count - recorded_count)


def _cleanup_failure_count(forward: dict, queue: dict) -> int:
    """Read explicit cleanup counts, with a narrow legacy error-message fallback."""
    for source in (forward, queue):
        if "cleanupFailureCount" in source:
            try:
                return max(0, int(source.get("cleanupFailureCount") or 0))
            except (TypeError, ValueError):
                pass
    account_runs = queue.get("accountRuns") or []
    if account_runs and any("cleanupFailureCount" in row for row in account_runs if isinstance(row, dict)):
        total = 0
        for row in account_runs:
            if isinstance(row, dict):
                try:
                    total += max(0, int(row.get("cleanupFailureCount") or 0))
                except (TypeError, ValueError):
                    continue
        return total
    cleanup_markers = ("post_send_cleanup", "cleanup_home", "未确认微信会话列表", "返回微信会话列表")
    return sum(
        1
        for row in queue.get("errors") or []
        if isinstance(row, dict)
        and any(marker in "{} {}".format(row.get("stage") or "", row.get("error") or "") for marker in cleanup_markers)
    )


def _account_forward_outcomes(report: dict, forward: dict, queue: dict) -> list[dict]:
    """Build per-account recipient counts without treating workflow errors as sends."""
    account_order: list[str] = []
    account_labels: dict[str, tuple[str, str]] = {}
    account_runs: dict[str, dict] = {}
    target_rows: dict[str, list[dict]] = {}

    def register(account_id: object, nickname: object = "") -> str:
        key = str(account_id or "").strip()
        if not key:
            return ""
        if key not in account_labels:
            account_order.append(key)
            account_labels[key] = (
                _one_line(key, 128),
                _one_line(nickname, 80),
            )
        elif nickname and not account_labels[key][1]:
            account_labels[key] = (account_labels[key][0], _one_line(nickname, 80))
        return key

    for account in report.get("accounts") or []:
        if not isinstance(account, dict):
            continue
        register(account.get("wechatId") or account.get("accountId"), account.get("nickname"))

    for run in queue.get("accountRuns") or []:
        if not isinstance(run, dict):
            continue
        key = register(
            run.get("wechatAccountId") or run.get("accountId"),
            run.get("nickname"),
        )
        if key:
            account_runs[key] = run

    for row in forward.get("targetResults") or []:
        if not isinstance(row, dict):
            continue
        key = register(row.get("wechatAccountId") or row.get("accountId"))
        if key:
            target_rows.setdefault(key, []).append(row)

    # Older reports only carried an aggregate queue target count. If all
    # returned target rows belong to one account, that aggregate can still be
    # assigned safely to that account; otherwise keep per-account row counts.
    active_target_accounts = [key for key, rows in target_rows.items() if rows]
    aggregate_target_count = _nonnegative_int(queue.get("targetCount"))
    outcomes: list[dict] = []
    for key in account_order:
        run = account_runs.get(key) or {}
        rows = target_rows.get(key) or []
        target_count = _nonnegative_int(run.get("targetCount"))
        if not target_count and rows and not account_runs and len(active_target_accounts) == 1:
            target_count = aggregate_target_count
        if not target_count:
            target_count = len(rows)
        # Same-name test targets can expand on the phone; recordedCount keeps
        # every returned physical target row visible alongside the plan.

        if rows:
            confirmed_count = sum(
                row.get("status") == "sent_ui_confirmed" for row in rows
            )
            action_sent_count = sum(
                row.get("status") == "send_action_sent_unverified" for row in rows
            )
            failure_count = len(rows) - confirmed_count - action_sent_count
            recorded_count = len(rows)
        else:
            # If a future sender supplies accountRuns without target rows, use
            # its explicit counts and leave the remainder as unreported.
            confirmed_count = _nonnegative_int(run.get("successCount"))
            action_sent_count = _nonnegative_int(
                run.get("actionSentCount")
                if run.get("actionSentCount") is not None
                else run.get("unconfirmedCount")
            )
            failure_count = _nonnegative_int(run.get("failureCount"))
            recorded_count = confirmed_count + action_sent_count + failure_count

        outcomes.append(
            {
                "accountId": key,
                "displayId": account_labels[key][0],
                "nickname": account_labels[key][1],
                "targetCount": target_count,
                "recordedCount": recorded_count,
                "confirmedCount": confirmed_count,
                "actionSentCount": action_sent_count,
                "failureCount": max(0, failure_count),
                "unreportedCount": max(0, target_count - recorded_count),
            }
        )
    return outcomes


def _report_body(report: dict) -> str:
    scan_config = report.get("scanConfig") if isinstance(report.get("scanConfig"), dict) else {}
    scan_prefixes = [
        _one_line(item, 24)
        for item in scan_config.get("searchPrefixes") or []
        if _one_line(item, 24)
    ]
    lines = [
        "teamBuy 微信助手运行完成",
        "状态：{}".format(_one_line(report.get("status"), 40)),
        "运行编号：{}".format(_one_line(report.get("runId"), 128)),
        "设备：{}".format(_one_line(report.get("deviceId"), 128)),
        "批次：{}".format(_one_line(report.get("batchNo"), 20)),
        "群编号：{}".format(", ".join(_one_line(item, 40) for item in report.get("groupCodes") or [])),
    ]
    if scan_prefixes:
        scan_mode = (
            "仅扫描并同步，不创建发送任务"
            if scan_config.get("scanOnly") is True
            else "扫描并按发送方案创建任务"
        )
        lines.append("扫描范围：{}；运行方式：{}".format(", ".join(scan_prefixes), scan_mode))
    lines.extend(["", "账号扫描："])
    for account in report.get("accounts") or []:
        lines.append(
            "- {} / {}：{} 个群，状态 {}，扫描 {} 秒，新增 {}，更新 {}".format(
                _one_line(account.get("wechatId") or account.get("accountId"), 128),
                _one_line(account.get("nickname"), 80),
                _one_line(account.get("groupCount"), 20),
                _one_line(account.get("status"), 40),
                _one_line(account.get("scanDurationSeconds"), 20),
                _one_line(account.get("createdCount"), 20),
                _one_line(account.get("updatedCount"), 20),
            )
    )
    forward = report.get("forwardSummary") if isinstance(report.get("forwardSummary"), dict) else {}
    queue = report.get("queueSummary") if isinstance(report.get("queueSummary"), dict) else {}
    (
        target_count,
        recorded_target_count,
        confirmed_count,
        action_sent_count,
        target_failure_count,
        unreported_target_count,
    ) = _forward_outcome_counts(forward, queue)
    account_outcomes = _account_forward_outcomes(report, forward, queue)
    if account_outcomes:
        lines.extend(["", "账号推送统计："])
        for account in account_outcomes:
            label = account["displayId"]
            if account["nickname"]:
                label = "{} / {}".format(label, account["nickname"])
            lines.append(
                "- {}：计划推送 {} 个，收到结果 {} 个，UI确认成功 {} 个，发送动作待确认 {} 个，失败/未发送 {} 个，结果未回报 {} 个".format(
                    label,
                    account["targetCount"],
                    account["recordedCount"],
                    account["confirmedCount"],
                    account["actionSentCount"],
                    account["failureCount"],
                    account["unreportedCount"],
                )
            )
    lines.extend(
        [
            "",
            "转发汇总：耗时 {} 秒，PC目标 {} 个（收到结果 {} 个），UI确认送达 {} 个，发送动作已发出待确认 {} 个，目标未发送/失败 {} 个，结果未回报 {} 个".format(
                _one_line(forward.get("durationSeconds"), 20),
                target_count,
                recorded_target_count,
                confirmed_count,
                action_sent_count,
                target_failure_count,
                unreported_target_count,
            ),
        ]
    )
    for target in forward.get("targetResults") or []:
        if isinstance(target, dict):
            lines.append(
                "- 目标 {} / {}：{}，原因 {}".format(
                    _one_line(target.get("wechatAccountId"), 80),
                    _one_line(target.get("groupName"), 100),
                    _one_line(target.get("status"), 40),
                    _one_line(target.get("error") or "-", 180),
                )
            )
    cleanup_failures = _cleanup_failure_count(forward, queue)
    workflow_failures = max(
        cleanup_failures,
        _nonnegative_int(
            queue.get("workflowFailureCount") or forward.get("workflowFailureCount")
        ),
    )
    if cleanup_failures:
        # Keep a degraded run label, but make explicit that cleanup is not a
        # per-recipient send failure when every returned target has an outcome.
        if target_failure_count == 0:
            lines[1] = "状态：{}（微信页面收尾未确认；不计为目标群发送失败）".format(
                _one_line(report.get("status"), 40)
            )
        lines.append(
            "微信页面收尾：{} 项未确认（不计入目标群发送失败）。".format(cleanup_failures)
        )
    elif workflow_failures:
        lines.append(
            "自动化流程异常：{} 项（与目标群发送结果分开统计）。".format(workflow_failures)
        )
    for error in queue.get("errors") or []:
        if isinstance(error, dict):
            detail = _one_line(error.get("error"), 240)
            if detail:
                lines.append(
                    "流程提示 {}：{}".format(
                        _one_line(error.get("wechatAccountId") or "", 80),
                        detail,
                    )
                )
    lines.extend(
        [
            "",
            "扫描汇总：{}".format(_one_line(report.get("scanSummary"), 1000)),
            "任务汇总：{}".format(_one_line(queue, 1000)),
        ]
    )
    return "\n".join(lines)


def send_automation_completion_email(report: dict) -> dict:
    """Send a completion summary using only server-side SMTP configuration."""

    if not settings.automation_completion_email_enabled:
        return {
            "configured": False,
            "sent": False,
            "reason": "automation_completion_email_disabled",
        }

    recipient = _recipient(settings.automation_completion_email_to)
    missing = [
        name
        for name, value in (
            ("AUTOMATION_SMTP_HOST", settings.automation_smtp_host),
            ("AUTOMATION_SMTP_FROM", settings.automation_smtp_from or settings.automation_smtp_username),
        )
        if not str(value or "").strip()
    ]
    if not recipient:
        return {"configured": False, "sent": False, "reason": "invalid_recipient"}
    if missing:
        return {
            "configured": False,
            "sent": False,
            "reason": "smtp_not_configured",
            "missing": missing,
        }

    message = EmailMessage()
    message["Subject"] = "teamBuy 微信助手运行完成：{} / 批次{}".format(
        _one_line(report.get("status"), 40),
        _one_line(report.get("batchNo"), 20),
    )
    message["From"] = settings.automation_smtp_from or settings.automation_smtp_username
    message["To"] = recipient
    sender = settings.automation_smtp_from or settings.automation_smtp_username
    message_id = _message_id(report, sender)
    recipient_fingerprint = _recipient_fingerprint(recipient)
    message["Message-ID"] = message_id
    message.set_content(_report_body(report))

    try:
        refused = {}
        if settings.automation_smtp_use_ssl:
            with smtplib.SMTP_SSL(
                settings.automation_smtp_host,
                settings.automation_smtp_port,
                timeout=settings.automation_smtp_timeout_seconds,
            ) as smtp:
                if settings.automation_smtp_username:
                    smtp.login(settings.automation_smtp_username, settings.automation_smtp_password)
                refused = smtp.send_message(message) or {}
        else:
            with smtplib.SMTP(
                settings.automation_smtp_host,
                settings.automation_smtp_port,
                timeout=settings.automation_smtp_timeout_seconds,
            ) as smtp:
                smtp.ehlo()
                smtp.starttls()
                smtp.ehlo()
                if settings.automation_smtp_username:
                    smtp.login(settings.automation_smtp_username, settings.automation_smtp_password)
                refused = smtp.send_message(message) or {}
    except Exception as exc:
        error = _one_line(exc, 240).replace(recipient, "<redacted-recipient>")
        return {
            "configured": True,
            "sent": False,
            "smtpAccepted": False,
            "reason": "smtp_send_failed",
            "errorType": type(exc).__name__,
            "error": error,
            "messageId": message_id,
            "recipientFingerprint": recipient_fingerprint,
        }
    refusals = _smtp_refusal_summary(refused)
    if refusals:
        return {
            "configured": True,
            "sent": False,
            "smtpAccepted": False,
            "reason": "smtp_recipient_rejected",
            "messageId": message_id,
            "recipientFingerprint": recipient_fingerprint,
            "refusedCount": len(refusals),
            "refused": refusals,
        }
    return {
        "configured": True,
        "sent": True,
        "smtpAccepted": True,
        "messageId": message_id,
        "recipientFingerprint": recipient_fingerprint,
    }
