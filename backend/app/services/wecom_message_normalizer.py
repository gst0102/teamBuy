from __future__ import annotations

from datetime import datetime
from typing import Any

from app.services.time_utils import SHANGHAI


class WecomMessageNormalizer:
    def normalize_messages(
        self,
        messages: list[dict[str, Any]],
        fallback_external_user_id: str | None = None,
        fallback_conversation_id: str | None = None,
    ) -> list[dict]:
        return [
            self.normalize_message(item, fallback_external_user_id, fallback_conversation_id)
            for item in messages
        ]

    def normalize_message(
        self,
        message: dict[str, Any],
        fallback_external_user_id: str | None = None,
        fallback_conversation_id: str | None = None,
    ) -> dict:
        msg_type = message.get("msgType") or message.get("msgtype") or "unknown"
        content = self._normalize_content(msg_type, message)
        received_at = message.get("receivedAt") or self._normalize_time(message.get("send_time") or message.get("sendTime"))
        token = message.get("wecomToken") or message.get("token")
        open_kfid = message.get("openKfid") or message.get("open_kfid")
        external_user_id = (
            message.get("externalUserId")
            or message.get("external_userid")
            or message.get("external_user_id")
            or fallback_external_user_id
        )
        conversation_id = (
            message.get("conversationId")
            or message.get("conversation_id")
            or token
            or fallback_conversation_id
        )

        return {
            "wecomMsgId": message.get("wecomMsgId") or message.get("msgid") or message.get("msg_id"),
            "wecomToken": token,
            "openKfid": open_kfid,
            "externalUserId": external_user_id,
            "conversationId": conversation_id,
            "msgType": msg_type,
            "content": content,
            "mediaId": message.get("mediaId") or self._extract_media_id(msg_type, message),
            "receivedAt": received_at,
        }

    def _normalize_content(self, msg_type: str, message: dict[str, Any]) -> dict:
        if "content" in message and isinstance(message["content"], dict):
            return message["content"]
        if msg_type == "text":
            text_payload = message.get("text") or {}
            return {"text": text_payload.get("content") or message.get("content") or ""}
        if msg_type == "image":
            image_payload = message.get("image") or {}
            return {"caption": image_payload.get("caption") or image_payload.get("filename") or ""}
        if msg_type == "video":
            video_payload = message.get("video") or {}
            return {"caption": video_payload.get("caption") or video_payload.get("filename") or ""}
        if msg_type == "link":
            link_payload = message.get("link") or {}
            return {
                "title": link_payload.get("title") or "",
                "description": link_payload.get("desc") or link_payload.get("description") or "",
                "url": link_payload.get("url") or "",
                "thumbUrl": link_payload.get("picurl") or link_payload.get("thumb_url") or "",
            }
        if msg_type == "location":
            location_payload = message.get("location") or {}
            return {
                "label": location_payload.get("name") or location_payload.get("address") or "",
                "latitude": location_payload.get("latitude"),
                "longitude": location_payload.get("longitude"),
            }
        return message.get("content") if isinstance(message.get("content"), dict) else {}

    def _extract_media_id(self, msg_type: str, message: dict[str, Any]) -> str | None:
        payload = message.get(msg_type) or {}
        return payload.get("media_id") or payload.get("mediaId")

    def _normalize_time(self, value: Any) -> str:
        if value is None:
            return datetime.now(tz=SHANGHAI).isoformat()
        if isinstance(value, str) and "T" in value:
            return value
        timestamp = int(value)
        if timestamp > 10_000_000_000:
            timestamp = timestamp // 1000
        return datetime.fromtimestamp(timestamp, tz=SHANGHAI).isoformat()
