from __future__ import annotations

from app.models.domain import ImportBatch, RawMessage
from app.services.helpers import new_id
from app.services.time_utils import now_iso, parse_iso


WINDOW_SECONDS = 60


def detect_source_type(messages: list[RawMessage]) -> str:
    if any(item.msgType == "weapp" for item in messages):
        return "miniapp_link"
    for item in messages:
        if item.msgType == "link":
            url = str(item.content.get("url", "")).lower()
            if "mp.weixin.qq.com" in url:
                return "mp_link"
            if "servicewechat.com" in url or "miniprogram" in url:
                return "miniapp_link"
            return "web_link"
    if any(item.msgType in {"image", "video"} for item in messages):
        return "wechat_note"
    return "unknown"


def resolve_title_candidate(messages: list[RawMessage]) -> str:
    for item in messages:
        if item.msgType == "weapp":
            title = str(item.content.get("title", "")).strip()
            if title:
                return title
    for item in messages:
        if item.msgType == "link":
            title = str(item.content.get("title", "")).strip()
            if title:
                return title
    for item in messages:
        if item.msgType == "text":
            text = str(item.content.get("text", "")).strip()
            if text:
                return text[:40]
    return "未命名素材"


class MessageAggregator:
    def aggregate(self, messages: list[RawMessage]) -> list[ImportBatch]:
        if not messages:
            return []

        ordered = sorted(messages, key=lambda item: parse_iso(item.receivedAt))
        batches: list[list[RawMessage]] = []
        current: list[RawMessage] = [ordered[0]]

        for message in ordered[1:]:
            last_message = current[-1]
            is_same_source = (
                message.externalUserId == last_message.externalUserId
                and message.conversationId == last_message.conversationId
            )
            within_window = (
                parse_iso(message.receivedAt) - parse_iso(last_message.receivedAt)
            ).total_seconds() <= WINDOW_SECONDS
            if is_same_source and within_window:
                current.append(message)
            else:
                batches.append(current)
                current = [message]
        batches.append(current)

        aggregated_batches: list[ImportBatch] = []
        for group in batches:
            now = now_iso()
            aggregated_batches.append(
                ImportBatch(
                    id=new_id("import"),
                    externalUserId=group[0].externalUserId,
                    conversationId=group[0].conversationId,
                    status="pending",
                    titleCandidate=resolve_title_candidate(group),
                    sourceType=detect_source_type(group),
                    rawMessageIds=[item.id for item in group],
                    startedAt=group[0].receivedAt,
                    endedAt=group[-1].receivedAt,
                    createdAt=now,
                    updatedAt=now,
                )
            )
        return aggregated_batches
