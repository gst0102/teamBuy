from __future__ import annotations

from app.models.domain import ImportBatch, RawMessage
from app.schemas.skills import ContentLinkPayload, ContentMediaPayload, ContentObjectPayload, ContentParticipantPayload


class ContentObjectAdapter:
    def from_wecom_batch(self, batch: ImportBatch, messages: list[RawMessage]) -> ContentObjectPayload:
        text_blocks: list[str] = []
        media: list[ContentMediaPayload] = []
        links: list[ContentLinkPayload] = []
        participants: list[ContentParticipantPayload] = []
        timestamps: list[str] = []

        for message in messages:
            content = message.content
            timestamps.append(message.receivedAt)
            participants.append(ContentParticipantPayload(id=message.externalUserId, role="external_user"))
            if message.msgType == "text":
                text = str(content.get("text", "")).strip()
                if text:
                    text_blocks.append(text)
            elif message.msgType in {"image", "video", "file"}:
                media.append(
                    ContentMediaPayload(
                        type=message.msgType,
                        url=message.localMediaUrl,
                        mediaId=message.mediaId,
                        title=str(content.get("filename", "")).strip() or None,
                        sourceRef=message.id,
                    )
                )
            elif message.msgType == "link":
                links.append(
                    ContentLinkPayload(
                        url=str(content.get("url", "")).strip(),
                        title=str(content.get("title", "")).strip() or None,
                        description=str(content.get("description", "")).strip() or None,
                        coverUrl=str(content.get("thumbUrl", "")).strip() or None,
                    )
                )
            elif message.msgType == "location":
                location = str(content.get("label", "")).strip()
                if location:
                    text_blocks.append(f"位置：{location}")

        return ContentObjectPayload(
            sourceType=self._source_type(batch.sourceType),
            title=batch.titleCandidate,
            textBlocks=text_blocks,
            media=media,
            links=[link for link in links if link.url],
            participants=self._unique_participants(participants),
            timestamps=timestamps,
            sourceRefs=[batch.id],
            rawMessageIds=[message.id for message in messages],
        )

    def _source_type(self, batch_source_type: str) -> str:
        if batch_source_type in {"wechat_note", "miniapp_link"}:
            return "wecom_thread"
        if batch_source_type in {"mp_link", "web_link"}:
            return "link_article"
        return "wecom_thread"

    def _unique_participants(self, participants: list[ContentParticipantPayload]) -> list[ContentParticipantPayload]:
        seen: set[tuple[str | None, str | None]] = set()
        result: list[ContentParticipantPayload] = []
        for participant in participants:
            key = (participant.id, participant.role)
            if key in seen:
                continue
            seen.add(key)
            result.append(participant)
        return result
