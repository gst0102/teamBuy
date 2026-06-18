from __future__ import annotations

import json
from urllib.parse import parse_qs, urlparse

from app.models.domain import ImportBatch, RawMessage, WecomArchiveMessage
from app.schemas.skills import ContentLinkPayload, ContentMediaPayload, ContentObjectPayload, ContentParticipantPayload


BEIKE_CITY_SLUGS = {
    "150200": "baotou",
}


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
            elif message.msgType == "weapp":
                miniapp = self._miniapp_metadata(content)
                text_blocks.extend(self._miniapp_text_blocks(miniapp))

        miniapp_metadata = next(
            (self._miniapp_metadata(message.content) for message in messages if message.msgType == "weapp"),
            {},
        )
        return ContentObjectPayload(
            sourceType="miniapp_card" if miniapp_metadata else self._source_type(batch.sourceType),
            title=miniapp_metadata.get("title") or batch.titleCandidate,
            textBlocks=text_blocks,
            media=media,
            links=[link for link in links if link.url],
            metadata={"miniapp": miniapp_metadata} if miniapp_metadata else {},
            participants=self._unique_participants(participants),
            timestamps=timestamps,
            sourceRefs=[batch.id],
            rawMessageIds=[message.id for message in messages],
        )

    def from_wecom_archive_message(self, message: WecomArchiveMessage) -> ContentObjectPayload:
        payload = message.decryptedPayload or message.rawPayload
        text_blocks: list[str] = []
        media: list[ContentMediaPayload] = []
        links: list[ContentLinkPayload] = []

        msg_type = message.msgType or payload.get("msgtype") or "unknown"
        if msg_type == "text":
            content = payload.get("text", {}).get("content") if isinstance(payload.get("text"), dict) else payload.get("content")
            if content:
                text_blocks.append(str(content).strip())
        elif msg_type == "link":
            link = payload.get("link") if isinstance(payload.get("link"), dict) else payload
            links.append(
                ContentLinkPayload(
                    url=str(link.get("link_url") or link.get("url") or "").strip(),
                    title=str(link.get("title") or "").strip() or None,
                    description=str(link.get("description") or "").strip() or None,
                    coverUrl=str(link.get("image_url") or link.get("thumbUrl") or "").strip() or None,
                )
            )
        elif msg_type in {"image", "video", "file"}:
            media_id = self._archive_media_id(payload, msg_type)
            media.append(
                ContentMediaPayload(
                    type=msg_type,
                    url=None,
                    mediaId=media_id,
                    title=str(payload.get("filename") or payload.get("file", {}).get("filename") or "").strip() or None,
                    sourceRef=message.id,
                )
            )
            text_blocks.append(f"收到{msg_type}素材，媒体稍后转存。")
        elif msg_type == "location":
            location = payload.get("location") if isinstance(payload.get("location"), dict) else payload
            label = str(location.get("address") or location.get("title") or "").strip()
            if label:
                text_blocks.append(f"位置：{label}")
        elif msg_type == "note":
            self._append_archive_note_parts(message, payload, text_blocks, media, links)
        elif msg_type == "weapp":
            miniapp_payload = payload.get("weapp") if isinstance(payload.get("weapp"), dict) else payload
            miniapp = self._miniapp_metadata(miniapp_payload)
            text_blocks.extend(self._miniapp_text_blocks(miniapp))
        else:
            text = payload.get("content") or payload.get("text")
            if text:
                text_blocks.append(str(text).strip())

        title = self._archive_title(payload, msg_type, text_blocks, links)
        if msg_type == "weapp":
            miniapp_payload = payload.get("weapp") if isinstance(payload.get("weapp"), dict) else payload
            miniapp = self._miniapp_metadata(miniapp_payload)
            title = miniapp.get("title") or title
        return ContentObjectPayload(
            sourceType="link_article" if msg_type == "link" else "miniapp_card" if msg_type == "weapp" else "wecom_thread",
            title=title,
            textBlocks=[item for item in text_blocks if item],
            media=media,
            links=[link for link in links if link.url],
            metadata={"miniapp": miniapp} if msg_type == "weapp" else {},
            participants=[
                ContentParticipantPayload(id=message.fromUser, role="from_user"),
                *[ContentParticipantPayload(id=item, role="to_user") for item in message.toList],
            ],
            timestamps=[message.msgTime] if message.msgTime else [],
            sourceRefs=[message.id],
            rawMessageIds=[message.id],
        )

    def _source_type(self, batch_source_type: str) -> str:
        if batch_source_type == "miniapp_link":
            return "miniapp_card"
        if batch_source_type == "wechat_note":
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

    def _archive_media_id(self, payload: dict, msg_type: str) -> str | None:
        value = payload.get(msg_type)
        if isinstance(value, dict):
            return value.get("sdkfileid") or value.get("media_id") or value.get("md5sum")
        return payload.get("sdkfileid") or payload.get("media_id")

    def _append_archive_note_parts(
        self,
        message: WecomArchiveMessage,
        payload: dict,
        text_blocks: list[str],
        media: list[ContentMediaPayload],
        links: list[ContentLinkPayload],
    ) -> None:
        items = payload.get("info", {}).get("items") if isinstance(payload.get("info"), dict) else []
        if not isinstance(items, list):
            return
        for index, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            part_type = item.get("msg_type") or item.get("msgType")
            content = self._parse_note_content(item.get("content"))
            source_ref = f"{message.id}#{index}"
            if part_type == "text":
                text = str(content.get("content") or "").strip()
                if text and text not in {"[图片]", "[视频]", "[文件]"}:
                    text_blocks.append(text)
            elif part_type == "location":
                label = str(content.get("address") or content.get("title") or "").strip()
                if label:
                    text_blocks.append(f"位置：{label}")
            elif part_type == "link":
                links.append(
                    ContentLinkPayload(
                        url=str(content.get("link_url") or content.get("url") or "").strip(),
                        title=str(content.get("title") or "").strip() or None,
                        description=str(content.get("description") or "").strip() or None,
                        coverUrl=str(content.get("image_url") or content.get("thumbUrl") or "").strip() or None,
                    )
                )
            elif part_type in {"image", "video", "file"}:
                media.append(
                    ContentMediaPayload(
                        type=part_type,
                        url=None,
                        mediaId=content.get("sdkfileid") or content.get("media_id") or content.get("md5sum"),
                        title=str(content.get("filename") or "").strip() or None,
                        sourceRef=source_ref,
                    )
                )

    def _parse_note_content(self, value) -> dict:
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError:
                return {"content": value}
            return parsed if isinstance(parsed, dict) else {"content": value}
        return {}

    def _miniapp_metadata(self, payload: dict) -> dict:
        page_path = str(payload.get("pagepath") or payload.get("pagePath") or "").strip()
        query = parse_qs(urlparse(page_path).query)
        city_id = (query.get("cityId") or query.get("city_id") or [""])[0]
        house_code = (query.get("houseCode") or query.get("house_code") or [""])[0]
        appid = str(payload.get("appid") or payload.get("appId") or "").strip()
        display_name = str(payload.get("displayname") or payload.get("displayName") or "").strip()
        description = str(payload.get("description") or payload.get("desc") or "").strip()
        metadata = {
            "appid": appid,
            "username": str(payload.get("username") or "").strip(),
            "title": str(payload.get("title") or "").strip(),
            "description": description,
            "displayName": display_name,
            "pagePath": page_path,
            "houseCode": house_code,
            "cityId": city_id,
            "source": (query.get("source") or [""])[0],
        }
        web_url = self._miniapp_web_url(metadata)
        if web_url:
            metadata["webUrl"] = web_url
        return metadata

    def _miniapp_web_url(self, miniapp: dict) -> str:
        source_text = " ".join(
            str(miniapp.get(key) or "")
            for key in ["appid", "username", "displayName", "description", "source"]
        )
        if "贝壳" not in source_text and "wxcfd8224218167d98" not in source_text:
            return ""
        city_slug = BEIKE_CITY_SLUGS.get(str(miniapp.get("cityId") or ""))
        house_code = str(miniapp.get("houseCode") or "").strip()
        if not city_slug or not house_code:
            return ""
        return f"https://m.ke.com/{city_slug}/ershoufang/{house_code}.html"

    def _miniapp_text_blocks(self, miniapp: dict) -> list[str]:
        parts = [
            f"小程序标题：{miniapp.get('title')}" if miniapp.get("title") else "",
            f"小程序来源：{miniapp.get('displayName') or miniapp.get('description')}" if miniapp.get("displayName") or miniapp.get("description") else "",
            f"小程序 appid：{miniapp.get('appid')}" if miniapp.get("appid") else "",
            f"房源编码：{miniapp.get('houseCode')}" if miniapp.get("houseCode") else "",
        ]
        return [part for part in parts if part]

    def _archive_title(
        self,
        payload: dict,
        msg_type: str,
        text_blocks: list[str],
        links: list[ContentLinkPayload],
    ) -> str:
        if links and links[0].title:
            return links[0].title
        if text_blocks:
            return text_blocks[0][:40]
        return f"企业微信{msg_type}归档"
