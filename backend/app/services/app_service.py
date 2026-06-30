from __future__ import annotations

import hashlib
import hmac
import json
import re
import time
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse
from uuid import uuid4
import httpx
from fastapi import HTTPException, status

from app.core.config import settings
from app.models.domain import AppState, Card, CardMedia, Category, CustomerAction, ImportBatch, LeadFollowUpLog, LeadReminder, MediaAsset, MediaAssetRef, MessageRecord, MessageThread, MediaRetryJob, RawMessage, RelayConfig, RelayEntry, ShowcaseEvent, ShowcaseItem, ShowcasePage, SkillRun, SyncCursor, Topic, User, UserNote, ViewEvent, WecomArchiveCursor, WecomArchiveMessage, WecomIdentityBinding
from app.schemas.auth import MockLoginRequest, UserProfileUpdateRequest, WechatLoginRequest
from app.schemas.categories import CategoryCreateRequest
from app.schemas.cards import CardCreateRequest, CardUpdateRequest, CreateRelayRequest, LeadReminderUpdateRequest, LeadReminderUpsertRequest, RecordViewRequest
from app.schemas.notes import CustomerActionSubmitRequest, ManualNoteDraftRequest, NoteTypeConfirmRequest, PropertyBatchCreateRequest, PropertyBatchParseRequest, PropertySameCloneRequest, QuickNoteCaptureRequest, TopicCreateRequest, UserNoteUpdateRequest
from app.schemas.showcases import ShowcaseEventRequest, ShowcasePageRequest
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
from app.services.text_safety import strip_unicode_surrogates
from app.services.time_utils import SHANGHAI, date_key, now_iso, parse_iso
from app.services.wecom_message_normalizer import WecomMessageNormalizer
from app.services.wecom_mock_service import WecomMockService


LEAD_REMINDER_STATUSES = {"pending", "contacted", "invalid", "paused", "completed"}
LEAD_CLOSED_STATUSES = {"invalid", "paused", "completed"}
WECOM_EXTERNAL_BINDING_SOURCE = "wecom_external_user"
WECOM_BIND_INTENT_SOURCE = "wecom_bind_intent"
WECOM_BIND_INTENT_PENDING = "pending_assistant_bind"
WECOM_BIND_INTENT_CONSUMED = "consumed_assistant_bind"
IMPORT_CLAIM_TOKEN_TTL_SECONDS = 7 * 24 * 60 * 60
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
CONFIRMABLE_CARD_TYPES = {"property_listing", "groupbuy_product", "business_card", "service_offer", "text_note"}
MANUAL_DRAFT_CARD_TYPES = {"property_listing", "groupbuy_product", "business_card", "service_offer", "text_note"}
MANUAL_DRAFT_INPUT_MODES = {"paste_text", "blank"}
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
SERVICE_CONVERSION_DEFAULTS = {
    "showContactPhone": True,
    "enableLightScrm": True,
    "collectLeads": True,
    "enableAppointment": True,
    "enablePrivateConsultation": True,
    "enableSharePoster": True,
    "enableGroupRelay": False,
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
OPPORTUNITY_KEY_SECTIONS = {"价格/优惠", "联系方式", "FAQ/保障", "商品规格", "课程内容"}
OPPORTUNITY_HIGH_ACTIONS = {"lead-contact", "appointment", "order-intent", "relay-intent", "consult-click"}
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
DASHBOARD_DEMO_TAG = "dashboard_demo"
VISITOR_IDENTITY_DEFAULT = {
    "type": "customer",
    "label": "客户线索",
    "group": "customer",
}
VISITOR_IDENTITY_PEER_AGENT = {
    "type": "peer_agent",
    "label": "疑似中介",
    "group": "peer",
}
VISITOR_IDENTITY_UPSTREAM = {
    "type": "upstream",
    "label": "疑似上游",
    "group": "upstream",
}


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
        if not settings.allow_mock_login:
            raise HTTPException(status_code=403, detail="测试登录已关闭")
        return self._upsert_user_by_openid(
            payload.openid or f"openid_{payload.nickname}",
            payload.nickname,
            payload.avatarUrl,
            payload.phone,
            None,
            payload.wechat,
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
        return self._upsert_user_by_openid(
            openid,
            payload.nickname or "微信用户",
            payload.avatarUrl,
            payload.phone,
            session_data.get("unionid"),
            payload.wechat,
        )

    def update_user_profile(self, user_id: str, payload: UserProfileUpdateRequest) -> User:
        user = self.repo.get_user(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")

        if payload.nickname is not None:
            nickname = strip_unicode_surrogates(payload.nickname).strip()
            if not nickname:
                raise HTTPException(status_code=400, detail="昵称不能为空")
            user.nickname = nickname[:40]
        if payload.avatarUrl is not None:
            avatar_url = self._clean_user_avatar_url(payload.avatarUrl, reject_invalid=True)
            user.avatarUrl = avatar_url
        if payload.phone is not None:
            phone = strip_unicode_surrogates(payload.phone).strip()
            user.phone = phone[:40] if phone else None
        if payload.wechat is not None:
            wechat = strip_unicode_surrogates(payload.wechat).strip()
            user.wechat = wechat[:40] if wechat else None

        user.updatedAt = now_iso()
        self.repo.save_user(user)
        return user

    def create_wecom_bind_intent(self, user_id: str) -> dict:
        user = self.repo.get_user(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")
        now = now_iso()
        expires_at = datetime.now(tz=SHANGHAI) + timedelta(seconds=max(60, settings.wecom_bind_intent_ttl_seconds))
        intent = WecomIdentityBinding(
            id=f"wecom_bind_intent_{new_id('intent')}",
            sourceType=WECOM_BIND_INTENT_SOURCE,
            externalUserId=f"pending:{user.id}:{uuid4().hex}",
            ownerUserId=user.id,
            ownerOpenid=user.openid,
            bindSource=WECOM_BIND_INTENT_PENDING,
            firstImportBatchId=None,
            lastImportBatchId=None,
            createdAt=now,
            updatedAt=now,
        )
        self.repo.save_wecom_identity_binding(intent)
        return {
            "intentId": intent.id,
            "ownerUserId": user.id,
            "ownerOpenid": user.openid,
            "expiresAt": expires_at.isoformat(),
            "ttlSeconds": max(60, settings.wecom_bind_intent_ttl_seconds),
        }

    def _upsert_user_by_openid(
        self,
        openid: str,
        nickname: str,
        avatar_url: str,
        phone: str | None = None,
        unionid: str | None = None,
        wechat: str | None = None,
    ) -> User:
        now = now_iso()
        avatar_url = self._clean_user_avatar_url(avatar_url, reject_invalid=False)
        existing = self.repo.get_user_by_openid(openid)
        if existing:
            existing.nickname = nickname
            existing.avatarUrl = avatar_url
            existing.phone = phone
            existing.wechat = wechat or existing.wechat
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
            wechat=wechat,
            phone=phone,
            createdAt=now,
            updatedAt=now,
        )
        self.repo.save_user(user)
        return user

    def _clean_user_avatar_url(self, value: str | None, reject_invalid: bool = False) -> str:
        avatar_url = strip_unicode_surrogates(value or "").strip()[:500]
        if not avatar_url:
            return ""
        invalid = (
            not re.match(r"^https://", avatar_url, flags=re.IGNORECASE)
            or re.search(r"example\.com|avatar-default", avatar_url, flags=re.IGNORECASE)
            or re.match(r"^(wxfile|file|blob):", avatar_url, flags=re.IGNORECASE)
            or avatar_url.startswith("/tmp/")
        )
        if invalid:
            if reject_invalid:
                raise HTTPException(status_code=400, detail="头像地址必须是可访问的 HTTPS 地址")
            return ""
        return avatar_url

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

        notifications = []
        for batch in new_batches:
            batch_messages = [item for item in raw_messages if item.id in batch.rawMessageIds]
            for message in batch_messages:
                message.importBatchId = batch.id
            notification = self._process_import_batch(batch, batch_messages, notification_channel)
            notifications.append(notification)

        return {
            "message": notification.message,
            "importBatchIds": [item.id for item in new_batches],
            "deduplicatedCount": len(existing_wecom_msg_ids),
            "notifications": [item.model_dump() for item in notifications],
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
            content_object = self._enrich_internal_miniapp_content(content_object)
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

    def create_manual_note_draft(self, payload: ManualNoteDraftRequest) -> UserNote:
        owner_user_id = payload.ownerUserId.strip()
        card_type = payload.cardType.strip()
        input_mode = payload.inputMode.strip()
        raw_text = strip_unicode_surrogates(payload.rawText or "").strip()
        title = strip_unicode_surrogates(payload.title or "").strip()
        if card_type not in MANUAL_DRAFT_CARD_TYPES:
            raise HTTPException(status_code=400, detail="不支持的资料类型")
        if input_mode not in MANUAL_DRAFT_INPUT_MODES:
            raise HTTPException(status_code=400, detail="不支持的创建方式")
        if not self.repo.get_user(owner_user_id):
            raise HTTPException(status_code=404, detail="用户不存在")
        if input_mode == "paste_text" and not raw_text:
            raise HTTPException(status_code=400, detail="请先粘贴资料文案")
        if input_mode == "paste_text":
            return self._create_manual_note_from_text(owner_user_id, card_type, raw_text, title)
        return self._create_blank_manual_note(owner_user_id, card_type, title)

    def parse_property_batch(self, payload: PropertyBatchParseRequest) -> dict:
        owner_user_id = payload.ownerUserId.strip()
        if not self.repo.get_user(owner_user_id):
            raise HTTPException(status_code=404, detail="用户不存在")
        raw_text = strip_unicode_surrogates(payload.rawText or "").strip()
        if not raw_text:
            raise HTTPException(status_code=400, detail="请先粘贴房源文案")
        return self._parse_property_batch_text(raw_text)

    def create_property_batch(self, payload: PropertyBatchCreateRequest) -> dict:
        owner_user_id = payload.ownerUserId.strip()
        if not self.repo.get_user(owner_user_id):
            raise HTTPException(status_code=404, detail="用户不存在")
        raw_text = strip_unicode_surrogates(payload.rawText or "").strip()
        candidates = [item for item in payload.candidates if item.selected]
        if not candidates:
            raise HTTPException(status_code=400, detail="请至少选择一套房源")
        notes = [self._create_property_note_from_batch_candidate(owner_user_id, raw_text, item.model_dump()) for item in candidates]
        return {
            "noteIds": [item.id for item in notes],
            "notes": [item.model_dump() for item in notes],
            "createdCount": len(notes),
        }

    def _parse_property_batch_text(self, raw_text: str) -> dict:
        lines = [line.strip() for line in re.split(r"[\r\n]+", raw_text) if line.strip()]
        common_private = self._property_batch_common_private_data(raw_text)
        public_tags = self._property_batch_public_tags(raw_text)
        private_tags = self._property_batch_private_tags(raw_text, common_private)
        candidates: list[dict] = []
        current_base = ""
        current_features: list[str] = []
        for line in lines:
            clean = re.sub(r"^[0-9一二三四五六七八九十]+[，,、.．]\s*", "", line).strip()
            if not clean or re.search(r"1[3-9]\d{9}", clean) and len(clean) < 40:
                continue
            if re.search(r"(苑|园|府|里|城|公寓|小区|花园).{0,12}(号|栋|幢|座|室|户|房)", clean) and not re.search(r"1[3-9]\d{9}", clean):
                current_base = clean
                current_features = self._property_features_from_text(clean)
                continue
            if current_base:
                unit = self._property_candidate_from_unit_line(current_base, clean, public_tags, private_tags, common_private, current_features, len(candidates))
                if unit:
                    candidates.append(unit)
                    continue
            direct = self._property_candidate_from_direct_line(clean, public_tags, private_tags, common_private, len(candidates))
            if direct:
                candidates.append(direct)
                current_base = ""
                current_features = []
        unique: list[dict] = []
        seen: set[str] = set()
        for item in candidates:
            key = f"{item.get('title')}|{item.get('price')}"
            if key in seen:
                continue
            seen.add(key)
            item["candidateId"] = f"property_candidate_{len(unique) + 1}"
            unique.append(item)
        return {
            "detectedCount": len(unique),
            "candidates": unique,
            "rawText": raw_text,
            "privacySummary": {
                "publicTags": public_tags,
                "privateTags": private_tags,
                "upstreamPhones": common_private.get("upstreamPhones", []),
                "upstreamWechat": common_private.get("upstreamWechat", ""),
                "commission": common_private.get("commission", ""),
            },
        }

    def _property_batch_common_private_data(self, raw_text: str) -> dict:
        phones = self._unique_strings(re.findall(r"1[3-9]\d{9}", raw_text))
        wechat_match = re.search(r"(?:微信|v|V|➕微信|加微信)[：:\s➕+]*([A-Za-z0-9_-]{5,30})", raw_text)
        v_match = re.search(r"\b(1[3-9]\d{9}v)\b", raw_text, re.IGNORECASE)
        commission_match = re.search(r"(中介费\s*[%％]?\s*\d+%?|中介费\s*\d+[%％]|租高有红包|红包)", raw_text)
        restrictions = []
        if re.search(r"带小孩|孕妇|老人", raw_text):
            restrictions.append("带小孩/孕妇/老人不租")
        return {
            "upstreamPhones": phones,
            "upstreamWechat": (wechat_match.group(1) if wechat_match else v_match.group(1) if v_match else ""),
            "commission": commission_match.group(0) if commission_match else "",
            "lockNote": "全部密码锁" if "密码锁" in raw_text else "",
            "bonusNote": "租高有红包" if "红包" in raw_text else "",
            "viewingNote": "看房先联系上游" if "看房" in raw_text and phones else "",
            "restrictions": restrictions,
            "sourceHasMediaHint": bool(re.search(r"照片|视频|朋友圈", raw_text)),
        }

    def _property_batch_public_tags(self, raw_text: str) -> list[str]:
        tags = []
        checks = [
            ("禁宠", r"禁.*宠|🈲️?养宠物|不养宠|养宠物"),
            ("可办居住证", r"办居住证|居住证"),
            ("可落户", r"落户"),
            ("可办停车位", r"停车位"),
            ("可开发票", r"开发票|发票"),
            ("燃气", r"燃气"),
            ("卫生间带窗", r"卫生间带窗"),
            ("干湿分离", r"干湿分离"),
            ("已空", r"已空|空置"),
        ]
        for label, pattern in checks:
            if re.search(pattern, raw_text):
                tags.append(label)
        return self._unique_strings(tags)

    def _property_batch_private_tags(self, raw_text: str, private_data: dict) -> list[str]:
        tags = []
        if private_data.get("upstreamPhones"):
            tags.append(f"上游电话{len(private_data['upstreamPhones'])}个")
        if private_data.get("commission"):
            tags.append(private_data["commission"])
        if private_data.get("lockNote"):
            tags.append("密码锁")
        if private_data.get("bonusNote"):
            tags.append("红包")
        if private_data.get("sourceHasMediaHint"):
            tags.append("朋友圈有照片视频")
        return self._unique_strings(tags)

    def _property_features_from_text(self, text: str) -> list[str]:
        features = []
        for label, pattern in [("燃气", r"燃气"), ("卫生间带窗", r"卫生间带窗"), ("干湿分离", r"干湿分离"), ("新装", r"新装")]:
            if re.search(pattern, text):
                features.append(label)
        return features

    def _property_base_title(self, text: str) -> str:
        text = re.sub(r"(新装|燃气|洗澡|做饭|卫生间|干湿分离|带窗户|，|,).*", "", text).strip()
        return text or "未命名房源"

    def _property_candidate_from_unit_line(self, base: str, line: str, public_tags: list[str], private_tags: list[str], private_data: dict, base_features: list[str], index: int) -> dict | None:
        if re.search(r"1[3-9]\d{9}", line):
            return None
        match = re.search(r"(.{1,24}?)[\s，,]*(\d{3,5})(?:元|/月|，|,)?$", line)
        if not match:
            return None
        unit_name = match.group(1).strip(" ，,")
        price = match.group(2)
        base_title = self._property_base_title(base)
        return self._property_candidate_payload(base_title, unit_name, price, public_tags, private_tags, private_data, base_features, index)

    def _property_candidate_from_direct_line(self, line: str, public_tags: list[str], private_tags: list[str], private_data: dict, index: int) -> dict | None:
        if re.search(r"1[3-9]\d{9}", line):
            return None
        match = re.search(r"(.{2,36}?)(北次阁楼|主卧独卫|[A-Z]?[东西南北]?一房|阁楼|两房|一室户|[A-Z]室)(?:[^\d]{0,8})(\d{3,5})(?:元|/月|已空|，|,|$)", line)
        if not match:
            return None
        base_title = match.group(1).strip(" 🎉，,")
        unit_name = match.group(2).strip()
        price = match.group(3)
        features = self._property_features_from_text(line)
        return self._property_candidate_payload(base_title, unit_name, price, public_tags, private_tags, private_data, features, index)

    def _property_candidate_payload(self, base_title: str, unit_name: str, price: str, public_tags: list[str], private_tags: list[str], private_data: dict, features: list[str], index: int) -> dict:
        layout = "一房" if "一房" in unit_name or "一室" in base_title else "阁楼" if "阁楼" in unit_name else unit_name
        title = f"{base_title} · {unit_name}".strip(" ·")
        summary_parts = self._unique_strings([layout, *features, *public_tags])
        candidate_private = {**private_data, "sourceLineHint": title}
        return {
            "candidateId": f"property_candidate_{index + 1}",
            "title": title,
            "community": re.split(r"(?:\d+号|\d+栋|\d+幢)", base_title)[0] or base_title,
            "buildingRoom": base_title,
            "unitName": unit_name,
            "layout": layout,
            "price": f"{price}元/月",
            "summary": " / ".join(summary_parts),
            "publicTags": self._unique_strings([*public_tags, *features]),
            "privateTags": private_tags,
            "privateData": candidate_private,
            "selected": True,
        }

    def _create_property_note_from_batch_candidate(self, owner_user_id: str, raw_text: str, candidate: dict) -> UserNote:
        now = now_iso()
        structured_data = {
            "community": candidate.get("community") or "",
            "buildingRoom": candidate.get("buildingRoom") or "",
            "unitName": candidate.get("unitName") or "",
            "layout": candidate.get("layout") or "",
            "price": candidate.get("price") or "",
            "systemTags": candidate.get("publicTags") or [],
            "rawText": raw_text,
        }
        config = self._normalize_note_visibility_config(
            {
                "contentMode": "structured_card",
                "cardType": "property_listing",
                "cardState": "generated",
                "sourceType": "property_batch_text",
                "systemCategory": "房源",
                "structuredData": structured_data,
                "conversionConfig": self._default_conversion_config("property_listing"),
                "tags": self._unique_strings(["房产", "房源", *(candidate.get("publicTags") or [])]),
                "privateData": candidate.get("privateData") or {},
                "privateTags": candidate.get("privateTags") or [],
                "batchImport": {"candidateId": candidate.get("candidateId"), "rawTextLength": len(raw_text)},
            }
        )
        note = UserNote(
            id=new_id("note"),
            ownerUserId=owner_user_id,
            importBatchId=None,
            sourceCardId=None,
            status="active",
            title=candidate.get("title") or "未命名房源",
            summary=candidate.get("summary") or candidate.get("price") or "房源信息",
            body="批量拆分自房东房源文本，可继续补图和完善字段。",
            coverUrl=None,
            media=[],
            categoryIds=[],
            phone=None,
            locationText=candidate.get("buildingRoom") or candidate.get("community"),
            sourceRefs=[new_id("property_batch")],
            visibilityConfig=config,
            createdAt=now,
            updatedAt=now,
        )
        self.repo.save_user_note(note)
        return note

    def create_quick_note_capture(self, payload: QuickNoteCaptureRequest) -> UserNote:
        owner_user_id = payload.ownerUserId.strip()
        raw_text = strip_unicode_surrogates(payload.rawText).strip()
        title = strip_unicode_surrogates(payload.title or "").strip()
        if not self.repo.get_user(owner_user_id):
            raise HTTPException(status_code=404, detail="用户不存在")
        if not raw_text:
            raise HTTPException(status_code=400, detail="请先输入内容")
        content_object = ContentObjectPayload(
            sourceType="manual_text",
            title=title or None,
            textBlocks=[raw_text],
            metadata={"entryMode": "quick_note"},
            sourceRefs=[new_id("quick_note")],
        )
        note_result = self.skill_router_service.run_content_to_note(owner_user_id, content_object)
        note = self._build_user_note_from_note_draft(note_result.noteDraft)
        note.status = "active"
        note.visibilityConfig = self._quick_capture_visibility_config(note.visibilityConfig)
        skill_run = SkillRun.model_validate(note_result.skillRun.model_dump())
        skill_run.outputRef = note.id
        skill_run.inputSnapshot = {
            **skill_run.inputSnapshot,
            "entryMode": "quick_note",
        }
        self.repo.save_user_note(note)
        self.repo.save_skill_run(skill_run)
        return note

    def _quick_capture_visibility_config(self, config: dict) -> dict:
        normalized = self._normalize_note_visibility_config(config)
        normalized["sourceType"] = "manual_text"
        normalized["entryMode"] = "quick_note"
        structured_data = dict(normalized.get("structuredData") or {})
        if normalized.get("cardType") == "groupbuy_product":
            sku_config = structured_data.get("skuConfig") if isinstance(structured_data.get("skuConfig"), dict) else {}
            structured_data["skuConfig"] = sku_config
        normalized["structuredData"] = structured_data
        return normalized

    def _create_manual_note_from_text(self, owner_user_id: str, card_type: str, raw_text: str, title: str) -> UserNote:
        content_object = ContentObjectPayload(
            sourceType="manual_text",
            title=title or None,
            textBlocks=[raw_text],
            metadata={"manualCardType": card_type, "inputMode": "paste_text"},
            sourceRefs=[new_id("manual_text")],
        )
        note_result = self.skill_router_service.run_content_to_note(owner_user_id, content_object)
        note = self._build_user_note_from_note_draft(note_result.noteDraft)
        note = self._apply_manual_selected_note_type(note, card_type, input_mode="paste_text")
        skill_run = SkillRun.model_validate(note_result.skillRun.model_dump())
        skill_run.outputRef = note.id
        skill_run.inputSnapshot = {
            **skill_run.inputSnapshot,
            "manualCardType": card_type,
            "inputMode": "paste_text",
        }
        self.repo.save_user_note(note)
        self.repo.save_skill_run(skill_run)
        return note

    def _create_blank_manual_note(self, owner_user_id: str, card_type: str, title: str) -> UserNote:
        now = now_iso()
        defaults = {
            "property_listing": ("未命名房源", "补充房源字段后即可发给客户"),
            "groupbuy_product": ("未命名商品", "补充商品信息后即可发给客户"),
            "business_card": ("我的电子名片", "补充个人介绍和服务范围后即可发给客户"),
            "service_offer": ("未命名服务方案", "补充服务内容和预约方式后即可发给客户"),
            "text_note": ("未命名笔记", "手动创建的普通笔记"),
        }
        default_title, default_summary = defaults[card_type]
        user = self.repo.get_user(owner_user_id)
        seed_config = {}
        if card_type == "business_card" and user:
            seed_config = {
                "structuredData": {
                    "name": user.nickname,
                    "title": "",
                    "company": "",
                    "serviceScope": "",
                    "headline": f"你好，我是{user.nickname}",
                    "bio": "",
                    "phone": user.phone or "",
                    "wechat": "",
                    "city": "",
                    "avatarUrl": user.avatarUrl,
                    "qrCodeUrl": "",
                    "images": [user.avatarUrl] if user.avatarUrl else [],
                }
            }
        note = UserNote(
            id=new_id("note"),
            ownerUserId=owner_user_id,
            importBatchId=None,
            sourceCardId=None,
            status="active",
            title=title or default_title,
            summary=default_summary,
            body="手动创建，可继续补充内容。",
            coverUrl=user.avatarUrl if card_type == "business_card" and user and user.avatarUrl else None,
            media=[],
            categoryIds=[],
            phone=user.phone if card_type == "business_card" and user and user.phone else None,
            locationText=None,
            sourceRefs=[],
            visibilityConfig=seed_config,
            createdAt=now,
            updatedAt=now,
        )
        note = self._apply_manual_selected_note_type(note, card_type, input_mode="blank")
        self.repo.save_user_note(note)
        return note

    def _build_user_note_from_note_draft(self, note_draft: UserNoteDraftPayload) -> UserNote:
        now = now_iso()
        return UserNote(
            id=new_id("note"),
            ownerUserId=note_draft.ownerUserId or "unclaimed",
            importBatchId=None,
            sourceCardId=None,
            status="active",
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

    def _apply_manual_selected_note_type(self, note: UserNote, card_type: str, input_mode: str) -> UserNote:
        current_config = self._normalize_note_visibility_config(note.visibilityConfig)
        structured_data = self._build_confirmed_structured_data(note, current_config, card_type)
        system_category_map = {
            "property_listing": "房源",
            "groupbuy_product": "团购",
            "business_card": "名片",
            "service_offer": "服务",
        }
        tag_map = {
            "property_listing": ["房产", "房源"],
            "groupbuy_product": ["团购", "商品"],
            "business_card": ["名片", "顾问"],
            "service_offer": ["服务", "销售"],
        }
        system_category = system_category_map.get(card_type, "待整理")
        extra_tags = tag_map.get(card_type, ["待整理"])
        confirmed_at = now_iso()
        config = {
            **current_config,
            "contentMode": "note" if card_type == "text_note" else "structured_card",
            "cardType": card_type,
            "cardState": "collected" if card_type == "text_note" else "generated",
            "sourceType": "manual_text",
            "systemCategory": system_category,
            "structuredData": structured_data,
            "conversionConfig": self._manual_conversion_config(card_type, current_config),
            "typeSuggestions": [],
            "recognitionConfidence": {
                "level": "manual",
                "selectedType": card_type,
                "inputMode": input_mode,
                "confirmedAt": confirmed_at,
            },
            "recognitionExplanation": self._manual_recognition_explanation(current_config, card_type, input_mode, confirmed_at),
            "tags": self._unique_strings([*current_config.get("tags", []), *extra_tags]),
        }
        note.visibilityConfig = self._normalize_note_visibility_config(config)
        note.updatedAt = confirmed_at
        return note

    def _manual_conversion_config(self, card_type: str, config: dict) -> dict:
        if config.get("cardType") == card_type:
            return self._confirmed_conversion_config(card_type, config)
        return self._default_conversion_config(card_type)

    def _manual_recognition_explanation(self, config: dict, card_type: str, input_mode: str, confirmed_at: str) -> dict:
        previous = config.get("recognitionExplanation") if isinstance(config.get("recognitionExplanation"), dict) else {}
        return {
            **previous,
            "level": "manual",
            "selectedType": card_type,
            "selectedLabel": self._card_type_label(card_type),
            "manualConfirmation": {
                "cardType": card_type,
                "label": self._card_type_label(card_type),
                "inputMode": input_mode,
                "confirmedAt": confirmed_at,
            },
        }

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
                content_object = self._enrich_internal_miniapp_content(content_object)
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
                notification = self.notification_service.build_notification(
                    batch,
                    channel="wecom",
                    media_warning_count=int(media_result.get("failedCount") or 0),
                )
                notification.resultPath = self.build_import_claim_link(batch.id)["pagePath"]
                notification.actions = [
                    {"key": "claim-result", "label": "查看整理结果", "path": notification.resultPath}
                ]
                self.repo.save_import_notification(notification)
                processed.append(
                    {
                        "archiveMessageId": primary.id,
                        "archiveMessageIds": [item.id for item in group_messages],
                        "seq": primary.seq,
                        "seqs": [item.seq for item in group_messages],
                        "noteId": note.id,
                        "cardId": card.id,
                        "media": media_result,
                        "notification": notification.model_dump(),
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

    def _enrich_internal_miniapp_content(self, content_object: ContentObjectPayload) -> ContentObjectPayload:
        miniapp = content_object.metadata.get("miniapp") if isinstance(content_object.metadata, dict) else None
        if not isinstance(miniapp, dict) or not self._is_own_miniapp(miniapp):
            return content_object
        source = self._resolve_internal_miniapp_source(miniapp)
        if not source:
            return content_object
        metadata = dict(content_object.metadata or {})
        metadata["internalMiniapp"] = source
        return content_object.model_copy(
            update={
                "title": source.get("title") or content_object.title,
                "textBlocks": [*content_object.textBlocks, *source.get("textBlocks", [])],
                "media": [*content_object.media, *source.get("media", [])],
                "metadata": metadata,
            }
        )

    def _is_own_miniapp(self, miniapp: dict) -> bool:
        appid = str(miniapp.get("appid") or "").strip()
        if settings.wechat_miniapp_appid and appid == settings.wechat_miniapp_appid:
            return True
        page_path = str(miniapp.get("pagePath") or "")
        return any(marker in page_path for marker in ["/pages/note-preview/", "/pages/showcase-view/", "note-preview", "showcase-view"])

    def _resolve_internal_miniapp_source(self, miniapp: dict) -> dict | None:
        note_id = str(miniapp.get("noteId") or "").strip()
        showcase_id = str(miniapp.get("showcaseId") or "").strip()
        if not note_id and not showcase_id:
            note_id, showcase_id = self._ids_from_miniapp_page_path(str(miniapp.get("pagePath") or ""))
        if showcase_id:
            showcase = self.repo.get_showcase_page(showcase_id)
            if showcase and showcase.status == "published":
                return self._internal_showcase_source(showcase)
        if note_id:
            note = self.repo.get_user_note(note_id)
            if note and note.status != "deleted":
                return self._internal_note_source(note)
        return None

    def _ids_from_miniapp_page_path(self, page_path: str) -> tuple[str, str]:
        parsed = urlparse(page_path)
        query = parse_qs(parsed.query)
        note_id = (query.get("noteId") or query.get("sourceNoteId") or [""])[0]
        showcase_id = (query.get("showcaseId") or [""])[0]
        generic_id = (query.get("id") or [""])[0]
        if not note_id and "note" in parsed.path and generic_id:
            note_id = generic_id
        if not showcase_id and "showcase" in parsed.path and generic_id:
            showcase_id = generic_id
        return note_id, showcase_id

    def _internal_note_source(self, note: UserNote) -> dict:
        config = note.visibilityConfig if isinstance(note.visibilityConfig, dict) else {}
        structured = config.get("structuredData") if isinstance(config.get("structuredData"), dict) else {}
        public_data = self._public_clone_structured_data(structured)
        media_urls = self._note_image_urls(note)
        text_blocks = [
            "来源：资料整理助手自有小程序房源卡",
            f"公开房源标题：{note.title}",
            f"公开摘要：{note.summary}" if note.summary else "",
            *[f"{label}：{value}" for label, value in self._public_property_field_pairs(public_data)],
            "隐私边界：只复制公开房源内容，不继承原发布者私密保存的房东、二房东或渠道联系方式。",
        ]
        media = [
            ContentMediaPayload(type="image", url=url, mediaId=None, title=note.title, sourceRef=note.id)
            for url in media_urls
        ]
        return {
            "kind": "note",
            "noteId": note.id,
            "ownerUserId": note.ownerUserId,
            "title": note.title,
            "cardType": config.get("cardType", "text_note"),
            "structuredData": public_data,
            "textBlocks": [item for item in text_blocks if item],
            "media": media,
        }

    def _internal_showcase_source(self, showcase: ShowcasePage) -> dict:
        snapshot = self.get_public_showcase(showcase.id)
        items = snapshot.get("items") if isinstance(snapshot.get("items"), list) else []
        text_blocks = [
            "来源：资料整理助手自有小程序房源合集",
            f"合集标题：{snapshot.get('name') or showcase.name}",
            f"合集说明：{snapshot.get('description')}" if snapshot.get("description") else "",
            f"模板：{snapshot.get('templateId') or showcase.templateId}",
            f"排列：{(snapshot.get('displayConfig') or {}).get('layoutMode') or 'list'}",
            f"房源数量：{len(items)}",
            "隐私边界：只复制公开房源内容和公开展示结构，不继承原发布者私密保存的上游联系人。",
        ]
        media: list[ContentMediaPayload] = []
        for index, item in enumerate(items[:30], start=1):
            text_blocks.append(f"房源{index}：{item.get('title') or '未命名房源'} {item.get('primaryText') or ''} {item.get('secondaryText') or ''} {item.get('priceText') or ''}".strip())
            cover_url = item.get("coverUrl")
            if cover_url:
                media.append(ContentMediaPayload(type="image", url=cover_url, mediaId=None, title=item.get("title"), sourceRef=item.get("noteId")))
        return {
            "kind": "showcase",
            "showcaseId": showcase.id,
            "ownerUserId": showcase.ownerUserId,
            "title": snapshot.get("name") or showcase.name,
            "templateId": snapshot.get("templateId") or showcase.templateId,
            "displayConfig": snapshot.get("displayConfig") or {},
            "contactConfig": snapshot.get("contactConfig") or {},
            "items": items,
            "textBlocks": text_blocks,
            "media": media,
        }

    def _public_clone_structured_data(self, data: dict) -> dict:
        blocked_fragments = ["contact", "phone", "wechat", "微信", "电话", "landlord", "房东", "upstream", "上游", "channel", "渠道", "rawtext"]
        public_data: dict = {}
        for key, value in data.items():
            key_text = str(key)
            key_match_text = key_text.lower()
            if any(fragment in key_match_text for fragment in blocked_fragments):
                continue
            value_match_text = value.lower() if isinstance(value, str) else ""
            if isinstance(value, str) and any(fragment in value_match_text for fragment in blocked_fragments):
                continue
            if isinstance(value, (str, int, float, bool)) or value is None:
                public_data[key] = value
            elif key == "images" and isinstance(value, list):
                public_data[key] = [item for item in value if isinstance(item, str)]
            elif key == "miniapp" and isinstance(value, dict):
                public_data[key] = {k: v for k, v in value.items() if k not in {"contact", "phone", "wechat"}}
        return public_data

    def _public_property_field_pairs(self, data: dict) -> list[tuple[str, str]]:
        labels = {
            "community": "小区",
            "layout": "户型",
            "area": "面积",
            "price": "租金",
            "businessArea": "商圈",
            "address": "地址",
            "floor": "楼层",
            "utilities": "配套",
            "paymentMethod": "押付",
            "moveInTime": "入住",
            "remark": "备注",
        }
        return [(label, str(data.get(key) or "").strip()) for key, label in labels.items() if str(data.get(key) or "").strip()]

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
            intent_owner_user_id = self._consume_wecom_bind_intent(external_user_id)
            if intent_owner_user_id != "unclaimed":
                return intent_owner_user_id
            default_owner_user_id = (settings.wecom_unclaimed_default_owner_user_id or "").strip()
            if default_owner_user_id and self.repo.get_user(default_owner_user_id):
                self._save_wecom_identity_binding(
                    external_user_id=external_user_id,
                    owner_user_id=default_owner_user_id,
                    import_batch_id=None,
                    bind_source="default_owner_for_test",
                )
                return default_owner_user_id
            return "unclaimed"
        if binding.ownerOpenid:
            user = self.repo.get_user_by_openid(binding.ownerOpenid)
            return user.id if user else "unclaimed"
        if not self.repo.get_user(binding.ownerUserId):
            return "unclaimed"
        return binding.ownerUserId

    def _consume_wecom_bind_intent(self, external_user_id: str) -> str:
        active_intents = self._active_wecom_bind_intents()
        if len(active_intents) != 1:
            return "unclaimed"
        intent = active_intents[0]
        owner = self.repo.get_user(intent.ownerUserId)
        if not owner:
            return "unclaimed"
        now = now_iso()
        self._save_wecom_identity_binding(
            external_user_id=external_user_id,
            owner_user_id=owner.id,
            import_batch_id=None,
            bind_source="auto_bind_intent",
        )
        consumed = intent.model_copy(
            update={
                "bindSource": WECOM_BIND_INTENT_CONSUMED,
                "lastImportBatchId": external_user_id,
                "updatedAt": now,
            }
        )
        self.repo.save_wecom_identity_binding(consumed)
        return owner.id

    def _active_wecom_bind_intents(self) -> list[WecomIdentityBinding]:
        now = datetime.now(tz=SHANGHAI)
        ttl_seconds = max(60, settings.wecom_bind_intent_ttl_seconds)
        active: list[WecomIdentityBinding] = []
        for item in self.repo.load().wecom_identity_bindings:
            if item.sourceType != WECOM_BIND_INTENT_SOURCE or item.bindSource != WECOM_BIND_INTENT_PENDING:
                continue
            try:
                parsed = parse_iso(item.updatedAt).astimezone(SHANGHAI)
            except Exception:
                parsed = None
            if not parsed or (now - parsed).total_seconds() > ttl_seconds:
                continue
            if not self.repo.get_user(item.ownerUserId):
                continue
            active.append(item)
        return sorted(active, key=lambda item: item.updatedAt, reverse=True)

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

    def update_import_notification_delivery(
        self,
        notification_id: str,
        send_status: str,
        send_error: str | None = None,
    ) -> dict | None:
        notification = next((item for item in self.repo.list_import_notifications() if item.id == notification_id), None)
        if not notification:
            return None
        notification.sendStatus = send_status
        notification.sendError = send_error
        notification.sentMessageAt = now_iso() if send_status == "sent" else notification.sentMessageAt
        self.repo.save_import_notification(notification)
        return notification.model_dump()

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
        owner_user_id: str | None = None,
        ref_type: str = "media",
        ref_id: str | None = None,
        usage: str = "media",
    ) -> str:
        if not content:
            raise HTTPException(status_code=400, detail="媒体内容不能为空")
        normalized_type = "video" if media_type == "video" else "image" if media_type == "image" else str(media_type or "file")
        original_sha256 = hashlib.sha256(content).hexdigest()
        existing = self.repo.get_media_asset_by_original_hash(normalized_type, original_sha256)
        if existing:
            self._save_media_asset_ref(existing, owner_user_id, ref_type, ref_id or media_id, usage)
            return existing.url
        processed = self.media_processing_service.process_upload(
            media_type=normalized_type,
            content=content,
            content_type=content_type,
            filename=filename,
        )
        storage_sha256 = hashlib.sha256(processed.content).hexdigest()
        existing = self.repo.get_media_asset_by_storage_hash(normalized_type, storage_sha256)
        if existing:
            self._save_media_asset_ref(existing, owner_user_id, ref_type, ref_id or media_id, usage)
            return existing.url
        url = self.media_storage_service.store_bytes(
            media_id=media_id,
            media_type=normalized_type,
            content=processed.content,
            content_type=processed.content_type,
            filename=processed.filename,
        )
        now = now_iso()
        asset = MediaAsset(
            id=new_id("media_asset"),
            mediaType=normalized_type,
            originalSha256=original_sha256,
            storageSha256=storage_sha256,
            url=url,
            contentType=processed.content_type,
            filename=processed.filename or filename,
            originalSize=processed.original_size,
            storedSize=processed.stored_size,
            status="active",
            createdAt=now,
            updatedAt=now,
        )
        self.repo.save_media_asset(asset)
        self._save_media_asset_ref(asset, owner_user_id, ref_type, ref_id or media_id, usage)
        return url

    def _save_media_asset_ref(
        self,
        asset: MediaAsset,
        owner_user_id: str | None,
        ref_type: str,
        ref_id: str,
        usage: str = "media",
    ) -> None:
        if not ref_id:
            return
        now = now_iso()
        ref = MediaAssetRef(
            id=new_id("media_ref"),
            assetId=asset.id,
            ownerUserId=self._clean_optional_text(owner_user_id),
            refType=self._clean_optional_text(ref_type) or "media",
            refId=ref_id,
            usage=self._clean_optional_text(usage) or "media",
            createdAt=now,
            updatedAt=now,
        )
        self.repo.save_media_asset_ref(ref)

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
        original_sha256 = hashlib.sha256(content).hexdigest()
        existing = self.repo.get_media_asset_by_original_hash("image", original_sha256)
        if existing:
            self._save_media_asset_ref(existing, None, "ocr_upload", existing.id, "source_image")
            return existing.url
        processed = self.media_processing_service.process_upload(
            media_type="image",
            content=content,
            content_type=content_type,
            filename=filename,
        )
        storage_sha256 = hashlib.sha256(processed.content).hexdigest()
        existing = self.repo.get_media_asset_by_storage_hash("image", storage_sha256)
        if existing:
            self._save_media_asset_ref(existing, None, "ocr_upload", existing.id, "source_image")
            return existing.url
        media_id = new_id("ocr_image")
        url = storage.store_bytes(
            media_id=media_id,
            media_type="image",
            content=processed.content,
            content_type=processed.content_type,
            filename=processed.filename,
        )
        now = now_iso()
        asset = MediaAsset(
            id=new_id("media_asset"),
            mediaType="image",
            originalSha256=original_sha256,
            storageSha256=storage_sha256,
            url=url,
            contentType=processed.content_type,
            filename=processed.filename or filename,
            originalSize=processed.original_size,
            storedSize=processed.stored_size,
            status="active",
            createdAt=now,
            updatedAt=now,
        )
        self.repo.save_media_asset(asset)
        self._save_media_asset_ref(asset, None, "ocr_upload", media_id, "source_image")
        return url

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
        if batch.claimedByUserId and batch.claimedByUserId != user_id:
            raise HTTPException(status_code=409, detail="该导入已被其他账号认领")
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

    def build_import_claim_link(self, import_id: str, ttl_seconds: int = IMPORT_CLAIM_TOKEN_TTL_SECONDS) -> dict:
        batch = self.repo.get_import_batch(import_id)
        if not batch:
            raise HTTPException(status_code=404, detail="导入批次不存在")
        token = self._build_import_claim_token(import_id, ttl_seconds=ttl_seconds)
        page_path = f"pages/import-claim/index?token={token}"
        return {
            "token": token,
            "pagePath": page_path,
            "title": batch.titleCandidate or "房源助手整理完成",
            "importBatchId": import_id,
            "expiresIn": ttl_seconds,
        }

    def claim_import_by_token(self, token: str, user_id: str) -> dict:
        import_id = self._verify_import_claim_token(token)
        return self.claim_import(import_id, user_id)

    def _import_claim_token_secret(self) -> str:
        return (
            settings.admin_token
            or settings.wecom_archive_secret
            or settings.wecom_callback_token
            or settings.wechat_miniapp_secret
            or "teamBuy-import-claim-dev-secret"
        )

    def _build_import_claim_token(self, import_id: str, ttl_seconds: int = IMPORT_CLAIM_TOKEN_TTL_SECONDS) -> str:
        expires_at = int(time.time()) + max(60, ttl_seconds)
        payload = f"{import_id}.{expires_at}"
        signature = hmac.new(
            self._import_claim_token_secret().encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return f"{payload}.{signature}"

    def _verify_import_claim_token(self, token: str) -> str:
        raw = strip_unicode_surrogates(token or "").strip()
        parts = raw.rsplit(".", 2)
        if len(parts) != 3:
            raise HTTPException(status_code=400, detail="认领链接无效")
        import_id, expires_at_text, signature = parts
        try:
            expires_at = int(expires_at_text)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="认领链接无效") from exc
        if expires_at < int(time.time()):
            raise HTTPException(status_code=400, detail="认领链接已过期")
        payload = f"{import_id}.{expires_at}"
        expected = hmac.new(
            self._import_claim_token_secret().encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise HTTPException(status_code=400, detail="认领链接无效")
        return import_id

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
        return [self._user_note_list_payload(item) for item in filtered]

    def _user_note_list_payload(self, note: UserNote) -> dict:
        return {
            **note.model_dump(),
            "stats": self._build_note_stats(note),
            "customerSummary": self._build_note_customer_summary(note),
        }

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

    def get_public_note(self, note_id: str) -> dict:
        note = self._get_active_note(note_id)
        payload = note.model_dump()
        payload["visibilityConfig"] = self._public_note_visibility_config(note.visibilityConfig)
        return payload

    def _public_note_visibility_config(self, config: dict | None) -> dict:
        source = dict(config or {})
        for key in ("privateData", "privateTags", "analyticsData", "opportunityAlerts", "radarProfiles", "internalNotes"):
            source.pop(key, None)
        structured = source.get("structuredData") if isinstance(source.get("structuredData"), dict) else {}
        source["structuredData"] = self._public_clone_structured_data(structured)
        return source

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
            templateId=self._clean_optional_text(payload.templateId) or "featured_window",
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
        showcase.templateId = self._clean_optional_text(payload.templateId) or "featured_window"
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
        next_version = (showcase.snapshotVersion or 0) + 1
        showcase.publicSnapshot = self._build_showcase_public_snapshot(showcase, now, next_version)
        showcase.snapshotVersion = next_version
        showcase.snapshotCreatedAt = now
        self.repo.save_showcase_page(showcase)
        return showcase

    def archive_showcase(self, showcase_id: str, owner_user_id: str) -> ShowcasePage:
        showcase = self.get_showcase_for_owner(showcase_id, owner_user_id)
        showcase.status = "archived"
        showcase.updatedAt = now_iso()
        self.repo.save_showcase_page(showcase)
        return showcase

    def delete_showcase(self, showcase_id: str, owner_user_id: str) -> dict:
        self.get_showcase_for_owner(showcase_id, owner_user_id)
        self.repo.delete_showcase_page(showcase_id)
        return {"deletedShowcaseId": showcase_id}

    def record_showcase_event(self, showcase_id: str, payload: ShowcaseEventRequest) -> dict:
        showcase = self.repo.get_showcase_page(showcase_id)
        if not showcase or showcase.status != "published":
            raise HTTPException(status_code=404, detail="展示页不存在或未发布")
        event_type = str(payload.eventType or "").strip()
        if event_type not in {"view", "note_click", "phone_click", "wechat_copy", "share"}:
            raise HTTPException(status_code=400, detail="展示页事件类型无效")
        viewer_user_id = self._clean_optional_text(payload.viewerUserId)
        if event_type != "share" and viewer_user_id and viewer_user_id == showcase.ownerUserId:
            return {"recorded": False, "ignored": "owner_event"}
        note_id = self._clean_optional_text(payload.noteId)
        if note_id and note_id not in {item.noteId for item in self._valid_showcase_items(showcase)}:
            note_id = None
        now = now_iso()
        event = ShowcaseEvent(
            id=self._existing_showcase_session_event_id(showcase.id, payload) or new_id("showcase_event"),
            showcaseId=showcase.id,
            ownerUserId=showcase.ownerUserId,
            eventType=event_type,
            noteId=note_id,
            shareId=self._clean_optional_text(payload.shareId),
            shareFromUserId=self._clean_optional_text(payload.shareFromUserId),
            scene=self._clean_optional_text(payload.scene),
            referrer=self._clean_optional_text(payload.referrer),
            viewerUserId=viewer_user_id,
            viewType="logged_in" if viewer_user_id else "anonymous",
            anonymousId=self._clean_optional_text(payload.anonymousId),
            nickname=self._clean_optional_text(payload.nickname),
            avatarUrl=self._clean_optional_text(payload.avatarUrl),
            sessionId=self._clean_optional_text(payload.sessionId),
            durationSeconds=self._safe_int(payload.durationSeconds, 0, 24 * 60 * 60),
            maxScrollPercent=self._safe_int(payload.maxScrollPercent, 0, 100),
            focusSections=self._normalize_focus_sections(payload.focusSections),
            createdAt=now,
            dateKey=date_key(now),
        )
        self.repo.add_showcase_event(event)
        return {"recorded": True, "eventId": event.id}

    def get_showcase_analytics(self, showcase_id: str, owner_user_id: str) -> dict:
        showcase = self.get_showcase_for_owner(showcase_id, owner_user_id)
        return self._build_showcase_analytics(showcase)

    def get_public_showcase(self, showcase_id: str) -> dict:
        showcase = self.repo.get_showcase_page(showcase_id)
        if not showcase or showcase.status != "published":
            raise HTTPException(status_code=404, detail="展示页不存在或未发布")
        snapshot = showcase.publicSnapshot if isinstance(showcase.publicSnapshot, dict) else {}
        if snapshot and isinstance(snapshot.get("items"), list):
            return snapshot
        now = now_iso()
        next_version = (showcase.snapshotVersion or 0) + 1
        snapshot = self._build_showcase_public_snapshot(showcase, now, next_version)
        showcase.publicSnapshot = snapshot
        showcase.snapshotVersion = next_version
        showcase.snapshotCreatedAt = now
        self.repo.save_showcase_page(showcase)
        return snapshot

    def _build_showcase_public_snapshot(self, showcase: ShowcasePage, snapshot_at: str, snapshot_version: int) -> dict:
        return {
            "id": showcase.id,
            "name": showcase.name,
            "description": showcase.description,
            "bannerUrl": showcase.bannerUrl,
            "templateId": showcase.templateId,
            "shareTitle": showcase.shareTitle or showcase.name,
            "contactConfig": showcase.contactConfig,
            "displayConfig": showcase.displayConfig,
            "items": self._public_showcase_items(showcase),
            "publishedAt": showcase.publishedAt,
            "updatedAt": showcase.updatedAt,
            "snapshotVersion": snapshot_version,
            "snapshotCreatedAt": snapshot_at,
            "snapshotSource": "published_snapshot",
        }

    def _ensure_showcase_owner(self, owner_user_id: str) -> None:
        if not self.repo.get_user(owner_user_id):
            raise HTTPException(status_code=404, detail="用户不存在")

    def _showcase_owner_payload(self, showcase: ShowcasePage) -> dict:
        payload = showcase.model_dump()
        payload["itemCount"] = len(self._valid_showcase_items(showcase))
        payload["sharePath"] = f"/pages/showcase-view/index?id={showcase.id}"
        payload["analytics"] = self._build_showcase_analytics(showcase, compact=True)
        return payload

    def _build_showcase_analytics(self, showcase: ShowcasePage, compact: bool = False) -> dict:
        events = self.repo.list_showcase_events(showcase.id)
        valid_items = self._valid_showcase_items(showcase)
        note_titles = {}
        for item in valid_items:
            note = self.repo.get_user_note(item.noteId)
            note_titles[item.noteId] = item.displayTitle or (note.title if note else "资料")
        counts = defaultdict(int)
        viewers: dict[str, dict] = {}
        anonymous_ids = set()
        note_clicks = defaultdict(int)
        share_rows: dict[str, dict] = {}
        recent_events = []
        for event in events:
            counts[event.eventType] += 1
            if event.shareId:
                share_row = share_rows.setdefault(
                    event.shareId,
                    {
                        "shareId": event.shareId,
                        "shareFromUserId": event.shareFromUserId,
                        "scene": event.scene,
                        "eventCount": 0,
                        "openCount": 0,
                        "noteClickCount": 0,
                        "consultCount": 0,
                        "lastEventAt": event.createdAt,
                    },
                )
                share_row["eventCount"] += 1
                if event.eventType == "view":
                    share_row["openCount"] += 1
                if event.eventType == "note_click":
                    share_row["noteClickCount"] += 1
                if event.eventType in {"phone_click", "wechat_copy"}:
                    share_row["consultCount"] += 1
                if event.createdAt > share_row["lastEventAt"]:
                    share_row["lastEventAt"] = event.createdAt
                    share_row["scene"] = event.scene or share_row["scene"]
            if event.eventType == "note_click" and event.noteId:
                note_clicks[event.noteId] += 1
            if event.eventType == "view":
                if event.viewerUserId:
                    viewer = viewers.setdefault(
                        event.viewerUserId,
                        {
                            "viewerUserId": event.viewerUserId,
                            "nickname": event.nickname or "微信用户",
                            "avatarUrl": event.avatarUrl,
                            "viewCount": 0,
                            "lastViewedAt": event.createdAt,
                        },
                    )
                    viewer["viewCount"] += 1
                    if event.createdAt > viewer["lastViewedAt"]:
                        viewer["lastViewedAt"] = event.createdAt
                        viewer["nickname"] = event.nickname or viewer["nickname"]
                        viewer["avatarUrl"] = event.avatarUrl or viewer["avatarUrl"]
                else:
                    anonymous_ids.add(event.anonymousId or event.id)
            if len(recent_events) < (6 if compact else 20):
                recent_events.append(self._showcase_event_row(event, note_titles))
        recent_viewers = sorted(viewers.values(), key=lambda item: item.get("lastViewedAt") or "", reverse=True)
        top_notes = [
            {"noteId": note_id, "title": note_titles.get(note_id, "资料"), "clickCount": count}
            for note_id, count in sorted(note_clicks.items(), key=lambda item: item[1], reverse=True)
        ]
        top_shares = sorted(
            share_rows.values(),
            key=lambda item: (item.get("openCount") or 0, item.get("noteClickCount") or 0, item.get("consultCount") or 0, item.get("lastEventAt") or ""),
            reverse=True,
        )
        summary = {
            "pv": counts["view"],
            "uv": len(viewers) + len(anonymous_ids),
            "loggedInUv": len(viewers),
            "anonymousUv": len(anonymous_ids),
            "noteClickCount": counts["note_click"],
            "phoneClickCount": counts["phone_click"],
            "wechatCopyCount": counts["wechat_copy"],
            "shareCount": counts["share"],
            "shareSourceCount": len(share_rows),
            "consultClickCount": counts["phone_click"] + counts["wechat_copy"],
        }
        return {
            "summary": summary,
            "recentViewers": recent_viewers[: 3 if compact else 20],
            "recentEvents": recent_events,
            "topNotes": top_notes[: 3 if compact else 20],
            "topShares": top_shares[: 3 if compact else 20],
        }

    def _showcase_event_row(self, event: ShowcaseEvent, note_titles: dict[str, str]) -> dict:
        labels = {
            "view": "打开展示页",
            "note_click": "查看资料",
            "phone_click": "电话咨询",
            "wechat_copy": "复制微信",
            "share": "分享展示页",
        }
        viewer_name = event.nickname or ("匿名客户" if not event.viewerUserId else "微信用户")
        return {
            "id": event.id,
            "eventType": event.eventType,
            "eventLabel": labels.get(event.eventType, "客户动作"),
            "noteId": event.noteId,
            "noteTitle": note_titles.get(event.noteId or "", ""),
            "shareId": event.shareId,
            "shareFromUserId": event.shareFromUserId,
            "scene": event.scene,
            "referrer": event.referrer,
            "viewerUserId": event.viewerUserId,
            "anonymous": not bool(event.viewerUserId),
            "nickname": viewer_name,
            "avatarUrl": event.avatarUrl,
            "createdAt": event.createdAt,
        }

    def get_business_dashboard(self, owner_user_id: str, requester_user_id: str | None = None, mode: str | None = None) -> dict:
        if not self.repo.get_user(owner_user_id):
            raise HTTPException(status_code=404, detail="用户不存在")
        if not requester_user_id:
            raise HTTPException(status_code=401, detail="请先登录后查看工作台")
        if requester_user_id != owner_user_id:
            raise HTTPException(status_code=403, detail="仅工作台拥有者可查看")
        if mode == "property":
            return self._property_customer_dashboard(owner_user_id)
        notes = self.repo.list_user_notes(owner_user_id, include_deleted=False)
        if mode == "groupbuy":
            notes = [item for item in notes if self._is_groupbuy_note(item)]
        if mode == "service":
            notes = [item for item in notes if self._is_service_note(item)]
        note_by_id = {item.id: item for item in notes}
        note_ids = set(note_by_id.keys())
        note_view_events: dict[str, list[ViewEvent]] = {
            note.id: self.repo.list_view_events_for_card(note.sourceCardId or note.id)
            for note in notes
        }
        note_card_ids = {item.sourceCardId for item in notes if item.sourceCardId}
        note_source_ids = note_ids | note_card_ids
        showcases = self.repo.list_showcase_pages(owner_user_id)
        if mode in {"groupbuy", "service"}:
            showcases = [
                item
                for item in showcases
                if any(showcase_item.noteId in note_ids for showcase_item in item.items)
            ]
        showcase_by_id = {item.id: item for item in showcases}
        showcase_events = [
            event
            for showcase in showcases
            for event in self.repo.list_showcase_events(showcase.id)
            if event.ownerUserId == owner_user_id
            and (mode not in {"groupbuy", "service"} or not event.noteId or event.noteId in note_ids)
        ]
        actions = [
            action
            for note in notes
            for action in self.repo.list_customer_actions_for_note(note.id)
            if action.ownerUserId == owner_user_id
        ]
        leads = self.repo.list_lead_reminders(owner_user_id)
        if mode in {"groupbuy", "service"}:
            leads = [item for item in leads if item.cardId in note_source_ids]
        today = date_key(now_iso())
        event_counts = defaultdict(int)
        visitor_keys: set[str] = set()
        anonymous_keys: set[str] = set()
        note_clicks = defaultdict(int)
        share_rows: dict[str, dict] = {}
        for event in showcase_events:
            event_counts[event.eventType] += 1
            if event.shareId:
                showcase = showcase_by_id.get(event.showcaseId)
                share_row = share_rows.setdefault(
                    event.shareId,
                    {
                        "shareId": event.shareId,
                        "shareFromUserId": event.shareFromUserId,
                        "showcaseId": event.showcaseId,
                        "showcaseName": showcase.name if showcase else "展示页",
                        "scene": event.scene,
                        "eventCount": 0,
                        "openCount": 0,
                        "noteClickCount": 0,
                        "consultCount": 0,
                        "lastEventAt": event.createdAt,
                    },
                )
                share_row["eventCount"] += 1
                if event.eventType == "view":
                    share_row["openCount"] += 1
                if event.eventType == "note_click":
                    share_row["noteClickCount"] += 1
                if event.eventType in {"phone_click", "wechat_copy"}:
                    share_row["consultCount"] += 1
                if event.createdAt > share_row["lastEventAt"]:
                    share_row["lastEventAt"] = event.createdAt
                    share_row["scene"] = event.scene or share_row["scene"]
            if event.eventType == "view":
                if event.viewerUserId:
                    visitor_keys.add(event.viewerUserId)
                else:
                    anonymous_keys.add(event.anonymousId or event.id)
            if event.eventType == "note_click" and event.noteId:
                note_clicks[event.noteId] += 1
        order_actions = [item for item in actions if item.actionKey in PRODUCT_ORDER_ACTION_KEYS]
        open_orders = [
            item
            for item in order_actions
            if str((item.payload or {}).get("orderStatus") or "submitted") not in {"completed", "cancelled"}
        ]
        pending_leads = [item for item in leads if item.status == "pending"]
        contacts = [
            item
            for item in leads
            if item.customerPhone or item.customerWechat or item.budgetText or item.intentLevel or item.customerTags
        ]
        summary = {
            "showcaseOpenCount": event_counts["view"],
            "visitorCount": len(visitor_keys) + len(anonymous_keys),
            "loggedInVisitorCount": len(visitor_keys),
            "anonymousVisitorCount": len(anonymous_keys),
            "noteClickCount": event_counts["note_click"],
            "consultCount": event_counts["phone_click"] + event_counts["wechat_copy"],
            "shareCount": event_counts["share"],
            "shareSourceCount": len(share_rows),
            "pendingLeadCount": len(pending_leads),
            "customerCount": len(contacts),
            "orderCount": len(order_actions),
            "pendingOrderCount": len(open_orders),
            "todayEventCount": sum(1 for item in showcase_events if item.dateKey == today),
            "todayActionCount": sum(1 for item in actions if date_key(item.createdAt) == today),
            "showcaseCount": len(showcases),
            "publishedShowcaseCount": sum(1 for item in showcases if item.status == "published"),
        }
        dashboard = {
            "summary": summary,
            "entries": self._business_dashboard_entries(summary),
            "recentVisitors": self._business_dashboard_recent_visitors(showcase_events, showcase_by_id),
            "topNotes": self._business_dashboard_top_notes(note_clicks, note_by_id),
            "topShares": self._business_dashboard_top_shares(share_rows, showcase_events),
            "latestActions": self._business_dashboard_latest_actions(actions, note_by_id),
            "showcaseBreakdown": self._business_dashboard_showcase_breakdown(showcases, showcase_events),
            "visitorProfiles": self._business_dashboard_visitor_profiles(showcase_events, actions, leads, showcase_by_id, note_by_id),
        }
        return self._attach_opportunity_radar(dashboard, notes, showcase_events, actions, leads, note_view_events)

    def _is_property_note(self, note: UserNote) -> bool:
        config = note.visibilityConfig or {}
        if config.get("cardType") == "property_listing":
            return True
        system_category = str(config.get("systemCategory") or "")
        if system_category in {"property", "property_listing", "房源"}:
            return True
        haystack = " ".join(
            [
                note.title or "",
                note.summary or "",
                note.body or "",
                note.locationText or "",
                str(config.get("sourceName") or ""),
                json.dumps(config.get("structuredData", {}), ensure_ascii=False),
            ]
        )
        return any(keyword in haystack for keyword in ["房源", "小区", "户型", "租房", "买房", "看房", "房租", "押金"])

    def _is_groupbuy_note(self, note: UserNote) -> bool:
        config = note.visibilityConfig or {}
        if config.get("cardType") == "groupbuy_product":
            return True
        system_category = str(config.get("systemCategory") or "")
        if system_category in {"groupbuy", "groupbuy_product", "团购", "商品"}:
            return True
        haystack = " ".join(
            [
                note.title or "",
                note.summary or "",
                note.body or "",
                str(config.get("sourceName") or ""),
                json.dumps(config.get("structuredData", {}), ensure_ascii=False),
            ]
        )
        return any(keyword in haystack for keyword in ["团购", "接龙", "商品", "下单", "买家", "库存", "自提", "配送"])

    def _is_service_note(self, note: UserNote) -> bool:
        config = note.visibilityConfig or {}
        if config.get("cardType") in {"business_card", "service_offer"}:
            return True
        system_category = str(config.get("systemCategory") or "")
        if system_category in {"service", "business_card", "service_offer", "名片", "服务"}:
            return True
        haystack = " ".join(
            [
                note.title or "",
                note.summary or "",
                note.body or "",
                str(config.get("sourceName") or ""),
                json.dumps(config.get("structuredData", {}), ensure_ascii=False),
            ]
        )
        return any(keyword in haystack for keyword in ["名片", "服务方案", "预约沟通", "咨询服务", "服务介绍"])

    def _property_customer_dashboard(self, owner_user_id: str) -> dict:
        notes = [item for item in self.repo.list_user_notes(owner_user_id, include_deleted=False) if self._is_property_note(item)]
        note_by_id = {item.id: item for item in notes}
        note_ids = set(note_by_id)
        actions = [
            action
            for note in notes
            for action in self.repo.list_customer_actions_for_note(note.id)
            if action.ownerUserId == owner_user_id
        ]
        projected_lead_ids = {
            str((action.projectionRefs or {}).get("leadReminderId") or "")
            for action in actions
            if (action.projectionRefs or {}).get("leadReminderId")
        }
        all_leads = self.repo.list_lead_reminders(owner_user_id)
        leads = [item for item in all_leads if item.id in projected_lead_ids or item.cardId in note_ids]
        note_stats = {note.id: self._build_note_stats(note) for note in notes}
        note_view_events: dict[str, list[ViewEvent]] = {
            note.id: self.repo.list_view_events_for_card(note.sourceCardId or note.id)
            for note in notes
        }
        showcases = [
            showcase
            for showcase in self.repo.list_showcase_pages(owner_user_id)
            if any(item.noteId in note_ids for item in showcase.items)
        ]
        showcase_by_id = {item.id: item for item in showcases}
        showcase_events = [
            event
            for showcase in showcases
            for event in self.repo.list_showcase_events(showcase.id)
            if event.ownerUserId == owner_user_id
        ]
        today = date_key(now_iso())
        note_clicks = defaultdict(int)
        today_note_clicks = defaultdict(int)
        share_rows: dict[str, dict] = {}
        showcase_visitor_keys: set[str] = set()
        today_showcase_visitor_keys: set[str] = set()
        package_view_count = 0
        today_package_view_count = 0
        package_consult_count = 0
        today_package_consult_count = 0
        package_share_count = 0
        today_package_share_count = 0
        for event in showcase_events:
            is_today_event = event.dateKey == today
            if event.eventType == "view":
                package_view_count += 1
                showcase_visitor_keys.add(self._dashboard_identity_key(event.viewerUserId, event.anonymousId, event.id))
                if is_today_event:
                    today_package_view_count += 1
                    today_showcase_visitor_keys.add(self._dashboard_identity_key(event.viewerUserId, event.anonymousId, event.id))
            elif event.eventType == "note_click" and event.noteId in note_ids:
                note_clicks[event.noteId] += 1
                if is_today_event:
                    today_note_clicks[event.noteId] += 1
            elif event.eventType in {"phone_click", "wechat_copy"}:
                package_consult_count += 1
                if is_today_event:
                    today_package_consult_count += 1
            elif event.eventType == "share":
                package_share_count += 1
                if is_today_event:
                    today_package_share_count += 1
            if event.shareId:
                showcase = showcase_by_id.get(event.showcaseId)
                share_row = share_rows.setdefault(
                    event.shareId,
                    {
                        "shareId": event.shareId,
                        "shareFromUserId": event.shareFromUserId,
                        "showcaseId": event.showcaseId,
                        "showcaseName": showcase.name if showcase else "房源推荐包",
                        "scene": event.scene,
                        "eventCount": 0,
                        "openCount": 0,
                        "noteClickCount": 0,
                        "consultCount": 0,
                        "lastEventAt": event.createdAt,
                    },
                )
                share_row["eventCount"] += 1
                if event.eventType == "view":
                    share_row["openCount"] += 1
                if event.eventType == "note_click" and event.noteId in note_ids:
                    share_row["noteClickCount"] += 1
                if event.eventType in {"phone_click", "wechat_copy"}:
                    share_row["consultCount"] += 1
                if event.createdAt > share_row["lastEventAt"]:
                    share_row["lastEventAt"] = event.createdAt
                    share_row["scene"] = event.scene or share_row["scene"]
        note_visitor_keys: set[str] = set()
        today_note_visitor_keys: set[str] = set()
        today_note_view_count = 0
        for note in notes:
            stats = note_stats.get(note.id, {})
            for viewer in stats.get("loggedInViewers") or []:
                note_visitor_keys.add(self._dashboard_identity_key(viewer.get("userId") or viewer.get("viewerUserId")))
            for index in range(int(stats.get("anonymousUv") or 0)):
                note_visitor_keys.add(f"note-anon:{note.id}:{index}")
            for event in note_view_events.get(note.id, []):
                if event.dateKey != today:
                    continue
                today_note_view_count += 1
                today_note_visitor_keys.add(self._dashboard_identity_key(event.viewerUserId, event.anonymousId, event.id))
        action_contact_count = sum(1 for item in actions if item.actionKey in {"lead-contact", "appointment", "consult-click"})
        today_actions = [item for item in actions if date_key(item.createdAt) == today]
        today_action_contact_count = sum(1 for item in today_actions if item.actionKey in {"lead-contact", "appointment", "consult-click"})
        pending_leads = [item for item in leads if item.status == "pending"]
        today_pending_leads = [item for item in pending_leads if date_key(item.createdAt) == today]
        property_rows = []
        for index, note in enumerate(notes):
            stats = note_stats.get(note.id, {})
            note_actions = [action for action in actions if action.noteId == note.id]
            note_lead_ids = {
                str((action.projectionRefs or {}).get("leadReminderId") or "")
                for action in note_actions
                if (action.projectionRefs or {}).get("leadReminderId")
            }
            note_card_ids = {note.id}
            if note.sourceCardId:
                note_card_ids.add(note.sourceCardId)
            note_pending = sum(1 for lead in leads if (lead.id in note_lead_ids or lead.cardId in note_card_ids) and lead.status == "pending")
            click_count = int(stats.get("pv") or 0) + int(note_clicks.get(note.id) or 0)
            today_open_count = (
                sum(1 for event in note_view_events.get(note.id, []) if event.dateKey == today)
                + int(today_note_clicks.get(note.id) or 0)
            )
            today_visitor_count = len({
                self._dashboard_identity_key(event.viewerUserId, event.anonymousId, event.id)
                for event in note_view_events.get(note.id, [])
                if event.dateKey == today
            })
            today_followup_count = sum(1 for lead in leads if (lead.id in note_lead_ids or lead.cardId in note_card_ids) and lead.status == "pending" and date_key(lead.createdAt) == today)
            property_rows.append(
                {
                    "noteId": note.id,
                    "title": note.title or "房源资料",
                    "clickCount": click_count,
                    "openCount": click_count,
                    "visitorCount": int(stats.get("uv") or 0),
                    "followupCount": note_pending,
                    "todayOpenCount": today_open_count,
                    "todayVisitorCount": today_visitor_count,
                    "todayFollowupCount": today_followup_count,
                    "cardType": (note.visibilityConfig or {}).get("cardType", "property_listing"),
                    "lastEventAt": max((action.createdAt for action in note_actions), default=note.updatedAt),
                    "rankNo": index + 1,
                }
            )
        property_rows = sorted(
            property_rows,
            key=lambda item: (item["openCount"], item["followupCount"], item["lastEventAt"]),
            reverse=True,
        )
        for index, row in enumerate(property_rows):
            row["rankNo"] = index + 1
        summary = {
            "propertyCount": len(notes),
            "showcaseOpenCount": package_view_count,
            "visitorCount": len(note_visitor_keys | showcase_visitor_keys),
            "loggedInVisitorCount": sum(1 for key in note_visitor_keys | showcase_visitor_keys if key.startswith("user:")),
            "anonymousVisitorCount": sum(1 for key in note_visitor_keys | showcase_visitor_keys if not key.startswith("user:")),
            "noteClickCount": sum(int(item.get("openCount") or 0) for item in property_rows),
            "consultCount": package_consult_count + action_contact_count,
            "shareCount": package_share_count,
            "shareSourceCount": len(share_rows),
            "pendingLeadCount": len(pending_leads),
            "customerCount": len(leads),
            "orderCount": 0,
            "pendingOrderCount": 0,
            "todayEventCount": sum(1 for item in showcase_events if item.dateKey == today),
            "todayActionCount": sum(1 for item in actions if date_key(item.createdAt) == today),
            "showcaseCount": len(showcases),
            "publishedShowcaseCount": sum(1 for item in showcases if item.status == "published"),
        }
        today_summary = {
            "propertyCount": sum(1 for note in notes if date_key(note.createdAt) == today),
            "updatedPropertyCount": sum(1 for note in notes if date_key(note.updatedAt) == today),
            "showcaseOpenCount": today_package_view_count,
            "visitorCount": len(today_note_visitor_keys | today_showcase_visitor_keys),
            "loggedInVisitorCount": sum(1 for key in today_note_visitor_keys | today_showcase_visitor_keys if key.startswith("user:")),
            "anonymousVisitorCount": sum(1 for key in today_note_visitor_keys | today_showcase_visitor_keys if not key.startswith("user:")),
            "noteClickCount": today_note_view_count + sum(today_note_clicks.values()),
            "consultCount": today_package_consult_count + today_action_contact_count,
            "shareCount": today_package_share_count,
            "shareSourceCount": len({
                event.shareId
                for event in showcase_events
                if event.shareId and event.dateKey == today
            }),
            "pendingLeadCount": len(today_pending_leads),
            "customerCount": len({
                self._dashboard_identity_key(action.viewerUserId, action.anonymousId, action.id)
                for action in today_actions
            } | today_note_visitor_keys | today_showcase_visitor_keys),
            "orderCount": 0,
            "pendingOrderCount": 0,
            "todayEventCount": summary["todayEventCount"],
            "todayActionCount": summary["todayActionCount"],
            "showcaseCount": summary["showcaseCount"],
            "publishedShowcaseCount": summary["publishedShowcaseCount"],
        }
        property_showcase_events = [
            event
            for event in showcase_events
            if event.eventType != "note_click" or event.noteId in note_ids
        ]
        visitor_profiles = self._business_dashboard_visitor_profiles(property_showcase_events, actions, leads, showcase_by_id, note_by_id)
        visitor_profiles = self._merge_property_note_view_profiles(visitor_profiles, notes, note_view_events)
        latest_actions = self._business_dashboard_latest_actions(actions, note_by_id)
        latest_actions = self._merge_pending_lead_actions(latest_actions, pending_leads, notes)
        dashboard = {
            "summary": summary,
            "todaySummary": today_summary,
            "entries": self._business_dashboard_entries(summary),
            "recentVisitors": self._property_dashboard_recent_visitors(notes, note_stats, property_showcase_events, showcase_by_id),
            "topNotes": property_rows[:8],
            "propertyBreakdown": property_rows,
            "topShares": self._business_dashboard_top_shares(share_rows, property_showcase_events),
            "latestActions": latest_actions,
            "showcaseBreakdown": self._business_dashboard_showcase_breakdown(showcases, property_showcase_events),
            "visitorProfiles": visitor_profiles,
        }
        return self._attach_opportunity_radar(dashboard, notes, property_showcase_events, actions, leads, note_view_events)

    def _attach_opportunity_radar(
        self,
        dashboard: dict,
        notes: list[UserNote],
        showcase_events: list[ShowcaseEvent],
        actions: list[CustomerAction],
        leads: list[LeadReminder],
        note_view_events: dict[str, list[ViewEvent]] | None = None,
    ) -> dict:
        note_by_id = {item.id: item for item in notes}
        note_by_card_id: dict[str, UserNote] = {}
        for note in notes:
            note_by_card_id[note.id] = note
            if note.sourceCardId:
                note_by_card_id[note.sourceCardId] = note
        profiles = self._build_opportunity_profiles(note_by_id, note_by_card_id, showcase_events, actions, leads, note_view_events or {})
        alerts = self._build_opportunity_alerts(profiles)
        content_insights = self._build_content_insights(notes, profiles)
        revival_alerts = [item for item in alerts if item.get("alertType") == "revival"]
        today = date_key(now_iso())
        dashboard["radarProfiles"] = profiles[:20]
        dashboard["opportunityAlerts"] = alerts[:8]
        dashboard["contentInsights"] = content_insights[:8]
        dashboard["revivalAlerts"] = revival_alerts[:6]
        dashboard["opportunitySummary"] = {
            "highIntentCount": sum(1 for item in profiles if item.get("intentLevel") == "高"),
            "mediumIntentCount": sum(1 for item in profiles if item.get("intentLevel") == "中"),
            "todayHighIntentCount": sum(1 for item in profiles if item.get("intentLevel") == "高" and item.get("lastActivityDateKey") == today),
            "todayVisitorCount": (dashboard.get("todaySummary") or {}).get("visitorCount", (dashboard.get("summary") or {}).get("todayEventCount", 0)),
            "pendingFollowupCount": (dashboard.get("summary") or {}).get("pendingLeadCount", 0),
            "opportunityCount": len(alerts),
            "revivalCount": len(revival_alerts),
            "topContentTitle": content_insights[0]["title"] if content_insights else "",
        }
        return dashboard

    def _build_opportunity_profiles(
        self,
        note_by_id: dict[str, UserNote],
        note_by_card_id: dict[str, UserNote],
        showcase_events: list[ShowcaseEvent],
        actions: list[CustomerAction],
        leads: list[LeadReminder],
        note_view_events: dict[str, list[ViewEvent]],
    ) -> list[dict]:
        profiles: dict[str, dict] = {}

        def ensure_profile(viewer_user_id: str | None, anonymous_id: str | None, fallback_id: str, nickname: str | None, avatar_url: str | None) -> dict:
            key = self._dashboard_identity_key(viewer_user_id, anonymous_id, fallback_id)
            return profiles.setdefault(
                key,
                {
                    "id": key,
                    "viewerUserId": viewer_user_id or "",
                    "anonymousId": anonymous_id or "",
                    "anonymous": not bool(viewer_user_id),
                    "nickname": self._dashboard_display_name(nickname, viewer_user_id),
                    "avatarUrl": avatar_url or "",
                    "viewCount": 0,
                    "noteClickCount": 0,
                    "consultCount": 0,
                    "actionCount": 0,
                    "durationSeconds": 0,
                    "maxScrollPercent": 0,
                    "focusSections": [],
                    "noteIds": [],
                    "noteTitles": [],
                    "firstActivityAt": "",
                    "lastActivityAt": "",
                    "lastActivityDateKey": "",
                    "visitorIdentityType": VISITOR_IDENTITY_DEFAULT["type"],
                    "visitorIdentityLabel": VISITOR_IDENTITY_DEFAULT["label"],
                    "visitorIdentityGroup": VISITOR_IDENTITY_DEFAULT["group"],
                    "hasLead": False,
                },
            )

        def add_note(profile: dict, note: UserNote | None) -> None:
            if not note:
                return
            if note.id not in profile["noteIds"]:
                profile["noteIds"].append(note.id)
            if note.title and note.title not in profile["noteTitles"]:
                profile["noteTitles"].append(note.title)

        def touch(profile: dict, at: str) -> None:
            if not profile["firstActivityAt"] or at < profile["firstActivityAt"]:
                profile["firstActivityAt"] = at
            if not profile["lastActivityAt"] or at > profile["lastActivityAt"]:
                profile["lastActivityAt"] = at
                profile["lastActivityDateKey"] = date_key(at)

        for event in showcase_events:
            profile = ensure_profile(event.viewerUserId, event.anonymousId, event.id, event.nickname, event.avatarUrl)
            if event.eventType == "view":
                profile["viewCount"] += 1
            elif event.eventType == "note_click":
                profile["noteClickCount"] += 1
            elif event.eventType in {"phone_click", "wechat_copy"}:
                profile["consultCount"] += 1
            profile["durationSeconds"] = max(profile["durationSeconds"], int(event.durationSeconds or 0))
            profile["maxScrollPercent"] = max(profile["maxScrollPercent"], int(event.maxScrollPercent or 0))
            profile["focusSections"] = self._merge_focus_sections(profile["focusSections"], event.focusSections)
            add_note(profile, note_by_id.get(event.noteId or ""))
            touch(profile, event.createdAt)

        for note_id, events in note_view_events.items():
            note = note_by_id.get(note_id)
            for event in events:
                profile = ensure_profile(event.viewerUserId, event.anonymousId, event.id, event.nickname, event.avatarUrl)
                profile["viewCount"] += 1
                profile["durationSeconds"] = max(profile["durationSeconds"], int(event.durationSeconds or 0))
                profile["maxScrollPercent"] = max(profile["maxScrollPercent"], int(event.maxScrollPercent or 0))
                profile["focusSections"] = self._merge_focus_sections(profile["focusSections"], event.focusSections)
                add_note(profile, note)
                touch(profile, event.viewedAt)

        for action in actions:
            profile = ensure_profile(action.viewerUserId, action.anonymousId, action.id, (action.payload or {}).get("name") or (action.payload or {}).get("nickname"), (action.payload or {}).get("avatarUrl"))
            visitor_identity = self._customer_action_visitor_identity(action)
            profile["visitorIdentityType"] = visitor_identity["type"]
            profile["visitorIdentityLabel"] = visitor_identity["label"]
            profile["visitorIdentityGroup"] = visitor_identity["group"]
            profile["actionCount"] += 1
            if action.actionKey in OPPORTUNITY_HIGH_ACTIONS:
                profile["consultCount"] += 1
            add_note(profile, note_by_id.get(action.noteId))
            touch(profile, action.createdAt)

        for lead in leads:
            profile = ensure_profile(lead.viewerUserId, None, lead.id, lead.nickname, lead.avatarUrl)
            profile["hasLead"] = True
            profile["viewCount"] = max(profile["viewCount"], int(lead.viewCount or 0))
            add_note(profile, note_by_card_id.get(lead.cardId))
            touch(profile, lead.updatedAt or lead.createdAt)

        rows = []
        for profile in profiles.values():
            score, level = self._opportunity_score(profile)
            explanation = self._opportunity_explanation(profile)
            advice = self._opportunity_advice(profile)
            rows.append({
                **profile,
                "intentScore": score,
                "intentLevel": level,
                "intentLabel": f"{level}意向",
                "intentExplanation": explanation,
                "suggestedAction": advice["action"],
                "followupWindow": advice["window"],
                "followupScript": self._followup_script(profile),
                "isRevival": self._is_revival_profile(profile),
            })
        return sorted(
            rows,
            key=lambda item: (
                item.get("visitorIdentityType") == "customer",
                item.get("intentScore") or 0,
                item.get("lastActivityAt") or "",
            ),
            reverse=True,
        )

    def _merge_focus_sections(self, existing: list[str], incoming: list[str] | None) -> list[str]:
        result = list(existing or [])
        for item in incoming or []:
            text = str(item or "").strip()[:20]
            if text and text not in result:
                result.append(text)
        return result[:8]

    def _opportunity_score(self, profile: dict) -> tuple[int, str]:
        score = 0
        if profile.get("visitorIdentityType") != "customer":
            return 0, "低"
        duration = int(profile.get("durationSeconds") or 0)
        has_key_section = bool(OPPORTUNITY_KEY_SECTIONS.intersection(set(profile.get("focusSections") or [])))
        if int(profile.get("consultCount") or 0) > 0 or profile.get("hasLead"):
            return 90, "高"
        if int(profile.get("viewCount") or 0) >= 3:
            return 72, "高"
        if duration >= 90 and has_key_section:
            return 70, "高"
        if self._is_revival_profile(profile):
            return 68, "高"
        score += min(int(profile.get("viewCount") or 0) * 8, 32)
        score += min(int(profile.get("noteClickCount") or 0) * 12, 36)
        score += min(int(profile.get("consultCount") or 0) * 35, 70)
        score += 25 if profile.get("hasLead") else 0
        if duration >= 90:
            score += 25
        elif duration >= 30:
            score += 12
        if has_key_section:
            score += 18
        if profile.get("isRevival") or self._is_revival_profile(profile):
            score += 22
        if score >= 65:
            return score, "高"
        if score >= 28:
            return score, "中"
        return score, "低"

    def _opportunity_explanation(self, profile: dict) -> str:
        sections = set(profile.get("focusSections") or [])
        if "价格/优惠" in sections:
            return "重点看了价格和优惠，可能正在比较预算。"
        if "联系方式" in sections or int(profile.get("consultCount") or 0) > 0:
            return "已经看过联系方式或发生咨询动作，建议尽快联系。"
        if "案例/成果" in sections:
            return "看了案例和成果，可能还在建立信任。"
        if "FAQ/保障" in sections:
            return "重点看了保障和常见问题，可能在排除顾虑。"
        if self._is_revival_profile(profile):
            return "沉默后再次打开，可能重新进入决策。"
        if int(profile.get("viewCount") or 0) >= 3:
            return "多次查看同一批资料，兴趣正在升温。"
        if int(profile.get("durationSeconds") or 0) >= 30:
            return "停留时间较长，可能认真看过核心内容。"
        return "有新的浏览动态，可继续观察。"

    def _opportunity_advice(self, profile: dict) -> dict:
        sections = set(profile.get("focusSections") or [])
        if int(profile.get("consultCount") or 0) > 0 or profile.get("hasLead"):
            return {"action": "立即跟进客户", "window": "建议 30 分钟内跟进"}
        if self._is_revival_profile(profile):
            return {"action": "发送最新优惠或预约入口", "window": "建议今天内跟进"}
        if "价格/优惠" in sections:
            return {"action": "发送优惠说明", "window": "建议 30 分钟内跟进"}
        if "案例/成果" in sections:
            return {"action": "发送案例或客户反馈", "window": "建议今天内跟进"}
        if "FAQ/保障" in sections:
            return {"action": "补充保障说明", "window": "建议今天内跟进"}
        if len(profile.get("noteIds") or []) >= 2:
            return {"action": "生成对比资料", "window": "建议今天内跟进"}
        return {"action": "继续观察或轻触达", "window": "可稍后跟进"}

    def _followup_script(self, profile: dict) -> str:
        name = profile.get("nickname") or "您好"
        title = (profile.get("noteTitles") or ["这份资料"])[0]
        action = profile.get("suggestedAction") or self._opportunity_advice(profile)["action"]
        if "优惠" in action:
            return f"{name}，刚看到你在看《{title}》的价格和优惠，我帮你把实际到手方案整理一下，要不要发你看看？"
        if "案例" in action:
            return f"{name}，你刚看了《{title}》的案例部分，我可以再发你几个相近案例，方便你判断。"
        if "对比" in action:
            return f"{name}，我看你看了几份资料，我可以帮你做个简单对比，价格、亮点和适合人群放一起看。"
        return f"{name}，刚看到你打开了《{title}》，如果你方便，我可以把重点和下一步安排发你。"

    def _is_revival_profile(self, profile: dict) -> bool:
        first_at = profile.get("firstActivityAt")
        last_at = profile.get("lastActivityAt")
        if not first_at or not last_at or first_at == last_at:
            return False
        try:
            return (parse_iso(last_at) - parse_iso(first_at)) >= timedelta(days=3)
        except Exception:
            return False

    def _build_opportunity_alerts(self, profiles: list[dict]) -> list[dict]:
        alerts = []
        for profile in profiles:
            if profile.get("visitorIdentityType") != "customer":
                continue
            if profile.get("intentLevel") == "低" and not profile.get("isRevival"):
                continue
            title = (profile.get("noteTitles") or ["资料"])[0]
            sections = "、".join(profile.get("focusSections") or [])
            detail = f"{profile.get('nickname') or '客户'}刚刚查看了《{title}》"
            if profile.get("durationSeconds"):
                detail += f"，停留 {self._format_duration(int(profile.get('durationSeconds') or 0))}"
            if sections:
                detail += f"，重点看了{sections}"
            alerts.append({
                "id": f"opp_{profile.get('id')}",
                "alertType": "revival" if profile.get("isRevival") else "intent",
                "customerName": profile.get("nickname") or "客户",
                "title": title,
                "message": f"{detail}，{profile.get('followupWindow')}。",
                "intentLevel": profile.get("intentLevel"),
                "intentLabel": profile.get("intentLabel"),
                "reason": profile.get("intentExplanation"),
                "suggestedAction": profile.get("suggestedAction"),
                "followupScript": profile.get("followupScript"),
                "lastActivityAt": profile.get("lastActivityAt"),
            })
        return sorted(alerts, key=lambda item: item.get("lastActivityAt") or "", reverse=True)

    def _build_content_insights(self, notes: list[UserNote], profiles: list[dict]) -> list[dict]:
        rows = []
        for note in notes:
            related = [item for item in profiles if note.id in (item.get("noteIds") or [])]
            if not related:
                continue
            view_count = sum(int(item.get("viewCount") or 0) for item in related)
            consult_count = sum(int(item.get("consultCount") or 0) for item in related)
            focus_sections = {section for item in related for section in (item.get("focusSections") or [])}
            if view_count >= 3 and consult_count == 0:
                suggestion = "打开不少但咨询偏少，建议把联系方式或行动按钮提前。"
            elif "价格/优惠" in focus_sections:
                suggestion = "价格和优惠被反复查看，建议补充优惠说明或对比口径。"
            elif "案例/成果" in focus_sections:
                suggestion = "案例内容被关注，建议强化客户反馈和成功案例。"
            elif "FAQ/保障" in focus_sections:
                suggestion = "客户在看保障和常见问题，建议把风险说明前置。"
            else:
                suggestion = "继续观察这份资料的打开和咨询转化。"
            rows.append({
                "noteId": note.id,
                "title": note.title,
                "viewCount": view_count,
                "consultCount": consult_count,
                "focusSections": list(focus_sections)[:6],
                "suggestion": suggestion,
            })
        return sorted(rows, key=lambda item: (item["consultCount"], item["viewCount"]), reverse=True)

    def _format_duration(self, seconds: int) -> str:
        if seconds < 60:
            return f"{seconds} 秒"
        minutes = seconds // 60
        rest = seconds % 60
        return f"{minutes} 分 {rest} 秒" if rest else f"{minutes} 分钟"

    def _safe_int(self, value, minimum: int = 0, maximum: int = 100) -> int:
        try:
            number = int(value or 0)
        except (TypeError, ValueError):
            number = 0
        return max(minimum, min(maximum, number))

    def _normalize_focus_sections(self, sections: list[str] | None) -> list[str]:
        result = []
        for item in sections or []:
            text = str(item or "").strip()[:20]
            if text and text not in result:
                result.append(text)
        return result[:8]

    def _existing_view_session_event_id(self, card_id: str, payload: RecordViewRequest) -> str | None:
        session_id = self._clean_optional_text(payload.sessionId)
        if not session_id:
            return None
        viewer_user_id = self._clean_optional_text(payload.viewerUserId)
        anonymous_id = self._clean_optional_text(payload.anonymousId)
        for event in self.repo.list_view_events_for_card(card_id):
            if event.sessionId != session_id:
                continue
            if viewer_user_id and event.viewerUserId != viewer_user_id:
                continue
            if anonymous_id and event.anonymousId != anonymous_id:
                continue
            return event.id
        return None

    def _existing_showcase_session_event_id(self, showcase_id: str, payload: ShowcaseEventRequest) -> str | None:
        session_id = self._clean_optional_text(payload.sessionId)
        if not session_id or payload.eventType != "view":
            return None
        viewer_user_id = self._clean_optional_text(payload.viewerUserId)
        anonymous_id = self._clean_optional_text(payload.anonymousId)
        for event in self.repo.list_showcase_events(showcase_id):
            if event.eventType != "view" or event.sessionId != session_id:
                continue
            if viewer_user_id and event.viewerUserId != viewer_user_id:
                continue
            if anonymous_id and event.anonymousId != anonymous_id:
                continue
            return event.id
        return None

    def _merge_pending_lead_actions(
        self,
        action_rows: list[dict],
        pending_leads: list[LeadReminder],
        notes: list[UserNote],
    ) -> list[dict]:
        existing_lead_ids = {str(item.get("leadReminderId") or "") for item in action_rows if item.get("leadReminderId")}
        lead_by_id = {lead.id: lead for lead in pending_leads}
        note_by_card_id: dict[str, UserNote] = {}
        for note in notes:
            note_by_card_id[note.id] = note
            if note.sourceCardId:
                note_by_card_id[note.sourceCardId] = note
        rows = []
        for row in action_rows:
            enriched = dict(row)
            lead = lead_by_id.get(str(enriched.get("leadReminderId") or ""))
            if lead:
                if (not enriched.get("customerName")) or enriched.get("customerName") in {"客户", "微信客户", "匿名客户", "匿名访客"}:
                    enriched["customerName"] = lead.nickname or "客户"
                enriched["avatarUrl"] = enriched.get("avatarUrl") or lead.avatarUrl or ""
                enriched["phone"] = enriched.get("phone") or lead.customerPhone or ""
                enriched["wechat"] = enriched.get("wechat") or lead.customerWechat or ""
            rows.append(enriched)
        for lead in pending_leads:
            if lead.id in existing_lead_ids:
                continue
            note = note_by_card_id.get(lead.cardId)
            created_at = lead.updatedAt or lead.createdAt
            rows.append(
                {
                    "id": f"lead_action_{lead.id}",
                    "noteId": note.id if note else lead.cardId,
                    "leadReminderId": lead.id,
                    "orderActionId": "",
                    "targetType": "lead",
                    "noteTitle": note.title if note else "房源资料",
                    "actionKey": "lead-followup",
                    "actionLabel": "待跟进客户",
                    "customerName": lead.nickname or "客户",
                    "avatarUrl": lead.avatarUrl or "",
                    "phone": lead.customerPhone or "",
                    "wechat": lead.customerWechat or "",
                    "orderStatus": "",
                    "orderStatusText": "",
                    "createdAt": created_at,
                    "createdDateKey": date_key(created_at),
                    "isToday": date_key(created_at) == date_key(now_iso()),
                    "statusText": "待联系",
                    "priority": 95,
                    "visitorIdentityType": VISITOR_IDENTITY_DEFAULT["type"],
                    "visitorIdentityLabel": VISITOR_IDENTITY_DEFAULT["label"],
                    "visitorIdentityGroup": VISITOR_IDENTITY_DEFAULT["group"],
                }
            )
        return sorted(
            rows,
            key=lambda item: (item.get("priority") or 0, item.get("createdAt") or ""),
            reverse=True,
        )[:12]

    def _merge_property_note_view_profiles(
        self,
        profiles: list[dict],
        notes: list[UserNote],
        note_view_events: dict[str, list[ViewEvent]],
    ) -> list[dict]:
        today = date_key(now_iso())
        note_by_id = {note.id: note for note in notes}
        merged = {item.get("id"): dict(item) for item in profiles if item.get("id")}
        for note_id, events in note_view_events.items():
            note = note_by_id.get(note_id)
            if not note:
                continue
            for event in sorted(events, key=lambda item: item.viewedAt):
                key = self._dashboard_identity_key(event.viewerUserId, event.anonymousId, event.id)
                profile = merged.setdefault(
                    key,
                    {
                        "id": key,
                        "viewerUserId": event.viewerUserId or "",
                        "anonymousId": event.anonymousId or "",
                        "anonymous": not bool(event.viewerUserId),
                        "nickname": event.nickname or ("匿名访客" if not event.viewerUserId else "微信客户"),
                        "avatarUrl": event.avatarUrl or "",
                        "phone": "",
                        "wechat": "",
                        "budgetText": "",
                        "intentLevel": "待判断",
                        "customerTags": [],
                        "viewCount": 0,
                        "noteClickCount": 0,
                        "consultCount": 0,
                        "actionCount": 0,
                        "showcaseNames": [],
                        "shareIds": [],
                        "noteIds": [],
                        "noteTitles": [],
                        "leadReminderId": "",
                        "orderActionId": "",
                        "noteId": note.id,
                        "visitorIdentityType": VISITOR_IDENTITY_DEFAULT["type"],
                        "visitorIdentityLabel": VISITOR_IDENTITY_DEFAULT["label"],
                        "visitorIdentityGroup": VISITOR_IDENTITY_DEFAULT["group"],
                        "lastActionLabel": "",
                        "lastActivityAt": event.viewedAt,
                        "lastActivityDateKey": event.dateKey,
                        "isToday": event.dateKey == today,
                    },
                )
                profile["viewerUserId"] = profile.get("viewerUserId") or event.viewerUserId or ""
                profile["anonymousId"] = profile.get("anonymousId") or event.anonymousId or ""
                profile["nickname"] = profile.get("nickname") or event.nickname or ("匿名访客" if not event.viewerUserId else "微信客户")
                profile["avatarUrl"] = profile.get("avatarUrl") or event.avatarUrl or ""
                profile["viewCount"] = int(profile.get("viewCount") or 0) + 1
                profile["noteId"] = profile.get("noteId") or note.id
                if note.id not in profile["noteIds"]:
                    profile["noteIds"].append(note.id)
                if note.title not in profile["noteTitles"]:
                    profile["noteTitles"].append(note.title)
                if event.viewedAt >= str(profile.get("lastActivityAt") or ""):
                    profile["lastActivityAt"] = event.viewedAt
                    profile["lastActivityDateKey"] = event.dateKey
                    profile["isToday"] = event.dateKey == today
        return sorted(
            merged.values(),
            key=lambda item: (
                item.get("consultCount") or 0,
                item.get("actionCount") or 0,
                item.get("noteClickCount") or 0,
                item.get("viewCount") or 0,
                item.get("lastActivityAt") or "",
            ),
            reverse=True,
        )[:20]

    def _property_dashboard_recent_visitors(
        self,
        notes: list[UserNote],
        note_stats: dict[str, dict],
        showcase_events: list[ShowcaseEvent],
        showcase_by_id: dict[str, ShowcasePage],
    ) -> list[dict]:
        rows = self._business_dashboard_recent_visitors(showcase_events, showcase_by_id)
        for note in notes:
            for viewer in (note_stats.get(note.id, {}) or {}).get("loggedInViewers") or []:
                rows.append(
                    {
                        "id": f"{note.id}:{viewer.get('userId') or viewer.get('viewedAt')}",
                        "showcaseId": "",
                        "showcaseName": note.title,
                        "noteId": note.id,
                        "noteTitle": note.title,
                        "shareId": "",
                        "scene": "property_note",
                        "viewerUserId": viewer.get("userId") or viewer.get("viewerUserId"),
                        "anonymous": False,
                        "nickname": viewer.get("nickname") or "微信用户",
                        "avatarUrl": viewer.get("avatarUrl") or "",
                        "viewCount": viewer.get("viewCount") or 1,
                        "lastViewedAt": viewer.get("viewedAt") or "",
                        "lastViewedDateKey": date_key(viewer.get("viewedAt")) if viewer.get("viewedAt") else "",
                        "isToday": date_key(viewer.get("viewedAt")) == date_key(now_iso()) if viewer.get("viewedAt") else False,
                        "actionText": f"查看了{note.title or '房源'}",
                    }
                )
        return sorted(rows, key=lambda item: item.get("lastViewedAt") or "", reverse=True)[:12]

    def _dashboard_identity_key(
        self,
        viewer_user_id: str | None = None,
        anonymous_id: str | None = None,
        fallback_id: str | None = None,
    ) -> str:
        if viewer_user_id:
            return f"user:{viewer_user_id}"
        if anonymous_id:
            return f"anon:{anonymous_id}"
        return f"anon:{fallback_id or new_id('visitor')}"

    def _dashboard_display_name(self, nickname: str | None, viewer_user_id: str | None = None) -> str:
        cleaned = str(nickname or "").strip()
        if cleaned:
            return cleaned
        return "微信客户" if viewer_user_id else "匿名客户"

    def _business_dashboard_contact_lookup(
        self,
        actions: list[CustomerAction],
        leads: list[LeadReminder],
    ) -> dict[str, dict]:
        lookup: dict[str, dict] = {}
        for lead in leads:
            key = self._dashboard_identity_key(lead.viewerUserId)
            row = lookup.setdefault(key, {})
            row.update(
                {
                    "viewerUserId": lead.viewerUserId,
                    "nickname": lead.nickname or row.get("nickname") or "微信客户",
                    "avatarUrl": lead.avatarUrl or row.get("avatarUrl") or "",
                    "phone": lead.customerPhone or row.get("phone") or "",
                    "wechat": lead.customerWechat or row.get("wechat") or "",
                    "budgetText": lead.budgetText or row.get("budgetText") or "",
                    "intentLevel": lead.intentLevel or row.get("intentLevel") or "待判断",
                    "customerTags": lead.customerTags or row.get("customerTags") or [],
                    "leadReminderId": lead.id,
                    "lastActivityAt": lead.updatedAt or lead.lastViewedAt or row.get("lastActivityAt") or "",
                }
            )
        for action in actions:
            key = self._dashboard_identity_key(action.viewerUserId, action.anonymousId, action.id)
            payload = action.payload or {}
            visitor_identity = self._customer_action_visitor_identity(action)
            row = lookup.setdefault(key, {})
            is_order_action = action.actionKey in PRODUCT_ORDER_ACTION_KEYS
            lead_id = (action.projectionRefs or {}).get("leadReminderId")
            row.update(
                {
                    "viewerUserId": action.viewerUserId or row.get("viewerUserId") or "",
                    "anonymousId": action.anonymousId or row.get("anonymousId") or "",
                    "nickname": payload.get("name") or payload.get("receiverName") or row.get("nickname") or self._dashboard_display_name(None, action.viewerUserId),
                    "avatarUrl": payload.get("avatarUrl") or row.get("avatarUrl") or "",
                    "phone": payload.get("phone") or row.get("phone") or "",
                    "wechat": payload.get("wechat") or row.get("wechat") or "",
                    "leadReminderId": lead_id or row.get("leadReminderId") or "",
                    "orderActionId": action.id if is_order_action else row.get("orderActionId") or "",
                    "noteId": action.noteId or row.get("noteId") or "",
                    "lastActionLabel": action.actionLabel,
                    "lastActivityAt": max(str(row.get("lastActivityAt") or ""), action.createdAt),
                    "visitorIdentityType": visitor_identity["type"],
                    "visitorIdentityLabel": visitor_identity["label"],
                    "visitorIdentityGroup": visitor_identity["group"],
                }
            )
        return lookup

    def _customer_action_visitor_identity(self, action: CustomerAction | None) -> dict:
        if not action:
            return dict(VISITOR_IDENTITY_DEFAULT)
        payload = action.payload or {}
        identity = payload.get("visitorIdentity") if isinstance(payload.get("visitorIdentity"), dict) else {}
        identity_type = str(identity.get("type") or (action.projectionRefs or {}).get("visitorIdentityType") or "").strip()
        if identity_type == VISITOR_IDENTITY_PEER_AGENT["type"]:
            return dict(VISITOR_IDENTITY_PEER_AGENT)
        if identity_type == VISITOR_IDENTITY_UPSTREAM["type"]:
            return dict(VISITOR_IDENTITY_UPSTREAM)
        return dict(VISITOR_IDENTITY_DEFAULT)

    def _business_dashboard_showcase_breakdown(
        self,
        showcases: list[ShowcasePage],
        showcase_events: list[ShowcaseEvent],
    ) -> list[dict]:
        rows: dict[str, dict] = {}
        for showcase in showcases:
            rows[showcase.id] = {
                "showcaseId": showcase.id,
                "showcaseName": showcase.name,
                "status": showcase.status,
                "openCount": 0,
                "visitorCount": 0,
                "noteClickCount": 0,
                "consultCount": 0,
                "shareCount": 0,
                "shareSourceCount": 0,
                "lastEventAt": "",
                "_visitorKeys": set(),
                "_shareIds": set(),
            }
        for event in showcase_events:
            row = rows.setdefault(
                event.showcaseId,
                {
                    "showcaseId": event.showcaseId,
                    "showcaseName": "展示页",
                    "status": "",
                    "openCount": 0,
                    "visitorCount": 0,
                    "noteClickCount": 0,
                    "consultCount": 0,
                    "shareCount": 0,
                    "shareSourceCount": 0,
                    "lastEventAt": "",
                    "_visitorKeys": set(),
                    "_shareIds": set(),
                },
            )
            if event.eventType == "view":
                row["openCount"] += 1
                row["_visitorKeys"].add(self._dashboard_identity_key(event.viewerUserId, event.anonymousId, event.id))
            elif event.eventType == "note_click":
                row["noteClickCount"] += 1
            elif event.eventType in {"phone_click", "wechat_copy"}:
                row["consultCount"] += 1
            elif event.eventType == "share":
                row["shareCount"] += 1
            if event.shareId:
                row["_shareIds"].add(event.shareId)
            if event.createdAt > row["lastEventAt"]:
                row["lastEventAt"] = event.createdAt
        result = []
        for row in rows.values():
            row["visitorCount"] = len(row.pop("_visitorKeys"))
            row["shareSourceCount"] = len(row.pop("_shareIds"))
            result.append(row)
        return sorted(
            result,
            key=lambda item: (item["openCount"], item["noteClickCount"], item["consultCount"], item["lastEventAt"]),
            reverse=True,
        )

    def _business_dashboard_visitor_profiles(
        self,
        showcase_events: list[ShowcaseEvent],
        actions: list[CustomerAction],
        leads: list[LeadReminder],
        showcase_by_id: dict[str, ShowcasePage],
        note_by_id: dict[str, UserNote],
    ) -> list[dict]:
        contact_lookup = self._business_dashboard_contact_lookup(actions, leads)
        profiles: dict[str, dict] = {}
        for event in sorted(showcase_events, key=lambda item: item.createdAt):
            key = self._dashboard_identity_key(event.viewerUserId, event.anonymousId, event.id)
            contact = contact_lookup.get(key, {})
            showcase = showcase_by_id.get(event.showcaseId)
            profile = profiles.setdefault(
                key,
                {
                    "id": key,
                    "viewerUserId": event.viewerUserId or contact.get("viewerUserId") or "",
                    "anonymousId": event.anonymousId or contact.get("anonymousId") or "",
                    "anonymous": not bool(event.viewerUserId),
                    "nickname": contact.get("nickname") or self._dashboard_display_name(event.nickname, event.viewerUserId),
                    "avatarUrl": contact.get("avatarUrl") or event.avatarUrl or "",
                    "phone": contact.get("phone") or "",
                    "wechat": contact.get("wechat") or "",
                    "budgetText": contact.get("budgetText") or "",
                    "intentLevel": contact.get("intentLevel") or "待判断",
                    "customerTags": contact.get("customerTags") or [],
                    "viewCount": 0,
                    "noteClickCount": 0,
                    "consultCount": 0,
                    "actionCount": 0,
                    "showcaseNames": [],
                    "shareIds": [],
                    "noteIds": [],
                    "noteTitles": [],
                    "leadReminderId": contact.get("leadReminderId") or "",
                    "orderActionId": contact.get("orderActionId") or "",
                    "noteId": contact.get("noteId") or "",
                    "visitorIdentityType": contact.get("visitorIdentityType") or VISITOR_IDENTITY_DEFAULT["type"],
                    "visitorIdentityLabel": contact.get("visitorIdentityLabel") or VISITOR_IDENTITY_DEFAULT["label"],
                    "visitorIdentityGroup": contact.get("visitorIdentityGroup") or VISITOR_IDENTITY_DEFAULT["group"],
                    "lastActionLabel": contact.get("lastActionLabel") or "",
                    "lastActivityAt": contact.get("lastActivityAt") or event.createdAt,
                    "lastActivityDateKey": date_key(contact.get("lastActivityAt") or event.createdAt),
                    "isToday": date_key(contact.get("lastActivityAt") or event.createdAt) == date_key(now_iso()),
                },
            )
            profile["nickname"] = contact.get("nickname") or self._dashboard_display_name(event.nickname, event.viewerUserId)
            profile["avatarUrl"] = contact.get("avatarUrl") or event.avatarUrl or profile["avatarUrl"]
            profile["phone"] = contact.get("phone") or profile["phone"]
            profile["wechat"] = contact.get("wechat") or profile["wechat"]
            profile["leadReminderId"] = contact.get("leadReminderId") or profile["leadReminderId"]
            profile["orderActionId"] = contact.get("orderActionId") or profile["orderActionId"]
            profile["noteId"] = contact.get("noteId") or event.noteId or profile["noteId"]
            profile["visitorIdentityType"] = contact.get("visitorIdentityType") or profile.get("visitorIdentityType") or VISITOR_IDENTITY_DEFAULT["type"]
            profile["visitorIdentityLabel"] = contact.get("visitorIdentityLabel") or profile.get("visitorIdentityLabel") or VISITOR_IDENTITY_DEFAULT["label"]
            profile["visitorIdentityGroup"] = contact.get("visitorIdentityGroup") or profile.get("visitorIdentityGroup") or VISITOR_IDENTITY_DEFAULT["group"]
            if contact.get("noteId") and contact.get("noteId") not in profile["noteIds"]:
                profile["noteIds"].append(contact.get("noteId"))
            profile["lastActionLabel"] = contact.get("lastActionLabel") or profile["lastActionLabel"]
            if event.eventType == "view":
                profile["viewCount"] += 1
            elif event.eventType == "note_click":
                profile["noteClickCount"] += 1
                if event.noteId:
                    if event.noteId not in profile["noteIds"]:
                        profile["noteIds"].append(event.noteId)
                    note = note_by_id.get(event.noteId)
                    title = note.title if note else "资料"
                    if title not in profile["noteTitles"]:
                        profile["noteTitles"].append(title)
            elif event.eventType in {"phone_click", "wechat_copy"}:
                profile["consultCount"] += 1
            if showcase and showcase.name not in profile["showcaseNames"]:
                profile["showcaseNames"].append(showcase.name)
            if event.shareId and event.shareId not in profile["shareIds"]:
                profile["shareIds"].append(event.shareId)
            if event.createdAt > profile["lastActivityAt"]:
                profile["lastActivityAt"] = event.createdAt
                profile["lastActivityDateKey"] = date_key(event.createdAt)
                profile["isToday"] = event.dateKey == date_key(now_iso())
        for key, contact in contact_lookup.items():
            profile = profiles.setdefault(
                key,
                {
                    "id": key,
                    "viewerUserId": contact.get("viewerUserId") or "",
                    "anonymousId": contact.get("anonymousId") or "",
                    "anonymous": not bool(contact.get("viewerUserId")),
                    "nickname": contact.get("nickname") or "微信客户",
                    "avatarUrl": contact.get("avatarUrl") or "",
                    "phone": contact.get("phone") or "",
                    "wechat": contact.get("wechat") or "",
                    "budgetText": contact.get("budgetText") or "",
                    "intentLevel": contact.get("intentLevel") or "待判断",
                    "customerTags": contact.get("customerTags") or [],
                    "viewCount": 0,
                    "noteClickCount": 0,
                    "consultCount": 0,
                    "actionCount": 0,
                    "showcaseNames": [],
                    "shareIds": [],
                    "noteIds": [contact.get("noteId")] if contact.get("noteId") else [],
                    "noteTitles": [],
                    "leadReminderId": contact.get("leadReminderId") or "",
                    "orderActionId": contact.get("orderActionId") or "",
                    "noteId": contact.get("noteId") or "",
                    "visitorIdentityType": contact.get("visitorIdentityType") or VISITOR_IDENTITY_DEFAULT["type"],
                    "visitorIdentityLabel": contact.get("visitorIdentityLabel") or VISITOR_IDENTITY_DEFAULT["label"],
                    "visitorIdentityGroup": contact.get("visitorIdentityGroup") or VISITOR_IDENTITY_DEFAULT["group"],
                    "lastActionLabel": contact.get("lastActionLabel") or "",
                    "lastActivityAt": contact.get("lastActivityAt") or "",
                    "lastActivityDateKey": date_key(contact.get("lastActivityAt")) if contact.get("lastActivityAt") else "",
                    "isToday": date_key(contact.get("lastActivityAt")) == date_key(now_iso()) if contact.get("lastActivityAt") else False,
                },
            )
            profile["phone"] = contact.get("phone") or profile["phone"]
            profile["wechat"] = contact.get("wechat") or profile["wechat"]
            profile["leadReminderId"] = contact.get("leadReminderId") or profile["leadReminderId"]
            profile["orderActionId"] = contact.get("orderActionId") or profile["orderActionId"]
            profile["noteId"] = contact.get("noteId") or profile["noteId"]
            profile["visitorIdentityType"] = contact.get("visitorIdentityType") or profile.get("visitorIdentityType") or VISITOR_IDENTITY_DEFAULT["type"]
            profile["visitorIdentityLabel"] = contact.get("visitorIdentityLabel") or profile.get("visitorIdentityLabel") or VISITOR_IDENTITY_DEFAULT["label"]
            profile["visitorIdentityGroup"] = contact.get("visitorIdentityGroup") or profile.get("visitorIdentityGroup") or VISITOR_IDENTITY_DEFAULT["group"]
            if contact.get("noteId") and contact.get("noteId") not in profile["noteIds"]:
                profile["noteIds"].append(contact.get("noteId"))
            profile["lastActionLabel"] = contact.get("lastActionLabel") or profile["lastActionLabel"]
            profile["actionCount"] += 1 if contact.get("lastActionLabel") else 0
            if contact.get("lastActivityAt") and contact.get("lastActivityAt") > profile.get("lastActivityAt", ""):
                profile["lastActivityAt"] = contact.get("lastActivityAt")
                profile["lastActivityDateKey"] = date_key(contact.get("lastActivityAt"))
                profile["isToday"] = date_key(contact.get("lastActivityAt")) == date_key(now_iso())
        return sorted(
            profiles.values(),
            key=lambda item: (
                item.get("consultCount") or 0,
                item.get("actionCount") or 0,
                item.get("noteClickCount") or 0,
                item.get("viewCount") or 0,
                item.get("lastActivityAt") or "",
            ),
            reverse=True,
        )[:20]

    def _business_dashboard_entries(self, summary: dict) -> list[dict]:
        return [
            {
                "key": "showcases",
                "title": "展示页效果",
                "desc": "看展示页发出去后的效果",
                "count": summary["showcaseOpenCount"],
                "badge": f"{summary['visitorCount']} 位访客",
                "target": "showcases",
            },
            {
                "key": "visitors",
                "title": "访客详情",
                "desc": "看最近谁打开和看过什么",
                "count": summary["visitorCount"],
                "badge": f"匿名 {summary['anonymousVisitorCount']}",
                "target": "visitors",
            },
            {
                "key": "notes",
                "title": "笔记数据",
                "desc": "看哪些资料被点击和咨询",
                "count": summary["noteClickCount"],
                "badge": "点击排行",
                "target": "notes",
            },
            {
                "key": "customers",
                "title": "客户资料",
                "desc": "看客户动作和待跟进",
                "count": summary["customerCount"],
                "badge": f"待联系 {summary['pendingLeadCount']}",
                "target": "customers",
            },
        ]

    def _business_dashboard_recent_visitors(
        self,
        showcase_events: list[ShowcaseEvent],
        showcase_by_id: dict[str, ShowcasePage],
    ) -> list[dict]:
        rows = []
        for event in sorted(showcase_events, key=lambda item: item.createdAt, reverse=True):
            if event.eventType != "view":
                continue
            showcase = showcase_by_id.get(event.showcaseId)
            rows.append(
                {
                    "id": event.id,
                    "showcaseId": event.showcaseId,
                    "showcaseName": showcase.name if showcase else "展示页",
                    "shareId": event.shareId,
                    "scene": event.scene,
                    "viewerUserId": event.viewerUserId,
                    "anonymous": not bool(event.viewerUserId),
                    "nickname": event.nickname or ("匿名客户" if not event.viewerUserId else "微信用户"),
                    "avatarUrl": event.avatarUrl,
                    "viewCount": 1,
                    "lastViewedAt": event.createdAt,
                    "lastViewedDateKey": event.dateKey,
                    "isToday": event.dateKey == date_key(now_iso()),
                    "actionText": f"打开了{showcase.name if showcase else '展示页'}",
                }
            )
            if len(rows) >= 6:
                break
        return rows

    def _business_dashboard_top_notes(self, note_clicks: dict[str, int], note_by_id: dict[str, UserNote]) -> list[dict]:
        rows = []
        for note_id, count in sorted(note_clicks.items(), key=lambda item: item[1], reverse=True)[:6]:
            note = note_by_id.get(note_id)
            rows.append(
                {
                    "noteId": note_id,
                    "title": note.title if note else "资料",
                    "clickCount": count,
                    "cardType": (note.visibilityConfig or {}).get("cardType") if note else "",
                }
            )
        return rows

    def _business_dashboard_top_shares(self, share_rows: dict[str, dict], showcase_events: list[ShowcaseEvent]) -> list[dict]:
        rows = sorted(
            share_rows.values(),
            key=lambda item: (
                item.get("openCount") or 0,
                item.get("noteClickCount") or 0,
                item.get("consultCount") or 0,
                item.get("lastEventAt") or "",
            ),
            reverse=True,
        )[:6]
        events_by_share: dict[str, list[ShowcaseEvent]] = defaultdict(list)
        for event in showcase_events:
            if event.shareId:
                events_by_share[event.shareId].append(event)
        for row in rows:
            visitor_names = []
            visitor_keys = set()
            for event in sorted(events_by_share.get(row["shareId"], []), key=lambda item: item.createdAt, reverse=True):
                if event.eventType != "view":
                    continue
                key = self._dashboard_identity_key(event.viewerUserId, event.anonymousId, event.id)
                if key in visitor_keys:
                    continue
                visitor_keys.add(key)
                visitor_names.append(self._dashboard_display_name(event.nickname, event.viewerUserId))
                if len(visitor_names) >= 3:
                    break
            row["visitorCount"] = len(visitor_keys)
            row["visitorNames"] = visitor_names
        return rows

    def _business_dashboard_latest_actions(
        self,
        actions: list[CustomerAction],
        note_by_id: dict[str, UserNote],
    ) -> list[dict]:
        rows = []
        sorted_actions = sorted(
            actions,
            key=lambda item: (self._customer_action_priority(item), item.createdAt),
            reverse=True,
        )
        for action in sorted_actions[:8]:
            note = note_by_id.get(action.noteId)
            payload = action.payload or {}
            visitor_identity = self._customer_action_visitor_identity(action)
            lead_id = (action.projectionRefs or {}).get("leadReminderId")
            is_order_action = action.actionKey in PRODUCT_ORDER_ACTION_KEYS
            rows.append(
                {
                    "id": action.id,
                    "noteId": action.noteId,
                    "leadReminderId": lead_id,
                    "orderActionId": action.id if is_order_action else "",
                    "targetType": "order" if is_order_action else ("lead" if lead_id else "note"),
                    "noteTitle": note.title if note else "资料",
                    "actionKey": action.actionKey,
                    "actionLabel": action.actionLabel or CUSTOMER_ACTION_LABELS.get(action.actionKey, "客户动作"),
                    "customerName": payload.get("name") or payload.get("receiverName") or self._dashboard_display_name(payload.get("nickname"), action.viewerUserId),
                    "avatarUrl": payload.get("avatarUrl") or "",
                    "phone": payload.get("phone") or "",
                    "wechat": payload.get("wechat") or "",
                    "visitorIdentityType": visitor_identity["type"],
                    "visitorIdentityLabel": visitor_identity["label"],
                    "visitorIdentityGroup": visitor_identity["group"],
                    "orderStatus": payload.get("orderStatus") or "",
                    "orderStatusText": self._order_status_text(payload.get("orderStatus") or "submitted", "seller") if is_order_action else "",
                    "createdAt": action.createdAt,
                    "createdDateKey": date_key(action.createdAt),
                    "isToday": date_key(action.createdAt) == date_key(now_iso()),
                    "statusText": self._customer_action_status_text(action.actionKey, payload),
                    "priority": self._customer_action_priority(action),
                }
            )
        return rows

    def _customer_action_priority(self, action: CustomerAction) -> int:
        payload = action.payload or {}
        if action.actionKey in {"order-intent", "relay-intent"}:
            return 90
        if action.actionKey == "appointment":
            return 80
        if action.actionKey == "lead-contact":
            return 75 if (payload.get("phone") or payload.get("wechat")) else 60
        if action.actionKey in {"consult-click", "navigation-click"}:
            return 50
        return 10

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
            "ownerName": self._clean_optional_text(source.get("ownerName")),
            "avatarUrl": self._clean_optional_text(source.get("avatarUrl")),
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
            "activeCategory": self._clean_optional_text(source.get("activeCategory")) or "全部",
            "showSearch": bool(source.get("showSearch", False)),
            "showTags": bool(source.get("showTags", True)),
            "layoutMode": "grid" if str(source.get("layoutMode") or "list").strip() == "grid" else "list",
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
        structured_data = config.get("structuredData") if isinstance(config.get("structuredData"), dict) else {}
        card_type = config.get("cardType", "text_note")
        return {
            "noteId": note.id,
            "title": item.displayTitle or note.title,
            "summary": note.summary,
            "coverUrl": note.coverUrl,
            "sectionTitle": item.sectionTitle,
            "sortOrder": item.sortOrder,
            "cardType": card_type,
            "systemCategory": config.get("systemCategory", ""),
            "tags": self._note_tags(note),
            "badge": self._showcase_note_badge(card_type),
            "primaryText": self._showcase_note_primary_text(card_type, structured_data, note),
            "secondaryText": self._showcase_note_secondary_text(card_type, structured_data, note),
            "priceText": str(structured_data.get("price") or "").strip(),
            "productMeta": self._showcase_product_meta(card_type, structured_data),
            "productActionText": "查看详情/接龙" if card_type == "groupbuy_product" else "",
            "updatedAt": note.updatedAt,
        }

    def _showcase_product_meta(self, card_type: str, data: dict) -> list[str]:
        if card_type != "groupbuy_product":
            return []
        return [
            str(item).strip()
            for item in [
                data.get("spec"),
                data.get("pickupMethod"),
                data.get("pickupLocation"),
                f"截止 {data.get('deadline')}" if data.get("deadline") else "",
            ]
            if str(item or "").strip()
        ][:4]

    def _showcase_note_badge(self, card_type: str) -> str:
        labels = {
            "property_listing": "房源",
            "groupbuy_product": "好物",
            "image_ocr": "图片",
            "link": "链接",
            "article": "文章",
        }
        return labels.get(card_type, "资料")

    def _showcase_note_primary_text(self, card_type: str, data: dict, note: UserNote) -> str:
        if card_type == "property_listing":
            return " | ".join([str(item) for item in [data.get("area"), data.get("businessArea"), data.get("layout")] if item]) or note.summary
        if card_type == "groupbuy_product":
            return " | ".join([str(item) for item in [data.get("spec"), data.get("pickupMethod"), data.get("pickupLocation")] if item]) or note.summary
        return note.summary

    def _showcase_note_secondary_text(self, card_type: str, data: dict, note: UserNote) -> str:
        if card_type == "property_listing":
            return " | ".join([str(item) for item in [data.get("address"), data.get("utilities"), data.get("remark")] if item]) or note.body
        if card_type == "groupbuy_product":
            return " | ".join([str(item) for item in [data.get("deadline"), data.get("remark")] if item]) or note.body
        return note.body

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

    def duplicate_user_note(self, note_id: str, owner_user_id: str) -> UserNote:
        source = self.get_user_note(note_id, owner_user_id)
        now = now_iso()
        copy_note = source.model_copy(deep=True)
        copy_note.id = new_id("note")
        copy_note.sourceCardId = None
        copy_note.importBatchId = None
        copy_note.title = f"{source.title} 副本"
        copy_note.status = "active"
        config = self._normalize_note_visibility_config(copy_note.visibilityConfig)
        config["cardState"] = "editing"
        copy_note.visibilityConfig = config
        copy_note.createdAt = now
        copy_note.updatedAt = now
        self.repo.save_user_note(copy_note)
        return copy_note

    def clone_property_same(self, payload: PropertySameCloneRequest) -> dict:
        owner = self.repo.get_user(payload.ownerUserId)
        if not owner:
            raise HTTPException(status_code=404, detail="用户不存在")
        source_type = str(payload.sourceType or "note").strip().lower()
        if source_type in {"showcase", "collection", "合集"}:
            showcase = self._clone_public_showcase_for_owner(payload, owner)
            return {
                "type": "showcase",
                "showcase": self._showcase_owner_payload(showcase),
                "sharePath": f"/pages/showcase-view/index?id={showcase.id}",
            }
        note = self._clone_public_note_for_owner(payload.sourceId, payload, owner)
        return {
            "type": "note",
            "note": note.model_dump(),
            "sharePath": f"/pages/note-preview/index?id={note.id}",
        }

    def _clone_public_showcase_for_owner(self, payload: PropertySameCloneRequest, owner: User) -> ShowcasePage:
        source = self.repo.get_showcase_page(payload.sourceId)
        if not source or source.status != "published":
            raise HTTPException(status_code=404, detail="公开合集不存在或未发布")
        now = now_iso()
        cloned_items: list[ShowcaseItem] = []
        for index, item in enumerate(self._valid_showcase_items(source), start=1):
            cloned_note = self._clone_public_note_for_owner(item.noteId, payload, owner, source_showcase_id=source.id)
            cloned_items.append(
                ShowcaseItem(
                    noteId=cloned_note.id,
                    sortOrder=item.sortOrder if item.sortOrder is not None else index,
                    sectionTitle=item.sectionTitle,
                    displayTitle=item.displayTitle,
                    visible=item.visible,
                    fieldConfig=dict(item.fieldConfig or {}),
                )
            )
        if not cloned_items:
            raise HTTPException(status_code=400, detail="合集里没有可复制的公开房源")
        contact_config = self._clone_contact_config(payload, owner)
        showcase = ShowcasePage(
            id=new_id("showcase"),
            ownerUserId=owner.id,
            status="published" if payload.publishShowcase else "draft",
            name=source.name,
            description=source.description,
            bannerUrl=source.bannerUrl,
            templateId=source.templateId,
            shareTitle=source.shareTitle,
            contactConfig=contact_config,
            displayConfig=dict(source.displayConfig or {}),
            items=cloned_items,
            publicSnapshot={},
            snapshotVersion=0,
            snapshotCreatedAt=None,
            publishedAt=now if payload.publishShowcase else None,
            createdAt=now,
            updatedAt=now,
        )
        if payload.publishShowcase:
            showcase.publicSnapshot = self._build_showcase_public_snapshot(showcase, now, 1)
            showcase.snapshotVersion = 1
            showcase.snapshotCreatedAt = now
        self.repo.save_showcase_page(showcase)
        self._register_media_refs_for_urls([source.bannerUrl], owner.id, "showcase", showcase.id, "banner")
        return showcase

    def _clone_public_note_for_owner(
        self,
        source_note_id: str,
        payload: PropertySameCloneRequest,
        owner: User,
        source_showcase_id: str | None = None,
    ) -> UserNote:
        source = self.repo.get_user_note(source_note_id)
        if not source or source.status == "deleted":
            raise HTTPException(status_code=404, detail="公开房源卡不存在")
        source_config = source.visibilityConfig if isinstance(source.visibilityConfig, dict) else {}
        source_structured = source_config.get("structuredData") if isinstance(source_config.get("structuredData"), dict) else {}
        structured_data = self._public_clone_structured_data(source_structured)
        phone = self._clean_optional_text(payload.phone) or owner.phone
        wechat = self._clean_optional_text(payload.wechat)
        if phone:
            structured_data["phone"] = phone
            structured_data["contactPhone"] = phone
        if wechat:
            structured_data["wechat"] = wechat
            structured_data["contactWechat"] = wechat
        media = self._clone_note_media(source)
        cover_url = source.coverUrl or self._first_media_url(media)
        now = now_iso()
        source_refs = self._unique_strings([*source.sourceRefs, source.id, source_showcase_id or ""])
        card_type = str(source_config.get("cardType") or "property_listing")
        visibility_config = self._normalize_note_visibility_config(
            {
                **source_config,
                "cardType": card_type,
                "cardState": "editing",
                "sourceType": "property_same_clone",
                "structuredData": structured_data,
                "conversionConfig": self._clone_conversion_config(card_type, source_config, phone, wechat),
                "cloneSource": {
                    "sourceNoteId": source.id,
                    "sourceShowcaseId": source_showcase_id,
                    "sourceOwnerUserId": source.ownerUserId,
                },
                "privateData": {
                    "upstreamContact": self._clone_upstream_contact(payload, source, source_config),
                    "editableByOwner": True,
                },
            }
        )
        note = UserNote(
            id=new_id("note"),
            ownerUserId=owner.id,
            importBatchId=None,
            sourceCardId=None,
            status="active",
            title=source.title,
            summary=source.summary,
            body=source.body,
            coverUrl=cover_url,
            media=media,
            categoryIds=[],
            phone=phone,
            locationText=source.locationText,
            sourceRefs=source_refs,
            visibilityConfig=visibility_config,
            createdAt=now,
            updatedAt=now,
        )
        self.repo.save_user_note(note)
        self._register_media_refs_for_urls([cover_url, *[item.get("url") for item in media if isinstance(item, dict)]], owner.id, "note", note.id, "clone_media")
        self._record_property_same_peer_signal(
            source_note_id=source.id,
            source_showcase_id=source_showcase_id,
            clone_owner=owner,
            payload=payload,
            clone_type="note",
            generated_ref_id=note.id,
        )
        return note

    def _record_property_same_peer_signal(
        self,
        source_note_id: str,
        source_showcase_id: str | None,
        clone_owner: User,
        payload: PropertySameCloneRequest,
        clone_type: str,
        generated_ref_id: str,
    ) -> None:
        source = self.repo.get_user_note(source_note_id)
        if not source or source.status == "deleted" or source.ownerUserId == clone_owner.id:
            return
        now = now_iso()
        phone = self._clean_optional_text(payload.phone) or clone_owner.phone or ""
        wechat = self._clean_optional_text(payload.wechat) or ""
        action = CustomerAction(
            id=new_id("action"),
            ownerUserId=source.ownerUserId,
            noteId=source.id,
            sourceCardId=source.sourceCardId,
            viewerUserId=clone_owner.id,
            anonymousId=None,
            actionKey="consult-click",
            actionLabel="生成同款",
            payload={
                "name": clone_owner.nickname,
                "avatarUrl": clone_owner.avatarUrl,
                "phone": phone,
                "wechat": wechat,
                "cloneType": clone_type,
                "generatedRefId": generated_ref_id,
                "sourceShowcaseId": source_showcase_id or "",
                "visitorIdentity": VISITOR_IDENTITY_PEER_AGENT,
                "note": "该访客通过生成同款进入，默认归为同行传播，不进入客户待跟进。",
            },
            projectionRefs={
                "visitorIdentityType": VISITOR_IDENTITY_PEER_AGENT["type"],
                "visitorIdentityLabel": VISITOR_IDENTITY_PEER_AGENT["label"],
                "generatedRefId": generated_ref_id,
            },
            createdAt=now,
            updatedAt=now,
        )
        self.repo.save_customer_action(action)

    def _clone_note_media(self, source: UserNote) -> list[dict]:
        media = [dict(item) for item in source.media if isinstance(item, dict)]
        if source.coverUrl and not any(item.get("url") == source.coverUrl for item in media):
            media.insert(0, self._image_media_payload(source.coverUrl, "封面图"))
        return media

    def _first_media_url(self, media: list[dict]) -> str | None:
        for item in media:
            if isinstance(item, dict) and item.get("url"):
                return str(item.get("url"))
        return None

    def _clone_contact_config(self, payload: PropertySameCloneRequest, owner: User) -> dict:
        phone = self._clean_optional_text(payload.phone) or owner.phone
        wechat = self._clean_optional_text(payload.wechat)
        return self._normalize_showcase_contact_config(
            {
                "phone": phone,
                "wechat": wechat,
                "contactText": "想了解房源细节，欢迎直接联系我。",
                "ownerName": self._clean_optional_text(payload.ownerName) or owner.nickname,
                "avatarUrl": self._clean_optional_text(payload.avatarUrl) or owner.avatarUrl,
                "showPhone": bool(phone),
                "showWechat": bool(wechat),
            }
        )

    def _clone_conversion_config(self, card_type: str, source_config: dict, phone: str | None, wechat: str | None) -> dict:
        incoming = source_config.get("conversionConfig") if isinstance(source_config.get("conversionConfig"), dict) else {}
        conversion = self._normalize_conversion_config(card_type, incoming)
        conversion["showContactPhone"] = bool(phone)
        conversion["enablePrivateConsultation"] = bool(wechat) or conversion.get("enablePrivateConsultation", False)
        return conversion

    def _clone_upstream_contact(self, payload: PropertySameCloneRequest, source: UserNote, source_config: dict) -> str:
        explicit = self._clean_optional_text(payload.upstreamContact)
        if explicit:
            return explicit
        structured = source_config.get("structuredData") if isinstance(source_config.get("structuredData"), dict) else {}
        candidates = [
            structured.get("wechat"),
            structured.get("contactWechat"),
            structured.get("phone"),
            structured.get("contactPhone"),
            source.phone,
        ]
        source_owner = self.repo.get_user(source.ownerUserId)
        if source_owner:
            candidates.extend([source_owner.nickname, source_owner.phone])
        return next((str(item).strip() for item in candidates if str(item or "").strip()), "原发布中介")

    def _register_media_refs_for_urls(
        self,
        urls: list[str | None],
        owner_user_id: str,
        ref_type: str,
        ref_id: str,
        usage: str,
    ) -> None:
        for url in self._unique_strings([str(item).strip() for item in urls if str(item or "").strip()]):
            asset = self.repo.get_media_asset_by_url(url)
            if asset:
                self._save_media_asset_ref(asset, owner_user_id, ref_type, ref_id, usage)

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
        if card_type in {"business_card", "service_offer"}:
            return dict(SERVICE_CONVERSION_DEFAULTS)
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
            summary = (note.summary or "").strip()
            if not summary or summary in {"已收藏，待整理。", "已收藏，待整理"} or summary == (note.title or "").strip():
                summary = (note.body or note.title or "")[:120]
                note.summary = summary
            structured_data["organizeResult"] = {
                "summary": summary,
                "generationOptions": ["日常合集", "分享摘要", "标签归类"],
                "enabledFeatures": [],
            }
            config["structuredData"] = structured_data
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
        system_category_map = {
            "property_listing": "房源",
            "groupbuy_product": "团购",
            "business_card": "名片",
            "service_offer": "服务",
        }
        tag_map = {
            "property_listing": ["房产", "房源"],
            "groupbuy_product": ["团购", "商品"],
            "business_card": ["名片", "顾问"],
            "service_offer": ["服务", "销售"],
        }
        system_category = system_category_map.get(card_type, current_config.get("systemCategory", "待整理"))
        extra_tags = tag_map.get(card_type, ["待整理"])
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
        if card_type == "business_card":
            return {
                **preserved,
                "name": current.get("name") or note.title,
                "title": current.get("title", ""),
                "company": current.get("company", ""),
                "serviceScope": current.get("serviceScope", ""),
                "headline": current.get("headline") or note.summary or "",
                "bio": current.get("bio") or note.body,
                "phone": current.get("phone") or note.phone or "",
                "wechat": current.get("wechat", ""),
                "city": current.get("city") or note.locationText or "",
                "avatarUrl": current.get("avatarUrl") or note.coverUrl or "",
                "qrCodeUrl": current.get("qrCodeUrl", ""),
                "images": images,
                "rawText": current.get("rawText") or note.body,
            }
        if card_type == "service_offer":
            return {
                **preserved,
                "serviceName": current.get("serviceName") or note.title,
                "headline": current.get("headline") or note.summary or "",
                "targetAudience": current.get("targetAudience", ""),
                "serviceContent": current.get("serviceContent") or note.body,
                "pricingNote": current.get("pricingNote", ""),
                "serviceProcess": current.get("serviceProcess", ""),
                "caseHighlights": current.get("caseHighlights", ""),
                "serviceArea": current.get("serviceArea") or note.locationText or "",
                "contact": current.get("contact") or note.phone or "",
                "appointmentNote": current.get("appointmentNote", ""),
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
            "business_card": "电子名片",
            "service_offer": "服务方案",
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

    def delete_topic(self, topic_id: str, owner_user_id: str) -> dict:
        if not self.repo.get_user(owner_user_id):
            raise HTTPException(status_code=404, detail="用户不存在")
        topic = self.repo.get_topic(topic_id)
        if not topic or topic.ownerUserId != owner_user_id:
            raise HTTPException(status_code=404, detail="专题不存在")
        self.repo.delete_topic(topic_id)
        return {"deletedTopicId": topic_id}

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
                "summary": "用于测试轻 SCRM 红点、留言和预约。",
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
                    "demoData": True,
                    "demoTag": DASHBOARD_DEMO_TAG,
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
                customerTags=["演示", "房源客户", DASHBOARD_DEMO_TAG],
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
                    "remark": "演示留言",
                    "demoData": True,
                    "demoTag": DASHBOARD_DEMO_TAG,
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
                appointment_action.payload = {**appointment_action.payload, "demoData": True, "demoTag": DASHBOARD_DEMO_TAG}
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
                "demoData": True,
                "demoTag": DASHBOARD_DEMO_TAG,
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
                "demoData": True,
                "demoTag": DASHBOARD_DEMO_TAG,
            },
            projectionRefs={},
            createdAt=now,
            updatedAt=now,
        )
        self.repo.save_customer_action(relay_action)
        actions.append(relay_action)
        showcase = ShowcasePage(
            id=new_id("showcase"),
            ownerUserId=owner_user_id,
            status="published",
            name="演示展示页：房源和好物精选",
            description="用于测试经营看板的展示页打开、访客、资料点击和咨询数据。",
            bannerUrl=notes[0].coverUrl or product_note.coverUrl,
            templateId="featured_window",
            shareTitle="演示展示页：近期精选资料",
            contactConfig={
                "phone": user.phone or "13800001001",
                "wechat": "demo_wechat",
                "contactText": "欢迎联系我了解详情",
                "ownerName": user.nickname,
                "avatarUrl": user.avatarUrl,
                "showPhone": True,
                "showWechat": True,
            },
            displayConfig={
                "groupBy": "tag",
                "activeCategory": "演示数据",
                "showSearch": False,
                "showTags": True,
                "primaryColor": "#1677ff",
                "demoData": True,
                "demoTag": DASHBOARD_DEMO_TAG,
            },
            items=[
                ShowcaseItem(noteId=note.id, sortOrder=index, visible=True)
                for index, note in enumerate(notes)
            ],
            publishedAt=now,
            createdAt=now,
            updatedAt=now,
        )
        showcase.snapshotVersion = 1
        showcase.snapshotCreatedAt = now
        showcase.publicSnapshot = self._build_showcase_public_snapshot(showcase, now, 1)
        self.repo.save_showcase_page(showcase)
        demo_events = [
            ShowcaseEvent(
                id=new_id("showcase_event"),
                showcaseId=showcase.id,
                ownerUserId=owner_user_id,
                eventType="view",
                noteId=None,
                viewerUserId=leads[0].viewerUserId if leads else None,
                viewType="logged_in" if leads else "anonymous",
                anonymousId=None if leads else "demo_anon_001",
                nickname=leads[0].nickname if leads else "匿名客户",
                avatarUrl=leads[0].avatarUrl if leads else None,
                createdAt=now,
                dateKey=date_key(now),
            ),
            ShowcaseEvent(
                id=new_id("showcase_event"),
                showcaseId=showcase.id,
                ownerUserId=owner_user_id,
                eventType="view",
                noteId=None,
                viewerUserId=None,
                viewType="anonymous",
                anonymousId="demo_anon_002",
                nickname=None,
                avatarUrl=None,
                createdAt=now,
                dateKey=date_key(now),
            ),
            ShowcaseEvent(
                id=new_id("showcase_event"),
                showcaseId=showcase.id,
                ownerUserId=owner_user_id,
                eventType="note_click",
                noteId=notes[0].id,
                viewerUserId=leads[0].viewerUserId if leads else None,
                viewType="logged_in" if leads else "anonymous",
                anonymousId=None if leads else "demo_anon_003",
                nickname=leads[0].nickname if leads else "匿名客户",
                avatarUrl=leads[0].avatarUrl if leads else None,
                createdAt=now,
                dateKey=date_key(now),
            ),
            ShowcaseEvent(
                id=new_id("showcase_event"),
                showcaseId=showcase.id,
                ownerUserId=owner_user_id,
                eventType="phone_click",
                noteId=None,
                viewerUserId=leads[0].viewerUserId if leads else None,
                viewType="logged_in" if leads else "anonymous",
                anonymousId=None if leads else "demo_anon_004",
                nickname=leads[0].nickname if leads else "匿名客户",
                avatarUrl=leads[0].avatarUrl if leads else None,
                createdAt=now,
                dateKey=date_key(now),
            ),
            ShowcaseEvent(
                id=new_id("showcase_event"),
                showcaseId=showcase.id,
                ownerUserId=owner_user_id,
                eventType="wechat_copy",
                noteId=None,
                viewerUserId=None,
                viewType="anonymous",
                anonymousId="demo_anon_005",
                nickname=None,
                avatarUrl=None,
                createdAt=now,
                dateKey=date_key(now),
            ),
        ]
        for event in demo_events:
            self.repo.add_showcase_event(event)
        return {
            "notes": [item.model_dump() for item in notes],
            "actionsCreated": len(actions),
            "leadsCreated": len(leads),
            "showcasesCreated": 1,
            "showcaseEventsCreated": len(demo_events),
        }

    def cleanup_note_demo_data(self, owner_user_id: str) -> dict:
        if not self.repo.get_user(owner_user_id):
            raise HTTPException(status_code=404, detail="用户不存在")
        state = self.repo.load()

        def is_demo_note(note: UserNote) -> bool:
            config = note.visibilityConfig or {}
            tags = set(config.get("tags") or [])
            return (
                note.ownerUserId == owner_user_id
                and (
                    config.get("demoData") is True
                    or config.get("demoTag") == DASHBOARD_DEMO_TAG
                    or "演示数据" in tags
                    or str(note.title or "").startswith(("测试房源", "测试商品"))
                )
            )

        demo_note_ids = {item.id for item in state.user_notes if is_demo_note(item)}

        def is_demo_showcase(showcase: ShowcasePage) -> bool:
            display = showcase.displayConfig or {}
            return (
                showcase.ownerUserId == owner_user_id
                and (
                    display.get("demoData") is True
                    or display.get("demoTag") == DASHBOARD_DEMO_TAG
                    or str(showcase.name or "").startswith("演示展示页")
                )
            )

        demo_showcase_ids = {item.id for item in state.showcase_pages if is_demo_showcase(item)}
        demo_lead_ids = {
            item.id
            for item in state.lead_reminders
            if item.ownerUserId == owner_user_id
            and (
                DASHBOARD_DEMO_TAG in set(item.customerTags or [])
                or "演示" in set(item.customerTags or [])
                or item.cardId in demo_note_ids
            )
        }
        demo_action_ids = {
            item.id
            for item in state.customer_actions
            if item.ownerUserId == owner_user_id
            and (
                (item.payload or {}).get("demoData") is True
                or (item.payload or {}).get("demoTag") == DASHBOARD_DEMO_TAG
                or item.noteId in demo_note_ids
                or (item.projectionRefs or {}).get("leadReminderId") in demo_lead_ids
            )
        }
        before = {
            "notes": len(state.user_notes),
            "showcases": len(state.showcase_pages),
            "showcaseEvents": len(state.showcase_events),
            "leads": len(state.lead_reminders),
            "actions": len(state.customer_actions),
        }
        state.user_notes = [item for item in state.user_notes if item.id not in demo_note_ids]
        state.showcase_pages = [item for item in state.showcase_pages if item.id not in demo_showcase_ids]
        state.showcase_events = [
            item
            for item in state.showcase_events
            if not (item.ownerUserId == owner_user_id and (item.showcaseId in demo_showcase_ids or item.noteId in demo_note_ids))
        ]
        state.lead_reminders = [item for item in state.lead_reminders if item.id not in demo_lead_ids]
        state.customer_actions = [item for item in state.customer_actions if item.id not in demo_action_ids]
        self.repo.save(state)
        return {
            "deleted": {
                "notes": before["notes"] - len(state.user_notes),
                "showcases": before["showcases"] - len(state.showcase_pages),
                "showcaseEvents": before["showcaseEvents"] - len(state.showcase_events),
                "leads": before["leads"] - len(state.lead_reminders),
                "actions": before["actions"] - len(state.customer_actions),
            }
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
            visitor_identity = self._customer_action_visitor_identity(action)
            row = action.model_dump()
            row["customerName"] = action.payload.get("name") or (lead.get("nickname") if lead else "") or "客户"
            row["customerAvatarUrl"] = action.payload.get("avatarUrl") or (lead.get("avatarUrl") if lead else None)
            row["leadReminderId"] = lead_id
            row["leadStatus"] = lead.get("status") if lead else None
            row["leadStatusText"] = self._lead_status_text(lead.get("status")) if lead else ""
            row["statusText"] = self._customer_action_status_text(action.actionKey, action.payload)
            row["visitorIdentityType"] = visitor_identity["type"]
            row["visitorIdentityLabel"] = visitor_identity["label"]
            row["visitorIdentityGroup"] = visitor_identity["group"]
            if action.actionKey in PRODUCT_ORDER_ACTION_KEYS:
                order_status = str((action.payload or {}).get("orderStatus") or "submitted")
                row["orderStatus"] = order_status
                row["orderStatusText"] = self._order_status_text(order_status, "seller")
                row["orderStatusGroup"] = self._order_status_group(order_status)
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

    def list_orders(self, user_id: str, role: str, note_id: str | None = None) -> dict:
        if role not in {"buyer", "seller"}:
            raise HTTPException(status_code=400, detail="订单角色不正确")
        rows = [
            self._build_order_row(note, action, role)
            for note, action in self._iter_order_actions()
            if (role == "buyer" and action.viewerUserId == user_id)
            or (role == "seller" and action.ownerUserId == user_id)
        ]
        if note_id:
            rows = [item for item in rows if item["noteId"] == note_id]
        return {
            "role": role,
            "summary": {
                "total": len(rows),
                "pending": sum(1 for item in rows if item["status"] == "submitted"),
                "contacted": sum(1 for item in rows if item["status"] == "contacted"),
                "completed": sum(1 for item in rows if item["status"] == "completed"),
                "cancelled": sum(1 for item in rows if item["status"] == "cancelled"),
                "relay": sum(1 for item in rows if item["actionKey"] == "relay-intent"),
                "order": sum(1 for item in rows if item["actionKey"] == "order-intent"),
            },
            "orders": rows,
        }

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
        return {
            "id": action.id,
            "actionKey": action.actionKey,
            "actionKindText": "接龙" if action.actionKey == "relay-intent" else "下单",
            "statusGroup": self._order_status_group(status_value),
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
            "statusText": self._order_status_text(status_value, role),
            "createdAt": action.createdAt,
            "updatedAt": action.updatedAt,
        }

    def _order_status_text(self, status_value: str, role: str = "seller") -> str:
        if status_value == "submitted":
            return "待处理" if role == "seller" else "已提交"
        if status_value == "contacted":
            return "已联系"
        if status_value == "completed":
            return "已完成"
        if status_value == "cancelled":
            return "已取消"
        return "待处理" if role == "seller" else "已提交"

    def _order_status_group(self, status_value: str) -> str:
        if status_value in {"completed", "cancelled"}:
            return "finished"
        if status_value == "contacted":
            return "processing"
        return "pending"

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
        self._remove_deleted_note_from_showcase_snapshots(note_id, owner_user_id)
        return {"deletedNoteId": note_id}

    def _remove_deleted_note_from_showcase_snapshots(self, note_id: str, owner_user_id: str) -> None:
        now = now_iso()
        for showcase in self.repo.list_showcase_pages(owner_user_id):
            changed = False
            if any(item.noteId == note_id for item in showcase.items):
                showcase.items = [item for item in showcase.items if item.noteId != note_id]
                changed = True
            snapshot = showcase.publicSnapshot if isinstance(showcase.publicSnapshot, dict) else {}
            snapshot_items = snapshot.get("items") if isinstance(snapshot, dict) else None
            if isinstance(snapshot_items, list):
                filtered_items = [item for item in snapshot_items if not isinstance(item, dict) or item.get("noteId") != note_id]
                if len(filtered_items) != len(snapshot_items):
                    next_version = (showcase.snapshotVersion or 0) + 1
                    showcase.publicSnapshot = {
                        **snapshot,
                        "items": filtered_items,
                        "updatedAt": now,
                        "snapshotVersion": next_version,
                        "snapshotCreatedAt": now,
                        "snapshotSource": "published_snapshot",
                    }
                    showcase.snapshotVersion = next_version
                    showcase.snapshotCreatedAt = now
                    changed = True
            if changed:
                showcase.updatedAt = now
                self.repo.save_showcase_page(showcase)

    def list_cards(self, owner_user_id: str | None = None, keyword: str | None = None, category_id: str | None = None) -> list[dict]:
        cards = self.repo.list_cards(owner_user_id=owner_user_id, keyword=keyword, category_id=category_id)
        rows = []
        backed_note_ids: set[str] = set()
        for item in cards:
            source_note = self._find_note_by_source_card(item.id)
            if source_note:
                backed_note_ids.add(source_note.id)
            source_note_config = source_note.visibilityConfig if source_note else {}
            source_note_cover_url = self._first_note_image_url(source_note) if source_note else ""
            rows.append(
                {
                    **item.model_dump(),
                    "coverUrl": item.coverUrl or source_note_cover_url,
                    "cardType": source_note_config.get("cardType"),
                    "systemCategory": source_note_config.get("systemCategory"),
                    "visibilityConfig": source_note_config,
                    "stats": self._build_card_stats(item.id),
                    "sourceNoteId": source_note.id if source_note else None,
                    "customerSummary": self._build_note_customer_summary(source_note) if source_note else {},
                }
            )
        rows.extend(self._note_card_rows(owner_user_id, keyword, category_id, backed_note_ids))
        rows.sort(key=lambda item: item.get("updatedAt") or item.get("createdAt") or "", reverse=True)
        return rows

    def _note_card_rows(
        self,
        owner_user_id: str | None,
        keyword: str | None,
        category_id: str | None,
        backed_note_ids: set[str],
    ) -> list[dict]:
        if not owner_user_id:
            return []
        notes = self.repo.list_user_notes(
            owner_user_id=owner_user_id,
            keyword=None,
            category_id=category_id,
            include_deleted=False,
        )
        if keyword:
            lowered = keyword.lower().strip()
            query_digits = re.sub(r"\D+", "", lowered)
            notes = [item for item in notes if self._note_matches_keyword(item, lowered, query_digits)]
        rows: list[dict] = []
        for note in notes:
            if note.id in backed_note_ids or note.sourceCardId:
                continue
            config = note.visibilityConfig or {}
            card_type = config.get("cardType") or ("link" if config.get("contentMode") == "bookmark" else "text_note")
            system_category = self._note_card_category_name(card_type, config.get("systemCategory"))
            cover_url = note.coverUrl or self._first_note_image_url(note)
            rows.append(
                {
                    "id": f"note_card_{note.id}",
                    "ownerUserId": note.ownerUserId,
                    "importBatchId": note.importBatchId,
                    "sourceCardId": note.sourceCardId,
                    "status": note.status,
                    "title": note.title,
                    "coverUrl": cover_url,
                    "detailText": note.body or note.summary,
                    "projectName": note.title,
                    "locationText": note.locationText,
                    "phone": note.phone,
                    "relayNotice": None,
                    "sourceUrl": None,
                    "enabledFields": [],
                    "categoryIds": note.categoryIds,
                    "media": note.media,
                    "relayConfig": {},
                    "publishedAt": note.updatedAt,
                    "createdAt": note.createdAt,
                    "updatedAt": note.updatedAt,
                    "cardType": card_type,
                    "systemCategory": system_category,
                    "categoryName": system_category,
                    "visibilityConfig": config,
                    "stats": self._build_note_stats(note),
                    "sourceNoteId": note.id,
                    "customerSummary": self._build_note_customer_summary(note),
                }
            )
        return rows

    def _note_card_category_name(self, card_type: str, system_category: str | None = None) -> str:
        if system_category and not (card_type in {"text_note", "link", "image_ocr"} and system_category in {"待整理", "未整理"}):
            return system_category
        return {
            "business_card": "名片",
            "service_offer": "服务",
            "property_listing": "房源",
            "groupbuy_product": "团购",
            "link": "链接",
            "image_ocr": "图片",
            "text_note": "普通笔记",
        }.get(card_type, "资料")

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

    def _find_note_by_source_card(self, card_id: str) -> UserNote | None:
        for note in self.repo.list_all_user_notes(include_deleted=False):
            if note.sourceCardId == card_id:
                return note
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
        is_share_event = self._clean_optional_text(payload.eventType) == "share"
        if not is_share_event and payload.viewerUserId and payload.viewerUserId == card.ownerUserId:
            now = now_iso()
            return ViewEvent(
                id=new_id("view_ignored"),
                cardId=card_id,
                viewerUserId=payload.viewerUserId,
                viewType="logged_in",
                anonymousId=payload.anonymousId,
                nickname=payload.nickname,
                avatarUrl=payload.avatarUrl,
                shareId=self._clean_optional_text(payload.shareId),
                shareFromUserId=self._clean_optional_text(payload.shareFromUserId),
                scene=self._clean_optional_text(payload.scene),
                referrer=self._clean_optional_text(payload.referrer),
                sessionId=self._clean_optional_text(payload.sessionId),
                durationSeconds=0,
                maxScrollPercent=0,
                focusSections=[],
                viewedAt=now,
                dateKey=date_key(now),
            )

        now = now_iso()
        event = ViewEvent(
            id=self._existing_view_session_event_id(card_id, payload) or new_id("view"),
            cardId=card_id,
            viewerUserId=payload.viewerUserId,
            viewType="share" if is_share_event else "logged_in" if payload.viewerUserId else "anonymous",
            anonymousId=payload.anonymousId,
            nickname=payload.nickname,
            avatarUrl=payload.avatarUrl,
            shareId=self._clean_optional_text(payload.shareId),
            shareFromUserId=self._clean_optional_text(payload.shareFromUserId),
            scene=self._clean_optional_text(payload.scene),
            referrer=self._clean_optional_text(payload.referrer),
            sessionId=self._clean_optional_text(payload.sessionId),
            durationSeconds=self._safe_int(payload.durationSeconds, 0, 24 * 60 * 60),
            maxScrollPercent=self._safe_int(payload.maxScrollPercent, 0, 100),
            focusSections=self._normalize_focus_sections(payload.focusSections),
            viewedAt=now,
            dateKey=date_key(now),
        )
        self.repo.add_view_event(event)
        return event

    def record_note_view(self, note_id: str, payload: RecordViewRequest) -> ViewEvent:
        note = self._get_active_note(note_id)
        event_card_id = note.sourceCardId or note.id
        is_share_event = self._clean_optional_text(payload.eventType) == "share"
        if not is_share_event and payload.viewerUserId and payload.viewerUserId == note.ownerUserId:
            now = now_iso()
            return ViewEvent(
                id=new_id("view_ignored"),
                cardId=event_card_id,
                viewerUserId=payload.viewerUserId,
                viewType="logged_in",
                anonymousId=payload.anonymousId,
                nickname=payload.nickname,
                avatarUrl=payload.avatarUrl,
                shareId=self._clean_optional_text(payload.shareId),
                shareFromUserId=self._clean_optional_text(payload.shareFromUserId),
                scene=self._clean_optional_text(payload.scene),
                referrer=self._clean_optional_text(payload.referrer),
                sessionId=self._clean_optional_text(payload.sessionId),
                durationSeconds=0,
                maxScrollPercent=0,
                focusSections=[],
                viewedAt=now,
                dateKey=date_key(now),
            )
        now = now_iso()
        event = ViewEvent(
            id=self._existing_view_session_event_id(event_card_id, payload) or new_id("view"),
            cardId=event_card_id,
            viewerUserId=payload.viewerUserId,
            viewType="share" if is_share_event else "logged_in" if payload.viewerUserId else "anonymous",
            anonymousId=payload.anonymousId,
            nickname=payload.nickname,
            avatarUrl=payload.avatarUrl,
            shareId=self._clean_optional_text(payload.shareId),
            shareFromUserId=self._clean_optional_text(payload.shareFromUserId),
            scene=self._clean_optional_text(payload.scene),
            referrer=self._clean_optional_text(payload.referrer),
            sessionId=self._clean_optional_text(payload.sessionId),
            durationSeconds=self._safe_int(payload.durationSeconds, 0, 24 * 60 * 60),
            maxScrollPercent=self._safe_int(payload.maxScrollPercent, 0, 100),
            focusSections=self._normalize_focus_sections(payload.focusSections),
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

    def _build_note_stats(self, note: UserNote) -> dict:
        stats_id = note.sourceCardId or note.id
        events = self.repo.list_view_events_for_card(stats_id)
        relays = self.repo.list_relay_entries_for_card(stats_id, relay_status="active")
        return self._build_stats_from_events(stats_id, events, relays)

    def _build_note_customer_summary(self, note: UserNote | None) -> dict:
        if not note:
            return {}
        actions = self.repo.list_customer_actions_for_note(note.id)
        projected_lead_ids = {
            str((action.projectionRefs or {}).get("leadReminderId") or "")
            for action in actions
            if (action.projectionRefs or {}).get("leadReminderId")
        }
        leads = [
            item
            for item in self.repo.list_lead_reminders(note.ownerUserId)
            if item.id in projected_lead_ids
        ]
        latest_action_at = max((action.createdAt for action in actions), default=None)
        order_count = sum(1 for action in actions if action.actionKey in PRODUCT_ORDER_ACTION_KEYS)
        relay_count = sum(1 for action in actions if action.actionKey == "relay-intent")
        pending_count = sum(1 for item in leads if item.status == "pending")
        return {
            "total": len(actions),
            "leadContact": sum(1 for action in actions if action.actionKey == "lead-contact"),
            "appointment": sum(1 for action in actions if action.actionKey == "appointment"),
            "orderIntent": order_count,
            "relayIntent": relay_count,
            "consult": sum(1 for action in actions if action.actionKey == "consult-click"),
            "leads": len(leads),
            "pending": pending_count,
            "hasUnread": pending_count > 0 or order_count > 0 or relay_count > 0,
            "latestActionAt": latest_action_at,
        }

    def _build_stats_map(self, state: AppState) -> dict[str, dict]:
        stats = defaultdict(
            lambda: {
                "pv": 0,
                "uv": 0,
                "anonymousPv": 0,
                "anonymousUv": 0,
                "loggedInViewers": [],
                "relayCount": 0,
                "shareCount": 0,
                "latestShareAt": None,
                "topShareId": "",
            }
        )
        logged_viewers = defaultdict(dict)
        unique_anonymous = defaultdict(set)
        for event in state.view_events:
            row = stats[event.cardId]
            if event.viewType == "share":
                row["shareCount"] += 1
                if not row["latestShareAt"] or event.viewedAt > row["latestShareAt"]:
                    row["latestShareAt"] = event.viewedAt
                    row["topShareId"] = event.shareId or ""
                continue
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
            "shareCount": 0,
            "latestShareAt": None,
            "topShareId": "",
        }
        logged_viewers = {}
        unique_anonymous = set()
        for event in events:
            if event.viewType == "share":
                row["shareCount"] += 1
                if not row["latestShareAt"] or event.viewedAt > row["latestShareAt"]:
                    row["latestShareAt"] = event.viewedAt
                    row["topShareId"] = event.shareId or ""
                continue
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
