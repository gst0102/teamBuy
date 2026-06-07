from __future__ import annotations

from app.models.domain import Card, CardMedia, ImportBatch, RawMessage, RelayConfig
from app.services.helpers import extract_phone, new_id
from app.services.time_utils import now_iso


class CardParserService:
    def build_card_draft(self, owner_user_id: str, batch: ImportBatch, messages: list[RawMessage]) -> Card:
        created_at = now_iso()
        text_blocks: list[str] = []
        image_urls: list[tuple[str, str | None]] = []
        source_url: str | None = None
        title_candidate = batch.titleCandidate or "未命名素材"
        project_name: str | None = None
        location_text: str | None = None
        video_media: list[tuple[str, str | None]] = []

        for message in messages:
            content = message.content
            if message.msgType == "text":
                text = str(content.get("text", "")).strip()
                if text:
                    text_blocks.append(text)
            elif message.msgType == "image" and message.localMediaUrl:
                image_urls.append((message.localMediaUrl, message.mediaId))
            elif message.msgType == "link":
                link_title = str(content.get("title", "")).strip()
                link_desc = str(content.get("description", "")).strip()
                source_url = str(content.get("url", "")).strip() or source_url
                if link_title and title_candidate == batch.titleCandidate:
                    title_candidate = link_title
                if link_desc:
                    text_blocks.append(link_desc)
            elif message.msgType == "location":
                location_text = str(content.get("label", "")).strip() or location_text
            elif message.msgType == "video" and message.localMediaUrl:
                video_media.append((message.localMediaUrl, message.mediaId))

        title = title_candidate
        if not title.strip():
            title = next((block for block in text_blocks if block.strip()), "未命名素材")

        detail_text = "\n\n".join(text_blocks).strip()
        phone = extract_phone(detail_text)
        if text_blocks:
            project_name = project_name or text_blocks[0][:30]

        media: list[CardMedia] = []
        sort_order = 1
        for url, source_media_id in image_urls:
            media.append(
                CardMedia(
                    id=new_id("card_media"),
                    cardId="",
                    type="image",
                    url=url,
                    sortOrder=sort_order,
                    sourceMediaId=source_media_id,
                    createdAt=created_at,
                )
            )
            sort_order += 1
        for url, source_media_id in video_media:
            media.append(
                CardMedia(
                    id=new_id("card_media"),
                    cardId="",
                    type="video",
                    url=url,
                    sortOrder=sort_order,
                    sourceMediaId=source_media_id,
                    createdAt=created_at,
                )
            )
            sort_order += 1

        card_id = new_id("card")
        for item in media:
            item.cardId = card_id

        cover_url = image_urls[0][0] if image_urls else None
        enabled_fields = ["projectName", "locationText", "phone", "relayNotice", "sourceUrl"]

        return Card(
            id=card_id,
            ownerUserId=owner_user_id,
            importBatchId=batch.id,
            status="draft",
            title=title,
            coverUrl=cover_url,
            detailText=detail_text,
            projectName=project_name,
            locationText=location_text,
            phone=phone,
            relayNotice="感兴趣请实名接龙报名。",
            sourceUrl=source_url,
            enabledFields=enabled_fields,
            categoryIds=[],
            media=media,
            relayConfig=RelayConfig(enabled=True, requirePhone=False, requireAddress=False),
            createdAt=created_at,
            updatedAt=created_at,
        )

