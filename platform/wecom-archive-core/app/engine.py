from __future__ import annotations

import asyncio
import hashlib
import json
from typing import Any

import httpx

from app.codec import SealedPayload, digest, media_token
from app.config import ProjectRoute, Settings
from app.sdk import FinanceSdkClient
from app.store import CursorConflict, PostgresStore


def _media_value(key: str) -> bool:
    return key.lower().replace("_", "") == "sdkfileid"


def _sanitize(value: Any, *, event_id: str, media_key: bytes, refs: list[dict[str, str]], path: str = "") -> Any:
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else key
            if _media_value(str(key)) and isinstance(child, str) and child:
                token = media_token(media_key, event_id, child_path, child)
                public_media_id = f"{event_id}:{token}"
                refs.append({"mediaId": public_media_id, "path": child_path})
                result["sdkfileid"] = public_media_id
            else:
                result[key] = _sanitize(child, event_id=event_id, media_key=media_key, refs=refs, path=child_path)
        return result
    if isinstance(value, list):
        return [_sanitize(item, event_id=event_id, media_key=media_key, refs=refs, path=f"{path}[{index}]") for index, item in enumerate(value)]
    if isinstance(value, str) and value.lstrip().startswith(("{", "[")):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return value
        if isinstance(parsed, (dict, list)):
            sanitized = _sanitize(parsed, event_id=event_id, media_key=media_key, refs=refs, path=path)
            if sanitized != parsed:
                return json.dumps(sanitized, ensure_ascii=False, separators=(",", ":"))
    return value


def normalize_message(raw: dict[str, Any], stream_key: str, media_key: bytes) -> tuple[dict[str, Any], dict[str, Any]]:
    seq = int(raw.get("seq") or 0)
    if seq <= 0:
        raise ValueError("archive message has no valid seq")
    event_id = f"archive_{digest(stream_key)}_{seq}"
    payload = raw.get("decryptedPayload") if isinstance(raw.get("decryptedPayload"), dict) else {}
    refs: list[dict[str, str]] = []
    safe_payload = _sanitize(payload, event_id=event_id, media_key=media_key, refs=refs)
    msg_id = raw.get("msgid") or raw.get("msgId")
    room_id = raw.get("roomid") or raw.get("roomId")
    message_type = raw.get("msgtype") or raw.get("msgType") or ""
    message_time = raw.get("msgtime") or raw.get("msgTime")
    safe_message = {
        "seq": seq,
        "msgId": msg_id,
        "action": raw.get("action"),
        "fromUser": raw.get("from") or raw.get("fromUser"),
        "toList": raw.get("tolist") or raw.get("toList") or [],
        "roomId": room_id,
        "msgTime": message_time,
        "msgType": message_type,
        "decryptedPayload": safe_payload,
        "mediaRefs": refs,
    }
    event = {
        "schemaVersion": 1,
        "eventId": event_id,
        "streamKey": stream_key,
        "seq": seq,
        "messageIdHash": digest(msg_id),
        "roomIdHash": digest(room_id),
        "messageType": str(message_type),
        "messageTime": message_time,
        "message": safe_message,
    }
    return event, {"rawMessage": raw, "eventId": event_id}


class ArchiveCoreEngine:
    def __init__(self, settings: Settings, store: PostgresStore, client: FinanceSdkClient):
        self.settings = settings
        self.store = store
        self.client = client
        self.sealed = SealedPayload(settings.data_key)
        self.stream_key = "archive_" + digest(settings.corp_id)
        self.routes = {route.project_id: route for route in settings.projects}

    def ingest_once(self) -> dict[str, Any]:
        start_seq = self.store.cursor(self.stream_key)
        raw_messages = self.client.pull_and_decrypt(start_seq, self.settings.batch_limit)
        if not raw_messages:
            return {"startSeq": start_seq, "pulled": 0, "inserted": 0, "deliveries": 0}
        events: list[dict[str, Any]] = []
        sealed_payloads: dict[str, str] = {}
        route_ids: dict[str, list[str]] = {}
        highest_seq = start_seq
        for raw in raw_messages:
            event, metadata = normalize_message(raw, self.stream_key, self.settings.media_token_key)
            events.append(event)
            sealed_payloads[event["eventId"]] = self.sealed.seal(metadata["rawMessage"])
            room_id = str(raw.get("roomid") or "")
            message_type = str(raw.get("msgtype") or "")
            route_ids[event["eventId"]] = [
                route.project_id
                for route in self.settings.projects
                if route.matches(
                    room_id,
                    message_type,
                    from_user=str(raw.get("from") or raw.get("fromUser") or ""),
                    to_user_ids=tuple(
                        str(value).strip()
                        for value in (raw.get("tolist") or raw.get("toList") or [])
                        if str(value).strip()
                    ),
                )
            ]
            highest_seq = max(highest_seq, int(event["seq"]))
        result = self.store.ingest(
            stream_key=self.stream_key,
            events=events,
            sealed_payloads=sealed_payloads,
            route_ids=route_ids,
        )
        self.store.advance_cursor(
            stream_key=self.stream_key,
            expected_seq=start_seq,
            next_seq=highest_seq,
            batch_count=len(events),
        )
        return {"startSeq": start_seq, "nextSeq": highest_seq, "pulled": len(events), **result}

    async def deliver_once(self) -> dict[str, int]:
        rows = self.store.pending_deliveries(self.settings.delivery_limit)
        delivered = 0
        failed = 0
        async with httpx.AsyncClient(timeout=self.settings.delivery_timeout_seconds) as client:
            for row in rows:
                route = self.routes.get(str(row["project_id"]))
                if route is None or not route.enabled:
                    self.store.mark_delivery_failure(row["event_id"], row["project_id"], "project route is not configured", int(row["attempts"]))
                    failed += 1
                    continue
                try:
                    raw_message = self.sealed.open(str(row["sealed_payload"]))
                    event, _ = normalize_message(raw_message, self.stream_key, self.settings.media_token_key)
                    response = await client.post(
                        route.endpoint_url,
                        json=event,
                        headers={
                            "X-WeCom-Archive-Project": route.project_id,
                            "X-WeCom-Archive-Project-Token": route.token,
                            "Idempotency-Key": str(row["event_id"]),
                        },
                    )
                    if response.status_code < 200 or response.status_code >= 300:
                        raise RuntimeError(f"project returned HTTP {response.status_code}")
                    self.store.mark_delivery_success(row["event_id"], route.project_id)
                    delivered += 1
                except Exception as exc:
                    self.store.mark_delivery_failure(row["event_id"], row["project_id"], str(exc), int(row["attempts"]))
                    failed += 1
        return {"attempted": len(rows), "delivered": delivered, "failed": failed}

    def cleanup_expired(self) -> int:
        return self.store.cleanup_expired_messages(self.settings.raw_retention_hours, self.settings.batch_limit)

    def replay_project(self, project_id: str, after_seq: int, limit: int) -> dict[str, int | str]:
        route = self.routes.get(project_id)
        if route is None or not route.enabled:
            raise KeyError("project route is not configured")
        rows = self.store.messages_after(self.stream_key, after_seq, limit)
        added = 0
        scanned = 0
        for row in rows:
            scanned += 1
            raw_message = self.sealed.open(str(row["sealed_payload"]))
            room_id = str(raw_message.get("roomid") or raw_message.get("roomId") or "")
            message_type = str(raw_message.get("msgtype") or raw_message.get("msgType") or "")
            if route.matches(
                room_id,
                message_type,
                from_user=str(raw_message.get("from") or raw_message.get("fromUser") or ""),
                to_user_ids=tuple(
                    str(value).strip()
                    for value in (raw_message.get("tolist") or raw_message.get("toList") or [])
                    if str(value).strip()
                ),
            ) and self.store.add_delivery(str(row["event_id"]), project_id):
                added += 1
        return {"projectId": project_id, "afterSeq": after_seq, "scanned": scanned, "deliveriesAdded": added}

    async def redeliver_event(self, project_id: str, event_id: str) -> dict[str, Any]:
        route = self.routes.get(project_id)
        if route is None or not route.enabled:
            raise KeyError("project route is not configured")
        sealed_payload = self.store.load_sealed_payload(event_id)
        if not sealed_payload:
            raise KeyError("archive event not found")
        raw_message = self.sealed.open(sealed_payload)
        room_id = str(raw_message.get("roomid") or raw_message.get("roomId") or "")
        message_type = str(raw_message.get("msgtype") or raw_message.get("msgType") or "")
        to_user_ids = tuple(
            str(value).strip()
            for value in (raw_message.get("tolist") or raw_message.get("toList") or [])
            if str(value).strip()
        )
        if not route.matches(
            room_id,
            message_type,
            from_user=str(raw_message.get("from") or raw_message.get("fromUser") or ""),
            to_user_ids=to_user_ids,
        ):
            raise KeyError("archive event does not match project route")
        if not self.store.reset_delivery(event_id, project_id):
            if not self.store.add_delivery(event_id, project_id):
                raise KeyError("project delivery does not exist")
        delivery = await self.deliver_once()
        return {"projectId": project_id, "eventId": event_id, "delivery": delivery}

    def media_bytes(self, event_id: str, media_id: str) -> bytes:
        if ":" in media_id:
            embedded_event_id, media_id = media_id.split(":", 1)
            if embedded_event_id != event_id:
                raise KeyError("media event mismatch")
        sealed = self.store.load_sealed_payload(event_id)
        if not sealed:
            raise KeyError("event not found")
        raw_message = self.sealed.open(sealed)
        payload = raw_message.get("decryptedPayload") if isinstance(raw_message.get("decryptedPayload"), dict) else {}
        sdk_file_id = self._find_media_id(payload, event_id, media_id)
        if not sdk_file_id:
            raise KeyError("media not found")
        return self.client.download_media(sdk_file_id).content

    def _find_media_id(self, value: Any, event_id: str, wanted: str, path: str = "") -> str | None:
        if isinstance(value, dict):
            for key, child in value.items():
                child_path = f"{path}.{key}" if path else key
                if _media_value(str(key)) and isinstance(child, str):
                    if media_token(self.settings.media_token_key, event_id, child_path, child) == wanted:
                        return child
                found = self._find_media_id(child, event_id, wanted, child_path)
                if found:
                    return found
        elif isinstance(value, list):
            for index, child in enumerate(value):
                found = self._find_media_id(child, event_id, wanted, f"{path}[{index}]")
                if found:
                    return found
        elif isinstance(value, str) and value.lstrip().startswith(("{", "[")):
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError:
                return None
            if isinstance(parsed, (dict, list)):
                return self._find_media_id(parsed, event_id, wanted, path)
        return None

    def project_status(self) -> dict[str, Any]:
        return {
            "streamKey": self.stream_key,
            "rawRetentionHours": self.settings.raw_retention_hours,
            "projectIds": sorted(self.routes),
            **self.store.status(self.stream_key),
        }
