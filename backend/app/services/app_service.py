from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import unquote, urlparse
from uuid import uuid4
import httpx
from fastapi import HTTPException, status

from app.core.config import settings
from app.models.domain import AppState, Card, CardMedia, Category, CustomerAction, ImportBatch, LeadFollowUpLog, LeadReminder, MessageRecord, MessageThread, MediaRetryJob, RawMessage, RelayConfig, RelayEntry, ShowcaseItem, ShowcasePage, SkillRun, SyncCursor, Topic, User, UserNote, ViewEvent, WecomArchiveCursor, WecomArchiveMessage, WecomIdentityBinding
from app.schemas.auth import MockLoginRequest, WechatLoginRequest
from app.schemas.categories import CategoryCreateRequest
from app.schemas.cards import CardCreateRequest, CardUpdateRequest, CreateRelayRequest, LeadReminderUpdateRequest, LeadReminderUpsertRequest, RecordViewRequest
from app.schemas.notes import CustomerActionSubmitRequest, NoteTypeConfirmRequest, TopicCreateRequest, UserNoteUpdateRequest
from app.schemas.showcases import ShowcasePageRequest
from app.schemas.skills import (
    ContentMediaPayload,
    ContentObjectPayload,
    IntentResultPayload,
    RunContentToNoteResponse,
    SkillRunPayload,
    UserNoteDraftPayload,
)
from app.services.card_parser_service import CardParserService
from app.services.content_object_adapter import ContentObjectAdapter
from app.services.helpers import mask_nickname, new_id
from app.services.import_notification_service import ImportNotificationService
from app.services.media_storage_service import MediaStorageService
from app.services.media_processing_service import MediaProcessingService
from app.services.message_aggregator import MessageAggregator
from app.services.ocr_service import OcrService
from app.services.repository import AppRepository
from app.services.skill_router_service import SkillRouterService
from app.services.time_utils import SHANGHAI, date_key, now_iso, parse_iso
from app.services.wecom_message_normalizer import WecomMessageNormalizer
from app.services.wecom_mock_service import WecomMockService


LEAD_REMINDER_STATUSES = {"pending", "contacted", "invalid", "paused", "completed"}
LEAD_CLOSED_STATUSES = {"invalid", "paused", "completed"}
WECOM_EXTERNAL_BINDING_SOURCE = "wecom_external_user"
CONVERSION_CONFIG_KEYS = {
    "showContactPhone",
    "enableLightScrm",
    "collectLeads",
    "enableAppointment",
    "enablePrivateConsultation",
    "enableSharePoster",
    "enableGroupRelay",
    "enablePaymentPlaceholder",
}
CONFIRMABLE_CARD_TYPES = {"property_listing", "groupbuy_product", "text_note"}
PROPERTY_CONVERSION_DEFAULTS = {
    "showContactPhone": True,
    "enableLightScrm": True,
    "collectLeads": True,
    "enableAppointment": True,
    "enablePrivateConsultation": True,
    "enableSharePoster": True,
    "enableGroupRelay": False,
    "enablePaymentPlaceholder": False,
}
GROUPBUY_CONVERSION_DEFAULTS = {
    "showContactPhone": True,
    "enableLightScrm": False,
    "collectLeads": False,
    "enableAppointment": False,
    "enablePrivateConsultation": False,
    "enableSharePoster": True,
    "enableGroupRelay": True,
    "enablePaymentPlaceholder": False,
}
CUSTOMER_ACTION_LABELS = {
    "lead-contact": "留下电话/微信",
    "appointment": "预约看房",
    "order-intent": "商品下单",
    "relay-intent": "参与接龙",
    "consult-click": "咨询动作",
    "navigation-click": "地图定位",
    "external-open": "打开外部详情",
}
CUSTOMER_ACTION_FIELDS = {
    "lead-contact": [
        {"key": "name", "label": "姓名", "type": "text", "required": False},
        {"key": "phone", "label": "电话", "type": "phone", "required": True},
        {"key": "wechat", "label": "微信号", "type": "text", "required": False},
        {"key": "remark", "label": "备注", "type": "textarea", "required": False},
    ],
    "appointment": [
        {"key": "date", "label": "日期", "type": "date", "required": True},
        {"key": "time", "label": "时间", "type": "time", "required": True},
        {"key": "remark", "label": "备注", "type": "text", "required": False},
    ],
    "order-intent": [
        {"key": "receiverName", "label": "收货人", "type": "text", "required": False},
        {"key": "quantity", "label": "数量", "type": "number", "required": True},
        {"key": "phone", "label": "电话", "type": "phone", "required": True},
        {"key": "address", "label": "地址", "type": "text", "required": True},
        {"key": "wechat", "label": "微信号", "type": "text", "required": False},
        {"key": "remark", "label": "备注", "type": "textarea", "required": False},
    ],
    "relay-intent": [
        {"key": "receiverName", "label": "收货人", "type": "text", "required": False},
        {"key": "quantity", "label": "数量", "type": "number", "required": True},
        {"key": "phone", "label": "电话", "type": "phone", "required": True},
        {"key": "address", "label": "地址", "type": "text", "required": True},
        {"key": "wechat", "label": "微信号", "type": "text", "required": False},
        {"key": "remark", "label": "备注", "type": "textarea", "required": False},
    ],
}
PRODUCT_ORDER_ACTION_KEYS = {"order-intent", "relay-intent"}
ORDER_STATUSES = {"submitted", "contacted", "completed", "cancelled"}


class AppService:
    def __init__(
        self,
        repo: AppRepository,
        wecom_mock_service: WecomMockService,
        media_storage_service: MediaStorageService,
        parser_service: CardParserService,
        aggregator: MessageAggregator,
        notification_service: ImportNotificationService,
        normalizer: WecomMessageNormalizer,
        media_processing_service: MediaProcessingService | None = None,
        skill_router_service: SkillRouterService | None = None,
        content_object_adapter: ContentObjectAdapter | None = None,
        ocr_service: OcrService | None = None,
    ):
        self.repo = repo
        self.wecom_mock_service = wecom_mock_service
        self.media_storage_service = media_storage_service
        self.media_processing_service = media_processing_service or MediaProcessingService()
        self.parser_service = parser_service
        self.aggregator = aggregator
        self.notification_service = notification_service
        self.normalizer = normalizer
        self.skill_router_service = skill_router_service or SkillRouterService()
        self.content_object_adapter = content_object_adapter or ContentObjectAdapter()
        self.ocr_service = ocr_service or OcrService(
            provider=settings.ocr_provider,
            language=settings.ocr_language,
            tesseract_bin=settings.ocr_tesseract_bin,
            mock_text=settings.ocr_mock_text,
        )

    def _load(self) -> AppState:
        return self.repo.load()

    def _save(self, state: AppState) -> None:
        self.repo.save(state)

    def _build_card_media(self, card_id: str, media_payload: list[dict] | None) -> list[CardMedia]:
        media_items: list[CardMedia] = []
        for index, item in enumerate(media_payload or []):
            if not item or item.get("type") not in {"image", "video"} or not item.get("url"):
                continue
            media_items.append(
                CardMedia(
                    id=new_id("card_media"),
                    cardId=card_id,
                    type=item["type"],
                    url=item["url"],
                    sortOrder=item.get("sortOrder") or index + 1,
                    sourceMediaId=None,
                    createdAt=now_iso(),
                )
            )
        return media_items

    def list_pending_imports(self) -> list[dict]:
        pending = self.repo.list_import_batches(statuses={"pending", "success"})
        result = []
        for batch in pending:
            card = self.repo.get_card(batch.generatedCardId) if batch.generatedCardId else None
            note = self.repo.get_user_note(batch.generatedNoteId) if batch.generatedNoteId else None
            result.append(
                {
                    **batch.model_dump(),
                    "generatedCard": card.model_dump() if card else None,
                    "generatedNote": note.model_dump() if note else None,
                }
            )
        return result

    def mock_login(self, payload: MockLoginRequest) -> User:
        return self._upsert_user_by_openid(
            payload.openid or f"openid_{payload.nickname}",
            payload.nickname,
            payload.avatarUrl,
            payload.phone,
        )

    def wechat_login(self, payload: WechatLoginRequest) -> User:
        if not settings.wechat_miniapp_appid or not settings.wechat_miniapp_secret:
            raise HTTPException(status_code=503, detail="微信登录未配置，请先配置小程序 AppSecret")
        code = (payload.code or "").strip()
        if not code:
            raise HTTPException(status_code=400, detail="缺少微信登录 code")
        try:
            response = httpx.get(
                settings.wechat_jscode2session_url,
                params={
                    "appid": settings.wechat_miniapp_appid,
                    "secret": settings.wechat_miniapp_secret,
                    "js_code": code,
                    "grant_type": "authorization_code",
                },
                timeout=8,
            )
            response.raise_for_status()
            session_data = response.json()
        except Exception as exc:
            raise HTTPException(status_code=502, detail="微信登录服务暂不可用") from exc
        if session_data.get("errcode"):
            raise HTTPException(status_code=400, detail=session_data.get("errmsg") or "微信登录失败")
        openid = session_data.get("openid")
        if not openid:
            raise HTTPException(status_code=400, detail="微信登录未返回 openid")
        return self._upsert_user_by_openid(openid, payload.nickname or "微信用户", payload.avatarUrl, payload.phone, session_data.get("unionid"))

    def _upsert_user_by_openid(
        self,
        openid: str,
        nickname: str,
        avatar_url: str,
        phone: str | None = None,
        unionid: str | None = None,
    ) -> User:
        now = now_iso()
        existing = self.repo.get_user_by_openid(openid)
        if existing:
            existing.nickname = nickname
            existing.avatarUrl = avatar_url
            existing.phone = phone
            existing.unionid = unionid or existing.unionid
            existing.updatedAt = now
            self.repo.save_user(existing)
            return existing

        user = User(
            id=new_id("user"),
            openid=openid,
            unionid=unionid,
            nickname=nickname,
            avatarUrl=avatar_url,
            phone=phone,
            createdAt=now,
            updatedAt=now,
        )
        self.repo.save_user(user)
        return user

    def trigger_mock_import(self, external_user_id: str, conversation_id: str, fixture: str) -> dict:
        synced_messages = self.wecom_mock_service.sync_messages(external_user_id, conversation_id, fixture)
        return self.import_synced_messages(synced_messages, notification_channel="mock")

    def normalize_sync_response(self, sync_response: dict, fallback_open_kfid: str | None = None) -> list[dict]:
        return self.normalizer.normalize_sync_response(sync_response, fallback_open_kfid=fallback_open_kfid)

    def trigger_sync_response_import(
        self,
        sync_response: dict,
        fallback_open_kfid: str | None = None,
        media_url_by_id: dict[str, str] | None = None,
        allow_media_storage_fallback: bool = True,
        notification_channel: str = "wecom",
    ) -> dict:
        synced_messages = self.normalizer.normalize_sync_response(sync_response, fallback_open_kfid=fallback_open_kfid)
        return self.import_synced_messages(
            synced_messages,
            media_url_by_id=media_url_by_id,
            allow_media_storage_fallback=allow_media_storage_fallback,
            notification_channel=notification_channel,
        )

    def import_synced_messages(
        self,
        synced_messages: list[dict],
        media_url_by_id: dict[str, str] | None = None,
        allow_media_storage_fallback: bool = True,
        notification_channel: str = "wecom",
    ) -> dict:
        raw_messages: list[RawMessage] = []
        incoming_wecom_msg_ids = {item["wecomMsgId"] for item in synced_messages if item.get("wecomMsgId")}
        existing_wecom_msg_ids = self.repo.existing_wecom_msg_ids(incoming_wecom_msg_ids)
        for item in synced_messages:
            if item.get("wecomMsgId") in existing_wecom_msg_ids:
                continue
            local_media_url = None
            media_id = item.get("mediaId")
            if media_id:
                local_media_url = (media_url_by_id or {}).get(media_id)
                if not local_media_url and allow_media_storage_fallback:
                    local_media_url = self.media_storage_service.download_and_store(media_id, item["msgType"])
            raw_message = RawMessage(
                id=new_id("msg"),
                wecomMsgId=item.get("wecomMsgId"),
                wecomToken=item.get("wecomToken"),
                openKfid=item.get("openKfid"),
                externalUserId=item["externalUserId"],
                conversationId=item["conversationId"],
                msgType=item["msgType"],
                content=item["content"],
                mediaId=media_id,
                localMediaUrl=local_media_url,
                receivedAt=item["receivedAt"],
                createdAt=now_iso(),
            )
            raw_messages.append(raw_message)
        if not raw_messages:
            return {
                "message": "没有新的企业微信客服消息需要导入",
                "importBatchIds": [],
                "deduplicatedCount": len(existing_wecom_msg_ids),
            }

        new_batches = self.aggregator.aggregate(raw_messages)
        if not new_batches:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="未生成导入批次")

        for batch in new_batches:
            batch_messages = [item for item in raw_messages if item.id in batch.rawMessageIds]
            for message in batch_messages:
                message.importBatchId = batch.id
            notification = self._process_import_batch(batch, batch_messages, notification_channel)

        return {
            "message": notification.message,
            "importBatchIds": [item.id for item in new_batches],
            "deduplicatedCount": len(existing_wecom_msg_ids),
        }

    def _process_import_batch(
        self,
        batch: ImportBatch,
        batch_messages: list[RawMessage],
        notification_channel: str,
    ):
        media_warning_count = sum(
            1
            for message in batch_messages
            if message.msgType in {"image", "video"} and message.mediaId and not message.localMediaUrl
        )
        try:
            content_object = self.content_object_adapter.from_wecom_batch(batch, batch_messages)
            owner_user_id = self._resolve_owner_user_id_for_external(batch.externalUserId)
            note_result = self._run_import_skill(owner_user_id, content_object)
            card = self._build_card_from_note_draft(batch, note_result.noteDraft, content_object)
            note = self._build_user_note_from_draft(batch, note_result.noteDraft, card.id)
            self._apply_resolved_owner(batch, card, note, owner_user_id)
            batch.generatedCardId = card.id
            batch.generatedNoteId = note.id
            batch.status = ("claimed" if owner_user_id != "unclaimed" else "success") if card.title else "failed"
            batch.claimedByUserId = owner_user_id if owner_user_id != "unclaimed" and card.title else batch.claimedByUserId
            batch.errorMessage = None if card.title else "未能解析标题"
            batch.updatedAt = now_iso()
            skill_run = SkillRun.model_validate(note_result.skillRun.model_dump())
            skill_run.outputRef = note.id if batch.status in {"success", "claimed"} else batch.id
            skill_run.inputSnapshot = {
                **skill_run.inputSnapshot,
                "importBatchId": batch.id,
                "rawMessageIds": batch.rawMessageIds,
                "mediaWarningCount": media_warning_count,
            }
            notification = self.notification_service.build_notification(
                batch,
                channel=notification_channel,
                media_warning_count=media_warning_count,
            )
            self.repo.save_import_artifacts(batch, batch_messages, card, notification)
            self.repo.save_user_note(note)
            self.repo.save_skill_run(skill_run)
            return notification
        except Exception as exc:
            batch.status = "failed"
            batch.errorMessage = str(exc)
            batch.updatedAt = now_iso()
            failed_run = SkillRun(
                id=new_id("skill_run"),
                skillId="content-to-note",
                status="failed",
                inputSnapshot={
                    "importBatchId": batch.id,
                    "rawMessageIds": batch.rawMessageIds,
                    "messages": [message.model_dump(mode="json") for message in batch_messages],
                    "mediaWarningCount": media_warning_count,
                },
                outputRef=batch.id,
                modelProvider="rule",
                errorMessage=str(exc),
                startedAt=batch.createdAt,
                endedAt=now_iso(),
            )
            notification = self.notification_service.build_notification(batch, channel=notification_channel)
            self.repo.save_raw_messages(batch_messages)
            self.repo.save_import_batch(batch)
            self.repo.save_import_notification(notification)
            self.repo.save_skill_run(failed_run)
            return notification

    def _build_card_from_note_draft(self, batch: ImportBatch, note_draft, content_object) -> Card:
        created_at = now_iso()
        card_id = new_id("card")
        media: list[CardMedia] = []
        sort_order = 1
        for item in note_draft.media:
            if item.type not in {"image", "video"} or not item.url:
                continue
            media.append(
                CardMedia(
                    id=new_id("card_media"),
                    cardId=card_id,
                    type=item.type,
                    url=item.url,
                    sortOrder=sort_order,
                    sourceMediaId=item.mediaId,
                    createdAt=created_at,
                )
            )
            sort_order += 1

        source_url = next((link.url for link in content_object.links if link.url), None)
        project_name = note_draft.summary[:30] if note_draft.summary else None
        return Card(
            id=card_id,
            ownerUserId=note_draft.ownerUserId or "unclaimed",
            importBatchId=batch.id,
            status="draft",
            title=note_draft.title or batch.titleCandidate or "未命名素材",
            coverUrl=note_draft.coverUrl,
            detailText=note_draft.body,
            projectName=project_name,
            locationText=note_draft.locationText,
            phone=note_draft.phone,
            relayNotice="感兴趣请实名接龙报名。",
            sourceUrl=source_url,
            enabledFields=["projectName", "locationText", "phone", "relayNotice", "sourceUrl"],
            categoryIds=[],
            media=media,
            relayConfig=RelayConfig(enabled=True, requirePhone=False, requireAddress=False),
            createdAt=created_at,
            updatedAt=created_at,
        )

    def _build_user_note_from_draft(self, batch: ImportBatch, note_draft, source_card_id: str | None = None) -> UserNote:
        now = now_iso()
        return UserNote(
            id=new_id("note"),
            ownerUserId=note_draft.ownerUserId or "unclaimed",
            importBatchId=batch.id,
            sourceCardId=source_card_id,
            status="draft",
            title=note_draft.title,
            summary=note_draft.summary,
            body=note_draft.body,
            coverUrl=note_draft.coverUrl,
            media=[item.model_dump() for item in note_draft.media],
            categoryIds=note_draft.categoryIds,
            phone=note_draft.phone,
            locationText=note_draft.locationText,
            sourceRefs=note_draft.sourceRefs,
            visibilityConfig=note_draft.visibilityConfig,
            createdAt=now,
            updatedAt=now,
        )

    def list_skill_runs(
        self,
        status: str | None = None,
        skill_id: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        return [item.model_dump() for item in self.repo.list_skill_runs(status=status, skill_id=skill_id, limit=limit)]

    def get_wecom_archive_cursor(self, corp_id: str) -> WecomArchiveCursor | None:
        return self.repo.get_wecom_archive_cursor(corp_id)

    def advance_wecom_archive_cursor(
        self,
        corp_id: str,
        seq: int,
        payload: dict | None = None,
        status: str = "success",
        error_message: str | None = None,
    ) -> WecomArchiveCursor:
        now = now_iso()
        existing = self.repo.get_wecom_archive_cursor(corp_id)
        cursor = WecomArchiveCursor(
            id=existing.id if existing else f"wecom_archive_cursor_{corp_id}",
            corpId=corp_id,
            seq=seq,
            status=status,
            lastPayload=payload or {},
            lastSyncedAt=now,
            lockToken=None,
            lockedAt=None,
            lastError=error_message,
            createdAt=existing.createdAt if existing else now,
            updatedAt=now,
        )
        self.repo.save_wecom_archive_cursor(cursor)
        return cursor

    def save_wecom_archive_messages(self, corp_id: str, messages: list[dict]) -> dict:
        existing_msg_ids = self.repo.existing_wecom_archive_msg_ids(
            {item.get("msgid") or item.get("msgId") for item in messages if item.get("msgid") or item.get("msgId")}
        )
        now = now_iso()
        archive_messages: list[WecomArchiveMessage] = []
        max_seq = 0
        skipped = 0
        for index, item in enumerate(messages):
            msg_id = item.get("msgid") or item.get("msgId")
            if msg_id and msg_id in existing_msg_ids:
                skipped += 1
                continue
            seq = int(item.get("seq") or item.get("Seq") or index + 1)
            max_seq = max(max_seq, seq)
            decrypted_payload = item.get("decryptedPayload")
            archive_messages.append(
                WecomArchiveMessage(
                    id=new_id("wecom_archive_msg"),
                    corpId=corp_id,
                    seq=seq,
                    msgId=msg_id,
                    action=item.get("action"),
                    fromUser=item.get("from") or item.get("fromUser") or item.get("from_user"),
                    toList=item.get("tolist") or item.get("toList") or item.get("to_list") or [],
                    roomId=item.get("roomid") or item.get("roomId") or item.get("room_id"),
                    msgTime=self._normalize_archive_msg_time(
                        item.get("msgtime") or item.get("msgTime") or item.get("msg_time")
                    ),
                    msgType=item.get("msgtype") or item.get("msgType") or item.get("msg_type"),
                    rawPayload=item,
                    decryptedPayload=decrypted_payload if isinstance(decrypted_payload, dict) else None,
                    mediaRefs=item.get("mediaRefs") or [],
                    createdAt=now,
                )
            )
        if archive_messages:
            self.repo.save_wecom_archive_messages(archive_messages)
            self.advance_wecom_archive_cursor(corp_id, max_seq, {"savedCount": len(archive_messages)}, status="success")
        cursor = self.repo.get_wecom_archive_cursor(corp_id)
        return {
            "savedCount": len(archive_messages),
            "skippedDuplicateCount": skipped,
            "cursor": cursor.model_dump() if cursor else None,
        }

    def list_wecom_archive_messages(self, limit: int = 100) -> list[dict]:
        return [item.model_dump() for item in self.repo.list_wecom_archive_messages(limit=limit)]

    def pull_wecom_archive_messages(self, archive_client, limit: int = 100) -> dict:
        corp_id = archive_client.corp_id or "default"
        cursor = self.repo.get_wecom_archive_cursor(corp_id)
        start_seq = cursor.seq if cursor else 0
        try:
            response = archive_client.pull_and_decrypt(start_seq, limit)
            result = self.save_wecom_archive_messages(corp_id, response.get("messages") or [])
            next_cursor = self.repo.get_wecom_archive_cursor(corp_id)
            if not response.get("messages"):
                next_cursor = self.advance_wecom_archive_cursor(
                    corp_id,
                    start_seq,
                    {"rawCount": response.get("rawCount", 0), "message": "no new archive messages"},
                    status="success",
                )
            return {
                "corpId": corp_id,
                "startSeq": start_seq,
                "rawCount": response.get("rawCount", 0),
                "savedCount": result.get("savedCount", 0),
                "skippedDuplicateCount": result.get("skippedDuplicateCount", 0),
                "cursor": next_cursor.model_dump() if next_cursor else None,
            }
        except Exception as exc:
            failed = self.advance_wecom_archive_cursor(
                corp_id,
                start_seq,
                {"limit": limit},
                status="failed",
                error_message=str(exc),
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={
                    "message": "会话内容存档拉取失败",
                    "error": str(exc),
                    "cursor": failed.model_dump(),
                },
            ) from exc

    def process_wecom_archive_messages(self, limit: int = 100, archive_client=None) -> dict:
        messages = [
            item
            for item in self.repo.list_wecom_archive_messages(limit=limit)
            if item.decryptedPayload and not item.generatedNoteId
        ]
        processed: list[dict] = []
        failed: list[dict] = []
        for group in self._group_wecom_archive_messages(messages):
            group_messages = sorted(group, key=lambda item: item.seq)
            primary = group_messages[0]
            try:
                content_object = self._build_archive_content_object(group_messages)
                media_result = self._download_and_attach_archive_media(content_object, archive_client)
                owner_user_id = self._resolve_owner_user_id_for_external(primary.fromUser)
                note_result = self._run_import_skill(owner_user_id, content_object)
                batch = self._build_archive_import_batch(primary, note_result.noteDraft.title, group_messages)
                card = self._build_card_from_note_draft(batch, note_result.noteDraft, content_object)
                note = self._build_user_note_from_draft(batch, note_result.noteDraft, card.id)
                batch.generatedCardId = card.id
                batch.generatedNoteId = note.id
                skill_run = SkillRun.model_validate(note_result.skillRun.model_dump())
                skill_run.outputRef = note.id
                skill_run.inputSnapshot = {
                    **skill_run.inputSnapshot,
                    "wecomArchiveMessageIds": [item.id for item in group_messages],
                    "archiveSeqs": [item.seq for item in group_messages],
                    "archiveMsgIds": [item.msgId for item in group_messages],
                    "archiveMedia": media_result,
                }
                self._apply_resolved_owner(batch, card, note, owner_user_id)
                batch.status = "claimed" if owner_user_id != "unclaimed" else batch.status
                batch.claimedByUserId = owner_user_id if owner_user_id != "unclaimed" else batch.claimedByUserId
                processed_at = now_iso()
                for message in group_messages:
                    message.generatedNoteId = note.id
                    message.generatedCardId = card.id
                    message.processedAt = processed_at
                    message.processError = None
                self.repo.save_import_batch(batch)
                self.repo.save_card(card)
                self.repo.save_user_note(note)
                self.repo.save_skill_run(skill_run)
                self.repo.save_wecom_archive_messages(group_messages)
                processed.append(
                    {
                        "archiveMessageId": primary.id,
                        "archiveMessageIds": [item.id for item in group_messages],
                        "seq": primary.seq,
                        "seqs": [item.seq for item in group_messages],
                        "noteId": note.id,
                        "cardId": card.id,
                        "media": media_result,
                    }
                )
            except Exception as exc:
                for message in group_messages:
                    message.processError = str(exc)
                self.repo.save_wecom_archive_messages(group_messages)
                failed.append(
                    {
                        "archiveMessageId": primary.id,
                        "archiveMessageIds": [item.id for item in group_messages],
                        "seq": primary.seq,
                        "seqs": [item.seq for item in group_messages],
                        "error": str(exc),
                    }
                )
        return {
            "processedCount": len(processed),
            "failedCount": len(failed),
            "processed": processed,
            "failed": failed,
        }

    def _download_and_attach_archive_media(self, content_object: ContentObjectPayload, archive_client=None) -> dict:
        result = {"downloadedCount": 0, "reusedCount": 0, "failedCount": 0, "skippedCount": 0}
        if not content_object.media:
            return result
        for item in content_object.media:
            media_id = item.mediaId
            media_type = item.type if item.type in {"image", "video", "file"} else "file"
            if not media_id:
                result["skippedCount"] += 1
                continue
            if item.url:
                result["skippedCount"] += 1
                continue
            status, url = self._download_archive_media_url(media_id, media_type, archive_client)
            if url:
                item.url = url
            result[f"{status}Count"] += 1
        return result

    def backfill_wecom_archive_media(self, archive_client=None, limit: int = 100) -> dict:
        result = {
            "checkedNoteCount": 0,
            "updatedNoteCount": 0,
            "updatedCardCount": 0,
            "downloadedCount": 0,
            "reusedCount": 0,
            "failedCount": 0,
            "skippedCount": 0,
            "remainingCount": 0,
            "notes": [],
        }
        handled_media = 0
        for note in self.repo.list_all_user_notes(include_deleted=False):
            note_has_missing = any(item.get("mediaId") and not item.get("url") for item in note.media if isinstance(item, dict))
            if not note_has_missing:
                continue
            result["checkedNoteCount"] += 1
            note_changed = False
            note_media_updates: list[dict] = []
            for item in note.media:
                if not isinstance(item, dict):
                    continue
                media_id = item.get("mediaId")
                media_type = item.get("type") if item.get("type") in {"image", "video", "file"} else "file"
                if not media_id or item.get("url"):
                    result["skippedCount"] += 1
                    continue
                if handled_media >= limit:
                    result["remainingCount"] += 1
                    continue
                status, url = self._download_archive_media_url(media_id, media_type, archive_client)
                result[f"{status}Count"] += 1
                handled_media += 1
                if not url:
                    continue
                item["url"] = url
                if media_type == "image" and not note.coverUrl:
                    note.coverUrl = url
                note_changed = True
                note_media_updates.append({"mediaId": media_id, "type": media_type, "url": url})
            if not note_changed:
                continue
            note.updatedAt = now_iso()
            self.repo.save_user_note(note)
            result["updatedNoteCount"] += 1
            card_updated = self._backfill_card_media_from_note(note)
            if card_updated:
                result["updatedCardCount"] += 1
            result["notes"].append(
                {
                    "noteId": note.id,
                    "sourceCardId": note.sourceCardId,
                    "media": note_media_updates,
                    "cardUpdated": card_updated,
                }
            )
        return result

    def _download_archive_media_url(self, media_id: str, media_type: str, archive_client=None) -> tuple[str, str | None]:
        existing_url = self.get_successful_media_url(media_id)
        if existing_url:
            return "reused", existing_url
        if archive_client is None:
            self.save_media_retry_failure(
                media_id=media_id,
                media_type=media_type,
                open_kfid="wecom_archive",
                error_message="archive media client not configured",
            )
            return "failed", None
        try:
            downloaded = archive_client.download_media(media_id)
            url = self.process_and_store_media(
                media_id=media_id,
                media_type=media_type,
                content=downloaded.content,
                content_type=downloaded.content_type,
                filename=downloaded.filename,
            )
            self.save_media_retry_success(
                media_id=media_id,
                media_type=media_type,
                open_kfid="wecom_archive",
                local_media_url=url,
            )
            return "downloaded", url
        except Exception as exc:
            self.save_media_retry_failure(
                media_id=media_id,
                media_type=media_type,
                open_kfid="wecom_archive",
                error_message=str(exc),
            )
            return "failed", None

    def _backfill_card_media_from_note(self, note: UserNote) -> bool:
        if not note.sourceCardId:
            return False
        card = self.repo.get_card(note.sourceCardId)
        if not card:
            return False
        changed = False
        existing_by_media_id = {item.sourceMediaId: item for item in card.media if item.sourceMediaId}
        max_sort_order = max((item.sortOrder for item in card.media), default=0)
        for item in note.media:
            if not isinstance(item, dict):
                continue
            media_id = item.get("mediaId")
            media_type = item.get("type")
            url = item.get("url")
            if media_type not in {"image", "video"} or not url:
                continue
            if media_id and media_id in existing_by_media_id:
                card_media = existing_by_media_id[media_id]
                if card_media.url != url:
                    card_media.url = url
                    changed = True
            else:
                max_sort_order += 1
                card.media.append(
                    CardMedia(
                        id=new_id("card_media"),
                        cardId=card.id,
                        type=media_type,
                        url=url,
                        sortOrder=max_sort_order,
                        sourceMediaId=media_id,
                        createdAt=now_iso(),
                    )
                )
                changed = True
            if media_type == "image" and not card.coverUrl:
                card.coverUrl = url
                changed = True
        if changed:
            card.updatedAt = now_iso()
            self.repo.save_card(card)
        return changed

    def _normalize_archive_msg_time(self, value) -> str | None:
        if value is None or value == "":
            return None
        if isinstance(value, (int, float)):
            timestamp = float(value)
            if timestamp > 10_000_000_000:
                timestamp = timestamp / 1000
            return datetime.fromtimestamp(timestamp, tz=SHANGHAI).isoformat()
        return str(value)

    def _group_wecom_archive_messages(self, messages: list[WecomArchiveMessage]) -> list[list[WecomArchiveMessage]]:
        sorted_messages = sorted(messages, key=lambda item: (self._archive_message_timestamp(item), item.seq))
        groups: list[list[WecomArchiveMessage]] = []
        for message in sorted_messages:
            if message.msgType == "note":
                groups.append([message])
                continue
            if not groups or not self._can_merge_archive_message(groups[-1][-1], message):
                groups.append([message])
                continue
            groups[-1].append(message)
        return groups

    def _can_merge_archive_message(self, previous: WecomArchiveMessage, current: WecomArchiveMessage) -> bool:
        if previous.msgType == "note" or current.msgType == "note":
            return False
        if previous.fromUser != current.fromUser:
            return False
        if self._archive_conversation_key(previous) != self._archive_conversation_key(current):
            return False
        return self._archive_message_timestamp(current) - self._archive_message_timestamp(previous) <= 5

    def _archive_conversation_key(self, message: WecomArchiveMessage) -> str:
        if message.roomId:
            return message.roomId
        users = sorted([item for item in [message.fromUser, *message.toList] if item])
        return ",".join(users) or message.msgId or message.id

    def _archive_message_timestamp(self, message: WecomArchiveMessage) -> float:
        if not message.msgTime:
            return float(message.seq)
        try:
            return parse_iso(message.msgTime).timestamp()
        except Exception:
            return float(message.seq)

    def _build_archive_content_object(self, messages: list[WecomArchiveMessage]) -> ContentObjectPayload:
        objects = [self.content_object_adapter.from_wecom_archive_message(message) for message in messages]
        if len(objects) == 1:
            return objects[0]
        return ContentObjectPayload(
            sourceType="miniapp_card" if any(item.sourceType == "miniapp_card" for item in objects) else "wecom_thread",
            title=next((item.title for item in objects if item.title), None),
            textBlocks=[block for item in objects for block in item.textBlocks],
            media=[media for item in objects for media in item.media],
            links=[link for item in objects for link in item.links],
            metadata=self._merge_content_metadata(objects),
            participants=self.content_object_adapter._unique_participants(
                [participant for item in objects for participant in item.participants]
            ),
            timestamps=[timestamp for item in objects for timestamp in item.timestamps],
            sourceRefs=[ref for item in objects for ref in item.sourceRefs],
            rawMessageIds=[raw_id for item in objects for raw_id in item.rawMessageIds],
        )

    def _build_archive_import_batch(
        self,
        message: WecomArchiveMessage,
        title: str,
        messages: list[WecomArchiveMessage] | None = None,
    ) -> ImportBatch:
        now = now_iso()
        group_messages = messages or [message]
        source_type = "miniapp_link" if any(item.msgType == "weapp" for item in group_messages) else "wechat_note"
        return ImportBatch(
            id=new_id("import"),
            externalUserId=message.fromUser or "archive_unknown",
            conversationId=message.roomId or ",".join(message.toList) or message.msgId or message.id,
            status="success",
            titleCandidate=title or f"企业微信{message.msgType or '消息'}归档",
            sourceType=source_type,
            rawMessageIds=[item.id for item in group_messages],
            startedAt=message.msgTime or now,
            endedAt=now,
            createdAt=now,
            updatedAt=now,
        )

    def _merge_content_metadata(self, objects: list[ContentObjectPayload]) -> dict:
        metadata: dict = {}
        for item in objects:
            if not isinstance(item.metadata, dict):
                continue
            for key, value in item.metadata.items():
                if value and key not in metadata:
                    metadata[key] = value
        return metadata

    def _run_import_skill(self, owner_user_id: str, content_object: ContentObjectPayload):
        if self._should_save_import_as_image_note(content_object):
            return self._build_image_import_note_result(owner_user_id, content_object)
        if self._should_light_bookmark(content_object):
            return self.skill_router_service.run_link_bookmark(owner_user_id, content_object)
        return self.skill_router_service.run_content_to_note(owner_user_id, content_object)

    def _should_save_import_as_image_note(self, content_object: ContentObjectPayload) -> bool:
        has_text = any(self._is_meaningful_import_text(block) for block in content_object.textBlocks)
        has_links = any(str(link.url or "").strip() for link in content_object.links)
        if has_text or has_links or not content_object.media:
            return False
        if any(item.type != "image" for item in content_object.media):
            return False
        return any(item.url for item in content_object.media)

    def _is_meaningful_import_text(self, text: str | None) -> bool:
        normalized = str(text or "").strip()
        return bool(normalized) and normalized not in {"收到image素材，媒体稍后转存。"}

    def _build_image_import_note_result(
        self,
        owner_user_id: str,
        content_object: ContentObjectPayload,
    ) -> RunContentToNoteResponse:
        first_image = next(item for item in content_object.media if item.type == "image" and item.url)
        visibility_config = self._image_note_visibility_config(first_image.url or "", first_image.title)
        structured_data = dict(visibility_config.get("structuredData") or {})
        structured_data["images"] = [item.url for item in content_object.media if item.type == "image" and item.url]
        structured_data["sourceRefs"] = content_object.sourceRefs or content_object.rawMessageIds
        visibility_config["structuredData"] = structured_data
        now = now_iso()
        note = UserNoteDraftPayload(
            ownerUserId=owner_user_id,
            title=self._image_import_title(content_object, first_image),
            summary="图片已保存，可按需识别文字。",
            body="图片已保存。你可以直接手动补充正文和字段，也可以点击识别图片文字后再整理。",
            coverUrl=first_image.url,
            media=content_object.media,
            categoryIds=[],
            sourceRefs=content_object.sourceRefs or content_object.rawMessageIds,
            visibilityConfig=visibility_config,
        )
        run = SkillRunPayload(
            id=new_id("skill_run"),
            skillId="image-note-ingest",
            status="success",
            inputSnapshot={
                **content_object.model_dump(),
                "imageNoteMode": "save_only_until_user_recognizes",
            },
            outputRef=None,
            modelProvider="rule",
            startedAt=now,
            endedAt=now,
        )
        intent = IntentResultPayload(
            intent="content_to_note",
            skillId="image-note-ingest",
            confidence=1,
            source="rule",
            needsConfirm=False,
            inputAdapter="input.image-media",
            message="纯图片导入已保存为待识别图片资料",
        )
        return RunContentToNoteResponse(intent=intent, skillRun=run, noteDraft=note)

    def _image_import_title(self, content_object: ContentObjectPayload, first_image: ContentMediaPayload) -> str:
        image_title = str(first_image.title or "").strip()
        if image_title:
            return image_title
        title = str(content_object.title or "").strip()
        if title and title not in {"未命名素材", "企业微信image归档"}:
            return title
        return "图片资料"

    def _should_light_bookmark(self, content_object: ContentObjectPayload) -> bool:
        if content_object.sourceType != "link_article" or not content_object.links:
            return False
        text = "\n".join(content_object.textBlocks)
        deep_keywords = ["整理链接", "链接总结", "文章总结", "整理文章", "总结文章", "提炼", "做笔记"]
        return not any(keyword in text for keyword in deep_keywords)

    def _resolve_owner_user_id_for_external(self, external_user_id: str | None) -> str:
        if not external_user_id or external_user_id == "archive_unknown":
            return "unclaimed"
        binding = self.repo.get_wecom_identity_binding(WECOM_EXTERNAL_BINDING_SOURCE, external_user_id)
        if not binding:
            return "unclaimed"
        if binding.ownerOpenid:
            user = self.repo.get_user_by_openid(binding.ownerOpenid)
            return user.id if user else "unclaimed"
        if not self.repo.get_user(binding.ownerUserId):
            return "unclaimed"
        return binding.ownerUserId

    def _apply_resolved_owner(self, batch: ImportBatch, card: Card, note: UserNote, owner_user_id: str) -> None:
        if owner_user_id == "unclaimed":
            return
        card.ownerUserId = owner_user_id
        note.ownerUserId = owner_user_id
        note.status = "active"
        batch.claimedByUserId = owner_user_id

    def _save_wecom_identity_binding(
        self,
        external_user_id: str | None,
        owner_user_id: str,
        import_batch_id: str | None,
        bind_source: str,
    ) -> WecomIdentityBinding | None:
        if not external_user_id or external_user_id == "archive_unknown":
            return None
        now = now_iso()
        existing = self.repo.get_wecom_identity_binding(WECOM_EXTERNAL_BINDING_SOURCE, external_user_id)
        owner = self.repo.get_user(owner_user_id)
        binding = WecomIdentityBinding(
            id=existing.id if existing else f"wecom_identity_{new_id('bind')}",
            sourceType=WECOM_EXTERNAL_BINDING_SOURCE,
            externalUserId=external_user_id,
            ownerUserId=owner_user_id,
            ownerOpenid=owner.openid if owner else existing.ownerOpenid if existing else None,
            bindSource=bind_source,
            firstImportBatchId=existing.firstImportBatchId if existing else import_batch_id,
            lastImportBatchId=import_batch_id or (existing.lastImportBatchId if existing else None),
            createdAt=existing.createdAt if existing else now,
            updatedAt=now,
        )
        self.repo.save_wecom_identity_binding(binding)
        return binding

    def list_import_failures(self, limit: int = 100) -> dict:
        failed_runs = self.repo.list_skill_runs(status="failed", limit=limit)
        failed_notifications = [item for item in self.repo.list_import_notifications() if item.status == "failed"]
        return {
            "skillRuns": [item.model_dump() for item in failed_runs],
            "notifications": [item.model_dump() for item in failed_notifications[:limit]],
        }

    def retry_failed_import(self, import_batch_id: str, notification_channel: str = "wecom") -> dict:
        batch = self.repo.get_import_batch(import_batch_id)
        if not batch:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="导入批次不存在")
        if batch.status != "failed":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="只有失败导入批次可以重试")
        batch_messages = self.repo.list_raw_messages_for_batch(import_batch_id)
        if not batch_messages:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="导入批次原始消息不存在")
        notification = self._process_import_batch(batch, batch_messages, notification_channel)
        card = self.repo.get_card(batch.generatedCardId) if batch.generatedCardId else None
        return {
            "importBatch": batch.model_dump(),
            "generatedCard": card.model_dump() if card else None,
            "notification": notification.model_dump(),
        }

    def get_wecom_retry_dashboard(self, limit: int = 100) -> dict:
        media_failed = self.repo.list_media_retry_jobs({"failed"})[:limit]
        failed_runs = self.repo.list_skill_runs(status="failed", limit=limit)
        failed_notifications = [item for item in self.repo.list_import_notifications() if item.status == "failed"][:limit]
        return {
            "summary": {
                "failedMediaCount": len(media_failed),
                "failedSkillRunCount": len(failed_runs),
                "failedNotificationCount": len(failed_notifications),
            },
            "actions": {
                "retryMedia": "/api/wecom/media-retries/retry",
                "retryImport": "/api/wecom/import-failures/retry",
            },
            "mediaRetries": [item.model_dump() for item in media_failed],
            "skillRuns": [item.model_dump() for item in failed_runs],
            "notifications": [item.model_dump() for item in failed_notifications],
        }

    def list_import_notifications(self) -> list[dict]:
        return [item.model_dump() for item in self.repo.list_import_notifications()]

    def get_sync_cursor(self, open_kfid: str) -> SyncCursor | None:
        return self.repo.get_sync_cursor(open_kfid)

    def acquire_sync_lock(self, open_kfid: str, source: str, timeout_seconds: int) -> SyncCursor | None:
        now = now_iso()
        stale_before = (parse_iso(now).astimezone(SHANGHAI) - timedelta(seconds=timeout_seconds)).isoformat()
        return self.repo.acquire_sync_lock(
            open_kfid=open_kfid,
            source=source,
            lock_token=uuid4().hex,
            now=now,
            stale_before=stale_before,
        )

    def release_sync_lock(
        self,
        open_kfid: str,
        lock_token: str,
        status: str,
        error_message: str | None = None,
    ) -> SyncCursor | None:
        return self.repo.release_sync_lock(
            open_kfid=open_kfid,
            lock_token=lock_token,
            status=status,
            error_message=error_message,
            now=now_iso(),
        )

    def force_release_sync_lock(self, open_kfid: str, reason: str) -> SyncCursor | None:
        return self.repo.force_release_sync_lock(open_kfid=open_kfid, reason=reason, now=now_iso())

    def get_successful_media_url(self, media_id: str) -> str | None:
        return self.repo.get_successful_media_url(media_id)

    def process_and_store_media(
        self,
        media_id: str,
        media_type: str,
        content: bytes,
        content_type: str | None = None,
        filename: str | None = None,
    ) -> str:
        processed = self.media_processing_service.process_upload(
            media_type=media_type,
            content=content,
            content_type=content_type,
            filename=filename,
        )
        return self.media_storage_service.store_bytes(
            media_id=media_id,
            media_type=media_type,
            content=processed.content,
            content_type=processed.content_type,
            filename=processed.filename,
        )

    def create_ocr_note_from_image(
        self,
        owner_user_id: str,
        content: bytes,
        filename: str | None = None,
        content_type: str | None = None,
    ) -> dict:
        note_data = self.create_image_note_from_upload(
            owner_user_id=owner_user_id,
            content=content,
            filename=filename,
            content_type=content_type,
        )
        note_id = note_data["note"]["id"]
        return self.recognize_ocr_note_image(note_id, owner_user_id)

    def create_image_note_from_upload(
        self,
        owner_user_id: str,
        content: bytes,
        filename: str | None = None,
        content_type: str | None = None,
    ) -> dict:
        if not self.repo.get_user(owner_user_id):
            raise HTTPException(status_code=404, detail="用户不存在")
        if not content:
            raise HTTPException(status_code=400, detail="图片不能为空")
        stored_url = self._store_uploaded_ocr_image(content, filename, content_type)
        now = now_iso()
        media = [self._image_media_payload(stored_url, filename)]
        note = UserNote(
            id=new_id("note"),
            ownerUserId=owner_user_id,
            importBatchId=None,
            sourceCardId=None,
            status="active",
            title="图片资料",
            summary="图片已保存，可按需识别文字。",
            body="图片已保存。你可以直接手动补充正文和字段，也可以点击识别图片文字后再整理。",
            coverUrl=stored_url,
            media=media,
            categoryIds=[],
            phone=None,
            locationText=None,
            sourceRefs=[],
            visibilityConfig=self._image_note_visibility_config(stored_url, filename),
            createdAt=now,
            updatedAt=now,
        )
        self.repo.save_user_note(note)
        return {
            "note": note.model_dump(),
            "ocr": {
                "status": "pending",
                "text": "",
                "provider": "",
                "configured": False,
                "confidence": None,
                "details": {"reason": "图片已保存，等待用户主动识别。"},
            },
        }

    def recognize_ocr_note_image(self, note_id: str, owner_user_id: str) -> dict:
        note = self.get_user_note(note_id, owner_user_id)
        image_content, image_name = self._load_note_image_bytes(note)
        ocr_result = self.ocr_service.extract_text(image_content, image_name)
        recognized_text = ocr_result.text.strip()
        if not recognized_text:
            note.visibilityConfig = self._ocr_visibility_config(note.visibilityConfig, ocr_result, recognized_text)
            note.updatedAt = now_iso()
            self.repo.save_user_note(note)
            return {
                "note": note.model_dump(),
                "ocr": self._ocr_response_payload(ocr_result, recognized_text),
            }
        content_object = ContentObjectPayload(
            sourceType="image_ocr",
            title="图片文字识别",
            textBlocks=[recognized_text] if recognized_text else [],
            media=[
                ContentMediaPayload(
                    type="image",
                    url=note.coverUrl or self._first_note_image_url(note),
                    title=image_name or "ocr-image",
                )
            ],
            metadata={
                "ocr": {
                    "provider": ocr_result.provider,
                    "configured": ocr_result.configured,
                    "confidence": ocr_result.confidence,
                    "details": ocr_result.details,
                    "textLength": len(recognized_text),
                }
            },
        )
        note_result = self.skill_router_service.run_content_to_note(owner_user_id, content_object)
        now = now_iso()
        existing_cover = note.coverUrl
        existing_media = note.media or []
        note.title = note_result.noteDraft.title
        note.summary = note_result.noteDraft.summary
        note.body = note_result.noteDraft.body
        note.coverUrl = existing_cover
        note.media = existing_media or [item.model_dump() for item in note_result.noteDraft.media]
        note.categoryIds = note_result.noteDraft.categoryIds
        note.phone = note_result.noteDraft.phone
        note.locationText = note_result.noteDraft.locationText
        note.sourceRefs = note_result.noteDraft.sourceRefs
        draft_config = self._preserve_ocr_image_refs(note_result.noteDraft.visibilityConfig, note.visibilityConfig)
        note.visibilityConfig = self._ocr_visibility_config(draft_config, ocr_result, recognized_text)
        note.status = "active"
        note.updatedAt = now
        skill_run = SkillRun.model_validate(note_result.skillRun.model_dump())
        skill_run.outputRef = note.id
        skill_run.inputSnapshot = {
            **skill_run.inputSnapshot,
            "ocr": {
                "provider": ocr_result.provider,
                "configured": ocr_result.configured,
                "confidence": ocr_result.confidence,
                "textLength": len(recognized_text),
            },
        }
        self.repo.save_user_note(note)
        self.repo.save_skill_run(skill_run)
        return {
            "note": note.model_dump(),
            "ocr": self._ocr_response_payload(ocr_result, recognized_text),
        }

    def _ocr_visibility_config(self, config: dict, ocr_result, recognized_text: str) -> dict:
        normalized = self._normalize_note_visibility_config(config)
        normalized["sourceType"] = "ocr"
        normalized["systemCategory"] = normalized.get("systemCategory") if normalized.get("cardType") in {"property_listing", "groupbuy_product"} else "图片"
        tags = self._unique_strings([*normalized.get("tags", []), "图片识别"])
        normalized["tags"] = tags
        structured_data = dict(normalized.get("structuredData") or {})
        structured_data["ocr"] = {
            "status": self._ocr_status(ocr_result, recognized_text),
            "provider": ocr_result.provider,
            "configured": ocr_result.configured,
            "confidence": ocr_result.confidence,
            "details": ocr_result.details,
            "text": recognized_text,
            "textLength": len(recognized_text),
        }
        if recognized_text:
            structured_data.setdefault("rawText", recognized_text)
        normalized["structuredData"] = structured_data
        return normalized

    def _store_uploaded_ocr_image(self, content: bytes, filename: str | None, content_type: str | None) -> str:
        storage = self.media_storage_service
        if storage.storage_mode == "mock":
            storage = MediaStorageService(
                storage_mode="local",
                storage_dir=settings.media_storage_dir,
                public_url_prefix=settings.media_public_url_prefix,
            )
        processed = self.media_processing_service.process_upload(
            media_type="image",
            content=content,
            content_type=content_type,
            filename=filename,
        )
        return storage.store_bytes(
            media_id=new_id("ocr_image"),
            media_type="image",
            content=processed.content,
            content_type=processed.content_type,
            filename=processed.filename,
        )

    def _image_media_payload(self, url: str, filename: str | None = None) -> dict:
        return {
            "type": "image",
            "url": url,
            "title": filename or "图片资料",
        }

    def _image_note_visibility_config(self, stored_url: str, filename: str | None = None) -> dict:
        normalized = self._normalize_note_visibility_config(
            {
                "cardType": "image_ocr",
                "cardState": "collected",
                "sourceType": "ocr",
                "systemCategory": "图片",
                "tags": ["图片", "图片识别", "待整理"],
                "structuredData": {
                    "images": [stored_url],
                    "rawText": "",
                    "ocr": {
                        "status": "pending",
                        "provider": "",
                        "configured": False,
                        "confidence": None,
                        "details": {"reason": "图片已保存，等待用户主动识别。"},
                        "text": "",
                        "textLength": 0,
                        "filename": filename or "",
                    },
                },
            }
        )
        normalized["conversionConfig"] = {key: False for key in CONVERSION_CONFIG_KEYS}
        return normalized

    def _preserve_ocr_image_refs(self, draft_config: dict, previous_config: dict) -> dict:
        result = dict(draft_config or {})
        draft_data = dict(result.get("structuredData") or {})
        previous_data = (previous_config or {}).get("structuredData") or {}
        if isinstance(previous_data, dict) and previous_data.get("images") and not draft_data.get("images"):
            draft_data["images"] = previous_data.get("images")
        result["structuredData"] = draft_data
        return result

    def _ocr_response_payload(self, ocr_result, recognized_text: str) -> dict:
        return {
            "status": self._ocr_status(ocr_result, recognized_text),
            "text": recognized_text,
            "provider": ocr_result.provider,
            "configured": ocr_result.configured,
            "confidence": ocr_result.confidence,
            "details": ocr_result.details,
        }

    def _ocr_status(self, ocr_result, recognized_text: str) -> str:
        if recognized_text:
            return "done"
        return "empty" if ocr_result.configured else "not_configured"

    def _load_note_image_bytes(self, note: UserNote) -> tuple[bytes, str]:
        image_url = self._first_note_image_url(note)
        if not image_url:
            raise HTTPException(status_code=400, detail="当前资料没有可识别的图片")
        local_path = self._local_media_path_from_url(image_url)
        if local_path and local_path.exists():
            return local_path.read_bytes(), local_path.name
        if image_url.startswith("http://") or image_url.startswith("https://"):
            try:
                response = httpx.get(image_url, timeout=15)
                response.raise_for_status()
            except Exception as exc:
                raise HTTPException(status_code=400, detail=f"图片读取失败：{exc}") from exc
            return response.content, Path(urlparse(image_url).path).name or "ocr-image"
        raise HTTPException(status_code=400, detail="图片文件不可读取，请重新上传图片")

    def _first_note_image_url(self, note: UserNote) -> str:
        if note.coverUrl:
            return note.coverUrl
        for item in note.media or []:
            if item.get("type") == "image" and item.get("url"):
                return str(item.get("url"))
        structured_data = (note.visibilityConfig or {}).get("structuredData") or {}
        images = structured_data.get("images") if isinstance(structured_data, dict) else []
        return str(images[0]) if images else ""

    def _local_media_path_from_url(self, image_url: str) -> Path | None:
        parsed = urlparse(image_url)
        path_value = unquote(parsed.path if parsed.scheme else image_url)
        prefix = settings.media_public_url_prefix.rstrip("/") or "/media"
        if not path_value.startswith(f"{prefix}/"):
            return None
        file_name = path_value[len(prefix) + 1 :]
        if not file_name or "/" in file_name or "\\" in file_name:
            return None
        return settings.media_storage_dir / file_name

    def save_media_retry_failure(
        self,
        media_id: str,
        media_type: str,
        open_kfid: str | None,
        error_message: str,
    ) -> MediaRetryJob:
        now = now_iso()
        existing = self.repo.get_media_retry_job(media_id)
        job = MediaRetryJob(
            id=existing.id if existing else f"media_retry_{media_id}",
            mediaId=media_id,
            mediaType=media_type,
            openKfid=open_kfid,
            status="failed",
            attempts=(existing.attempts if existing else 0) + 1,
            localMediaUrl=existing.localMediaUrl if existing else None,
            errorMessage=error_message,
            lastAttemptAt=now,
            createdAt=existing.createdAt if existing else now,
            updatedAt=now,
        )
        self.repo.save_media_retry_job(job)
        return job

    def save_media_retry_success(
        self,
        media_id: str,
        media_type: str,
        open_kfid: str | None,
        local_media_url: str,
    ) -> MediaRetryJob:
        now = now_iso()
        existing = self.repo.get_media_retry_job(media_id)
        job = MediaRetryJob(
            id=existing.id if existing else f"media_retry_{media_id}",
            mediaId=media_id,
            mediaType=media_type,
            openKfid=open_kfid,
            status="success",
            attempts=(existing.attempts if existing else 0) + 1,
            localMediaUrl=local_media_url,
            errorMessage=None,
            lastAttemptAt=now,
            createdAt=existing.createdAt if existing else now,
            updatedAt=now,
        )
        self.repo.save_media_retry_job(job)
        return job

    def list_media_retry_jobs(self, statuses: set[str] | None = None) -> list[dict]:
        return [item.model_dump() for item in self.repo.list_media_retry_jobs(statuses)]

    def advance_sync_cursor(
        self,
        open_kfid: str,
        cursor: str | None,
        has_more: bool,
        source: str,
        payload: dict,
    ) -> SyncCursor:
        now = now_iso()
        existing = self.repo.get_sync_cursor(open_kfid)
        sync_cursor = SyncCursor(
            id=existing.id if existing else f"sync_cursor_{open_kfid}",
            openKfid=open_kfid,
            cursor=cursor,
            hasMore=has_more,
            lastSource=source,
            lastPayload=payload,
            lastSyncedAt=now,
            syncStatus=existing.syncStatus if existing else "idle",
            lockToken=existing.lockToken if existing else None,
            lockedAt=existing.lockedAt if existing else None,
            lastError=existing.lastError if existing else None,
            createdAt=existing.createdAt if existing else now,
            updatedAt=now,
        )
        self.repo.save_sync_cursor(sync_cursor)
        return sync_cursor

    def claim_import(self, import_id: str, user_id: str) -> dict:
        batch = self.repo.get_import_batch(import_id)
        if not batch:
            raise HTTPException(status_code=404, detail="导入批次不存在")
        user = self.repo.get_user(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")
        if batch.generatedCardId is None:
            raise HTTPException(status_code=400, detail="该导入没有可认领卡片")
        card = self.repo.get_card(batch.generatedCardId)
        if not card:
            raise HTTPException(status_code=404, detail="草稿卡片不存在")

        now = now_iso()
        batch.claimedByUserId = user_id
        batch.status = "claimed"
        batch.updatedAt = now
        card.ownerUserId = user_id
        card.updatedAt = now
        if batch.generatedNoteId:
            note = self.repo.get_user_note(batch.generatedNoteId)
            if note:
                note.ownerUserId = user_id
                note.status = "active"
                note.updatedAt = now
                self.repo.save_user_note(note)
        binding = self._save_wecom_identity_binding(
            external_user_id=batch.externalUserId,
            owner_user_id=user_id,
            import_batch_id=batch.id,
            bind_source="claim_import",
        )
        self.repo.save_import_batch(batch)
        self.repo.save_card(card)
        return {
            "importBatch": batch,
            "card": card,
            "note": self.repo.get_user_note(batch.generatedNoteId) if batch.generatedNoteId else None,
            "identityBinding": binding,
        }

    def list_user_notes(
        self,
        owner_user_id: str,
        keyword: str | None = None,
        category_id: str | None = None,
        source_type: str | None = None,
        system_category: str | None = None,
        tag: str | None = None,
        topic_id: str | None = None,
        sort: str = "updated",
        include_deleted: bool = False,
    ) -> list[dict]:
        if not self.repo.get_user(owner_user_id):
            raise HTTPException(status_code=404, detail="用户不存在")
        notes = self.repo.list_user_notes(
            owner_user_id=owner_user_id,
            keyword=None,
            category_id=category_id,
            include_deleted=include_deleted,
        )
        filtered = self._filter_user_notes(notes, keyword, source_type, system_category, tag, topic_id)
        if sort == "collected":
            filtered = sorted(filtered, key=lambda item: item.createdAt, reverse=True)
        else:
            filtered = sorted(filtered, key=lambda item: item.updatedAt, reverse=True)
        return [item.model_dump() for item in filtered]

    def _filter_user_notes(
        self,
        notes: list[UserNote],
        keyword: str | None,
        source_type: str | None,
        system_category: str | None,
        tag: str | None,
        topic_id: str | None,
    ) -> list[UserNote]:
        result = notes
        if source_type:
            result = [item for item in result if (item.visibilityConfig or {}).get("sourceType") == source_type]
        if system_category:
            result = [item for item in result if (item.visibilityConfig or {}).get("systemCategory") == system_category]
        if tag:
            result = [item for item in result if tag in self._note_tags(item)]
        if topic_id:
            result = [item for item in result if topic_id in (item.visibilityConfig or {}).get("topicIds", [])]
        if keyword:
            lowered = keyword.lower().strip()
            query_digits = re.sub(r"\D+", "", lowered)
            result = [
                item
                for item in result
                if self._note_matches_keyword(item, lowered, query_digits)
            ]
        return result

    def _note_matches_keyword(self, note: UserNote, lowered: str, query_digits: str) -> bool:
        haystack = self._note_search_text(note).lower()
        if lowered in haystack:
            return True
        haystack_digits = re.sub(r"\D+", "", haystack)
        return bool(query_digits and query_digits in haystack_digits)

    def _note_search_text(self, note: UserNote) -> str:
        config = note.visibilityConfig or {}
        topics = " ".join(str(item.get("name", "")) for item in config.get("topics", []) if isinstance(item, dict))
        return " ".join(
            [
                note.title,
                note.summary,
                note.body,
                note.createdAt,
                self._date_search_text(note.createdAt),
                config.get("sourceName", ""),
                config.get("systemCategory", ""),
                config.get("cardType", ""),
                json.dumps(config.get("structuredData", {}), ensure_ascii=False),
                " ".join(self._note_tags(note)),
                topics,
            ]
        )

    def _date_search_text(self, value: str) -> str:
        parsed = parse_iso(value)
        if not parsed:
            return value or ""
        local = parsed.astimezone(SHANGHAI)
        month = local.month
        day = local.day
        return " ".join(
            [
                f"{local.year}年{month}月{day}日",
                f"{local.year}-{month:02d}-{day:02d}",
                f"{month}月{day}日",
                f"{month}{day}",
                f"{local.year}{month:02d}{day:02d}",
            ]
        )

    def _note_tags(self, note: UserNote) -> list[str]:
        config = note.visibilityConfig or {}
        tags: list[str] = []
        for key in ("tags", "userTags"):
            tags.extend([str(item).strip() for item in config.get(key, []) if str(item).strip()])
        for values in (config.get("tagLevels") or {}).values():
            if isinstance(values, list):
                tags.extend([str(item).strip() for item in values if str(item).strip()])
        return list(dict.fromkeys(tags))

    def get_user_note(self, note_id: str, owner_user_id: str) -> UserNote:
        note = self.repo.get_user_note(note_id)
        if not note or note.status == "deleted":
            raise HTTPException(status_code=404, detail="笔记不存在")
        if note.ownerUserId != owner_user_id:
            raise HTTPException(status_code=403, detail="仅笔记拥有者可查看")
        return note

    def list_showcases(self, owner_user_id: str) -> list[dict]:
        if not self.repo.get_user(owner_user_id):
            raise HTTPException(status_code=404, detail="用户不存在")
        return [self._showcase_owner_payload(item) for item in self.repo.list_showcase_pages(owner_user_id)]

    def create_showcase(self, payload: ShowcasePageRequest) -> ShowcasePage:
        self._ensure_showcase_owner(payload.ownerUserId)
        now = now_iso()
        showcase = ShowcasePage(
            id=new_id("showcase"),
            ownerUserId=payload.ownerUserId,
            status="draft",
            name=self._clean_showcase_name(payload.name),
            description=self._clean_optional_text(payload.description),
            bannerUrl=self._clean_optional_text(payload.bannerUrl),
            templateId=self._clean_optional_text(payload.templateId) or "classic_grid",
            shareTitle=self._clean_optional_text(payload.shareTitle),
            contactConfig=self._normalize_showcase_contact_config(payload.contactConfig),
            displayConfig=self._normalize_showcase_display_config(payload.displayConfig),
            items=self._normalize_showcase_items(payload.ownerUserId, payload.items),
            publishedAt=None,
            createdAt=now,
            updatedAt=now,
        )
        self.repo.save_showcase_page(showcase)
        return showcase

    def get_showcase_for_owner(self, showcase_id: str, owner_user_id: str) -> ShowcasePage:
        showcase = self.repo.get_showcase_page(showcase_id)
        if not showcase:
            raise HTTPException(status_code=404, detail="展示页不存在")
        if showcase.ownerUserId != owner_user_id:
            raise HTTPException(status_code=403, detail="仅展示页拥有者可查看")
        return showcase

    def update_showcase(self, showcase_id: str, payload: ShowcasePageRequest) -> ShowcasePage:
        showcase = self.get_showcase_for_owner(showcase_id, payload.ownerUserId)
        showcase.name = self._clean_showcase_name(payload.name)
        showcase.description = self._clean_optional_text(payload.description)
        showcase.bannerUrl = self._clean_optional_text(payload.bannerUrl)
        showcase.templateId = self._clean_optional_text(payload.templateId) or "classic_grid"
        showcase.shareTitle = self._clean_optional_text(payload.shareTitle)
        showcase.contactConfig = self._normalize_showcase_contact_config(payload.contactConfig)
        showcase.displayConfig = self._normalize_showcase_display_config(payload.displayConfig)
        showcase.items = self._normalize_showcase_items(payload.ownerUserId, payload.items)
        showcase.updatedAt = now_iso()
        self.repo.save_showcase_page(showcase)
        return showcase

    def publish_showcase(self, showcase_id: str, owner_user_id: str) -> ShowcasePage:
        showcase = self.get_showcase_for_owner(showcase_id, owner_user_id)
        valid_items = self._valid_showcase_items(showcase)
        if not self._clean_optional_text(showcase.name):
            raise HTTPException(status_code=400, detail="展示页名称不能为空")
        if not valid_items:
            raise HTTPException(status_code=400, detail="请至少选择一条有效资料后再发布")
        now = now_iso()
        showcase.status = "published"
        showcase.items = valid_items
        showcase.publishedAt = showcase.publishedAt or now
        showcase.updatedAt = now
        self.repo.save_showcase_page(showcase)
        return showcase

    def archive_showcase(self, showcase_id: str, owner_user_id: str) -> ShowcasePage:
        showcase = self.get_showcase_for_owner(showcase_id, owner_user_id)
        showcase.status = "archived"
        showcase.updatedAt = now_iso()
        self.repo.save_showcase_page(showcase)
        return showcase

    def get_public_showcase(self, showcase_id: str) -> dict:
        showcase = self.repo.get_showcase_page(showcase_id)
        if not showcase or showcase.status != "published":
            raise HTTPException(status_code=404, detail="展示页不存在或未发布")
        items = self._public_showcase_items(showcase)
        return {
            "id": showcase.id,
            "name": showcase.name,
            "description": showcase.description,
            "bannerUrl": showcase.bannerUrl,
            "templateId": showcase.templateId,
            "shareTitle": showcase.shareTitle or showcase.name,
            "contactConfig": showcase.contactConfig,
            "displayConfig": showcase.displayConfig,
            "items": items,
            "publishedAt": showcase.publishedAt,
            "updatedAt": showcase.updatedAt,
        }

    def _ensure_showcase_owner(self, owner_user_id: str) -> None:
        if not self.repo.get_user(owner_user_id):
            raise HTTPException(status_code=404, detail="用户不存在")

    def _showcase_owner_payload(self, showcase: ShowcasePage) -> dict:
        payload = showcase.model_dump()
        payload["itemCount"] = len(self._valid_showcase_items(showcase))
        payload["sharePath"] = f"/pages/showcase-view/index?id={showcase.id}"
        return payload

    def _clean_showcase_name(self, name: str) -> str:
        cleaned = str(name or "").strip()
        if not cleaned:
            raise HTTPException(status_code=400, detail="展示页名称不能为空")
        return cleaned[:80]

    def _clean_optional_text(self, value: str | None) -> str | None:
        cleaned = str(value or "").strip()
        return cleaned or None

    def _normalize_showcase_contact_config(self, config: dict | None) -> dict:
        source = config if isinstance(config, dict) else {}
        return {
            "phone": self._clean_optional_text(source.get("phone")),
            "wechat": self._clean_optional_text(source.get("wechat")),
            "contactText": self._clean_optional_text(source.get("contactText")) or "欢迎联系我了解详情",
            "showPhone": bool(source.get("showPhone", True)),
            "showWechat": bool(source.get("showWechat", True)),
        }

    def _normalize_showcase_display_config(self, config: dict | None) -> dict:
        source = config if isinstance(config, dict) else {}
        group_by = str(source.get("groupBy") or "none").strip()
        if group_by not in {"none", "cardType", "tag", "custom"}:
            group_by = "none"
        return {
            "groupBy": group_by,
            "showSearch": bool(source.get("showSearch", False)),
            "showTags": bool(source.get("showTags", True)),
            "primaryColor": str(source.get("primaryColor") or "#1677ff").strip()[:24],
        }

    def _normalize_showcase_items(self, owner_user_id: str, items: list) -> list[ShowcaseItem]:
        normalized: list[ShowcaseItem] = []
        seen: set[str] = set()
        for index, item in enumerate(items or []):
            note_id = str(getattr(item, "noteId", "") or "").strip()
            if not note_id or note_id in seen:
                continue
            note = self.repo.get_user_note(note_id)
            if not note or note.status == "deleted":
                raise HTTPException(status_code=400, detail=f"资料不存在或已删除：{note_id}")
            if note.ownerUserId != owner_user_id:
                raise HTTPException(status_code=403, detail="不能选择其他用户的资料")
            seen.add(note_id)
            normalized.append(
                ShowcaseItem(
                    noteId=note_id,
                    sortOrder=getattr(item, "sortOrder", index),
                    sectionTitle=self._clean_optional_text(getattr(item, "sectionTitle", None)),
                    displayTitle=self._clean_optional_text(getattr(item, "displayTitle", None)),
                    visible=bool(getattr(item, "visible", True)),
                    fieldConfig=getattr(item, "fieldConfig", {}) if isinstance(getattr(item, "fieldConfig", {}), dict) else {},
                )
            )
        return sorted(normalized, key=lambda row: row.sortOrder)

    def _valid_showcase_items(self, showcase: ShowcasePage) -> list[ShowcaseItem]:
        valid: list[ShowcaseItem] = []
        for item in sorted(showcase.items, key=lambda row: row.sortOrder):
            note = self.repo.get_user_note(item.noteId)
            if item.visible and note and note.status != "deleted" and note.ownerUserId == showcase.ownerUserId:
                valid.append(item)
        return valid

    def _public_showcase_items(self, showcase: ShowcasePage) -> list[dict]:
        rows: list[dict] = []
        for item in self._valid_showcase_items(showcase):
            note = self.repo.get_user_note(item.noteId)
            if note:
                rows.append(self._showcase_note_summary(note, item))
        return rows

    def _showcase_note_summary(self, note: UserNote, item: ShowcaseItem) -> dict:
        config = note.visibilityConfig or {}
        return {
            "noteId": note.id,
            "title": item.displayTitle or note.title,
            "summary": note.summary,
            "coverUrl": note.coverUrl,
            "sectionTitle": item.sectionTitle,
            "sortOrder": item.sortOrder,
            "cardType": config.get("cardType", "text_note"),
            "systemCategory": config.get("systemCategory", ""),
            "tags": self._note_tags(note),
            "updatedAt": note.updatedAt,
        }

    def update_user_note(self, note_id: str, payload: UserNoteUpdateRequest) -> UserNote:
        note = self.get_user_note(note_id, payload.ownerUserId)
        if not payload.title.strip():
            raise HTTPException(status_code=400, detail="标题不能为空")
        body = payload.body.strip()
        note.title = payload.title.strip()
        note.summary = (payload.summary or body[:120]).strip()
        note.body = body
        note.coverUrl = payload.coverUrl
        note.media = [item.model_dump() for item in payload.media]
        note.categoryIds = payload.categoryIds
        note.phone = payload.phone
        note.locationText = payload.locationText
        note.visibilityConfig = self._normalize_note_visibility_config(payload.visibilityConfig)
        note.updatedAt = now_iso()
        self.repo.save_user_note(note)
        return note

    def _normalize_note_visibility_config(self, config: dict) -> dict:
        normalized = dict(config or {})
        normalized.setdefault("cardType", "link" if normalized.get("contentMode") == "bookmark" else "text_note")
        normalized.setdefault("cardState", "collected")
        structured_data = normalized.get("structuredData")
        normalized["structuredData"] = structured_data if isinstance(structured_data, dict) else {}
        normalized["conversionConfig"] = self._normalize_conversion_config(
            normalized.get("cardType", "text_note"),
            normalized.get("conversionConfig", {}),
        )
        type_suggestions = normalized.get("typeSuggestions")
        normalized["typeSuggestions"] = type_suggestions if isinstance(type_suggestions, list) else []
        tag_levels = normalized.get("tagLevels") or {}
        if not isinstance(tag_levels, dict):
            tag_levels = {}
        for key in ("rule", "light", "deep"):
            tag_levels[key] = self._unique_strings(tag_levels.get(key, []))
        user_tags = self._unique_strings(normalized.get("userTags", []))
        tags = self._unique_strings([*tag_levels["rule"], *tag_levels["light"], *tag_levels["deep"], *user_tags, *normalized.get("tags", [])])
        normalized["tags"] = tags
        normalized["userTags"] = user_tags
        normalized["tagLevels"] = tag_levels
        normalized["topicIds"] = self._unique_strings(normalized.get("topicIds", []))
        normalized["topics"] = [item for item in normalized.get("topics", []) if isinstance(item, dict) and item.get("id")]
        normalized.setdefault("tagStatus", "user_updated" if user_tags else "rule_done")
        return normalized

    def _normalize_conversion_config(self, card_type: str, config: dict | None) -> dict:
        defaults = self._default_conversion_config(card_type)
        incoming = config if isinstance(config, dict) else {}
        result = dict(defaults)
        for key in CONVERSION_CONFIG_KEYS:
            if key in incoming:
                result[key] = bool(incoming.get(key))
        return result

    def _default_conversion_config(self, card_type: str) -> dict:
        if card_type == "property_listing":
            return dict(PROPERTY_CONVERSION_DEFAULTS)
        if card_type == "groupbuy_product":
            return dict(GROUPBUY_CONVERSION_DEFAULTS)
        return {key: False for key in CONVERSION_CONFIG_KEYS}

    def _unique_strings(self, values) -> list[str]:
        result: list[str] = []
        for value in values or []:
            text = str(value).strip()
            if text and text not in result:
                result.append(text)
        return result

    def organize_bookmark_note(self, note_id: str, owner_user_id: str) -> UserNote:
        note = self.get_user_note(note_id, owner_user_id)
        config = dict(note.visibilityConfig or {})
        card_type = config.get("cardType") or ("link" if config.get("contentMode") == "bookmark" else "text_note")
        tags = [item for item in config.get("tags", []) if item not in {"未整理", "待整理"}]
        if "已整理" not in tags:
            tags.append("已整理")
        config["cardState"] = "organized"
        config["tags"] = tags
        config["canDeepOrganize"] = False
        config["tagStatus"] = "deep_done"
        structured_data = dict(config.get("structuredData") or {})
        conversion_config = self._normalize_conversion_config(card_type, config.get("conversionConfig"))
        config["conversionConfig"] = conversion_config
        if card_type == "property_listing":
            config["contentMode"] = "structured_card"
            structured_data["organizeResult"] = {
                "summary": self._property_summary(structured_data, note),
                "generationOptions": ["房源推广图", "微信群文案", "客户话术", "对比表"],
                "enabledFeatures": self._enabled_conversion_features(card_type, conversion_config),
            }
            config["structuredData"] = structured_data
            note.summary = structured_data["organizeResult"]["summary"]
        elif card_type == "groupbuy_product":
            config["contentMode"] = "structured_card"
            structured_data["organizeResult"] = {
                "summary": self._groupbuy_summary(structured_data, note),
                "generationOptions": ["团购海报", "发群文案", "接龙格式", "商品卖点"],
                "enabledFeatures": self._enabled_conversion_features(card_type, conversion_config),
            }
            config["structuredData"] = structured_data
            note.summary = structured_data["organizeResult"]["summary"]
        else:
            config["contentMode"] = "deep_note"
            config["cardType"] = "article" if card_type == "link" else card_type
        note.visibilityConfig = config
        if note.summary in {"已收藏，待整理。", "已收藏，待整理"}:
            note.summary = note.body[:120] if note.body else note.title
        note.updatedAt = now_iso()
        self.repo.save_user_note(note)
        return note

    def generate_note_result(self, note_id: str, owner_user_id: str) -> UserNote:
        note = self.get_user_note(note_id, owner_user_id)
        config = self._normalize_note_visibility_config(note.visibilityConfig)
        card_type = config.get("cardType", "text_note")
        if card_type not in {"property_listing", "groupbuy_product"}:
            raise HTTPException(status_code=400, detail="当前资料卡暂不支持生成场景页")
        conversion_config = self._normalize_conversion_config(card_type, config.get("conversionConfig"))
        structured_data = dict(config.get("structuredData") or {})
        structured_data["generatedResult"] = {
            "pageType": "property_promo_page" if card_type == "property_listing" else "groupbuy_share_page",
            "status": "generated",
            "enabledActions": self._enabled_conversion_features(card_type, conversion_config),
            "note": "当前为生成态配置结果，正式海报/页面渲染后续由场景生成 Skill 接管。",
        }
        config["cardState"] = "generated"
        config["contentMode"] = "generated_card"
        config["conversionConfig"] = conversion_config
        config["structuredData"] = structured_data
        config["canDeepOrganize"] = False
        note.visibilityConfig = config
        note.updatedAt = now_iso()
        self.repo.save_user_note(note)
        return note

    def confirm_note_type(self, note_id: str, payload: NoteTypeConfirmRequest) -> UserNote:
        note = self.get_user_note(note_id, payload.ownerUserId)
        card_type = payload.cardType.strip()
        if card_type not in CONFIRMABLE_CARD_TYPES:
            raise HTTPException(status_code=400, detail="不支持确认成该资料类型")
        current_config = self._normalize_note_visibility_config(note.visibilityConfig)
        structured_data = self._build_confirmed_structured_data(note, current_config, card_type)
        system_category = "房源" if card_type == "property_listing" else "团购" if card_type == "groupbuy_product" else current_config.get("systemCategory", "待整理")
        extra_tags = ["房产", "房源"] if card_type == "property_listing" else ["团购", "商品"] if card_type == "groupbuy_product" else ["待整理"]
        conversion_config = self._confirmed_conversion_config(card_type, current_config)
        previous_explanation = current_config.get("recognitionExplanation") if isinstance(current_config.get("recognitionExplanation"), dict) else {}
        config = {
            **current_config,
            "contentMode": "note" if card_type == "text_note" else "structured_card",
            "cardType": card_type,
            "cardState": "collected" if card_type == "text_note" else "generated",
            "systemCategory": system_category,
            "structuredData": structured_data,
            "conversionConfig": conversion_config,
            "typeSuggestions": [],
            "recognitionConfidence": {
                "level": "manual",
                "selectedType": card_type,
                "confirmedAt": now_iso(),
            },
            "recognitionExplanation": {
                **previous_explanation,
                "level": "manual",
                "selectedType": card_type,
                "selectedLabel": self._card_type_label(card_type),
                "manualConfirmation": {
                    "cardType": card_type,
                    "label": self._card_type_label(card_type),
                    "confirmedAt": now_iso(),
                },
            },
            "tags": self._unique_strings([*current_config.get("tags", []), *extra_tags]),
        }
        note.visibilityConfig = self._normalize_note_visibility_config(config)
        note.updatedAt = now_iso()
        self.repo.save_user_note(note)
        return note

    def _build_confirmed_structured_data(self, note: UserNote, config: dict, card_type: str) -> dict:
        current = dict(config.get("structuredData") or {})
        miniapp = current.get("miniapp") if isinstance(current.get("miniapp"), dict) else None
        preserved = {"miniapp": miniapp} if miniapp else {}
        images = self._note_image_urls(note)
        if card_type == "property_listing":
            return {
                **preserved,
                "community": current.get("community") or note.title,
                "layout": current.get("layout", ""),
                "area": current.get("area", ""),
                "price": current.get("price", ""),
                "utilities": current.get("utilities", ""),
                "businessArea": current.get("businessArea", ""),
                "address": current.get("address") or note.locationText or "",
                "serviceFee": current.get("serviceFee", ""),
                "contact": current.get("contact") or note.phone or "",
                "propertyStatus": current.get("propertyStatus") or "active",
                "remark": current.get("remark") or note.summary or note.body,
                "images": images,
                "rawText": current.get("rawText") or note.body,
            }
        if card_type == "groupbuy_product":
            sku_config = current.get("skuConfig") if isinstance(current.get("skuConfig"), dict) else {}
            return {
                **preserved,
                "productName": current.get("productName") or note.title,
                "price": current.get("price", ""),
                "spec": current.get("spec", ""),
                "deadline": current.get("deadline", ""),
                "pickupMethod": current.get("pickupMethod", ""),
                "pickupLocation": current.get("pickupLocation") or note.locationText or "",
                "stockNote": current.get("stockNote", ""),
                "contact": current.get("contact") or note.phone or "",
                "remark": current.get("remark") or note.summary or note.body,
                "skuConfig": sku_config,
                "images": images,
                "rawText": current.get("rawText") or note.body,
            }
        return {
            **preserved,
            "rawText": current.get("rawText") or note.body,
            "images": images,
        }

    def _confirmed_conversion_config(self, card_type: str, config: dict) -> dict:
        source_type = config.get("sourceType")
        if card_type == "property_listing" and source_type == "miniapp":
            defaults = dict(PROPERTY_CONVERSION_DEFAULTS)
            defaults["showContactPhone"] = False
        else:
            defaults = self._default_conversion_config(card_type)
        incoming = config.get("conversionConfig") if isinstance(config.get("conversionConfig"), dict) else {}
        result = dict(defaults)
        for key in CONVERSION_CONFIG_KEYS:
            if key in incoming:
                result[key] = bool(incoming.get(key))
        return result

    def _note_image_urls(self, note: UserNote) -> list[str]:
        urls = [note.coverUrl, *[item.get("url") for item in note.media if isinstance(item, dict) and item.get("type") == "image"]]
        return self._unique_strings([item for item in urls if item])

    def _card_type_label(self, card_type: str) -> str:
        return {
            "property_listing": "房源",
            "groupbuy_product": "商品",
            "text_note": "普通笔记",
        }.get(card_type, "资料")

    def _enabled_conversion_features(self, card_type: str, config: dict) -> list[str]:
        labels = {
            "showContactPhone": "展示联系电话",
            "enableLightScrm": "轻 SCRM 跟进",
            "collectLeads": "收集线索",
            "enableAppointment": "预约看房",
            "enablePrivateConsultation": "私聊咨询",
            "enableSharePoster": "生成海报",
            "enableGroupRelay": "团购接龙",
            "enablePaymentPlaceholder": "下单按钮预留",
        }
        ordered_keys = [
            "showContactPhone",
            "enableLightScrm",
            "collectLeads",
            "enableAppointment",
            "enablePrivateConsultation",
            "enableSharePoster",
            "enableGroupRelay",
            "enablePaymentPlaceholder",
        ]
        return [labels[key] for key in ordered_keys if config.get(key)]

    def _property_summary(self, data: dict, note: UserNote) -> str:
        parts = [
            data.get("community") or note.title,
            data.get("price"),
            data.get("layout"),
            data.get("businessArea"),
        ]
        summary = " · ".join(str(item).strip() for item in parts if str(item or "").strip())
        return summary or note.summary or "已整理为房源字段卡。"

    def _groupbuy_summary(self, data: dict, note: UserNote) -> str:
        parts = [
            data.get("productName") or note.title,
            data.get("price"),
            data.get("spec"),
            data.get("pickupMethod"),
        ]
        summary = " · ".join(str(item).strip() for item in parts if str(item or "").strip())
        return summary or note.summary or "已整理为团购商品卡。"

    def suggest_note_tags(self, owner_user_id: str, note_id: str | None = None, text: str | None = None) -> dict:
        if note_id:
            note = self.get_user_note(note_id, owner_user_id)
            source_text = "\n".join([note.title, note.summary, note.body, (note.visibilityConfig or {}).get("sourceUrl", "")])
            config = note.visibilityConfig or {}
        else:
            if not self.repo.get_user(owner_user_id):
                raise HTTPException(status_code=404, detail="用户不存在")
            source_text = text or ""
            config = {}
        rule_tags = self._generate_rule_tags(source_text, config)
        return {
            "tagStatus": "rule_done",
            "tagLevels": {"rule": rule_tags, "light": [], "deep": []},
            "suggestedTags": rule_tags,
        }

    def _generate_rule_tags(self, text: str, config: dict | None = None) -> list[str]:
        source_url = (config or {}).get("sourceUrl", "")
        haystack = f"{text}\n{source_url}".lower()
        tags: list[str] = []
        if "mp.weixin.qq.com" in haystack:
            tags.append("微信文章")
        if "http://" in haystack or "https://" in haystack:
            tags.append("链接")
        keyword_tags = {
            "房源": ["房产", "房源"],
            "小区": ["房产"],
            "团购": ["团购"],
            "拼单": ["团购"],
            "草莓": ["草莓", "水果"],
            "露营": ["露营", "出行"],
            "亲子": ["亲子"],
            "装备": ["装备"],
            "合同": ["合同"],
            "python": ["Python"],
            "zip": ["文件"],
        }
        for keyword, values in keyword_tags.items():
            if keyword in haystack:
                tags.extend(values)
        return self._unique_strings(tags or ["待整理"])

    def list_topics(self, owner_user_id: str) -> list[dict]:
        if not self.repo.get_user(owner_user_id):
            raise HTTPException(status_code=404, detail="用户不存在")
        notes = self.repo.list_user_notes(owner_user_id, include_deleted=False)
        counts: dict[str, int] = {}
        for note in notes:
            for topic_id in (note.visibilityConfig or {}).get("topicIds", []):
                counts[topic_id] = counts.get(topic_id, 0) + 1
        return [{**topic.model_dump(), "noteCount": counts.get(topic.id, 0)} for topic in self.repo.list_topics(owner_user_id)]

    def create_topic(self, payload: TopicCreateRequest) -> Topic:
        if not self.repo.get_user(payload.ownerUserId):
            raise HTTPException(status_code=404, detail="用户不存在")
        name = payload.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="专题名称不能为空")
        if any(item.name == name for item in self.repo.list_topics(payload.ownerUserId)):
            raise HTTPException(status_code=400, detail="专题已存在")
        now = now_iso()
        topic = Topic(
            id=new_id("topic"),
            ownerUserId=payload.ownerUserId,
            name=name,
            description=(payload.description or "").strip() or None,
            color=(payload.color or "").strip() or None,
            createdAt=now,
            updatedAt=now,
        )
        self.repo.save_topic(topic)
        return topic

    def add_note_to_topic(self, note_id: str, topic_id: str, owner_user_id: str) -> UserNote:
        note = self.get_user_note(note_id, owner_user_id)
        topic = self.repo.get_topic(topic_id)
        if not topic or topic.ownerUserId != owner_user_id:
            raise HTTPException(status_code=404, detail="专题不存在")
        config = self._normalize_note_visibility_config(note.visibilityConfig)
        topic_ids = self._unique_strings([*config.get("topicIds", []), topic.id])
        topics = [item for item in config.get("topics", []) if item.get("id") != topic.id]
        topics.append({"id": topic.id, "name": topic.name})
        config["topicIds"] = topic_ids
        config["topics"] = topics
        note.visibilityConfig = config
        note.updatedAt = now_iso()
        self.repo.save_user_note(note)
        return note

    def remove_note_from_topic(self, note_id: str, topic_id: str, owner_user_id: str) -> UserNote:
        note = self.get_user_note(note_id, owner_user_id)
        config = self._normalize_note_visibility_config(note.visibilityConfig)
        config["topicIds"] = [item for item in config.get("topicIds", []) if item != topic_id]
        config["topics"] = [item for item in config.get("topics", []) if item.get("id") != topic_id]
        note.visibilityConfig = config
        note.updatedAt = now_iso()
        self.repo.save_user_note(note)
        return note

    def create_note_demo_data(self, owner_user_id: str) -> dict:
        user = self.repo.get_user(owner_user_id)
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")
        now = now_iso()
        demo_specs = [
            {
                "title": "测试房源A 万润时光里 27050 两房 近地铁",
                "summary": "用于测试轻 SCRM 红点、留资和预约。",
                "community": "万润时光里",
                "price": "27050",
                "layout": "loft 两房",
                "area": "万家丽 / 地铁口",
                "address": "长沙万润时光里",
                "phone": "13800001001",
                "customer": "王客户",
                "customerPhone": "13900001111",
                "customerWechat": "wx_demo_001",
                "appointment": {"date": "2026-06-20", "time": "14:30", "remark": "两个人看房"},
                "leadStatus": "pending",
            },
            {
                "title": "测试房源B 高桥北 精装一房 可短租",
                "summary": "用于测试已联系线索和拨号入口。",
                "community": "高桥北公寓",
                "price": "1600元/月",
                "layout": "精装一房",
                "area": "高桥北",
                "address": "长沙高桥北",
                "phone": "13800001002",
                "customer": "李客户",
                "customerPhone": "13900002222",
                "customerWechat": "wx_demo_002",
                "appointment": None,
                "leadStatus": "contacted",
            },
            {
                "title": "测试房源C 袁隆平地铁口 民水民电 首次出",
                "summary": "用于测试无客户动作时的空状态。",
                "community": "袁隆平地铁口公寓",
                "price": "1800元/月",
                "layout": "一室一厅",
                "area": "袁隆平地铁口",
                "address": "长沙袁隆平地铁口",
                "phone": "13800001003",
                "customer": "",
                "customerPhone": "",
                "customerWechat": "",
                "appointment": None,
                "leadStatus": "",
            },
        ]
        notes: list[UserNote] = []
        actions: list[CustomerAction] = []
        leads: list[LeadReminder] = []
        for spec in demo_specs:
            note_id = new_id("note")
            structured_data = {
                "community": spec["community"],
                "price": spec["price"],
                "layout": spec["layout"],
                "businessArea": spec["area"],
                "address": spec["address"],
                "contact": spec["phone"],
                "organizeResult": {
                    "summary": spec["summary"],
                    "generationOptions": ["房源推广图", "微信群文案", "客户话术", "对比表"],
                    "enabledFeatures": ["展示联系电话", "轻 SCRM 跟进", "收集线索", "预约看房"],
                },
                "generatedResult": {
                    "pageType": "property_promo_page",
                    "status": "generated",
                    "enabledActions": ["展示联系电话", "轻 SCRM 跟进", "收集线索", "预约看房"],
                    "note": "演示数据",
                },
            }
            note = UserNote(
                id=note_id,
                ownerUserId=owner_user_id,
                status="active",
                title=spec["title"],
                summary=spec["summary"],
                body=f"{spec['community']}，{spec['price']}，{spec['layout']}，{spec['area']}，带轻 SCRM 演示数据。",
                phone=spec["phone"],
                locationText=spec["address"],
                visibilityConfig={
                    "cardType": "property_listing",
                    "cardState": "generated",
                    "contentMode": "generated_card",
                    "tags": ["房源", "演示数据"],
                    "conversionConfig": {
                        "showContactPhone": True,
                        "enableLightScrm": True,
                        "collectLeads": True,
                        "enableAppointment": True,
                        "enablePrivateConsultation": True,
                        "enableSharePoster": True,
                        "enableGroupRelay": False,
                        "enablePaymentPlaceholder": False,
                    },
                    "structuredData": structured_data,
                },
                createdAt=now,
                updatedAt=now,
            )
            self.repo.save_user_note(note)
            notes.append(note)
            if not spec["customerPhone"]:
                continue
            lead = LeadReminder(
                id=new_id("lead"),
                ownerUserId=owner_user_id,
                cardId=note.id,
                viewerUserId=new_id("viewer"),
                nickname=spec["customer"],
                avatarUrl="https://example.com/avatar-demo.png",
                status=spec["leadStatus"],
                note="演示客户：可测试拨号、保存资料和跟进状态。",
                customerPhone=spec["customerPhone"],
                customerWechat=spec["customerWechat"],
                budgetText="预算待确认",
                intentLevel="高意向" if spec["leadStatus"] == "pending" else "中意向",
                customerTags=["演示", "房源客户"],
                viewCount=2,
                lastViewedAt=now,
                contactedAt=now if spec["leadStatus"] == "contacted" else None,
                nextFollowUpAt="2026-06-20T14:30:00+08:00" if spec["appointment"] else None,
                followUpLogs=[
                    LeadFollowUpLog(id=new_id("log"), content="演示线索已生成，可点击拨号或编辑客户资料。", createdAt=now)
                ],
                createdAt=now,
                updatedAt=now,
            )
            self.repo.save_lead_reminder(lead)
            leads.append(lead)
            lead_action = CustomerAction(
                id=new_id("action"),
                ownerUserId=owner_user_id,
                noteId=note.id,
                sourceCardId=note.id,
                viewerUserId=lead.viewerUserId,
                actionKey="lead-contact",
                actionLabel="留下电话/微信",
                payload={
                    "name": spec["customer"],
                    "phone": spec["customerPhone"],
                    "wechat": spec["customerWechat"],
                    "remark": "演示留资",
                },
                projectionRefs={"leadReminderId": lead.id},
                createdAt=now,
                updatedAt=now,
            )
            self.repo.save_customer_action(lead_action)
            actions.append(lead_action)
            if spec["appointment"]:
                appointment_action = CustomerAction(
                    id=new_id("action"),
                    ownerUserId=owner_user_id,
                    noteId=note.id,
                    sourceCardId=note.id,
                    viewerUserId=lead.viewerUserId,
                    actionKey="appointment",
                    actionLabel="预约看房",
                    payload=spec["appointment"],
                    projectionRefs={"leadReminderId": lead.id},
                    createdAt=now,
                    updatedAt=now,
                )
                self.repo.save_customer_action(appointment_action)
                actions.append(appointment_action)
        product_note = UserNote(
            id=new_id("note"),
            ownerUserId=owner_user_id,
            status="active",
            title="测试商品 周末现摘草莓",
            summary="用于测试商品展示、SKU 售罄和团购接龙。",
            body="周末现摘草莓，支持多规格选择；售罄 SKU 不可提交，接龙不进入 SCRM。",
            coverUrl="https://images.unsplash.com/photo-1464965911861-746a04b4bca6?auto=format&fit=crop&w=900&q=80",
            media=[
                {
                    "id": new_id("media"),
                    "type": "image",
                    "url": "https://images.unsplash.com/photo-1464965911861-746a04b4bca6?auto=format&fit=crop&w=900&q=80",
                    "sortOrder": 1,
                }
            ],
            categoryIds=[],
            phone="13800001004",
            locationText="社区自提点",
            visibilityConfig={
                "cardType": "groupbuy_product",
                "cardState": "generated",
                "contentMode": "generated_card",
                "tags": ["商品", "团购", "演示数据"],
                "conversionConfig": {
                    "showContactPhone": True,
                    "enableLightScrm": False,
                    "collectLeads": False,
                    "enableAppointment": False,
                    "enablePrivateConsultation": False,
                    "enableSharePoster": True,
                    "enableGroupRelay": True,
                    "enablePaymentPlaceholder": False,
                },
                "structuredData": {
                    "productName": "周末现摘草莓",
                    "price": "28-78 元",
                    "spec": "按口味和规格选择",
                    "deliveryMethod": "社区自提 / 同城配送",
                    "pickupLocation": "社区自提点，具体地址群内通知",
                    "contactPhone": "13800001004",
                    "stockNote": "数量有限，售罄 SKU 不可接龙",
                    "deadline": "",
                    "skuConfig": {
                        "attributeGroups": [
                            {
                                "id": "taste",
                                "name": "口味",
                                "options": [
                                    {"id": "sweet", "label": "甜口"},
                                    {"id": "sour_sweet", "label": "酸甜"},
                                ],
                            },
                            {
                                "id": "size",
                                "name": "规格",
                                "options": [
                                    {"id": "one_jin", "label": "1斤装"},
                                    {"id": "three_jin", "label": "3斤装"},
                                ],
                            },
                        ],
                        "skus": [
                            {"id": "sku_sweet_one", "key": "sweet|one_jin", "name": "甜口 / 1斤装", "price": "28", "description": "适合尝鲜", "soldOut": False},
                            {"id": "sku_sweet_three", "key": "sweet|three_jin", "name": "甜口 / 3斤装", "price": "78", "description": "家庭分享装", "soldOut": False},
                            {"id": "sku_sour_one", "key": "sour_sweet|one_jin", "name": "酸甜 / 1斤装", "price": "26", "description": "口感清爽", "soldOut": True},
                            {"id": "sku_sour_three", "key": "sour_sweet|three_jin", "name": "酸甜 / 3斤装", "price": "72", "description": "适合做果酱", "soldOut": False},
                        ],
                    },
                },
            },
            createdAt=now,
            updatedAt=now,
        )
        self.repo.save_user_note(product_note)
        notes.append(product_note)
        relay_action = CustomerAction(
            id=new_id("action"),
            ownerUserId=owner_user_id,
            noteId=product_note.id,
            sourceCardId=None,
            viewerUserId=new_id("viewer"),
            actionKey="relay-intent",
            actionLabel="参与接龙",
            payload={
                "skuKey": "sweet|three_jin",
                "skuId": "sku_sweet_three",
                "skuName": "甜口 / 3斤装",
                "skuPrice": "78",
                "quantity": 2,
                "phone": "13800138000",
                "wechat": "berry_fan",
                "remark": "周六下午自提",
                "name": "李小莓",
                "avatarUrl": "https://example.com/avatar-demo.png",
            },
            projectionRefs={},
            createdAt=now,
            updatedAt=now,
        )
        self.repo.save_customer_action(relay_action)
        actions.append(relay_action)
        return {
            "notes": [item.model_dump() for item in notes],
            "actionsCreated": len(actions),
            "leadsCreated": len(leads),
        }

    def get_customer_action_config(
        self,
        note_id: str,
        viewer_user_id: str | None = None,
        anonymous_id: str | None = None,
    ) -> dict:
        note = self._get_active_note(note_id)
        config = self._normalize_note_visibility_config(note.visibilityConfig)
        actions = self._available_customer_actions(config)
        submitted = self._submitted_customer_actions(note_id, viewer_user_id, anonymous_id)
        def submitted_for_action(action_key: str) -> dict:
            if action_key in PRODUCT_ORDER_ACTION_KEYS:
                return submitted.get(action_key) or next(
                    (submitted.get(key) for key in PRODUCT_ORDER_ACTION_KEYS if submitted.get(key)),
                    {},
                )
            return submitted.get(action_key, {})
        return {
            "noteId": note.id,
            "ownerUserId": note.ownerUserId,
            "sourceCardId": note.sourceCardId,
            "actions": [
                {
                    **item,
                    "submitted": bool(submitted_for_action(item["key"])),
                    "statusText": submitted_for_action(item["key"]).get("statusText", ""),
                    "submittedAt": submitted_for_action(item["key"]).get("createdAt"),
                    "submittedPayload": submitted_for_action(item["key"]).get("payload", {}),
                }
                for item in actions
            ],
        }

    def list_customer_actions_for_note_owner(self, note_id: str, owner_user_id: str) -> dict:
        note = self._get_active_note(note_id)
        if note.ownerUserId != owner_user_id:
            raise HTTPException(status_code=403, detail="仅发布者可查看客户动作")
        config = self._normalize_note_visibility_config(note.visibilityConfig)
        card_type = config.get("cardType", "text_note")
        actions = self.repo.list_customer_actions_for_note(note_id)
        projected_lead_ids = {
            str((action.projectionRefs or {}).get("leadReminderId") or "")
            for action in actions
            if (action.projectionRefs or {}).get("leadReminderId")
        }
        lead_rows = [
            self._build_lead_reminder_row(item)
            for item in self.repo.list_lead_reminders(owner_user_id)
            if item.id in projected_lead_ids
        ]
        pending_count = sum(1 for item in lead_rows if item.get("status") == "pending")
        action_rows = []
        lead_status_by_id = {item["id"]: item for item in lead_rows}
        for action in actions:
            lead_id = (action.projectionRefs or {}).get("leadReminderId")
            lead = lead_status_by_id.get(lead_id)
            row = action.model_dump()
            row["customerName"] = action.payload.get("name") or (lead.get("nickname") if lead else "") or "客户"
            row["customerAvatarUrl"] = action.payload.get("avatarUrl") or (lead.get("avatarUrl") if lead else None)
            row["leadReminderId"] = lead_id
            row["leadStatus"] = lead.get("status") if lead else None
            row["leadStatusText"] = self._lead_status_text(lead.get("status")) if lead else ""
            row["statusText"] = self._customer_action_status_text(action.actionKey, action.payload)
            row["displayRows"] = self._customer_action_display_rows(action)
            action_rows.append(row)
        order_count = sum(1 for item in actions if item.actionKey in PRODUCT_ORDER_ACTION_KEYS)
        relay_count = sum(1 for item in actions if item.actionKey == "relay-intent")
        summary = {
            "total": len(actions),
            "leadContact": sum(1 for item in actions if item.actionKey == "lead-contact"),
            "appointment": sum(1 for item in actions if item.actionKey == "appointment"),
            "orderIntent": order_count,
            "relayIntent": relay_count,
            "consult": sum(1 for item in actions if item.actionKey == "consult-click"),
            "leads": len(lead_rows),
            "pending": pending_count,
            "hasUnread": pending_count > 0 or order_count > 0,
            "latestActionAt": actions[0].createdAt if actions else None,
            "mode": "product_relay" if card_type == "groupbuy_product" else "customer_actions",
        }
        return {
            "noteId": note.id,
            "ownerUserId": note.ownerUserId,
            "sourceCardId": note.sourceCardId,
            "cardType": card_type,
            "summary": summary,
            "actions": action_rows,
            "leads": lead_rows,
        }

    def submit_customer_action(self, note_id: str, action_key: str, payload: CustomerActionSubmitRequest) -> dict:
        note = self._get_active_note(note_id)
        config = self._normalize_note_visibility_config(note.visibilityConfig)
        allowed_keys = {item["key"] for item in self._available_customer_actions(config)}
        if action_key not in allowed_keys:
            raise HTTPException(status_code=400, detail="当前资料未启用该客户动作")
        if action_key not in {"lead-contact", "appointment", "order-intent", "relay-intent"}:
            raise HTTPException(status_code=400, detail="该客户动作暂未接入持久化")
        viewer_key = self._customer_viewer_key(payload.viewerUserId, payload.anonymousId)
        if action_key in PRODUCT_ORDER_ACTION_KEYS:
            existing = next(
                (
                    item
                    for item in self.repo.list_customer_actions_for_note(note_id, payload.viewerUserId, payload.anonymousId)
                    if item.actionKey in PRODUCT_ORDER_ACTION_KEYS
                ),
                None,
            )
            if existing:
                raise HTTPException(status_code=409, detail="你已经提交过下单")
        clean_payload = self._normalize_customer_action_payload(action_key, payload.payload, config)
        if action_key in PRODUCT_ORDER_ACTION_KEYS:
            clean_payload["name"] = (payload.nickname or payload.payload.get("name") or "微信客户").strip()
            if payload.avatarUrl or payload.payload.get("avatarUrl"):
                clean_payload["avatarUrl"] = payload.avatarUrl or payload.payload.get("avatarUrl")
        now = now_iso()
        action = CustomerAction(
            id=new_id("action"),
            ownerUserId=note.ownerUserId,
            noteId=note.id,
            sourceCardId=note.sourceCardId,
            viewerUserId=payload.viewerUserId,
            anonymousId=payload.anonymousId,
            actionKey=action_key,
            actionLabel=CUSTOMER_ACTION_LABELS[action_key],
            payload=clean_payload,
            projectionRefs={},
            createdAt=now,
            updatedAt=now,
        )
        reminder = None
        if action_key in {"lead-contact", "appointment"}:
            reminder = self._project_customer_action_to_lead(note, action, payload, viewer_key)
            action.projectionRefs = {"leadReminderId": reminder.id}
        self.repo.save_customer_action(action)
        return {
            "action": action.model_dump(),
            "projection": {
                "leadReminderId": reminder.id,
                "status": reminder.status,
                "nextFollowUpAt": reminder.nextFollowUpAt,
            } if reminder else {},
            "statusText": self._customer_action_status_text(action_key, clean_payload),
        }

    def _get_active_note(self, note_id: str) -> UserNote:
        note = self.repo.get_user_note(note_id)
        if not note or note.status == "deleted":
            raise HTTPException(status_code=404, detail="笔记不存在")
        return note

    def _available_customer_actions(self, config: dict) -> list[dict]:
        conversion = config.get("conversionConfig") or {}
        card_type = config.get("cardType", "text_note")
        actions: list[dict] = []
        if conversion.get("collectLeads"):
            actions.append({
                "key": "lead-contact",
                "label": "留下电话/微信",
                "formTitle": "留下电话/微信",
                "submitText": "提交联系方式",
                "fields": CUSTOMER_ACTION_FIELDS["lead-contact"],
            })
        if conversion.get("enableAppointment"):
            actions.append({
                "key": "appointment",
                "label": "预约看房" if card_type == "property_listing" else "预约沟通",
                "formTitle": "预约看房" if card_type == "property_listing" else "预约沟通",
                "submitText": "提交预约",
                "fields": CUSTOMER_ACTION_FIELDS["appointment"],
            })
        if card_type == "groupbuy_product":
            structured_data = config.get("structuredData") or {}
            action_key = "relay-intent" if conversion.get("enableGroupRelay") else "order-intent"
            actions.append({
                "key": action_key,
                "label": "参与接龙" if action_key == "relay-intent" else "商品下单",
                "formTitle": "选择商品规格",
                "submitText": "下单并接龙" if action_key == "relay-intent" else "下单",
                "fields": CUSTOMER_ACTION_FIELDS[action_key],
                "skuConfig": self._normalize_sku_config(structured_data),
            })
        return actions

    def _submitted_customer_actions(
        self,
        note_id: str,
        viewer_user_id: str | None,
        anonymous_id: str | None,
    ) -> dict:
        if not viewer_user_id and not anonymous_id:
            return {}
        submitted: dict = {}
        for action in self.repo.list_customer_actions_for_note(note_id, viewer_user_id, anonymous_id):
            submitted.setdefault(action.actionKey, {
                "createdAt": action.createdAt,
                "statusText": self._customer_action_status_text(action.actionKey, action.payload),
                "payload": action.payload,
            })
        return submitted

    def _customer_viewer_key(self, viewer_user_id: str | None, anonymous_id: str | None) -> str:
        viewer_key = (viewer_user_id or anonymous_id or "").strip()
        if not viewer_key:
            raise HTTPException(status_code=400, detail="缺少客户身份")
        return viewer_key

    def _normalize_customer_action_payload(self, action_key: str, payload: dict, config: dict | None = None) -> dict:
        data = payload if isinstance(payload, dict) else {}
        if action_key == "lead-contact":
            phone = str(data.get("phone") or "").strip()
            wechat = str(data.get("wechat") or "").strip()
            if not phone and not wechat:
                raise HTTPException(status_code=400, detail="请填写电话或微信")
            return {
                "name": str(data.get("name") or "").strip(),
                "phone": phone,
                "wechat": wechat,
                "remark": str(data.get("remark") or "").strip(),
            }
        if action_key == "appointment":
            date = str(data.get("date") or "").strip()
            time = str(data.get("time") or "").strip()
            if not date or not time:
                raise HTTPException(status_code=400, detail="请选择预约日期和时间")
            return {
                "date": date,
                "time": time,
                "remark": str(data.get("remark") or "").strip(),
            }
        if action_key in PRODUCT_ORDER_ACTION_KEYS:
            sku_config = self._normalize_sku_config((config or {}).get("structuredData") or {})
            sku_key = str(data.get("skuKey") or "").strip()
            sku = next((item for item in sku_config["skus"] if item.get("key") == sku_key or item.get("id") == sku_key), None)
            if not sku:
                raise HTTPException(status_code=400, detail="请选择商品规格")
            if sku.get("soldOut"):
                raise HTTPException(status_code=400, detail="该规格已售罄")
            quantity = str(data.get("quantity") or "1").strip()
            try:
                quantity_number = int(quantity)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail="数量必须是整数") from exc
            if quantity_number < 1:
                raise HTTPException(status_code=400, detail="数量至少为 1")
            phone = str(data.get("phone") or "").strip()
            address = str(data.get("address") or "").strip()
            if not phone:
                raise HTTPException(status_code=400, detail="请填写联系电话")
            if not address:
                raise HTTPException(status_code=400, detail="请填写地址")
            order_status = str(data.get("orderStatus") or "submitted").strip() or "submitted"
            if order_status not in ORDER_STATUSES:
                order_status = "submitted"
            return {
                "skuKey": sku.get("key") or sku.get("id"),
                "skuId": sku.get("id") or sku.get("key"),
                "skuName": sku.get("name") or "默认规格",
                "skuPrice": sku.get("price") or "",
                "quantity": quantity_number,
                "receiverName": str(data.get("receiverName") or "").strip(),
                "phone": phone,
                "address": address,
                "wechat": str(data.get("wechat") or "").strip(),
                "remark": str(data.get("remark") or "").strip(),
                "orderStatus": order_status,
            }
        return dict(data)

    def _normalize_sku_config(self, structured_data: dict) -> dict:
        config = structured_data.get("skuConfig") if isinstance(structured_data, dict) else {}
        config = config if isinstance(config, dict) else {}
        groups = []
        for group_index, group in enumerate(config.get("attributeGroups") or []):
            if not isinstance(group, dict):
                continue
            options = [
                {
                    "id": str(option.get("id") or f"option_{group_index}_{option_index}"),
                    "label": str(option.get("label") or option.get("name") or "").strip(),
                }
                for option_index, option in enumerate(group.get("options") or [])
                if isinstance(option, dict) and str(option.get("label") or option.get("name") or "").strip()
            ]
            if options:
                groups.append({
                    "id": str(group.get("id") or f"group_{group_index}"),
                    "name": str(group.get("name") or f"属性{group_index + 1}").strip(),
                    "options": options,
                })
        skus = []
        for index, sku in enumerate(config.get("skus") or []):
            if not isinstance(sku, dict):
                continue
            key = str(sku.get("key") or sku.get("id") or "").strip()
            name = str(sku.get("name") or "").strip()
            if not key and not name:
                continue
            skus.append({
                "id": str(sku.get("id") or key or f"sku_{index}"),
                "key": key or str(sku.get("id") or f"sku_{index}"),
                "name": name or key or "默认规格",
                "price": str(sku.get("price") or structured_data.get("price") or "").strip(),
                "description": str(sku.get("description") or "").strip(),
                "soldOut": bool(sku.get("soldOut")),
            })
        if not skus:
            default_name = str(structured_data.get("spec") or structured_data.get("productName") or "默认规格").strip()
            skus = [{
                "id": "default",
                "key": "default",
                "name": default_name,
                "price": str(structured_data.get("price") or "").strip(),
                "description": str(structured_data.get("pickupMethod") or "").strip(),
                "soldOut": False,
            }]
        return {"attributeGroups": groups, "skus": skus}

    def _project_customer_action_to_lead(
        self,
        note: UserNote,
        action: CustomerAction,
        request: CustomerActionSubmitRequest,
        viewer_key: str,
    ) -> LeadReminder:
        source_card_id = note.sourceCardId or note.id
        existing = self.repo.get_lead_reminder_by_card_viewer(source_card_id, viewer_key)
        now = now_iso()
        nickname = (request.nickname or action.payload.get("name") or "客户").strip()
        logs = list(existing.followUpLogs if existing else [])
        log_content = self._customer_action_log_content(action.actionKey, action.payload)
        if log_content:
            logs.insert(0, LeadFollowUpLog(id=new_id("log"), content=log_content, createdAt=now))
        reminder = LeadReminder(
            id=existing.id if existing else new_id("lead"),
            ownerUserId=note.ownerUserId,
            cardId=source_card_id,
            viewerUserId=viewer_key,
            nickname=nickname,
            avatarUrl=request.avatarUrl or (existing.avatarUrl if existing else None),
            status="pending" if not existing else existing.status,
            note=self._merge_lead_note(existing.note if existing else None, action),
            customerPhone=action.payload.get("phone") or (existing.customerPhone if existing else None),
            customerWechat=action.payload.get("wechat") or (existing.customerWechat if existing else None),
            budgetText=existing.budgetText if existing else None,
            intentLevel=existing.intentLevel if existing else None,
            customerTags=existing.customerTags if existing else [],
            viewCount=existing.viewCount if existing else 0,
            lastViewedAt=now,
            contactedAt=existing.contactedAt if existing else None,
            closedAt=existing.closedAt if existing else None,
            conclusionReason=existing.conclusionReason if existing else None,
            nextFollowUpAt=self._appointment_follow_up_at(action.payload) if action.actionKey == "appointment" else (existing.nextFollowUpAt if existing else None),
            followUpLogs=logs,
            createdAt=existing.createdAt if existing else now,
            updatedAt=now,
        )
        self.repo.save_lead_reminder(reminder)
        return reminder

    def _customer_action_log_content(self, action_key: str, payload: dict) -> str:
        if action_key == "lead-contact":
            pieces = [
                "客户留下联系方式",
                f"电话：{payload.get('phone')}" if payload.get("phone") else "",
                f"微信：{payload.get('wechat')}" if payload.get("wechat") else "",
                f"备注：{payload.get('remark')}" if payload.get("remark") else "",
            ]
            return "；".join([item for item in pieces if item])
        if action_key == "appointment":
            remark = f"；备注：{payload.get('remark')}" if payload.get("remark") else ""
            return f"客户预约：{payload.get('date')} {payload.get('time')}{remark}"
        return ""

    def _merge_lead_note(self, current_note: str | None, action: CustomerAction) -> str:
        text = self._customer_action_log_content(action.actionKey, action.payload)
        if not text:
            return current_note or ""
        if current_note and text in current_note:
            return current_note
        return "\n".join([item for item in [text, current_note or ""] if item]).strip()

    def _appointment_follow_up_at(self, payload: dict) -> str | None:
        date = str(payload.get("date") or "").strip()
        time = str(payload.get("time") or "").strip()
        if not date or not time:
            return None
        return f"{date}T{time}:00+08:00"

    def _customer_action_status_text(self, action_key: str, payload: dict) -> str:
        if action_key == "lead-contact":
            return "已提交联系方式"
        if action_key == "appointment":
            return f"已预约 {payload.get('date', '')} {payload.get('time', '')}".strip()
        if action_key == "order-intent":
            sku = payload.get("skuName") or "商品"
            quantity = payload.get("quantity") or 1
            return f"已下单 {sku} x {quantity}"
        if action_key == "relay-intent":
            sku = payload.get("skuName") or "商品"
            quantity = payload.get("quantity") or 1
            return f"已接龙 {sku} x {quantity}"
        return "已记录"

    def _customer_action_display_rows(self, action: CustomerAction) -> list[dict]:
        payload = action.payload or {}
        if action.actionKey in PRODUCT_ORDER_ACTION_KEYS:
            rows = [
                ("规格", payload.get("skuName")),
                ("单价", payload.get("skuPrice")),
                ("数量", payload.get("quantity")),
                ("收货人", payload.get("receiverName")),
                ("地址", payload.get("address")),
                ("电话", payload.get("phone")),
                ("微信", payload.get("wechat")),
                ("备注", payload.get("remark")),
            ]
            return [{"label": label, "value": str(value)} for label, value in rows if value not in (None, "")]
        rows = [
            ("姓名", payload.get("name")),
            ("电话", payload.get("phone")),
            ("微信", payload.get("wechat")),
            ("预约", " ".join(str(payload.get(key) or "") for key in ("date", "time")).strip()),
            ("备注", payload.get("remark")),
        ]
        return [{"label": label, "value": str(value)} for label, value in rows if value]

    def list_orders(self, user_id: str, role: str) -> dict:
        if role not in {"buyer", "seller"}:
            raise HTTPException(status_code=400, detail="订单角色不正确")
        rows = [
            self._build_order_row(note, action, role)
            for note, action in self._iter_order_actions()
            if (role == "buyer" and action.viewerUserId == user_id)
            or (role == "seller" and action.ownerUserId == user_id)
        ]
        return {"role": role, "orders": rows}

    def get_order(self, order_id: str, user_id: str) -> dict:
        note, action, role = self._get_order_for_user(order_id, user_id)
        return self._build_order_row(note, action, role)

    def update_order_status(self, order_id: str, user_id: str, status_value: str) -> dict:
        note, action, role = self._get_order_for_user(order_id, user_id)
        if role != "seller":
            raise HTTPException(status_code=403, detail="仅商家可更新订单状态")
        if status_value not in ORDER_STATUSES:
            raise HTTPException(status_code=400, detail="订单状态不正确")
        action.payload = {**(action.payload or {}), "orderStatus": status_value}
        action.updatedAt = now_iso()
        self.repo.save_customer_action(action)
        return self._build_order_row(note, action, role)

    def _iter_order_actions(self) -> list[tuple[UserNote, CustomerAction]]:
        rows: list[tuple[UserNote, CustomerAction]] = []
        for note in self.repo.list_all_user_notes(include_deleted=False):
            config = self._normalize_note_visibility_config(note.visibilityConfig)
            if config.get("cardType") != "groupbuy_product":
                continue
            for action in self.repo.list_customer_actions_for_note(note.id):
                if action.actionKey in PRODUCT_ORDER_ACTION_KEYS:
                    rows.append((note, action))
        return sorted(rows, key=lambda row: row[1].createdAt, reverse=True)

    def _get_order_for_user(self, order_id: str, user_id: str) -> tuple[UserNote, CustomerAction, str]:
        action = self.repo.get_customer_action(order_id)
        if not action or action.actionKey not in PRODUCT_ORDER_ACTION_KEYS:
            raise HTTPException(status_code=404, detail="订单不存在")
        note = self._get_active_note(action.noteId)
        if action.ownerUserId == user_id:
            return note, action, "seller"
        if action.viewerUserId == user_id:
            return note, action, "buyer"
        raise HTTPException(status_code=403, detail="无权查看该订单")

    def _build_order_row(self, note: UserNote, action: CustomerAction, role: str) -> dict:
        config = self._normalize_note_visibility_config(note.visibilityConfig)
        structured_data = config.get("structuredData") or {}
        payload = action.payload or {}
        status_value = payload.get("orderStatus") or "submitted"
        status_labels = {
            "submitted": "已下单",
            "contacted": "已联系",
            "completed": "已完成",
            "cancelled": "已取消",
        }
        return {
            "id": action.id,
            "actionKey": action.actionKey,
            "role": role,
            "noteId": note.id,
            "sellerUserId": action.ownerUserId,
            "buyerUserId": action.viewerUserId,
            "buyerName": payload.get("name") or "微信用户",
            "buyerAvatarUrl": payload.get("avatarUrl") or "",
            "title": structured_data.get("productName") or note.title,
            "coverUrl": note.coverUrl,
            "skuName": payload.get("skuName") or "默认规格",
            "skuPrice": payload.get("skuPrice") or "",
            "quantity": payload.get("quantity") or 1,
            "receiverName": payload.get("receiverName") or "",
            "phone": payload.get("phone") or "",
            "address": payload.get("address") or "",
            "wechat": payload.get("wechat") or "",
            "remark": payload.get("remark") or "",
            "status": status_value,
            "statusText": status_labels.get(status_value, "已下单"),
            "createdAt": action.createdAt,
            "updatedAt": action.updatedAt,
        }

    def list_message_threads(self, user_id: str) -> dict:
        threads = [self._build_message_thread_row(thread, user_id) for thread in self.repo.list_message_threads_for_user(user_id)]
        return {
            "threads": threads,
            "unreadTotal": sum(item.get("unreadCount", 0) for item in threads),
        }

    def create_message_thread(self, payload: dict) -> dict:
        user_id = str(payload.get("userId") or "").strip()
        note_id = str(payload.get("noteId") or "").strip()
        order_action_id = str(payload.get("orderActionId") or "").strip() or None
        buyer_user_id = str(payload.get("buyerUserId") or "").strip() or None
        content = str(payload.get("content") or "").strip()
        if not user_id or not note_id:
            raise HTTPException(status_code=400, detail="缺少会话参数")
        note = self._get_active_note(note_id)
        order_action = self.repo.get_customer_action(order_action_id) if order_action_id else None
        if order_action:
            if order_action.noteId != note.id or order_action.actionKey not in PRODUCT_ORDER_ACTION_KEYS:
                raise HTTPException(status_code=400, detail="订单不属于当前资料")
            buyer_user_id = order_action.viewerUserId
            if user_id not in {note.ownerUserId, order_action.viewerUserId}:
                raise HTTPException(status_code=403, detail="无权打开该订单会话")
        elif user_id == note.ownerUserId:
            if not buyer_user_id:
                raise HTTPException(status_code=400, detail="缺少买家身份")
        else:
            buyer_user_id = user_id
        if not buyer_user_id:
            raise HTTPException(status_code=400, detail="缺少买家身份")
        participant_ids = sorted({note.ownerUserId, buyer_user_id})
        thread = next(
            (
                item
                for item in self.repo.list_message_threads_for_user(user_id)
                if item.noteId == note.id
                and item.orderActionId == order_action_id
                and item.ownerUserId == note.ownerUserId
                and item.buyerUserId == buyer_user_id
            ),
            None,
        )
        now = now_iso()
        if not thread:
            thread = MessageThread(
                id=new_id("thread"),
                noteId=note.id,
                orderActionId=order_action_id,
                ownerUserId=note.ownerUserId,
                buyerUserId=buyer_user_id,
                participantUserIds=participant_ids,
                title=note.title,
                unreadByUser={user_id: 0},
                createdAt=now,
                updatedAt=now,
            )
            self.repo.save_message_thread(thread)
        if content:
            self._append_message(thread, user_id, content)
            thread = self.repo.get_message_thread(thread.id) or thread
        return self._build_message_thread_row(thread, user_id)

    def list_thread_messages(self, thread_id: str, user_id: str) -> dict:
        thread = self._get_thread_for_user(thread_id, user_id)
        return {
            "thread": self._build_message_thread_row(thread, user_id),
            "messages": [item.model_dump() for item in self.repo.list_message_records_for_thread(thread.id)],
        }

    def send_thread_message(self, thread_id: str, user_id: str, content: str) -> dict:
        thread = self._get_thread_for_user(thread_id, user_id)
        record = self._append_message(thread, user_id, content)
        thread = self.repo.get_message_thread(thread.id) or thread
        return {
            "thread": self._build_message_thread_row(thread, user_id),
            "message": record.model_dump(),
        }

    def mark_message_thread_read(self, thread_id: str, user_id: str) -> dict:
        thread = self._get_thread_for_user(thread_id, user_id)
        thread.unreadByUser = {**(thread.unreadByUser or {}), user_id: 0}
        thread.updatedAt = now_iso()
        self.repo.save_message_thread(thread)
        return self._build_message_thread_row(thread, user_id)

    def _append_message(self, thread: MessageThread, sender_user_id: str, content: str) -> MessageRecord:
        text = str(content or "").strip()
        if not text:
            raise HTTPException(status_code=400, detail="消息不能为空")
        if sender_user_id not in set(thread.participantUserIds):
            raise HTTPException(status_code=403, detail="无权发送消息")
        now = now_iso()
        record = MessageRecord(id=new_id("msg"), threadId=thread.id, senderUserId=sender_user_id, content=text, createdAt=now)
        unread = dict(thread.unreadByUser or {})
        for participant_id in thread.participantUserIds:
            unread[participant_id] = 0 if participant_id == sender_user_id else int(unread.get(participant_id, 0)) + 1
        thread.lastMessage = text
        thread.lastMessageAt = now
        thread.unreadByUser = unread
        thread.updatedAt = now
        self.repo.save_message_record(record)
        self.repo.save_message_thread(thread)
        return record

    def _get_thread_for_user(self, thread_id: str, user_id: str) -> MessageThread:
        thread = self.repo.get_message_thread(thread_id)
        if not thread:
            raise HTTPException(status_code=404, detail="会话不存在")
        if user_id not in set(thread.participantUserIds):
            raise HTTPException(status_code=403, detail="无权查看该会话")
        return thread

    def _build_message_thread_row(self, thread: MessageThread, user_id: str) -> dict:
        note = self.repo.get_user_note(thread.noteId)
        order = self.repo.get_customer_action(thread.orderActionId) if thread.orderActionId else None
        owner = self.repo.get_user(thread.ownerUserId)
        buyer = self.repo.get_user(thread.buyerUserId)
        order_payload = order.payload if order else {}
        participants = {
            thread.ownerUserId: {
                "userId": thread.ownerUserId,
                "role": "owner",
                "nickname": owner.nickname if owner else "发布者",
                "avatarUrl": owner.avatarUrl if owner else "",
            },
            thread.buyerUserId: {
                "userId": thread.buyerUserId,
                "role": "buyer",
                "nickname": (buyer.nickname if buyer else "") or order_payload.get("name") or "客户",
                "avatarUrl": (buyer.avatarUrl if buyer else "") or order_payload.get("avatarUrl") or "",
            },
        }
        return {
            **thread.model_dump(),
            "noteTitle": note.title if note else thread.title,
            "noteCoverUrl": note.coverUrl if note else "",
            "orderStatus": (order.payload or {}).get("orderStatus", "submitted") if order else "",
            "orderSkuName": (order.payload or {}).get("skuName", "") if order else "",
            "peerUserId": thread.ownerUserId if user_id == thread.buyerUserId else thread.buyerUserId,
            "participants": participants,
            "currentUserId": user_id,
            "unreadCount": int((thread.unreadByUser or {}).get(user_id, 0)),
        }

    def delete_user_note(self, note_id: str, owner_user_id: str) -> dict:
        note = self.get_user_note(note_id, owner_user_id)
        note.status = "deleted"
        note.updatedAt = now_iso()
        self.repo.save_user_note(note)
        return {"deletedNoteId": note_id}

    def list_cards(self, owner_user_id: str | None = None, keyword: str | None = None, category_id: str | None = None) -> list[dict]:
        cards = self.repo.list_cards(owner_user_id=owner_user_id, keyword=keyword, category_id=category_id)
        return [
            {
                **item.model_dump(),
                "stats": self._build_card_stats(item.id),
                "sourceNoteId": self._find_note_id_by_source_card(item.id),
            }
            for item in cards
        ]

    def get_card_detail(self, card_id: str) -> dict:
        card = self.get_card(card_id)
        return {
            **card.model_dump(),
            "sourceNoteId": self._find_note_id_by_source_card(card.id),
        }

    def _find_note_id_by_source_card(self, card_id: str) -> str | None:
        for note in self.repo.list_all_user_notes(include_deleted=False):
            if note.sourceCardId == card_id:
                return note.id
        return None

    def list_categories(self, owner_user_id: str | None = None) -> list[dict]:
        return [item.model_dump() for item in self.repo.list_categories(owner_user_id)]

    def create_category(self, payload: CategoryCreateRequest) -> Category:
        user = self.repo.get_user(payload.ownerUserId)
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")
        name = payload.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="标签名称不能为空")
        existing = self.repo.list_categories(payload.ownerUserId)
        if any(item.name == name for item in existing):
            raise HTTPException(status_code=400, detail="标签已存在")
        now = now_iso()
        category = Category(
            id=new_id("cat"),
            ownerUserId=payload.ownerUserId,
            name=name,
            sortOrder=len(existing) + 1,
            createdAt=now,
        )
        self.repo.save_category(category)
        return category

    def delete_category(self, category_id: str, owner_user_id: str) -> dict:
        category = self.repo.get_category(category_id)
        if not category:
            raise HTTPException(status_code=404, detail="标签不存在")
        if category.ownerUserId != owner_user_id:
            raise HTTPException(status_code=403, detail="仅标签拥有者可删除")
        for card in self.repo.list_cards(owner_user_id=owner_user_id):
            if category_id in card.categoryIds:
                card.categoryIds = [item for item in card.categoryIds if item != category_id]
                card.updatedAt = now_iso()
                self.repo.save_card(card)
        self.repo.delete_category(category_id)
        return {"deletedCategoryId": category_id}

    def get_card(self, card_id: str) -> Card:
        card = self.repo.get_card(card_id)
        if not card:
            raise HTTPException(status_code=404, detail="卡片不存在")
        return card

    def delete_card(self, card_id: str, owner_user_id: str) -> dict:
        card = self.repo.get_card(card_id)
        if not card:
            raise HTTPException(status_code=404, detail="卡片不存在")
        if card.ownerUserId != owner_user_id:
            raise HTTPException(status_code=403, detail="仅卡片拥有者可删除")
        self.repo.delete_card(card_id)
        return {"deletedCardId": card_id}

    def create_card(self, payload: CardCreateRequest) -> Card:
        user = self.repo.get_user(payload.ownerUserId)
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")
        if not payload.title.strip():
            raise HTTPException(status_code=400, detail="标题不能为空")

        now = now_iso()
        card_id = new_id("card")
        card = Card(
            id=card_id,
            ownerUserId=payload.ownerUserId,
            status="draft",
            title=payload.title.strip(),
            coverUrl=payload.coverUrl,
            detailText=payload.detailText.strip() or payload.title.strip(),
            projectName=payload.projectName,
            locationText=payload.locationText,
            phone=payload.phone,
            relayNotice=payload.relayNotice,
            sourceUrl=payload.sourceUrl,
            enabledFields=payload.enabledFields,
            categoryIds=payload.categoryIds,
            media=self._build_card_media(card_id, payload.model_dump().get("media")),
            relayConfig=RelayConfig(**payload.relayConfig.model_dump()),
            createdAt=now,
            updatedAt=now,
        )
        self.repo.save_card(card)
        return card

    def update_card(self, card_id: str, payload: CardUpdateRequest) -> Card:
        card = self.repo.get_card(card_id)
        if not card:
            raise HTTPException(status_code=404, detail="卡片不存在")
        if card.ownerUserId != payload.ownerUserId:
            raise HTTPException(status_code=403, detail="仅卡片拥有者可编辑")

        update_data = payload.model_dump()
        now = now_iso()
        for key, value in update_data.items():
            if key == "relayConfig":
                relay_config_data = value.model_dump() if hasattr(value, "model_dump") else value
                card.relayConfig = card.relayConfig.model_copy(update=relay_config_data)
            elif key == "media":
                card.media = self._build_card_media(card.id, value)
            else:
                setattr(card, key, value)
        card.updatedAt = now
        self.repo.save_card(card)
        return card

    def publish_card(self, card_id: str, user_id: str) -> Card:
        card = self.repo.get_card(card_id)
        if not card:
            raise HTTPException(status_code=404, detail="卡片不存在")
        if card.ownerUserId != user_id:
            raise HTTPException(status_code=403, detail="仅卡片拥有者可发布")
        now = now_iso()
        card.status = "published"
        card.publishedAt = now
        card.updatedAt = now
        self.repo.save_card(card)
        return card

    def duplicate_card(self, card_id: str, user_id: str) -> Card:
        source = self.repo.get_card(card_id)
        if not source:
            raise HTTPException(status_code=404, detail="原卡片不存在")
        if source.ownerUserId != user_id:
            raise HTTPException(status_code=403, detail="仅卡片拥有者可复用")

        now = now_iso()
        copy_card = source.model_copy(deep=True)
        copy_card.id = new_id("card")
        copy_card.sourceCardId = source.id
        copy_card.importBatchId = None
        copy_card.status = "draft"
        copy_card.publishedAt = None
        copy_card.createdAt = now
        copy_card.updatedAt = now
        remapped_media = []
        for item in copy_card.media:
            item.id = new_id("card_media")
            item.cardId = copy_card.id
            item.createdAt = now
            remapped_media.append(item)
        copy_card.media = remapped_media
        self.repo.save_card(copy_card)
        return copy_card

    def record_view(self, card_id: str, payload: RecordViewRequest) -> ViewEvent:
        card = self.repo.get_card(card_id)
        if not card:
            raise HTTPException(status_code=404, detail="卡片不存在")

        now = now_iso()
        event = ViewEvent(
            id=new_id("view"),
            cardId=card_id,
            viewerUserId=payload.viewerUserId,
            viewType="logged_in" if payload.viewerUserId else "anonymous",
            anonymousId=payload.anonymousId,
            nickname=payload.nickname,
            avatarUrl=payload.avatarUrl,
            viewedAt=now,
            dateKey=date_key(now),
        )
        self.repo.add_view_event(event)
        return event

    def get_card_stats(self, card_id: str, requester_user_id: str | None = None) -> dict:
        card = self.repo.get_card(card_id)
        if not card:
            raise HTTPException(status_code=404, detail="卡片不存在")

        stats = self._build_card_stats(card_id)
        relay_entries = self.repo.list_relay_entries_for_card(card_id, relay_status="active")
        is_owner = requester_user_id == card.ownerUserId
        current_user_relay = None
        relay_payload = []
        for item in relay_entries:
            row = item.model_dump()
            if requester_user_id and item.userId == requester_user_id:
                current_user_relay = row.copy()
            if not is_owner:
                row["nickname"] = item.maskedNickname
                row["phone"] = None
                row["address"] = None
            relay_payload.append(row)
        return {
            **stats,
            "relayEntries": relay_payload,
            "currentUserRelay": current_user_relay,
        }

    def create_relay(self, card_id: str, payload: CreateRelayRequest) -> RelayEntry:
        card = self.repo.get_card(card_id)
        if not card:
            raise HTTPException(status_code=404, detail="卡片不存在")
        if not payload.userId:
            raise HTTPException(status_code=400, detail="未登录用户不能接龙")
        if card.relayConfig.requirePhone and not payload.phone:
            raise HTTPException(status_code=400, detail="手机号为必填项")
        if card.relayConfig.requireAddress and not payload.address:
            raise HTTPException(status_code=400, detail="地址为必填项")
        existing_relay = next(
            (
                item
                for item in self.repo.list_relay_entries_for_card(card_id, relay_status="active")
                if item.userId == payload.userId
            ),
            None,
        )
        if existing_relay:
            raise HTTPException(status_code=409, detail="你已经提交过接龙")

        now = now_iso()
        relay = RelayEntry(
            id=new_id("relay"),
            cardId=card_id,
            userId=payload.userId,
            nickname=payload.nickname,
            avatarUrl=payload.avatarUrl,
            maskedNickname=mask_nickname(payload.nickname),
            phone=payload.phone,
            address=payload.address,
            status="active",
            followUpStatus="pending",
            createdAt=now,
            updatedAt=now,
        )
        self.repo.add_relay_entry(relay)
        return relay

    def list_relays(self, card_id: str, requester_user_id: str) -> list[dict]:
        card = self.repo.get_card(card_id)
        if not card:
            raise HTTPException(status_code=404, detail="卡片不存在")
        is_owner = requester_user_id == card.ownerUserId
        rows = []
        for item in self.repo.list_relay_entries_for_card(card_id, relay_status="active"):
            payload = item.model_dump()
            if not is_owner:
                payload["nickname"] = item.maskedNickname
                payload["phone"] = None
                payload["address"] = None
            rows.append(payload)
        return rows

    def delete_relay(self, relay_id: str, operator_user_id: str) -> RelayEntry:
        relay = self.repo.get_relay_entry(relay_id)
        if not relay:
            raise HTTPException(status_code=404, detail="接龙记录不存在")
        card = self.repo.get_card(relay.cardId)
        if not card or card.ownerUserId != operator_user_id:
            raise HTTPException(status_code=403, detail="仅团长可删除接龙")
        relay.status = "deleted"
        relay.updatedAt = now_iso()
        self.repo.save_relay_entry(relay)
        return relay

    def mark_followed(self, relay_id: str, operator_user_id: str) -> RelayEntry:
        relay = self.repo.get_relay_entry(relay_id)
        if not relay:
            raise HTTPException(status_code=404, detail="接龙记录不存在")
        card = self.repo.get_card(relay.cardId)
        if not card or card.ownerUserId != operator_user_id:
            raise HTTPException(status_code=403, detail="仅团长可标记跟进")
        relay.followUpStatus = "followed"
        relay.updatedAt = now_iso()
        self.repo.save_relay_entry(relay)
        return relay

    def list_lead_reminders(self, owner_user_id: str, reminder_status: str | None = None) -> list[dict]:
        reminders = self.repo.list_lead_reminders(owner_user_id, reminder_status)
        return [self._build_lead_reminder_row(item) for item in reminders]

    def get_lead_reminder_detail(self, reminder_id: str, owner_user_id: str) -> dict:
        reminder = self.repo.get_lead_reminder(reminder_id)
        if not reminder:
            raise HTTPException(status_code=404, detail="线索不存在")
        if reminder.ownerUserId != owner_user_id:
            raise HTTPException(status_code=403, detail="仅发布者可查看线索")
        return self._build_lead_reminder_row(reminder)

    def _build_lead_reminder_row(self, reminder: LeadReminder) -> dict:
        row = reminder.model_dump()
        card = self.repo.get_card(reminder.cardId)
        note = self._find_note_by_lead_source(reminder.cardId)
        row["cardTitle"] = card.title if card else note.title if note else "资源已删除"
        row["cardStatus"] = card.status if card else "active" if note and note.status != "deleted" else "archived"
        row["sourceNoteId"] = note.id if note else None
        return row

    def _lead_status_text(self, status: str | None) -> str:
        status_map = {
            "pending": "待联系",
            "contacted": "已联系",
            "invalid": "无效",
            "paused": "暂不跟进",
            "completed": "已完成",
        }
        return status_map.get(status or "", "")

    def _find_note_by_lead_source(self, source_id: str) -> UserNote | None:
        note = self.repo.get_user_note(source_id)
        if note:
            return note
        return next(
            (item for item in self.repo.list_all_user_notes(include_deleted=False) if item.sourceCardId == source_id),
            None,
        )

    def upsert_lead_reminder(self, payload: LeadReminderUpsertRequest) -> LeadReminder:
        card = self.repo.get_card(payload.cardId)
        if not card:
            raise HTTPException(status_code=404, detail="资源不存在")
        if card.ownerUserId != payload.ownerUserId:
            raise HTTPException(status_code=403, detail="仅发布者可管理线索")
        if payload.status not in LEAD_REMINDER_STATUSES:
            raise HTTPException(status_code=400, detail="线索状态无效")

        now = now_iso()
        existing = self.repo.get_lead_reminder_by_card_viewer(payload.cardId, payload.viewerUserId)
        contacted_at = existing.contactedAt if existing else None
        if payload.status == "contacted" and not contacted_at:
            contacted_at = now
        if payload.status == "pending":
            contacted_at = None
        closed_at = existing.closedAt if existing else None
        conclusion_reason = existing.conclusionReason if existing else None
        if payload.status not in LEAD_CLOSED_STATUSES:
            closed_at = None
            conclusion_reason = None
        reminder = LeadReminder(
            id=existing.id if existing else new_id("lead"),
            ownerUserId=payload.ownerUserId,
            cardId=payload.cardId,
            viewerUserId=payload.viewerUserId,
            nickname=payload.nickname,
            avatarUrl=payload.avatarUrl,
            status=payload.status,
            note=payload.note,
            customerPhone=existing.customerPhone if existing else None,
            customerWechat=existing.customerWechat if existing else None,
            budgetText=existing.budgetText if existing else None,
            intentLevel=existing.intentLevel if existing else None,
            customerTags=existing.customerTags if existing else [],
            viewCount=max(0, int(payload.viewCount or 0)),
            lastViewedAt=payload.lastViewedAt,
            contactedAt=contacted_at,
            closedAt=closed_at,
            conclusionReason=conclusion_reason,
            nextFollowUpAt=payload.nextFollowUpAt,
            followUpLogs=existing.followUpLogs if existing else [],
            createdAt=existing.createdAt if existing else now,
            updatedAt=now,
        )
        self.repo.save_lead_reminder(reminder)
        return reminder

    def update_lead_reminder(self, reminder_id: str, payload: LeadReminderUpdateRequest) -> LeadReminder:
        reminder = self.repo.get_lead_reminder(reminder_id)
        if not reminder:
            raise HTTPException(status_code=404, detail="线索不存在")
        if reminder.ownerUserId != payload.ownerUserId:
            raise HTTPException(status_code=403, detail="仅发布者可管理线索")
        if payload.status is not None and payload.status not in LEAD_REMINDER_STATUSES:
            raise HTTPException(status_code=400, detail="线索状态无效")
        now = now_iso()
        if payload.status is not None:
            reminder.status = payload.status
            reminder.contactedAt = now if payload.status == "contacted" else None
            reminder.closedAt = now if payload.status in LEAD_CLOSED_STATUSES else None
            if payload.status not in LEAD_CLOSED_STATUSES:
                reminder.conclusionReason = None
        if payload.note is not None:
            reminder.note = payload.note
        if payload.customerPhone is not None:
            reminder.customerPhone = payload.customerPhone
        if payload.customerWechat is not None:
            reminder.customerWechat = payload.customerWechat
        if payload.budgetText is not None:
            reminder.budgetText = payload.budgetText
        if payload.intentLevel is not None:
            reminder.intentLevel = payload.intentLevel
        if payload.customerTags is not None:
            reminder.customerTags = [tag.strip() for tag in payload.customerTags if tag.strip()]
        if payload.conclusionReason is not None and reminder.status in LEAD_CLOSED_STATUSES:
            reminder.conclusionReason = payload.conclusionReason
        if payload.nextFollowUpAt is not None:
            reminder.nextFollowUpAt = payload.nextFollowUpAt
        log_content = (payload.logContent or "").strip()
        if log_content:
            reminder.followUpLogs.insert(0, LeadFollowUpLog(id=new_id("log"), content=log_content, createdAt=now))
        reminder.updatedAt = now
        self.repo.save_lead_reminder(reminder)
        return reminder

    def delete_lead_reminder(self, reminder_id: str, owner_user_id: str) -> dict:
        reminder = self.repo.get_lead_reminder(reminder_id)
        if not reminder:
            raise HTTPException(status_code=404, detail="线索不存在")
        if reminder.ownerUserId != owner_user_id:
            raise HTTPException(status_code=403, detail="仅发布者可管理线索")
        self.repo.delete_lead_reminder(reminder_id)
        return {"deletedLeadReminderId": reminder_id}

    def _build_card_stats(self, card_id: str) -> dict:
        events = self.repo.list_view_events_for_card(card_id)
        relays = self.repo.list_relay_entries_for_card(card_id, relay_status="active")
        return self._build_stats_from_events(card_id, events, relays)

    def _build_stats_map(self, state: AppState) -> dict[str, dict]:
        stats = defaultdict(
            lambda: {
                "pv": 0,
                "uv": 0,
                "anonymousPv": 0,
                "anonymousUv": 0,
                "loggedInViewers": [],
                "relayCount": 0,
            }
        )
        logged_viewers = defaultdict(dict)
        unique_anonymous = defaultdict(set)
        for event in state.view_events:
            row = stats[event.cardId]
            row["pv"] += 1
            if event.viewType == "logged_in":
                key = event.viewerUserId or event.id
                viewer = logged_viewers[event.cardId].setdefault(
                    key,
                    {
                        "userId": event.viewerUserId,
                        "nickname": event.nickname,
                        "avatarUrl": event.avatarUrl,
                        "viewedAt": event.viewedAt,
                        "viewCount": 0,
                    },
                )
                viewer["viewCount"] += 1
                if event.viewedAt > viewer["viewedAt"]:
                    viewer["viewedAt"] = event.viewedAt
                    viewer["nickname"] = event.nickname
                    viewer["avatarUrl"] = event.avatarUrl
            else:
                row["anonymousPv"] += 1
                key = event.anonymousId or event.id
                unique_anonymous[event.cardId].add(key)

        for card_id, row in stats.items():
            row["loggedInViewers"] = sorted(
                logged_viewers[card_id].values(),
                key=lambda item: item.get("viewedAt") or "",
                reverse=True,
            )
            row["uv"] = len(logged_viewers[card_id]) + len(unique_anonymous[card_id])
            row["anonymousUv"] = len(unique_anonymous[card_id])
            row["relayCount"] = len(
                [item for item in state.relay_entries if item.cardId == card_id and item.status == "active"]
            )
        return stats

    def _build_stats_from_events(self, card_id: str, events: list[ViewEvent], relays: list[RelayEntry]) -> dict:
        row = {
            "pv": 0,
            "uv": 0,
            "anonymousPv": 0,
            "anonymousUv": 0,
            "loggedInViewers": [],
            "relayCount": len(relays),
        }
        logged_viewers = {}
        unique_anonymous = set()
        for event in events:
            row["pv"] += 1
            if event.viewType == "logged_in":
                key = event.viewerUserId or event.id
                viewer = logged_viewers.setdefault(
                    key,
                    {
                        "userId": event.viewerUserId,
                        "nickname": event.nickname,
                        "avatarUrl": event.avatarUrl,
                        "viewedAt": event.viewedAt,
                        "viewCount": 0,
                    },
                )
                viewer["viewCount"] += 1
                if event.viewedAt > viewer["viewedAt"]:
                    viewer["viewedAt"] = event.viewedAt
                    viewer["nickname"] = event.nickname
                    viewer["avatarUrl"] = event.avatarUrl
            else:
                row["anonymousPv"] += 1
                unique_anonymous.add(event.anonymousId or event.id)
        row["loggedInViewers"] = sorted(
            logged_viewers.values(),
            key=lambda item: item.get("viewedAt") or "",
            reverse=True,
        )
        row["uv"] = len(logged_viewers) + len(unique_anonymous)
        row["anonymousUv"] = len(unique_anonymous)
        return row
