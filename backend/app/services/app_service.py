from __future__ import annotations

import hashlib
import hmac
import base64
import json
import secrets
from math import ceil
import re
from threading import RLock
import time
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse
from uuid import uuid4
import httpx
from fastapi import HTTPException, status

from app.core.config import settings
from app.models.domain import AppState, Card, CardMedia, Category, CustomerAction, CustomerRadarSummary, ImportBatch, LeadFollowUpLog, LeadReminder, MediaAsset, MediaAssetRef, MembershipEntitlement, MembershipOrder, MessageRecord, MessageThread, MediaRetryJob, MutualActivityEvent, MutualPointAccount, MutualPointLedger, MutualRechargeOrder, NotificationPreference, OpportunityLead, OpportunityLeadContact, OpportunityLeadFollowup, OpportunityLeadSave, OpportunityLeadSource, OpportunityPushDigest, OpportunitySubscription, RawMessage, ReferralRelation, ReferralReward, ReferralWithdrawal, RelayConfig, RelayEntry, ResourceFreeQuota, ResourcePointLedger, ResourceUnlockRecord, ResourceWallet, ResponsePackage, ResponsePackageEvent, ResponsePackageItem, SameStyleGeneration, ShowcaseEvent, ShowcaseItem, ShowcasePage, SkillRun, SupplyDemandApplication, SupplyDemandCard, SyncCursor, Topic, User, UserNote, ViewEvent, WechatSubscriptionDelivery, WechatSubscriptionGrant, WecomArchiveCursor, WecomArchiveMessage, WecomBindCardToken, WecomIdentityBinding
from app.schemas.auth import MockLoginRequest, UserProfileUpdateRequest, WechatLoginRequest
from app.schemas.categories import CategoryCreateRequest
from app.schemas.cards import CardCreateRequest, CardUpdateRequest, CreateRelayRequest, LeadReminderUpdateRequest, LeadReminderUpsertRequest, RecordViewRequest
from app.schemas.notes import CustomerActionSubmitRequest, LinkCaptureRequest, ManualNoteDraftRequest, NoteInteractionEventRequest, NoteTypeConfirmRequest, PropertyBatchCreateRequest, PropertyBatchParseRequest, PropertySameCloneRequest, QuickNoteCaptureRequest, TopicCreateRequest, UserNoteUpdateRequest
from app.schemas.share_snapshots import ShareSnapshotRequest
from app.schemas.showcases import ShowcaseEventRequest, ShowcasePageRequest
from app.schemas.scrm import SameStyleGenerateRequest
from app.schemas.skills import (
    ContentMediaPayload,
    ContentLinkPayload,
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
from app.services.link_preview_service import fetch_link_preview
from app.services.media_storage_service import MediaStorageService
from app.services.session_token import issue_user_session
from app.services.media_processing_service import MediaProcessingService
from app.services.message_aggregator import MessageAggregator, WINDOW_SECONDS
from app.services.ops_console_store import OpsConsoleStore
from app.services.ocr_service import OcrService
from app.services.property_table_ocr_service import PropertyTableOcrService
from app.services.points_core import DEFAULT_POINTS_ACCOUNT_TYPE, PointsCoreService
from app.services.repository import AppRepository
from app.services.skill_router_service import SkillRouterService
from app.services.showcase_templates import allowed_template_ids, default_template_id, normalize_scene_type, normalize_template_id, note_scene_type, scene_accepts_note
from app.services.text_safety import strip_unicode_surrogates
from app.services.time_utils import SHANGHAI, date_key, now_iso, parse_iso
from app.services.wecom_message_normalizer import WecomMessageNormalizer
from app.services.wecom_mock_service import WecomMockService
from app.services.wechat_miniapp_client import WechatMiniappClient, WechatMiniappClientError
from app.services.wechat_pay import WechatPayClient, WechatPayError
from app.services.sync_task_queue import SyncTaskQueue


LEAD_REMINDER_STATUSES = {"pending", "following", "contacted", "invalid", "paused", "completed", "deleted"}
LEAD_CLOSED_STATUSES = {"invalid", "paused", "completed", "deleted"}
LEAD_INBOX_RESOLVED_STATUSES = LEAD_CLOSED_STATUSES | {"contacted", "following"}
FOLLOWUP_ACTION_LOCK = RLock()
WECOM_EXTERNAL_BINDING_SOURCE = "wecom_external_user"
WECOM_BIND_INTENT_SOURCE = "wecom_bind_intent"
WECOM_BIND_INTENT_PENDING = "pending_assistant_bind"
WECOM_BIND_INTENT_CONSUMED = "consumed_assistant_bind"
WECOM_BIND_CARD_SOURCE = "contact_plugin_welcome"
WECOM_BIND_CODE_PATTERN = re.compile(r"\bTB-[A-Z0-9]{6}\b", re.IGNORECASE)
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
PUBLIC_ATTACHMENT_TYPES = {"image", "pdf", "link"}
NOTE_INTERACTION_TYPES = {"image_open", "pdf_open", "link_open", "source_open", "contact_click", "phone_click", "wechat_qr_open", "featured_note_open", "map_open"}
CUSTOMER_INTELLIGENCE_SHOWCASE_EVENTS = {"view", "note_click", "phone_click", "wechat_copy", "share"}
CUSTOMER_INTELLIGENCE_NOTE_EVENTS = set(NOTE_INTERACTION_TYPES)
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
    "enableLightScrm": True,
    "collectLeads": True,
    "enableAppointment": False,
    "enablePrivateConsultation": True,
    "enableSharePoster": True,
    "enableGroupRelay": True,
    "enablePaymentPlaceholder": False,
}
SERVICE_CONVERSION_DEFAULTS = {
    "showContactPhone": True,
    "enableLightScrm": True,
    "collectLeads": True,
    "enableAppointment": False,
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
        {"key": "email", "label": "邮箱", "type": "text", "required": False},
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
RESOURCE_WALLET_INITIAL_POINTS = 100
RESOURCE_UNLOCK_IDEMPOTENCY_HOURS = 24
RESPONSE_PACKAGE_COST_POINTS = 20
RESPONSE_PACKAGE_FREE_QUOTA_LIMIT = 3
OPPORTUNITY_CONTACT_UNLOCK_COST_POINTS = 10
SALES_SCRM_PLAN_CODE = "sales_scrm_monthly"
SALES_SCRM_MONTHLY_PRICE_FEN = 1990
SALES_SCRM_REWARD_BASIS_POINTS = 5000
SALES_SCRM_PERIOD_DAYS = 30
MEMBERSHIP_PENDING_ORDER_TTL_SECONDS = 30 * 60
MEMBERSHIP_PAYMENT_LOCK = RLock()
SHARE_SNAPSHOT_RETENTION_DAYS = 30
SHARE_SNAPSHOT_STYLE_ID = "share_card_v10"
SUBSCRIBE_ACCEPT_STATUSES = {"accept", "acceptWithAudio"}
SUBSCRIBE_DEDUPE_WINDOW_SECONDS = 30 * 60
SUBSCRIBE_DELIVERY_MAX_ATTEMPTS = 3
SUBSCRIBE_RESERVATION_TIMEOUT_SECONDS = 15 * 60
SUBSCRIBE_FIELD_NAMES = ("messageName", "customerName", "projectName", "messageContent", "reminderTime")
MUTUAL_INITIAL_POINTS = 100
MUTUAL_RESERVE_POINTS = 300
MUTUAL_POINTS_PER_YUAN = 10
MUTUAL_RECHARGE_PACKAGES = (100, 500, 1000, 2000)


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
        property_table_ocr_service: PropertyTableOcrService | None = None,
        wechat_miniapp_client: WechatMiniappClient | None = None,
        ops_console_store: OpsConsoleStore | None = None,
        points_core: PointsCoreService | None = None,
    ):
        self.repo = repo
        self.wecom_mock_service = wecom_mock_service
        self.media_storage_service = media_storage_service
        self.media_processing_service = media_processing_service or MediaProcessingService()
        self.parser_service = parser_service
        self.aggregator = aggregator
        self.notification_service = notification_service
        self.normalizer = normalizer
        self.wechat_miniapp_client = wechat_miniapp_client
        self.ops_console_store = ops_console_store
        self.points_core = points_core or PointsCoreService()
        self.skill_router_service = skill_router_service or SkillRouterService()
        self.content_object_adapter = content_object_adapter or ContentObjectAdapter()
        self._card_list_cache: dict[tuple[str, str, str], tuple[float, list[dict]]] = {}
        self._card_list_cache_ttl_seconds = 60
        self._card_list_cache_max_entries = 256
        self._note_list_cache: dict[tuple, tuple[float, list[dict]]] = {}
        self._note_list_cache_ttl_seconds = 60
        self._note_list_cache_max_entries = 256
        self._showcase_list_cache: dict[str, tuple[float, list[dict]]] = {}
        self._showcase_list_cache_ttl_seconds = 60
        self._showcase_list_cache_max_entries = 128
        self._customer_intelligence_cache: dict[tuple[str, str, str], tuple[float, dict]] = {}
        self._customer_intelligence_cache_ttl_seconds = 2 * 60
        self._customer_intelligence_cache_max_entries = 256
        self._customer_intelligence_summary_cache: dict[tuple[str, str, str], tuple[float, dict]] = {}
        self._customer_intelligence_summary_cache_ttl_seconds = 30
        self._customer_intelligence_summary_cache_max_entries = 256
        self.ocr_service = ocr_service or OcrService(
            provider=settings.ocr_provider,
            language=settings.ocr_language,
            tesseract_bin=settings.ocr_tesseract_bin,
            mock_text=settings.ocr_mock_text,
        )
        self.property_table_ocr_service = property_table_ocr_service or PropertyTableOcrService()

    def _load(self) -> AppState:
        return self.repo.load()

    def _save(self, state: AppState) -> None:
        self.repo.save(state)

    def customer_info_chain_enabled(self) -> bool:
        """Return the server-authoritative customer feature state.

        Test-only AppService instances may omit the ops store; preserving an
        enabled default there keeps existing isolated service tests focused on
        their business rule.  The production dependency always supplies the
        persistent store, whose safe default is closed.
        """
        if self.ops_console_store is None:
            return True
        return bool(self.ops_console_store.get_customer_info_chain_config()["enabled"])

    def customer_info_chain_payment_required(self) -> bool:
        if self.ops_console_store is None:
            return True
        return bool(self.ops_console_store.get_customer_info_chain_config().get("paymentRequired", True))

    def require_customer_info_chain_enabled(self) -> None:
        if not self.customer_info_chain_enabled():
            raise HTTPException(status_code=403, detail="客户信息链功能当前未开放")

    def get_resource_wallet(self, owner_user_id: str) -> dict:
        wallet = self._ensure_resource_wallet(owner_user_id)
        ledgers = self.repo.list_resource_point_ledgers(owner_user_id, limit=20)
        return {
            "wallet": wallet.model_dump(),
            "recentLedgers": [item.model_dump() for item in ledgers],
        }

    def list_resource_point_ledgers(self, owner_user_id: str, limit: int = 100) -> list[dict]:
        self._ensure_resource_wallet(owner_user_id)
        safe_limit = min(max(int(limit or 100), 1), 200)
        return [item.model_dump() for item in self.repo.list_resource_point_ledgers(owner_user_id, limit=safe_limit)]

    def consume_resource_points(
        self,
        owner_user_id: str,
        action_type: str,
        target_type: str,
        target_id: str,
        points_cost: int,
        reason: str | None = None,
        quota_type: str | None = None,
        free_quota_limit: int = 0,
        period_key: str | None = None,
        metadata: dict | None = None,
    ) -> dict:
        if points_cost < 0:
            raise HTTPException(status_code=400, detail="积分消耗不能为负数")
        if not action_type or not target_type or not target_id:
            raise HTTPException(status_code=400, detail="缺少积分消费对象")
        wallet = self._ensure_resource_wallet(owner_user_id)
        now = now_iso()
        existing = self.repo.find_resource_unlock_record(owner_user_id, action_type, target_type, target_id)
        if existing and self._is_resource_unlock_active(existing, now):
            return {
                "wallet": wallet.model_dump(),
                "ledger": None,
                "unlockRecord": existing.model_dump(),
                "freeQuota": None,
                "charged": False,
                "duplicate": True,
                "usedFreeQuota": existing.usedFreeQuota,
            }

        free_quota = None
        used_free_quota = False
        if quota_type and free_quota_limit > 0:
            quota_period = period_key or date_key(now)
            free_quota = self.repo.get_resource_free_quota(owner_user_id, quota_type, quota_period)
            if not free_quota:
                free_quota = ResourceFreeQuota(
                    id=f"quota_{owner_user_id}_{quota_type}_{quota_period}",
                    ownerUserId=owner_user_id,
                    quotaType=quota_type,
                    periodKey=quota_period,
                    limitCount=free_quota_limit,
                    usedCount=0,
                    createdAt=now,
                    updatedAt=now,
                )
            if free_quota.usedCount < free_quota.limitCount:
                free_quota.usedCount += 1
                free_quota.updatedAt = now
                used_free_quota = True
                self.repo.save_resource_free_quota(free_quota)

        if used_free_quota:
            ledger_delta = 0
            ledger_type = "free_quota"
        else:
            if wallet.balance < points_cost:
                raise HTTPException(status_code=402, detail="积分余额不足")
            wallet.balance -= points_cost
            wallet.totalConsumed += points_cost
            wallet.updatedAt = now
            self.repo.save_resource_wallet(wallet)
            ledger_delta = -points_cost
            ledger_type = "consume"

        unlock_record = ResourceUnlockRecord(
            id=new_id("unlock"),
            ownerUserId=owner_user_id,
            actionType=action_type,
            targetType=target_type,
            targetId=target_id,
            pointsCost=0 if used_free_quota else points_cost,
            usedFreeQuota=used_free_quota,
            quotaId=free_quota.id if free_quota else None,
            ledgerId=None,
            unlockedAt=now,
            expiresAt=(parse_iso(now) + timedelta(hours=RESOURCE_UNLOCK_IDEMPOTENCY_HOURS)).isoformat(),
            createdAt=now,
            updatedAt=now,
        )
        ledger = ResourcePointLedger(
            id=new_id("ledger"),
            ownerUserId=owner_user_id,
            walletId=wallet.id,
            ledgerType=ledger_type,
            actionType=action_type,
            targetType=target_type,
            targetId=target_id,
            pointsDelta=ledger_delta,
            balanceAfter=wallet.balance,
            reason=reason,
            relatedUnlockId=unlock_record.id,
            metadata=metadata or {},
            createdAt=now,
        )
        unlock_record.ledgerId = ledger.id
        self.repo.save_resource_point_ledger(ledger)
        self.repo.save_resource_unlock_record(unlock_record)
        return {
            "wallet": wallet.model_dump(),
            "ledger": ledger.model_dump(),
            "unlockRecord": unlock_record.model_dump(),
            "freeQuota": free_quota.model_dump() if free_quota else None,
            "charged": not used_free_quota and points_cost > 0,
            "duplicate": False,
            "usedFreeQuota": used_free_quota,
        }

    def adjust_resource_wallet(
        self,
        owner_user_id: str,
        points_delta: int,
        reason: str | None = None,
        operator_id: str | None = None,
    ) -> dict:
        if points_delta == 0:
            raise HTTPException(status_code=400, detail="调整积分不能为 0")
        wallet = self._ensure_resource_wallet(owner_user_id)
        now = now_iso()
        new_balance = wallet.balance + points_delta
        if new_balance < 0:
            raise HTTPException(status_code=400, detail="调整后积分不能小于 0")
        wallet.balance = new_balance
        if points_delta > 0:
            wallet.totalGranted += points_delta
        else:
            wallet.totalConsumed += abs(points_delta)
        wallet.updatedAt = now
        self.repo.save_resource_wallet(wallet)
        ledger = ResourcePointLedger(
            id=new_id("ledger"),
            ownerUserId=owner_user_id,
            walletId=wallet.id,
            ledgerType="adjust",
            actionType="ops_adjust",
            pointsDelta=points_delta,
            balanceAfter=wallet.balance,
            reason=reason,
            operatorId=operator_id,
            createdAt=now,
        )
        self.repo.save_resource_point_ledger(ledger)
        return {"wallet": wallet.model_dump(), "ledger": ledger.model_dump()}

    def _ensure_resource_wallet(self, owner_user_id: str) -> ResourceWallet:
        if not self.repo.get_user(owner_user_id):
            raise HTTPException(status_code=404, detail="用户不存在")
        wallet = self.repo.get_resource_wallet(owner_user_id)
        if wallet:
            return wallet
        now = now_iso()
        wallet = ResourceWallet(
            id=f"wallet_{owner_user_id}",
            ownerUserId=owner_user_id,
            balance=RESOURCE_WALLET_INITIAL_POINTS,
            totalGranted=RESOURCE_WALLET_INITIAL_POINTS,
            totalConsumed=0,
            createdAt=now,
            updatedAt=now,
        )
        ledger = ResourcePointLedger(
            id=new_id("ledger"),
            ownerUserId=owner_user_id,
            walletId=wallet.id,
            ledgerType="grant",
            actionType="initial_grant",
            pointsDelta=RESOURCE_WALLET_INITIAL_POINTS,
            balanceAfter=wallet.balance,
            reason="初始资源工具积分",
            createdAt=now,
        )
        self.repo.save_resource_wallet(wallet)
        self.repo.save_resource_point_ledger(ledger)
        return wallet

    def _is_resource_unlock_active(self, record: ResourceUnlockRecord, now: str) -> bool:
        if not record.expiresAt:
            return True
        try:
            return parse_iso(record.expiresAt) > parse_iso(now)
        except Exception:
            return False

    def upsert_opportunity_lead(self, payload) -> dict:
        title = (payload.title or "").strip()
        if not title:
            raise HTTPException(status_code=400, detail="线索标题不能为空")
        now = now_iso()
        existing = self.repo.get_opportunity_lead(payload.id) if payload.id else None
        status_value = payload.status if payload.status in {"draft", "published", "archived", "rejected"} else "draft"
        published_at = existing.publishedAt if existing else None
        if status_value == "published" and not published_at:
            published_at = now
        lead = OpportunityLead(
            id=existing.id if existing else new_id("opp"),
            title=title,
            summary=(payload.summary or "").strip(),
            city=(payload.city or "").strip() or None,
            district=(payload.district or "").strip() or None,
            industry=(payload.industry or "").strip() or None,
            demandType=(payload.demandType or "需求").strip() or "需求",
            content=(payload.content or "").strip(),
            tags=[str(item).strip() for item in (payload.tags or []) if str(item).strip()][:12],
            contactStatus=payload.contactStatus if payload.contactStatus in {"none", "available", "masked", "locked", "pending_verify"} else "pending_verify",
            trustStatus=payload.trustStatus if payload.trustStatus in {"verified", "pending", "risk"} else "pending",
            status=status_value,
            priority=(payload.priority or "").strip() or None,
            publishedAt=published_at,
            expiresAt=payload.expiresAt,
            createdAt=existing.createdAt if existing else now,
            updatedAt=now,
        )
        self.repo.save_opportunity_lead(lead)
        if payload.source:
            existing_sources = self.repo.list_opportunity_lead_sources(lead.id)
            source = OpportunityLeadSource(
                id=existing_sources[0].id if existing_sources else new_id("opp_source"),
                leadId=lead.id,
                sourcePlatform=(payload.source.sourcePlatform or "").strip() or None,
                sourceUrl=(payload.source.sourceUrl or "").strip() or None,
                sourceAuthor=(payload.source.sourceAuthor or "").strip() or None,
                sourcePublishedAt=payload.source.sourcePublishedAt,
                sourceCapturedAt=existing_sources[0].sourceCapturedAt if existing_sources else now,
                rawText=(payload.source.rawText or "").strip(),
                rawImages=payload.source.rawImages or [],
                createdAt=existing_sources[0].createdAt if existing_sources else now,
                updatedAt=now,
            )
            self.repo.save_opportunity_lead_source(source)
        for index, item in enumerate(payload.contacts or []):
            contact_value = (item.contactValue or "").strip()
            if not contact_value:
                continue
            contact = OpportunityLeadContact(
                id=new_id("opp_contact"),
                leadId=lead.id,
                contactType=(item.contactType or "wechat").strip() or "wechat",
                contactValueEncrypted=contact_value,
                contactMasked=(item.contactMasked or "").strip() or self._mask_opportunity_contact(contact_value),
                verifyStatus=(item.verifyStatus or "pending").strip() or "pending",
                createdAt=now,
                updatedAt=now,
            )
            self.repo.save_opportunity_lead_contact(contact)
            if index == 0 and lead.contactStatus in {"none", "pending_verify"}:
                lead.contactStatus = "masked"
                lead.updatedAt = now
                self.repo.save_opportunity_lead(lead)
        return self.get_opportunity_lead_detail(lead.id, include_ops=True)

    def list_opportunity_leads_public(
        self,
        keyword: str | None = None,
        city: str | None = None,
        industry: str | None = None,
        demand_type: str | None = None,
        contact_status: str | None = None,
    ) -> list[dict]:
        leads = self.repo.list_opportunity_leads(statuses={"published"}, keyword=keyword)
        return [
            self._opportunity_lead_public_payload(item)
            for item in leads
            if not self._opportunity_lead_expired(item)
            and self._opportunity_lead_matches_filters(item, city, industry, demand_type, contact_status)
        ]

    def list_opportunity_leads_for_user(
        self,
        user_id: str,
        keyword: str | None = None,
        city: str | None = None,
        industry: str | None = None,
        demand_type: str | None = None,
        contact_status: str | None = None,
    ) -> dict:
        if not self.repo.get_user(user_id):
            raise HTTPException(status_code=404, detail="用户不存在")
        subscriptions = [item for item in self.repo.list_opportunity_subscriptions(user_id) if item.status == "active"]
        subscription = subscriptions[0] if subscriptions else None
        leads = self.repo.list_opportunity_leads(statuses={"published"}, keyword=keyword)
        rows = []
        for index, lead in enumerate(leads):
            if self._opportunity_lead_expired(lead):
                continue
            if not self._opportunity_lead_matches_filters(lead, city, industry, demand_type, contact_status):
                continue
            payload = self._opportunity_lead_public_payload(lead)
            score, reasons = self._score_lead_for_subscription(lead, subscription)
            payload["matchScore"] = score
            payload["matchReasons"] = reasons
            payload["recommendationReason"] = " / ".join(reasons[:3]) if reasons else "今日推荐"
            payload["_sortIndex"] = index
            rows.append(payload)
        rows.sort(key=lambda item: (item.get("matchScore", 0), -item["_sortIndex"]), reverse=True)
        if subscription:
            rows = [item for item in rows if item.get("matchScore", 0) >= 62][:12]
        else:
            rows = rows[:12]
        for item in rows:
            item.pop("_sortIndex", None)
        return {
            "items": rows,
            "subscription": subscription.model_dump() if subscription else None,
            "recommendationTitle": "今日推荐机会",
            "generatedAt": now_iso(),
            "rule": "按订阅条件、联系方式、可信状态和时效排序生成",
        }

    def list_opportunity_leads_ops(self, keyword: str | None = None, status: str | None = None) -> list[dict]:
        statuses = {status} if status else None
        leads = self.repo.list_opportunity_leads(statuses=statuses, keyword=keyword)
        return [self._opportunity_lead_ops_payload(item) for item in leads]

    def get_opportunity_lead_detail(self, lead_id: str, include_ops: bool = False) -> dict:
        lead = self.repo.get_opportunity_lead(lead_id)
        if not lead:
            raise HTTPException(status_code=404, detail="商机线索不存在")
        if not include_ops and lead.status != "published":
            raise HTTPException(status_code=404, detail="商机线索不存在")
        return self._opportunity_lead_ops_payload(lead) if include_ops else self._opportunity_lead_public_payload(lead, detail=True)

    def save_opportunity_lead_for_user(
        self,
        lead_id: str,
        user_id: str,
        save_status: str = "saved",
        note: str | None = None,
        reminder_at: str | None = None,
    ) -> dict:
        if not self.repo.get_user(user_id):
            raise HTTPException(status_code=404, detail="用户不存在")
        lead = self.repo.get_opportunity_lead(lead_id)
        if not lead or lead.status != "published":
            raise HTTPException(status_code=404, detail="商机线索不存在")
        now = now_iso()
        existing = self.repo.get_opportunity_lead_save(lead_id, user_id)
        lead_save = OpportunityLeadSave(
            id=existing.id if existing else new_id("opp_save"),
            leadId=lead_id,
            userId=user_id,
            status=save_status if save_status in {"saved", "contacted", "following", "invalid", "archived"} else "saved",
            note=note,
            reminderAt=reminder_at,
            createdAt=existing.createdAt if existing else now,
            updatedAt=now,
        )
        self.repo.save_opportunity_lead_save(lead_save)
        return {"lead": self._opportunity_lead_public_payload(lead), "save": lead_save.model_dump()}

    def list_saved_opportunity_leads(
        self,
        user_id: str,
        status: str | None = None,
        keyword: str | None = None,
        package_status: str | None = None,
    ) -> list[dict]:
        if not self.repo.get_user(user_id):
            raise HTTPException(status_code=404, detail="用户不存在")
        rows = []
        for item in self.repo.list_opportunity_lead_saves_for_user(user_id):
            if status and item.status != status:
                continue
            lead = self.repo.get_opportunity_lead(item.leadId)
            if not lead:
                continue
            haystack = f"{lead.title} {lead.summary} {lead.city or ''} {lead.industry or ''} {lead.demandType} {item.note or ''}"
            if keyword and keyword not in haystack:
                continue
            package = self.repo.get_response_package_for_lead_user(lead.id, user_id)
            package_payload = self._build_response_package_payload(package) if package else None
            if package_status == "generated" and not package:
                continue
            if package_status == "not_generated" and package:
                continue
            followups = self.repo.list_opportunity_lead_followups(lead.id, user_id=user_id)
            latest_followup = sorted(followups, key=lambda row: row.createdAt, reverse=True)[0] if followups else None
            rows.append(
                {
                    "lead": self._opportunity_lead_public_payload(lead),
                    "save": item.model_dump(),
                    "responsePackage": package_payload,
                    "packageStatus": "generated" if package else "not_generated",
                    "packageStatusText": "已生成" if package else "未生成",
                    "latestFollowup": latest_followup.model_dump() if latest_followup else None,
                    "followupCount": len(followups),
                }
            )
        return rows

    def list_opportunity_subscriptions(self, owner_user_id: str) -> list[dict]:
        if not self.repo.get_user(owner_user_id):
            raise HTTPException(status_code=404, detail="用户不存在")
        return [item.model_dump() for item in self.repo.list_opportunity_subscriptions(owner_user_id)]

    def upsert_opportunity_subscription(self, payload) -> dict:
        if not self.repo.get_user(payload.userId):
            raise HTTPException(status_code=404, detail="用户不存在")
        now = now_iso()
        existing = None
        if payload.id:
            existing = next((item for item in self.repo.list_opportunity_subscriptions(payload.userId) if item.id == payload.id), None)
        if not existing:
            existing = next(iter(self.repo.list_opportunity_subscriptions(payload.userId)), None)
        status_value = payload.status if payload.status in {"active", "paused", "deleted"} else "active"
        item = OpportunitySubscription(
            id=existing.id if existing else new_id("opp_sub"),
            ownerUserId=payload.userId,
            direction=(payload.direction or "两边都看").strip() or "两边都看",
            lookingFor=(payload.lookingFor or "").strip(),
            providing=(payload.providing or "").strip(),
            city=(payload.city or "").strip(),
            contactRequirement=(payload.contactRequirement or "有电话").strip() or "有电话",
            keywords=(payload.keywords or "").strip(),
            reminderCadence=(payload.reminderCadence or "每天早上").strip() or "每天早上",
            status=status_value,
            createdAt=existing.createdAt if existing else now,
            updatedAt=now,
        )
        self.repo.save_opportunity_subscription(item)
        return item.model_dump()

    def delete_opportunity_subscription(self, subscription_id: str, owner_user_id: str) -> dict:
        if not self.repo.get_user(owner_user_id):
            raise HTTPException(status_code=404, detail="用户不存在")
        subscription = next((item for item in self.repo.list_opportunity_subscriptions(owner_user_id) if item.id == subscription_id), None)
        if not subscription:
            raise HTTPException(status_code=404, detail="订阅不存在")
        subscription.status = "deleted"
        subscription.updatedAt = now_iso()
        self.repo.save_opportunity_subscription(subscription)
        return subscription.model_dump()

    def add_opportunity_followup(self, lead_id: str, user_id: str, action_type: str, note: str | None = None) -> dict:
        if not self.repo.get_user(user_id):
            raise HTTPException(status_code=404, detail="用户不存在")
        lead = self.repo.get_opportunity_lead(lead_id)
        if not lead:
            raise HTTPException(status_code=404, detail="商机线索不存在")
        now = now_iso()
        followup = OpportunityLeadFollowup(
            id=new_id("opp_follow"),
            leadId=lead_id,
            userId=user_id,
            actionType=(action_type or "note").strip() or "note",
            note=note,
            createdAt=now,
        )
        self.repo.save_opportunity_lead_followup(followup)
        existing = self.repo.get_opportunity_lead_save(lead_id, user_id)
        if existing:
            existing.status = "contacted" if followup.actionType == "contacted" else "following"
            existing.updatedAt = now
            self.repo.save_opportunity_lead_save(existing)
        return {"followup": followup.model_dump(), "save": existing.model_dump() if existing else None}

    def unlock_opportunity_contact(self, lead_id: str, user_id: str) -> dict:
        if not self.repo.get_user(user_id):
            raise HTTPException(status_code=404, detail="用户不存在")
        lead = self.repo.get_opportunity_lead(lead_id)
        if not lead or lead.status != "published":
            raise HTTPException(status_code=404, detail="商机线索不存在")
        contacts = self.repo.list_opportunity_lead_contacts(lead_id)
        if not contacts:
            raise HTTPException(status_code=404, detail="该线索暂无联系方式")
        consume = self.consume_resource_points(
            owner_user_id=user_id,
            action_type="opportunity_contact_unlock",
            target_type="opportunity_lead",
            target_id=lead_id,
            points_cost=OPPORTUNITY_CONTACT_UNLOCK_COST_POINTS,
            reason="查看商机联系方式",
            metadata={"leadTitle": lead.title},
        )
        followup = self.add_opportunity_followup(
            lead_id=lead_id,
            user_id=user_id,
            action_type="contact_unlocked",
            note="已查看联系方式",
        )
        return {
            "lead": self._opportunity_lead_public_payload(lead, detail=True),
            "contacts": [
                {
                    "contactType": item.contactType,
                    "contactValue": item.contactValueEncrypted,
                    "contactMasked": item.contactMasked,
                    "verifyStatus": item.verifyStatus,
                }
                for item in contacts
            ],
            "wallet": consume["wallet"],
            "charged": consume["charged"],
            "duplicate": consume["duplicate"],
            "followup": followup.get("followup"),
        }

    def preview_response_package(
        self,
        lead_id: str,
        owner_user_id: str,
        selected_asset_ids: list[str] | None = None,
    ) -> dict:
        if not self.repo.get_user(owner_user_id):
            raise HTTPException(status_code=404, detail="用户不存在")
        lead = self.repo.get_opportunity_lead(lead_id)
        if not lead or lead.status != "published" or self._opportunity_lead_expired(lead):
            raise HTTPException(status_code=404, detail="商机线索不存在")
        existing = self.repo.get_response_package_for_lead_user(lead_id, owner_user_id)
        preview = self._build_response_package_preview(lead, owner_user_id, selected_asset_ids=selected_asset_ids)
        preview["existingPackageId"] = existing.id if existing else None
        preview["costPoints"] = 0 if existing else RESPONSE_PACKAGE_COST_POINTS
        preview["freeQuotaHint"] = "每月前 3 次生成回应包免费，之后每次 20 积分。"
        return preview

    def create_response_package(
        self,
        lead_id: str,
        owner_user_id: str,
        selected_asset_ids: list[str] | None = None,
    ) -> dict:
        if not self.repo.get_user(owner_user_id):
            raise HTTPException(status_code=404, detail="用户不存在")
        lead = self.repo.get_opportunity_lead(lead_id)
        if not lead or lead.status != "published" or self._opportunity_lead_expired(lead):
            raise HTTPException(status_code=404, detail="商机线索不存在")
        existing = self.repo.get_response_package_for_lead_user(lead_id, owner_user_id)
        if existing:
            return self._build_response_package_payload(existing)

        period_key = datetime.now(tz=SHANGHAI).strftime("%Y-%m")
        consume_result = self.consume_resource_points(
            owner_user_id=owner_user_id,
            action_type="response_package_generate",
            target_type="opportunity_lead",
            target_id=lead_id,
            points_cost=RESPONSE_PACKAGE_COST_POINTS,
            reason="生成商机回应包",
            quota_type="response_package_monthly",
            free_quota_limit=RESPONSE_PACKAGE_FREE_QUOTA_LIMIT,
            period_key=period_key,
            metadata={"leadTitle": lead.title},
        )
        preview = self._build_response_package_preview(lead, owner_user_id, selected_asset_ids=selected_asset_ids)
        now = now_iso()
        package = ResponsePackage(
            id=new_id("resp_pkg"),
            ownerUserId=owner_user_id,
            leadId=lead_id,
            status="ready",
            title=f"{lead.title} · 回应包",
            demandSummary=preview["demandSummary"],
            openingText=preview["openingText"],
            trackingUrl="",
            followupSuggestion=preview["followupSuggestion"],
            costPoints=0 if consume_result.get("usedFreeQuota") else RESPONSE_PACKAGE_COST_POINTS,
            usedFreeQuota=bool(consume_result.get("usedFreeQuota")),
            createdAt=now,
            updatedAt=now,
        )
        package.trackingUrl = self._response_tracking_url(package.id)
        self.repo.save_response_package(package)
        for index, asset in enumerate(preview["recommendedAssets"]):
            item = ResponsePackageItem(
                id=new_id("resp_item"),
                responsePackageId=package.id,
                assetType=asset["assetType"],
                assetId=asset["assetId"],
                assetTitle=asset["assetTitle"],
                assetSummary=asset.get("assetSummary"),
                recommendReason=asset.get("recommendReason"),
                sortOrder=index + 1,
                createdAt=now,
            )
            self.repo.save_response_package_item(item)
        self.save_opportunity_lead_for_user(
            lead_id=lead_id,
            user_id=owner_user_id,
            save_status="following",
            note="已生成回应包",
        )
        self.add_opportunity_followup(
            lead_id=lead_id,
            user_id=owner_user_id,
            action_type="response_package_generated",
            note=f"已生成回应包：{package.title}",
        )
        return self._build_response_package_payload(package)

    def get_response_package(self, package_id: str, owner_user_id: str | None = None) -> dict:
        package = self.repo.get_response_package(package_id)
        if not package:
            raise HTTPException(status_code=404, detail="回应包不存在")
        if owner_user_id and package.ownerUserId != owner_user_id:
            raise HTTPException(status_code=403, detail="无权查看该回应包")
        return self._build_response_package_payload(package)

    def record_response_package_event(
        self,
        package_id: str,
        event_type: str,
        viewer_id: str | None = None,
        anonymous_id: str | None = None,
        metadata: dict | None = None,
    ) -> dict:
        package = self.repo.get_response_package(package_id)
        if not package:
            raise HTTPException(status_code=404, detail="回应包不存在")
        now = now_iso()
        event = ResponsePackageEvent(
            id=new_id("resp_evt"),
            responsePackageId=package_id,
            eventType=(event_type or "view").strip() or "view",
            viewerId=viewer_id,
            anonymousId=anonymous_id,
            metadata=metadata or {},
            createdAt=now,
        )
        self.repo.save_response_package_event(event)
        if event.eventType == "view":
            package.lastViewedAt = now
            package.updatedAt = now
            self.repo.save_response_package(package)
        return {"event": event.model_dump(), "package": self._build_response_package_payload(package)}

    def get_response_package_radar(self, package_id: str, owner_user_id: str) -> dict:
        package = self.repo.get_response_package(package_id)
        if not package:
            raise HTTPException(status_code=404, detail="回应包不存在")
        if package.ownerUserId != owner_user_id:
            raise HTTPException(status_code=403, detail="无权查看该回应包")
        state = self.repo.load()
        events = [item for item in state.response_package_events if item.responsePackageId == package_id]
        event_counts = defaultdict(int)
        latest_event_at = None
        for event in events:
            event_counts[event.eventType] += 1
            if not latest_event_at or event.createdAt > latest_event_at:
                latest_event_at = event.createdAt
        opened = event_counts["view"] > 0 or bool(package.lastViewedAt)
        suggestion = "对方已打开资料，可以优先电话或微信跟进。" if opened else "先复制回应内容发给对方，稍后再看是否打开。"
        return {
            "package": self._build_response_package_payload(package),
            "opened": opened,
            "lastOpenedAt": package.lastViewedAt,
            "latestEventAt": latest_event_at,
            "eventCounts": dict(event_counts),
            "events": [item.model_dump() for item in sorted(events, key=lambda row: row.createdAt, reverse=True)[:50]],
            "nextSuggestion": suggestion,
        }

    def list_supply_demand_cards_public(
        self,
        keyword: str | None = None,
        city: str | None = None,
        industry: str | None = None,
        demand_type: str | None = None,
        card_type: str | None = None,
        contact_status: str | None = None,
    ) -> list[dict]:
        return [
            self._supply_demand_card_payload(item)
            for item in self.repo.list_supply_demand_cards(statuses={"published"}, keyword=keyword)
            if self._supply_demand_card_matches_filters(item, city, industry, demand_type, card_type, contact_status)
        ]

    def list_my_supply_demand_cards(self, owner_user_id: str) -> list[dict]:
        if not self.repo.get_user(owner_user_id):
            raise HTTPException(status_code=404, detail="用户不存在")
        return [self._supply_demand_card_payload(item, viewer_user_id=owner_user_id, include_applications=True) for item in self.repo.list_supply_demand_cards(owner_user_id=owner_user_id)]

    def get_supply_demand_card_detail(self, card_id: str, viewer_user_id: str | None = None) -> dict:
        card = self.repo.get_supply_demand_card(card_id)
        if not card:
            raise HTTPException(status_code=404, detail="供需卡不存在")
        if card.status != "published" and card.ownerUserId != viewer_user_id:
            raise HTTPException(status_code=404, detail="供需卡不存在")
        return self._supply_demand_card_payload(card, viewer_user_id=viewer_user_id, include_detail=True)

    def apply_supply_demand_card(self, card_id: str, applicant_user_id: str, message: str | None = None) -> dict:
        applicant = self.repo.get_user(applicant_user_id)
        if not applicant:
            raise HTTPException(status_code=404, detail="用户不存在")
        card = self.repo.get_supply_demand_card(card_id)
        if not card or card.status != "published":
            raise HTTPException(status_code=404, detail="供需卡不存在")
        if card.ownerUserId == applicant_user_id:
            raise HTTPException(status_code=400, detail="不能申请自己的供需卡")
        now = now_iso()
        existing = next(
            (
                item
                for item in self.repo.list_supply_demand_applications(card_id=card_id, applicant_user_id=applicant_user_id)
                if item.status in {"pending", "accepted"}
            ),
            None,
        )
        application = SupplyDemandApplication(
            id=existing.id if existing else new_id("sd_apply"),
            cardId=card_id,
            applicantUserId=applicant_user_id,
            ownerUserId=card.ownerUserId,
            status=existing.status if existing else "pending",
            message=(message or "").strip() or "我想进一步沟通这个合作机会。",
            contactSnapshot={
                "nickname": applicant.nickname,
                "phone": applicant.phone,
                "wechat": applicant.wechat,
            },
            createdAt=existing.createdAt if existing else now,
            updatedAt=now,
        )
        self.repo.save_supply_demand_application(application)
        return {
            "application": application.model_dump(),
            "card": self._supply_demand_card_payload(card, viewer_user_id=applicant_user_id),
            "duplicate": bool(existing),
        }

    def list_supply_demand_applications_for_user(self, owner_user_id: str, role: str = "owner") -> list[dict]:
        if not self.repo.get_user(owner_user_id):
            raise HTTPException(status_code=404, detail="用户不存在")
        if role == "applicant":
            applications = self.repo.list_supply_demand_applications(applicant_user_id=owner_user_id)
        else:
            applications = self.repo.list_supply_demand_applications(owner_user_id=owner_user_id)
        rows = []
        for application in applications:
            card = self.repo.get_supply_demand_card(application.cardId)
            applicant = self.repo.get_user(application.applicantUserId)
            rows.append(
                {
                    "application": application.model_dump(),
                    "card": self._supply_demand_card_payload(card, viewer_user_id=owner_user_id) if card else None,
                    "applicant": {
                        "id": applicant.id,
                        "nickname": applicant.nickname,
                        "avatarUrl": applicant.avatarUrl,
                    } if applicant else None,
                }
            )
        return rows

    def review_supply_demand_application(self, application_id: str, owner_user_id: str, status_value: str) -> dict:
        application = self.repo.get_supply_demand_application(application_id)
        if not application:
            raise HTTPException(status_code=404, detail="申请不存在")
        if application.ownerUserId != owner_user_id:
            raise HTTPException(status_code=403, detail="无权处理该申请")
        if status_value not in {"accepted", "rejected", "closed"}:
            raise HTTPException(status_code=400, detail="申请状态不合法")
        application.status = status_value
        application.updatedAt = now_iso()
        self.repo.save_supply_demand_application(application)
        return {"application": application.model_dump()}

    def list_opportunity_push_digests(self, owner_user_id: str) -> list[dict]:
        if not self.repo.get_user(owner_user_id):
            raise HTTPException(status_code=404, detail="用户不存在")
        return [self._opportunity_push_digest_payload(item) for item in self.repo.list_opportunity_push_digests(owner_user_id)]

    def generate_opportunity_push_digest(self, owner_user_id: str) -> dict:
        if not self.repo.get_user(owner_user_id):
            raise HTTPException(status_code=404, detail="用户不存在")
        recommendations = self.list_opportunity_leads_for_user(owner_user_id)
        lead_ids = [item["id"] for item in recommendations.get("items", [])[:5]]
        supply_cards = self.list_supply_demand_cards_public(city=(recommendations.get("subscription") or {}).get("city") or None)[:5]
        supply_ids = [item["id"] for item in supply_cards]
        subscription = recommendations.get("subscription") or {}
        now = now_iso()
        digest = OpportunityPushDigest(
            id=new_id("opp_push"),
            ownerUserId=owner_user_id,
            subscriptionId=subscription.get("id"),
            title="今日推荐机会",
            summary=f"为你找到 {len(lead_ids)} 条商机线索、{len(supply_ids)} 条供需广场内容。",
            status="pending",
            recommendedLeadIds=lead_ids,
            recommendedSupplyDemandCardIds=supply_ids,
            createdAt=now,
            updatedAt=now,
        )
        self.repo.save_opportunity_push_digest(digest)
        return self._opportunity_push_digest_payload(digest)

    def generate_opportunity_push_digests_for_active_subscriptions(self) -> dict:
        state = self.repo.load()
        owner_ids = sorted({item.ownerUserId for item in state.opportunity_subscriptions if item.status == "active"})
        rows = []
        failed = []
        for owner_id in owner_ids:
            try:
                rows.append(self.generate_opportunity_push_digest(owner_id))
            except Exception as exc:  # noqa: BLE001 - ops endpoint should report per-user failures
                failed.append({"ownerUserId": owner_id, "error": str(exc)})
        return {"items": rows, "total": len(rows), "failed": failed}

    def mark_opportunity_push_digest_read(self, digest_id: str, owner_user_id: str) -> dict:
        digest = self.repo.get_opportunity_push_digest(digest_id)
        if not digest:
            raise HTTPException(status_code=404, detail="推荐摘要不存在")
        if digest.ownerUserId != owner_user_id:
            raise HTTPException(status_code=403, detail="无权操作该摘要")
        digest.status = "read"
        digest.readAt = now_iso()
        digest.updatedAt = digest.readAt
        self.repo.save_opportunity_push_digest(digest)
        return self._opportunity_push_digest_payload(digest)

    def upsert_supply_demand_card(self, payload) -> dict:
        if not self.repo.get_user(payload.userId):
            raise HTTPException(status_code=404, detail="用户不存在")
        title = (payload.title or "").strip()
        if not title:
            raise HTTPException(status_code=400, detail="标题不能为空")
        now = now_iso()
        existing = self.repo.get_supply_demand_card(payload.id) if payload.id else None
        if existing and existing.ownerUserId != payload.userId:
            raise HTTPException(status_code=403, detail="无权编辑该发布")
        status_value = payload.status if payload.status in {"draft", "pending_review", "published", "rejected", "archived"} else "draft"
        if status_value == "published":
            status_value = "pending_review"
        card = SupplyDemandCard(
            id=existing.id if existing else new_id("sd"),
            ownerUserId=payload.userId,
            cardType=payload.cardType if payload.cardType in {"demand", "supply"} else "supply",
            status=status_value,
            title=title,
            summary=(payload.summary or "").strip(),
            city=(payload.city or "").strip() or None,
            industry=(payload.industry or "").strip() or None,
            demandType=(payload.demandType or "合作").strip() or "合作",
            contactRequirement=(payload.contactRequirement or "").strip() or None,
            linkedNoteId=(payload.linkedNoteId or "").strip() or None,
            linkedResourceType=(payload.linkedResourceType or "").strip() or None,
            linkedResourceId=(payload.linkedResourceId or "").strip() or None,
            tags=[str(item).strip() for item in (payload.tags or []) if str(item).strip()][:12],
            reviewNote=existing.reviewNote if existing else None,
            publishedAt=existing.publishedAt if existing else None,
            reviewedAt=existing.reviewedAt if existing else None,
            createdAt=existing.createdAt if existing else now,
            updatedAt=now,
        )
        self.repo.save_supply_demand_card(card)
        return self._supply_demand_card_payload(card)

    def submit_supply_demand_card(self, card_id: str, owner_user_id: str) -> dict:
        card = self.repo.get_supply_demand_card(card_id)
        if not card:
            raise HTTPException(status_code=404, detail="发布不存在")
        if card.ownerUserId != owner_user_id:
            raise HTTPException(status_code=403, detail="无权提交该发布")
        card.status = "pending_review"
        card.updatedAt = now_iso()
        self.repo.save_supply_demand_card(card)
        return self._supply_demand_card_payload(card)

    def archive_supply_demand_card(self, card_id: str, owner_user_id: str) -> dict:
        card = self.repo.get_supply_demand_card(card_id)
        if not card:
            raise HTTPException(status_code=404, detail="发布不存在")
        if card.ownerUserId != owner_user_id:
            raise HTTPException(status_code=403, detail="无权下架该发布")
        card.status = "archived"
        card.updatedAt = now_iso()
        self.repo.save_supply_demand_card(card)
        return self._supply_demand_card_payload(card)

    def review_supply_demand_card(self, card_id: str, status_value: str, review_note: str | None = None) -> dict:
        card = self.repo.get_supply_demand_card(card_id)
        if not card:
            raise HTTPException(status_code=404, detail="发布不存在")
        if status_value not in {"published", "rejected", "archived"}:
            raise HTTPException(status_code=400, detail="审核状态不合法")
        now = now_iso()
        card.status = status_value
        card.reviewNote = review_note
        card.reviewedAt = now
        card.updatedAt = now
        if status_value == "published" and not card.publishedAt:
            card.publishedAt = now
        self.repo.save_supply_demand_card(card)
        return self._supply_demand_card_payload(card)

    def _opportunity_lead_public_payload(self, lead: OpportunityLead, detail: bool = False) -> dict:
        contacts = self.repo.list_opportunity_lead_contacts(lead.id)
        payload = {
            **lead.model_dump(),
            "sourceLabel": "官方收录",
            "contactList": [
                {
                    "contactType": item.contactType,
                    "contactMasked": item.contactMasked,
                    "verifyStatus": item.verifyStatus,
                }
                for item in contacts
            ],
            "hasContact": bool(contacts),
        }
        if not detail:
            payload.pop("content", None)
        return payload

    def _opportunity_lead_ops_payload(self, lead: OpportunityLead) -> dict:
        state = self.repo.load()
        return {
            **lead.model_dump(),
            "sources": [item.model_dump() for item in self.repo.list_opportunity_lead_sources(lead.id)],
            "contacts": [item.model_dump() for item in self.repo.list_opportunity_lead_contacts(lead.id)],
            "saveCount": sum(1 for item in state.opportunity_lead_saves if item.leadId == lead.id),
            "responsePackageCount": sum(1 for item in state.response_packages if item.leadId == lead.id),
        }

    def _score_lead_for_subscription(
        self,
        lead: OpportunityLead,
        subscription: OpportunitySubscription | None,
    ) -> tuple[int, list[str]]:
        if not subscription:
            return 70, [item for item in [lead.city, lead.industry, lead.demandType] if item][:3] or ["默认推荐"]
        score = 55
        reasons = []
        lead_text = f"{lead.title} {lead.summary} {lead.content} {lead.city or ''} {lead.industry or ''} {lead.demandType} {' '.join(lead.tags or [])}"
        for label, value, weight in [
            ("城市", subscription.city, 14),
            ("我在找", subscription.lookingFor, 12),
            ("我能提供", subscription.providing, 10),
            ("关键词", subscription.keywords, 12),
        ]:
            tokens = [item.strip() for item in re.split(r"[/,，\s]+", value or "") if item.strip()]
            if any(token and token in lead_text for token in tokens):
                score += weight
                reasons.append(label)
        if subscription.contactRequirement and subscription.contactRequirement != "待核验也看" and lead.contactStatus in {"available", "masked", "locked"}:
            score += 8
            reasons.append("联系方式")
        if lead.trustStatus == "verified":
            score += 6
            reasons.append("可信")
        return min(score, 98), reasons[:5] or ["订阅推荐"]

    def _opportunity_lead_matches_filters(
        self,
        lead: OpportunityLead,
        city: str | None = None,
        industry: str | None = None,
        demand_type: str | None = None,
        contact_status: str | None = None,
    ) -> bool:
        if city and city != "全部" and city not in (lead.city or ""):
            return False
        if industry and industry != "全部" and industry not in (lead.industry or ""):
            return False
        if demand_type and demand_type != "全部" and demand_type not in (lead.demandType or ""):
            return False
        if contact_status and contact_status != "全部":
            has_contact = bool(self.repo.list_opportunity_lead_contacts(lead.id))
            if contact_status in {"有联系方式", "可联系", "有电话"} and not has_contact:
                return False
            if contact_status in {"待核验", "无联系方式"} and has_contact:
                return False
        return True

    def _supply_demand_card_matches_filters(
        self,
        card: SupplyDemandCard,
        city: str | None = None,
        industry: str | None = None,
        demand_type: str | None = None,
        card_type: str | None = None,
        contact_status: str | None = None,
    ) -> bool:
        if city and city != "全部" and city not in (card.city or ""):
            return False
        if industry and industry != "全部" and industry not in (card.industry or ""):
            return False
        if demand_type and demand_type != "全部" and demand_type not in (card.demandType or ""):
            return False
        if card_type and card_type != "全部" and card.cardType != card_type:
            return False
        if contact_status and contact_status != "全部":
            has_contact_hint = bool(card.contactRequirement)
            if contact_status in {"有联系方式", "可联系", "有电话"} and not has_contact_hint:
                return False
            if contact_status in {"待核验", "无联系方式"} and has_contact_hint:
                return False
        return True

    def _opportunity_lead_expired(self, lead: OpportunityLead) -> bool:
        if not lead.expiresAt:
            return False
        try:
            return parse_iso(lead.expiresAt) < datetime.now(tz=SHANGHAI)
        except Exception:
            return False

    def _mask_opportunity_contact(self, value: str) -> str:
        clean = re.sub(r"\s+", "", value or "")
        if re.fullmatch(r"1\d{10}", clean):
            return f"{clean[:3]}****{clean[-4:]}"
        if len(clean) <= 4:
            return clean[:1] + "*"
        return f"{clean[:2]}***{clean[-2:]}"

    def _supply_demand_card_payload(
        self,
        card: SupplyDemandCard,
        viewer_user_id: str | None = None,
        include_detail: bool = False,
        include_applications: bool = False,
    ) -> dict:
        owner = self.repo.get_user(card.ownerUserId)
        note = self.repo.get_user_note(card.linkedNoteId) if card.linkedNoteId else None
        linked_resource_type = card.linkedResourceType or ("note" if card.linkedNoteId else None)
        linked_resource_id = card.linkedResourceId or card.linkedNoteId
        linked_resource_title = None
        if linked_resource_type == "showcase" and linked_resource_id:
            showcase = self.repo.get_showcase_page(linked_resource_id)
            linked_resource_title = showcase.name if showcase else None
        elif linked_resource_type == "note" and linked_resource_id:
            resource_note = self.repo.get_user_note(linked_resource_id)
            linked_resource_title = resource_note.title if resource_note else None
        applications = self.repo.list_supply_demand_applications(card_id=card.id)
        my_application = next((item for item in applications if item.applicantUserId == viewer_user_id), None) if viewer_user_id else None
        payload = {
            **card.model_dump(),
            "ownerNickname": owner.nickname if owner else card.ownerUserId,
            "ownerAvatarUrl": owner.avatarUrl if owner else "",
            "linkedNoteTitle": note.title if note else None,
            "linkedResourceType": linked_resource_type,
            "linkedResourceId": linked_resource_id,
            "linkedResourceTitle": linked_resource_title or (note.title if note else None),
            "badge": "我能提供" if card.cardType == "supply" else "我在找",
            "applicationCount": len(applications),
            "myApplicationStatus": my_application.status if my_application else None,
            "isMine": bool(viewer_user_id and viewer_user_id == card.ownerUserId),
        }
        if include_detail and linked_resource_id:
            linked_resource = None
            if linked_resource_type == "showcase":
                showcase = self.repo.get_showcase_page(linked_resource_id)
                if showcase:
                    linked_resource = {
                        "id": showcase.id,
                        "type": "showcase",
                        "title": showcase.name,
                        "summary": showcase.description,
                    }
            elif linked_resource_type == "note":
                resource_note = self.repo.get_user_note(linked_resource_id)
                if resource_note:
                    linked_resource = {
                        "id": resource_note.id,
                        "type": "note",
                        "title": resource_note.title,
                        "summary": resource_note.summary,
                        "cardType": (resource_note.visibilityConfig or {}).get("cardType") or (resource_note.visibilityConfig or {}).get("noteType"),
                    }
            if linked_resource:
                payload["linkedResource"] = linked_resource
        if include_detail and note:
            payload["linkedNote"] = {
                "id": note.id,
                "title": note.title,
                "summary": note.summary,
                "cardType": (note.visibilityConfig or {}).get("cardType") or (note.visibilityConfig or {}).get("noteType"),
            }
        if include_applications:
            payload["applications"] = [
                {
                    **item.model_dump(),
                    "applicantNickname": (self.repo.get_user(item.applicantUserId).nickname if self.repo.get_user(item.applicantUserId) else item.applicantUserId),
                }
                for item in applications[:20]
            ]
        return payload

    def _opportunity_push_digest_payload(self, digest: OpportunityPushDigest) -> dict:
        leads = [
            self._opportunity_lead_public_payload(lead)
            for lead_id in digest.recommendedLeadIds
            for lead in [self.repo.get_opportunity_lead(lead_id)]
            if lead and lead.status == "published"
        ]
        supply_cards = [
            self._supply_demand_card_payload(card)
            for card_id in digest.recommendedSupplyDemandCardIds
            for card in [self.repo.get_supply_demand_card(card_id)]
            if card and card.status == "published"
        ]
        return {
            **digest.model_dump(),
            "leads": leads,
            "supplyDemandCards": supply_cards,
            "totalCount": len(leads) + len(supply_cards),
        }

    def _build_response_package_preview(
        self,
        lead: OpportunityLead,
        owner_user_id: str,
        selected_asset_ids: list[str] | None = None,
    ) -> dict:
        recommended_assets = self._recommend_response_assets(lead, owner_user_id, selected_asset_ids=selected_asset_ids)
        asset_options = self._response_asset_options(lead, owner_user_id, selected_asset_ids=selected_asset_ids)
        demand_summary = {
            "title": lead.title,
            "summary": lead.summary,
            "city": lead.city,
            "industry": lead.industry,
            "demandType": lead.demandType,
            "tags": lead.tags[:6],
            "contactStatus": lead.contactStatus,
            "trustStatus": lead.trustStatus,
        }
        return {
            "lead": self._opportunity_lead_public_payload(lead, detail=True),
            "demandSummary": demand_summary,
            "recommendedAssets": recommended_assets,
            "assetOptions": asset_options,
            "selectedAssetIds": [item["assetId"] for item in recommended_assets],
            "openingText": self._response_opening_text(lead, recommended_assets),
            "trackingUrl": None,
            "followupSuggestion": self._response_followup_suggestion(lead, recommended_assets),
        }

    def _build_response_package_payload(self, package: ResponsePackage) -> dict:
        lead = self.repo.get_opportunity_lead(package.leadId)
        items = self.repo.list_response_package_items(package.id)
        return {
            **package.model_dump(),
            "lead": self._opportunity_lead_public_payload(lead, detail=True) if lead else None,
            "items": [item.model_dump() for item in items],
        }

    def _recommend_response_assets(
        self,
        lead: OpportunityLead,
        owner_user_id: str,
        selected_asset_ids: list[str] | None = None,
    ) -> list[dict]:
        options = self._response_asset_options(lead, owner_user_id, selected_asset_ids=selected_asset_ids)
        return [item for item in options if item.get("selected")][:3] or options[:3]

    def _response_asset_options(
        self,
        lead: OpportunityLead,
        owner_user_id: str,
        selected_asset_ids: list[str] | None = None,
    ) -> list[dict]:
        selected_ids = {item for item in (selected_asset_ids or []) if item}
        keywords = {
            item
            for item in [
                lead.city,
                lead.district,
                lead.industry,
                lead.demandType,
                *(lead.tags or []),
            ]
            if item
        }
        notes = self.repo.list_user_notes(owner_user_id, include_deleted=False)
        scored: list[tuple[int, UserNote]] = []
        for note in notes:
            if note.status not in {"active", "draft"}:
                continue
            visibility_config = note.visibilityConfig or {}
            note_tags = [
                str(item)
                for item in [
                    *(visibility_config.get("tags") or []),
                    *(visibility_config.get("systemTags") or []),
                    *(visibility_config.get("userTags") or []),
                ]
                if item
            ]
            note_type = visibility_config.get("cardType") or visibility_config.get("noteType") or ""
            haystack = " ".join(
                [
                    note.title or "",
                    note.summary or "",
                    note.body or "",
                    " ".join(note_tags),
                    note_type,
                ]
            )
            score = 30 if not selected_ids else 0
            if note.id in selected_ids:
                score += 100
            for keyword in keywords:
                if keyword and keyword in haystack:
                    score += 18
            if note_type in {"service_offer", "business_card"}:
                score += 10
            if note_type in {"property_listing", "groupbuy_product"} and lead.demandType in {"找货源", "找房源", "找资源"}:
                score += 8
            scored.append((score, note))
        scored.sort(key=lambda item: (item[0], item[1].updatedAt), reverse=True)
        assets = []
        for score, note in scored[:10]:
            if score <= 0 and note.id not in selected_ids:
                continue
            reason = self._response_asset_reason(lead, note)
            assets.append(
                {
                    "assetType": "note",
                    "assetId": note.id,
                    "assetTitle": note.title,
                    "assetSummary": note.summary,
                    "recommendReason": reason,
                    "score": score,
                    "selected": note.id in selected_ids,
                }
            )
        if not selected_ids:
            for index, asset in enumerate(assets):
                asset["selected"] = index < 3
        return assets

    def _response_asset_reason(self, lead: OpportunityLead, note: UserNote) -> str:
        matched = []
        visibility_config = note.visibilityConfig or {}
        note_tags = [
            str(item)
            for item in [
                *(visibility_config.get("tags") or []),
                *(visibility_config.get("systemTags") or []),
                *(visibility_config.get("userTags") or []),
            ]
            if item
        ]
        note_type = visibility_config.get("cardType") or visibility_config.get("noteType") or ""
        haystack = f"{note.title} {note.summary} {' '.join(note_tags)}"
        for keyword in [lead.city, lead.industry, lead.demandType, *(lead.tags or [])]:
            if keyword and keyword in haystack and keyword not in matched:
                matched.append(keyword)
        if matched:
            return f"匹配 {' / '.join(matched[:3])}"
        if note_type in {"service_offer", "business_card"}:
            return "适合作为首次介绍资料"
        return "可作为补充资料发送"

    def _response_opening_text(self, lead: OpportunityLead, assets: list[dict]) -> str:
        asset_text = "，也整理了相关资料给你参考" if assets else "，可以先简单对齐需求"
        city = f"{lead.city}这边" if lead.city else "这边"
        industry = f"{lead.industry}方向" if lead.industry else "这个方向"
        return f"你好，我看到你在找{city}{industry}的合作资源{asset_text}。如果方便，我先发一份简短介绍和案例，你看是否匹配。"

    def _response_followup_suggestion(self, lead: OpportunityLead, assets: list[dict]) -> str:
        if assets:
            return "先发送回应包，30 分钟后根据对方是否打开资料决定电话/微信跟进。"
        if lead.contactStatus in {"masked", "available", "locked"}:
            return "先补一份可发送资料，再查看联系方式跟进。"
        return "先保存线索，等联系方式核验后再生成正式跟进动作。"

    def _response_tracking_url(self, package_id: str) -> str:
        return f"/pages/response-package/index?id={package_id}"

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

    def login_payload(self, user: User) -> dict:
        """Return the public user profile plus a signed API session token."""
        return {**user.model_dump(), **issue_user_session(user.id)}

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
        existing = self.repo.get_user_by_openid(openid)
        nickname = (payload.nickname or "").strip()
        if not nickname or nickname in {"微信用户", "未设置昵称"}:
            nickname = existing.nickname if existing and existing.nickname else "微信用户"
        requested_avatar_url = (payload.avatarUrl or "").strip()
        cleaned_avatar_url = self._clean_user_avatar_url(requested_avatar_url, reject_invalid=False) if requested_avatar_url else ""
        avatar_url = cleaned_avatar_url or (existing.avatarUrl if existing else "")
        phone = payload.phone if payload.phone is not None else (existing.phone if existing else None)
        wechat = payload.wechat if payload.wechat is not None else (existing.wechat if existing else None)
        return self._upsert_user_by_openid(
            openid,
            nickname,
            avatar_url,
            phone,
            session_data.get("unionid"),
            wechat,
        )

    def create_h5_session_ticket(self, user_id: str, entry: str = "resource-tools") -> dict:
        user = self.repo.get_user(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")
        normalized_entry = re.sub(r"[^a-z0-9_-]", "", (entry or "resource-tools").lower()) or "resource-tools"
        now_ts = int(time.time())
        payload = {
            "userId": user.id,
            "openid": user.openid,
            "entry": normalized_entry,
            "iat": now_ts,
            "exp": now_ts + max(60, settings.h5_auth_ticket_ttl_seconds),
            "nonce": uuid4().hex,
        }
        body = self._h5_ticket_encode(payload)
        signature = self._h5_ticket_signature(body)
        return {
            "ticket": f"{body}.{signature}",
            "expiresAt": datetime.fromtimestamp(payload["exp"], tz=SHANGHAI).isoformat(),
            "entry": normalized_entry,
        }

    def verify_h5_session_ticket(self, ticket: str) -> dict:
        body, signature = self._split_h5_ticket(ticket)
        expected_signature = self._h5_ticket_signature(body)
        if not hmac.compare_digest(signature, expected_signature):
            raise HTTPException(status_code=401, detail="H5 登录票据无效")
        try:
            payload = json.loads(base64.urlsafe_b64decode(self._pad_h5_ticket_body(body)).decode("utf-8"))
        except Exception as exc:
            raise HTTPException(status_code=401, detail="H5 登录票据无效") from exc
        exp = int(payload.get("exp") or 0)
        if exp < int(time.time()):
            raise HTTPException(status_code=401, detail="H5 登录票据已过期")
        user = self.repo.get_user(str(payload.get("userId") or ""))
        if not user or user.openid != payload.get("openid"):
            raise HTTPException(status_code=401, detail="H5 登录用户不存在")
        return {
            "user": user.model_dump(),
            "entry": payload.get("entry") or "resource-tools",
            "expiresAt": datetime.fromtimestamp(exp, tz=SHANGHAI).isoformat(),
        }

    @staticmethod
    def _membership_pending_expires_at(order: MembershipOrder):
        return parse_iso(order.createdAt) + timedelta(seconds=MEMBERSHIP_PENDING_ORDER_TTL_SECONDS)

    @classmethod
    def _membership_pending_order_payload(cls, order: MembershipOrder, now) -> dict:
        expires_at = cls._membership_pending_expires_at(order)
        seconds_remaining = max(0, int(ceil((expires_at - now).total_seconds())))
        return {
            **order.model_dump(),
            "expiresAt": expires_at.isoformat(),
            "secondsRemaining": seconds_remaining,
        }

    @classmethod
    def _close_expired_membership_orders(cls, state: AppState, now) -> bool:
        changed = False
        for order in state.membership_orders:
            if order.status != "pending":
                continue
            try:
                expired = cls._membership_pending_expires_at(order) <= now
            except (TypeError, ValueError, OverflowError):
                expired = True
            if expired:
                order.status = "closed"
                order.updatedAt = now.isoformat()
                changed = True
        return changed

    def _close_expired_membership_order(self, state: AppState, order: MembershipOrder, now) -> bool:
        if order.status != "pending":
            return False
        try:
            expired = self._membership_pending_expires_at(order) <= now
        except (TypeError, ValueError, OverflowError):
            expired = True
        if not expired:
            return False
        order.status = "closed"
        order.updatedAt = now.isoformat()
        self._save(state)
        return True

    def get_membership_status(self, user_id: str) -> dict:
        user = self.repo.get_user(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")
        if not self.customer_info_chain_enabled():
            return {
                "featureEnabled": False,
                "paymentRequired": self.customer_info_chain_payment_required(),
                "plan": {
                    "code": SALES_SCRM_PLAN_CODE,
                    "name": "客户信息链会员",
                    "priceFen": SALES_SCRM_MONTHLY_PRICE_FEN,
                    "billingCycle": "month",
                    "benefits": ["客户身份与联系方式", "完整访问轨迹", "客户档案与跟进", "跨资料兴趣与提醒"],
                },
                "active": False,
                "status": "disabled",
                "expiresAt": None,
                "latestOrder": None,
            }
        now = parse_iso(now_iso())
        # The JSON repository is still used by local/dev mode and rewrites one
        # file for mutations. Keep the narrow read under the existing process
        # lock so a status request cannot observe a half-written snapshot.
        with MEMBERSHIP_PAYMENT_LOCK:
            membership_records = self.repo.get_membership_records(user_id)
        raw_orders, raw_entitlements = membership_records
        # Status reads are a hot dependency of the radar summary.  Keep the
        # read narrow and make expired pending orders look closed in this
        # response; mutation endpoints still persist the full state transition
        # under MEMBERSHIP_PAYMENT_LOCK.
        orders = []
        for order in raw_orders:
            if order.status == "pending":
                try:
                    expired = self._membership_pending_expires_at(order) <= now
                except (TypeError, ValueError, OverflowError):
                    expired = True
                if expired:
                    order = order.model_copy(update={"status": "closed", "updatedAt": now.isoformat()})
            orders.append(order)
        entitlements = [
            item for item in raw_entitlements
            if item.userId == user_id and item.entitlementKey == "customer_intelligence"
        ]
        active = [
            item for item in entitlements
            if item.status == "active" and parse_iso(item.expiresAt) > now
        ]
        latest = max(active or entitlements, key=lambda item: item.expiresAt, default=None)
        orders = sorted(
            orders,
            key=lambda item: item.createdAt,
            reverse=True,
        )
        pending_order = next((item for item in orders if item.status == "pending"), None)
        return {
            "featureEnabled": True,
            "paymentRequired": self.customer_info_chain_payment_required(),
            "plan": {
                "code": SALES_SCRM_PLAN_CODE,
                "name": "客户信息链会员",
                "priceFen": SALES_SCRM_MONTHLY_PRICE_FEN,
                "billingCycle": "month",
                "benefits": ["客户身份与联系方式", "完整访问轨迹", "客户档案与跟进", "跨资料兴趣与提醒"],
            },
            "active": bool(active),
            "status": "active" if active else "expired" if latest else "free",
            "expiresAt": max((item.expiresAt for item in active), default=latest.expiresAt if latest else None),
            "latestOrder": orders[0].model_dump() if orders else None,
            "pendingOrder": self._membership_pending_order_payload(pending_order, now) if pending_order else None,
        }

    def _has_customer_intelligence(self, user_id: str) -> bool:
        return self.customer_info_chain_enabled() and (
            not self.customer_info_chain_payment_required() or self._has_active_customer_entitlement(user_id)
        )

    def _is_paid_customer_member(self, user_id: str) -> bool:
        return self.customer_info_chain_enabled() and self.customer_info_chain_payment_required() and self._has_active_customer_entitlement(user_id)

    def _has_active_customer_entitlement(self, user_id: str) -> bool:
        now = parse_iso(now_iso())
        state = self._load()
        return any(
            item.userId == user_id
            and item.entitlementKey == "customer_intelligence"
            and item.status == "active"
            and parse_iso(item.expiresAt) > now
            for item in state.membership_entitlements
        )

    @staticmethod
    def _mutual_help_notification_config() -> dict:
        template_id = settings.wechat_miniapp_mutual_help_subscribe_template_id
        field_keys = settings.wechat_miniapp_mutual_help_subscribe_field_keys()
        return {
            "enabled": bool(template_id and field_keys),
            "templateId": template_id,
            "page": settings.wechat_miniapp_mutual_help_subscribe_page,
        }

    def get_notification_config(self, user_id: str) -> dict:
        if not self.repo.get_user(user_id):
            raise HTTPException(status_code=404, detail="用户不存在")
        mutual_help_config = self._mutual_help_notification_config()
        if not self.customer_info_chain_enabled():
            return {
                "enabled": False,
                "featureEnabled": False,
                "templateId": settings.wechat_miniapp_subscribe_template_id,
                "page": settings.wechat_miniapp_subscribe_page,
                "mutualHelp": mutual_help_config,
                "member": False,
                "preferences": {
                    "importantCustomerViewEnabled": False,
                    "ordinaryAnonymousViewEnabled": False,
                    "isDefault": True,
                },
            }
        member = self._is_paid_customer_member(user_id)
        preference = self.repo.get_notification_preference(user_id)
        return {
            "enabled": bool(settings.wechat_miniapp_subscribe_template_id and settings.wechat_miniapp_subscribe_field_keys()),
            "featureEnabled": True,
            "templateId": settings.wechat_miniapp_subscribe_template_id,
            "page": settings.wechat_miniapp_subscribe_page,
            "mutualHelp": mutual_help_config,
            "member": member,
            "preferences": self._notification_preference_payload(preference, member),
        }

    def _notification_preference_payload(self, preference: NotificationPreference | None, member: bool) -> dict:
        return {
            "importantCustomerViewEnabled": preference.importantCustomerViewEnabled if preference else True,
            # An authorized owner has opted into subscription messages; keep
            # anonymous view alerts enabled by default for members as well.
            # An explicit preference still wins and can disable this channel.
            "ordinaryAnonymousViewEnabled": preference.ordinaryAnonymousViewEnabled if preference else True,
            "isDefault": preference is None,
        }

    def update_notification_preferences(self, user_id: str, important_enabled: bool, ordinary_enabled: bool) -> dict:
        if not self.repo.get_user(user_id):
            raise HTTPException(status_code=404, detail="用户不存在")
        self.require_customer_info_chain_enabled()
        now = now_iso()
        preference = self.repo.get_notification_preference(user_id)
        if not preference:
            preference = NotificationPreference(
                id=new_id("notification_preference"),
                userId=user_id,
                importantCustomerViewEnabled=bool(important_enabled),
                ordinaryAnonymousViewEnabled=bool(ordinary_enabled),
                createdAt=now,
                updatedAt=now,
            )
        else:
            preference.importantCustomerViewEnabled = bool(important_enabled)
            preference.ordinaryAnonymousViewEnabled = bool(ordinary_enabled)
            preference.updatedAt = now
        self.repo.save_notification_preference(preference)
        return self._notification_preference_payload(preference, self._is_paid_customer_member(user_id))

    def record_notification_subscription(
        self,
        user_id: str,
        template_id: str,
        status_value: str,
        source: str,
        request_id: str | None = None,
        purpose: str = "customer",
    ) -> dict:
        if not self.repo.get_user(user_id):
            raise HTTPException(status_code=404, detail="用户不存在")
        normalized_purpose = str(purpose or "customer").strip() or "customer"
        if normalized_purpose == "customer":
            self.require_customer_info_chain_enabled()
            expected_template_id = settings.wechat_miniapp_subscribe_template_id
            field_keys = settings.wechat_miniapp_subscribe_field_keys()
        elif normalized_purpose == "mutual_help_task":
            expected_template_id = settings.wechat_miniapp_mutual_help_subscribe_template_id
            field_keys = settings.wechat_miniapp_mutual_help_subscribe_field_keys()
        else:
            raise HTTPException(status_code=400, detail="订阅消息用途无效")
        if not expected_template_id or not field_keys:
            raise HTTPException(status_code=400, detail="订阅模板未配置")
        if template_id != expected_template_id:
            raise HTTPException(status_code=400, detail="订阅模板不匹配")
        normalized_status = str(status_value or "").strip()
        if normalized_status not in SUBSCRIBE_ACCEPT_STATUSES and normalized_status not in {"reject", "ban"}:
            raise HTTPException(status_code=400, detail="订阅授权状态无效")
        clean_request_id = self._clean_optional_text(request_id)
        if clean_request_id:
            existing = next(
                (
                    item for item in self.repo.list_wechat_subscription_grants(user_id, expected_template_id)
                    if item.requestId == clean_request_id
                ),
                None,
            )
            if existing:
                return {"recorded": False, "duplicate": True, "grant": existing.model_dump()}
        if normalized_status not in SUBSCRIBE_ACCEPT_STATUSES:
            return {"recorded": True, "accepted": False, "status": normalized_status}
        now = now_iso()
        grant_id = (
            f"wechat_subscription_grant_{hashlib.sha256(f'{user_id}:{expected_template_id}:{clean_request_id}'.encode('utf-8')).hexdigest()[:32]}"
            if clean_request_id
            else new_id("wechat_subscription_grant")
        )
        if clean_request_id:
            existing_by_id = self.repo.get_wechat_subscription_grant(grant_id)
            if existing_by_id:
                return {"recorded": False, "duplicate": True, "grant": existing_by_id.model_dump()}
        grant = WechatSubscriptionGrant(
            id=grant_id,
            userId=user_id,
            templateId=expected_template_id,
            requestId=clean_request_id or new_id("subscription_request"),
            status="available",
            source=self._clean_optional_text(source) or "share",
            authorizedAt=now,
            createdAt=now,
            updatedAt=now,
        )
        self.repo.save_wechat_subscription_grant(grant)
        return {"recorded": True, "accepted": True, "grant": grant.model_dump()}

    def _important_customer_view(self, owner_user_id: str, resource_id: str, viewer_user_id: str | None, note_id: str | None = None, showcase_id: str | None = None) -> bool:
        viewer_id = self._clean_optional_text(viewer_user_id)
        viewer = self.repo.get_user(viewer_id) if viewer_id else None
        if not viewer or viewer.id == owner_user_id:
            return False
        lead_card_id = resource_id
        lead = self.repo.get_lead_reminder_by_card_viewer(lead_card_id, viewer.id)
        if lead and lead.status not in LEAD_CLOSED_STATUSES:
            return True
        if note_id:
            actions = self.repo.list_customer_actions_for_note(note_id, viewer_user_id=viewer.id)
            if any(item.actionKey in OPPORTUNITY_HIGH_ACTIONS for item in actions):
                return True
        if showcase_id:
            events = self.repo.list_showcase_events(showcase_id)
            if sum(1 for item in events if item.eventType == "view" and item.viewerUserId == viewer.id) >= 2:
                return True
        events = self.repo.list_view_events_for_card(resource_id)
        return sum(1 for item in events if item.viewerUserId == viewer.id and item.viewType != "share") >= 2

    def _subscription_event_viewer(self, owner_user_id: str, viewer_user_id: str | None, anonymous_id: str | None) -> tuple[str, str, str]:
        viewer = self.repo.get_user(self._clean_optional_text(viewer_user_id)) if viewer_user_id else None
        if viewer and viewer.id != owner_user_id:
            return viewer.id, "known", (viewer.nickname or "微信客户")[:20]
        if self._clean_optional_text(anonymous_id):
            return self._clean_optional_text(anonymous_id) or "anonymous", "anonymous", "匿名访客"
        return "anonymous", "anonymous", "匿名访客"

    def recover_stale_subscription_grants(self) -> int:
        now = now_iso()
        cutoff = (parse_iso(now) - timedelta(seconds=SUBSCRIBE_RESERVATION_TIMEOUT_SECONDS)).isoformat()
        return self.repo.release_stale_wechat_subscription_grants(cutoff, now)

    def queue_note_view_notification(self, note_id: str, event: ViewEvent, queue: SyncTaskQueue) -> dict:
        note = self.repo.get_user_note(note_id)
        if not note or event.id.startswith("view_ignored") or event.viewType == "share":
            return {"queued": False, "reason": "not_a_customer_view"}
        return self._queue_view_notification(
            queue=queue,
            owner_user_id=note.ownerUserId,
            resource_type="note",
            resource_id=note.id,
            resource_title=note.title,
            note_id=note.id,
            card_id=event.cardId,
            event_at=event.viewedAt,
            viewer_user_id=event.viewerUserId,
            anonymous_id=event.anonymousId,
        )

    def queue_card_view_notification(self, card_id: str, event: ViewEvent, queue: SyncTaskQueue) -> dict:
        card = self.repo.get_card(card_id)
        if not card or event.id.startswith("view_ignored") or event.viewType == "share":
            return {"queued": False, "reason": "not_a_customer_view"}
        return self._queue_view_notification(
            queue=queue,
            owner_user_id=card.ownerUserId,
            resource_type="card",
            resource_id=card.id,
            resource_title=card.title,
            card_id=event.cardId,
            event_at=event.viewedAt,
            viewer_user_id=event.viewerUserId,
            anonymous_id=event.anonymousId,
        )

    def queue_showcase_view_notification(self, showcase_id: str, event: ShowcaseEvent, queue: SyncTaskQueue) -> dict:
        showcase = self.repo.get_showcase_page(showcase_id)
        if not showcase or event.eventType != "view" or event.viewType == "share":
            return {"queued": False, "reason": "not_a_customer_view"}
        return self._queue_view_notification(
            queue=queue,
            owner_user_id=showcase.ownerUserId,
            resource_type="showcase",
            resource_id=showcase.id,
            resource_title=showcase.shareTitle or showcase.name,
            note_id=event.noteId,
            showcase_id=showcase.id,
            event_at=event.createdAt,
            viewer_user_id=event.viewerUserId,
            anonymous_id=event.anonymousId,
        )

    def _subscription_template_data(
        self,
        *,
        message_name: str,
        customer_name: str,
        resource_title: str,
        message_content: str,
        event_at: str,
    ) -> tuple[dict, dict]:
        field_keys = settings.wechat_miniapp_subscribe_field_keys()
        safe_message_content = self._safe_subscription_message_content(message_content)
        data_values = {
            "messageName": message_name,
            "customerName": customer_name,
            "projectName": resource_title or "资料",
            "messageContent": safe_message_content,
            "reminderTime": datetime.fromisoformat(event_at.replace("Z", "+00:00")).astimezone(SHANGHAI).strftime("%Y-%m-%d %H:%M"),
        }
        data = {
            field_keys[name]: {"value": str(data_values[name])[:20]}
            for name in SUBSCRIBE_FIELD_NAMES
            if field_keys.get(name)
        }
        return data_values, data

    @staticmethod
    def _safe_subscription_message_content(value: str) -> str:
        """Keep subscription previews useful without broadcasting contact details."""
        text = strip_unicode_surrogates(str(value or ""))
        text = re.sub(r"\s+", " ", text).strip()
        text = re.sub(r"(?<!\d)1[3-9]\d{9}(?!\d)", "手机号", text)
        text = re.sub(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b", "邮箱", text)
        text = re.sub(
            r"(?i)(微信号|微信|wx|vx|v信)\s*[:：]?\s*[A-Za-z0-9_-]{3,}",
            r"\1",
            text,
        )
        return text[:80]

    def _release_queued_view_notifications_for_message(
        self,
        owner_user_id: str,
        now: str,
    ) -> WechatSubscriptionDelivery | None:
        # One message needs at most one grant. Preserve other queued view
        # notifications instead of cancelling the owner's whole pending queue.
        for delivery in self.repo.list_wechat_subscription_deliveries(owner_user_id, limit=100):
            if delivery.notificationType != "view" or delivery.status != "queued":
                continue
            grant = self.repo.get_wechat_subscription_grant(delivery.grantId)
            if not grant or grant.status != "reserved":
                continue
            delivery.status = "skipped"
            delivery.lastError = "superseded_by_customer_message"
            delivery.updatedAt = now
            self.repo.save_wechat_subscription_delivery(delivery)
            grant.status = "available"
            grant.reservedAt = None
            grant.updatedAt = now
            self.repo.save_wechat_subscription_grant(grant)
            return delivery
        return None

    def _restore_view_notification_after_message_failure(
        self,
        delivery: WechatSubscriptionDelivery | None,
    ) -> None:
        if not delivery:
            return
        now = now_iso()
        grant = self.repo.get_wechat_subscription_grant(delivery.grantId)
        if not grant or grant.status != "available":
            return
        grant.status = "reserved"
        grant.reservedAt = now
        grant.updatedAt = now
        self.repo.save_wechat_subscription_grant(grant)
        delivery.status = "queued"
        delivery.lastError = None
        delivery.updatedAt = now
        self.repo.save_wechat_subscription_delivery(delivery)

    def queue_message_notification(self, thread_id: str, message_id: str, queue: SyncTaskQueue) -> dict:
        self.recover_stale_subscription_grants()
        thread = self.repo.get_message_thread(thread_id)
        if not thread or thread.status != "active":
            return {"queued": False, "reason": "thread_not_found"}
        message = next(
            (item for item in self.repo.list_message_records_for_thread(thread.id) if item.id == message_id),
            None,
        )
        if not message or message.senderUserId != thread.buyerUserId or message.senderUserId == thread.ownerUserId:
            return {"queued": False, "reason": "not_a_customer_message"}
        if not self.customer_info_chain_enabled():
            return {"queued": False, "reason": "customer_info_chain_disabled"}
        template_id = settings.wechat_miniapp_subscribe_template_id
        if not template_id or not settings.wechat_miniapp_subscribe_field_keys():
            return {"queued": False, "reason": "template_not_configured"}
        member = self._is_paid_customer_member(thread.ownerUserId)
        preference = self.repo.get_notification_preference(thread.ownerUserId)
        preference_payload = self._notification_preference_payload(preference, member)
        if not preference_payload["importantCustomerViewEnabled"]:
            return {"queued": False, "reason": "important_disabled"}
        try:
            bucket = int(parse_iso(message.createdAt).timestamp() // SUBSCRIBE_DEDUPE_WINDOW_SECONDS)
        except (TypeError, ValueError, OverflowError):
            bucket = int(time.time() // SUBSCRIBE_DEDUPE_WINDOW_SECONDS)
        dedupe_key = f"message:{thread.ownerUserId}:{thread.id}:{bucket}"
        existing_delivery = self.repo.find_wechat_subscription_delivery_by_dedupe_key(dedupe_key)
        if existing_delivery and not (
            existing_delivery.status == "failed" and existing_delivery.lastError == "queue_unavailable"
        ):
            return {"queued": False, "reason": "duplicate"}
        now = now_iso()
        released_view_delivery = self._release_queued_view_notifications_for_message(thread.ownerUserId, now)
        grant = self.repo.reserve_wechat_subscription_grant(thread.ownerUserId, template_id, now)
        if not grant:
            self._restore_view_notification_after_message_failure(released_view_delivery)
            return {"queued": False, "reason": "no_subscription_quota"}
        buyer = self.repo.get_user(thread.buyerUserId)
        note = self.repo.get_user_note(thread.noteId)
        customer_name = (buyer.nickname if buyer else "微信客户")[:20]
        resource_title = (note.title if note else thread.title) or "资料"
        data_values, data = self._subscription_template_data(
            message_name="客户留言提醒",
            customer_name=customer_name,
            resource_title=resource_title,
            message_content=f"客户留言：{message.content}",
            event_at=message.createdAt,
        )
        if len(data) != len(SUBSCRIBE_FIELD_NAMES):
            grant.status = "available"
            grant.reservedAt = None
            grant.updatedAt = now
            self.repo.save_wechat_subscription_grant(grant)
            self._restore_view_notification_after_message_failure(released_view_delivery)
            return {"queued": False, "reason": "template_fields_incomplete"}
        delivery = WechatSubscriptionDelivery(
            id=new_id("wechat_subscription_delivery"),
            ownerUserId=thread.ownerUserId,
            grantId=grant.id,
            templateId=template_id,
            notificationType="message",
            resourceType="note",
            resourceId=thread.noteId,
            resourceTitle=resource_title[:80],
            viewerType="important",
            viewerLabel=customer_name,
            messageContent=data_values["messageContent"][:80],
            threadId=thread.id,
            messageId=message.id,
            eventAt=message.createdAt,
            dedupeKey=dedupe_key,
            page=(
                f"/pages/message-thread/index?id={quote(thread.id, safe='')}"
                "&source=subscription&autoHome=1"
            ),
            data=data,
            createdAt=now,
            updatedAt=now,
        )
        try:
            self.repo.save_wechat_subscription_delivery(delivery)
            queue.enqueue(
                "wechat-subscription-send",
                {"deliveryId": delivery.id},
                max_attempts=SUBSCRIBE_DELIVERY_MAX_ATTEMPTS,
            )
        except Exception:
            delivery.status = "failed"
            delivery.lastError = "queue_unavailable"
            delivery.updatedAt = now_iso()
            try:
                self.repo.save_wechat_subscription_delivery(delivery)
            except Exception:
                pass
            grant.status = "available"
            grant.reservedAt = None
            grant.updatedAt = now_iso()
            self.repo.save_wechat_subscription_grant(grant)
            self._restore_view_notification_after_message_failure(released_view_delivery)
            return {"queued": False, "reason": "queue_unavailable"}
        return {
            "queued": True,
            "deliveryId": delivery.id,
            "notificationType": delivery.notificationType,
            "threadId": delivery.threadId,
            "messageContent": data_values["messageContent"][:20],
        }

    def _queue_view_notification(
        self,
        *,
        queue: SyncTaskQueue,
        owner_user_id: str,
        resource_type: str,
        resource_id: str,
        resource_title: str,
        event_at: str,
        viewer_user_id: str | None,
        anonymous_id: str | None,
        note_id: str | None = None,
        showcase_id: str | None = None,
        card_id: str | None = None,
    ) -> dict:
        self.recover_stale_subscription_grants()
        if not self.customer_info_chain_enabled():
            return {"queued": False, "reason": "customer_info_chain_disabled"}
        if not settings.wechat_miniapp_subscribe_template_id or not settings.wechat_miniapp_subscribe_field_keys():
            return {"queued": False, "reason": "template_not_configured"}
        viewer_key, viewer_kind, viewer_label = self._subscription_event_viewer(owner_user_id, viewer_user_id, anonymous_id)
        important = viewer_kind == "known" and self._important_customer_view(owner_user_id, card_id or resource_id, viewer_key, note_id, showcase_id)
        member = self._is_paid_customer_member(owner_user_id)
        preference = self.repo.get_notification_preference(owner_user_id)
        preference_payload = self._notification_preference_payload(preference, member)
        if important:
            if not preference_payload["importantCustomerViewEnabled"]:
                return {"queued": False, "reason": "important_disabled"}
            viewer_type = "important"
        else:
            if not preference_payload["ordinaryAnonymousViewEnabled"]:
                return {"queued": False, "reason": "ordinary_disabled"}
            viewer_type = "ordinary" if viewer_kind == "known" else "anonymous"
        # Anonymous views are valuable signals too. Collapse all anonymous
        # viewers into one dedupe bucket per owner/resource/time window so a
        # rotating anonymous ID cannot consume one grant per device.
        dedupe_viewer_key = "anonymous" if viewer_kind == "anonymous" else viewer_key
        try:
            bucket = int(parse_iso(event_at).timestamp() // SUBSCRIBE_DEDUPE_WINDOW_SECONDS)
        except (TypeError, ValueError, OverflowError):
            bucket = int(time.time() // SUBSCRIBE_DEDUPE_WINDOW_SECONDS)
        dedupe_key = f"view:{owner_user_id}:{resource_type}:{resource_id}:{dedupe_viewer_key}:{bucket}"
        existing_delivery = self.repo.find_wechat_subscription_delivery_by_dedupe_key(dedupe_key)
        if existing_delivery and not (
            existing_delivery.status == "failed" and existing_delivery.lastError == "queue_unavailable"
        ):
            return {"queued": False, "reason": "duplicate"}
        now = now_iso()
        grant = self.repo.reserve_wechat_subscription_grant(owner_user_id, settings.wechat_miniapp_subscribe_template_id, now)
        if not grant:
            return {"queued": False, "reason": "no_subscription_quota"}
        data_values, data = self._subscription_template_data(
            message_name="客户查看提醒",
            customer_name=viewer_label,
            resource_title=resource_title,
            message_content=f"{viewer_label}打开了《{resource_title or '资料'}》",
            event_at=event_at,
        )
        if len(data) != len(SUBSCRIBE_FIELD_NAMES):
            grant.status = "available"
            grant.reservedAt = None
            grant.updatedAt = now
            self.repo.save_wechat_subscription_grant(grant)
            return {"queued": False, "reason": "template_fields_incomplete"}
        delivery = existing_delivery or WechatSubscriptionDelivery(
            id=new_id("wechat_subscription_delivery"),
            ownerUserId=owner_user_id,
            grantId=grant.id,
            templateId=settings.wechat_miniapp_subscribe_template_id,
            resourceType=resource_type if resource_type in {"card", "note", "showcase"} else "note",
            resourceId=resource_id,
            resourceTitle=(resource_title or "资料")[:80],
            viewerType=viewer_type,
            viewerLabel=viewer_label,
            messageContent=data_values["messageContent"][:80],
            eventAt=event_at,
            dedupeKey=dedupe_key,
            page=settings.wechat_miniapp_subscribe_page,
            data=data,
            createdAt=now,
            updatedAt=now,
        )
        if existing_delivery:
            old_grant = self.repo.get_wechat_subscription_grant(existing_delivery.grantId)
            if old_grant and old_grant.id != grant.id and old_grant.status == "reserved":
                old_grant.status = "available"
                old_grant.reservedAt = None
                old_grant.updatedAt = now
                self.repo.save_wechat_subscription_grant(old_grant)
            delivery.grantId = grant.id
            delivery.status = "queued"
            delivery.attempts = 0
            delivery.lastError = None
            delivery.sentAt = None
            delivery.updatedAt = now
        try:
            self.repo.save_wechat_subscription_delivery(delivery)
            queue.enqueue(
                "wechat-subscription-send",
                {"deliveryId": delivery.id},
                max_attempts=SUBSCRIBE_DELIVERY_MAX_ATTEMPTS,
            )
        except Exception:
            delivery.status = "failed"
            delivery.lastError = "queue_unavailable"
            delivery.updatedAt = now_iso()
            try:
                self.repo.save_wechat_subscription_delivery(delivery)
            except Exception:
                pass
            grant.status = "available"
            grant.reservedAt = None
            grant.updatedAt = now_iso()
            self.repo.save_wechat_subscription_grant(grant)
            return {"queued": False, "reason": "queue_unavailable"}
        return {"queued": True, "deliveryId": delivery.id, "viewerType": viewer_type}

    async def send_wechat_subscription_task(self, payload: dict) -> dict:
        self.recover_stale_subscription_grants()
        delivery_id = str(payload.get("deliveryId") or "")
        delivery = self.repo.get_wechat_subscription_delivery(delivery_id)
        if not delivery:
            return {"syncStatus": "skipped", "reason": "delivery_not_found"}
        if delivery.status in {"sent", "failed", "skipped"}:
            return {"syncStatus": "skipped", "reason": f"delivery_{delivery.status}"}
        grant = self.repo.get_wechat_subscription_grant(delivery.grantId)
        user = self.repo.get_user(delivery.ownerUserId)
        if not self.customer_info_chain_enabled():
            if grant and grant.status in {"reserved", "available"}:
                grant.status = "available"
                grant.reservedAt = None
                grant.updatedAt = now_iso()
                self.repo.save_wechat_subscription_grant(grant)
            delivery.status = "skipped"
            delivery.lastError = "customer_info_chain_disabled"
            delivery.updatedAt = now_iso()
            self.repo.save_wechat_subscription_delivery(delivery)
            return {"syncStatus": "skipped", "reason": "customer_info_chain_disabled"}
        if not grant or not user or grant.status not in {"reserved", "available"}:
            delivery.status = "skipped"
            delivery.lastError = "subscription_grant_unavailable"
            delivery.updatedAt = now_iso()
            self.repo.save_wechat_subscription_delivery(delivery)
            return {"syncStatus": "skipped", "reason": "subscription_grant_unavailable"}
        if not self.wechat_miniapp_client or not self.wechat_miniapp_client.is_configured():
            delivery.status = "failed"
            delivery.lastError = "wechat_miniapp_client_not_configured"
            delivery.updatedAt = now_iso()
            grant.status = "available"
            grant.reservedAt = None
            grant.updatedAt = delivery.updatedAt
            self.repo.save_wechat_subscription_grant(grant)
            self.repo.save_wechat_subscription_delivery(delivery)
            return {"syncStatus": "skipped", "reason": "wechat_miniapp_client_not_configured"}
        now = now_iso()
        delivery.status = "sending"
        delivery.attempts += 1
        delivery.updatedAt = now
        self.repo.save_wechat_subscription_delivery(delivery)
        try:
            result = await self.wechat_miniapp_client.send_subscribe_message(
                openid=user.openid,
                page=delivery.page,
                data=delivery.data,
            )
        except WechatMiniappClientError as exc:
            delivery.lastError = str(exc)
            delivery.updatedAt = now_iso()
            if exc.errcode == 43101:
                grant.status = "invalid"
                grant.invalidAt = delivery.updatedAt
                grant.updatedAt = delivery.updatedAt
                self.repo.save_wechat_subscription_grant(grant)
                delivery.status = "skipped"
            elif exc.retryable:
                if delivery.attempts >= SUBSCRIBE_DELIVERY_MAX_ATTEMPTS:
                    delivery.status = "failed"
                    grant.status = "available"
                    grant.reservedAt = None
                    grant.updatedAt = delivery.updatedAt
                    self.repo.save_wechat_subscription_grant(grant)
                    self.repo.save_wechat_subscription_delivery(delivery)
                    return {"syncStatus": "skipped", "reason": "retry_exhausted", "errcode": exc.errcode}
                delivery.status = "queued"
                self.repo.save_wechat_subscription_delivery(delivery)
                raise
            else:
                delivery.status = "failed"
                grant.status = "available"
                grant.reservedAt = None
                grant.updatedAt = delivery.updatedAt
                self.repo.save_wechat_subscription_grant(grant)
            self.repo.save_wechat_subscription_delivery(delivery)
            return {"syncStatus": "skipped", "reason": "wechat_api_rejected", "errcode": exc.errcode}
        except Exception:
            delivery.lastError = "network_error"
            delivery.updatedAt = now_iso()
            if delivery.attempts >= SUBSCRIBE_DELIVERY_MAX_ATTEMPTS:
                delivery.status = "failed"
                grant.status = "available"
                grant.reservedAt = None
                grant.updatedAt = delivery.updatedAt
                self.repo.save_wechat_subscription_grant(grant)
                self.repo.save_wechat_subscription_delivery(delivery)
                return {"syncStatus": "skipped", "reason": "retry_exhausted"}
            delivery.status = "queued"
            self.repo.save_wechat_subscription_delivery(delivery)
            raise
        grant.status = "consumed"
        grant.consumedAt = now_iso()
        grant.updatedAt = grant.consumedAt
        self.repo.save_wechat_subscription_grant(grant)
        delivery.status = "sent"
        delivery.sentAt = grant.consumedAt
        delivery.lastError = None
        delivery.updatedAt = grant.consumedAt
        self.repo.save_wechat_subscription_delivery(delivery)
        return {"syncStatus": "success", "deliveryId": delivery.id, "response": result}

    def require_customer_intelligence(self, user_id: str) -> None:
        self.require_customer_info_chain_enabled()
        if not self._has_customer_intelligence(user_id):
            raise HTTPException(status_code=402, detail="开通客户信息链会员后可查看完整客户情报")

    def _mutual_help_config(self) -> dict:
        if self.ops_console_store is None:
            return {
                "rechargeEnabled": True,
                "rechargeVisible": True,
                "withdrawalEnabled": False,
                "withdrawalVisible": False,
                "available": True,
                "reservePoints": MUTUAL_RESERVE_POINTS,
                "initialPoints": MUTUAL_INITIAL_POINTS,
            }
        return self.ops_console_store.get_mutual_help_config()

    @staticmethod
    def _mutual_recharge_pending_expires_at(order: MutualRechargeOrder) -> datetime:
        return parse_iso(order.createdAt) + timedelta(minutes=30)

    def _close_expired_mutual_recharge_orders(self, state: AppState, now: datetime) -> bool:
        changed = False
        for order in state.mutual_recharge_orders:
            if order.status != "pending":
                continue
            try:
                expired = self._mutual_recharge_pending_expires_at(order) <= now
            except Exception:
                expired = True
            if expired:
                order.status = "closed"
                order.updatedAt = now.isoformat()
                changed = True
        return changed

    def _ensure_mutual_point_account(self, state: AppState, user_id: str) -> MutualPointAccount:
        user_id = str(user_id or "").strip()
        if not user_id or not self.repo.get_user(user_id):
            raise HTTPException(status_code=404, detail="用户不存在")
        return self.points_core.ensure_account(
            state,
            user_id,
            account_type=DEFAULT_POINTS_ACCOUNT_TYPE,
            initial_points=MUTUAL_INITIAL_POINTS,
            initial_reason="首次进入互帮互助赠送积分",
        )

    def get_mutual_help_status(self, user_id: str) -> dict:
        state = self._load()
        account = self._ensure_mutual_point_account(state, user_id)
        self._save(state)
        config = self._mutual_help_config()
        orders = sorted(
            [item.model_dump() for item in state.mutual_recharge_orders if item.userId == user_id],
            key=lambda item: (item.get("createdAt") or "", item.get("id") or ""),
            reverse=True,
        )[:10]
        return {
            "config": config,
            "account": account.model_dump(),
            "recentLedgers": [
                item.model_dump()
                for item in self.points_core.list_ledgers(
                    state,
                    user_id,
                    account_type=DEFAULT_POINTS_ACCOUNT_TYPE,
                    limit=20,
                )
            ],
            "orders": orders,
            "rechargePackages": [
                {
                    "points": points,
                    "amountFen": points * 100 // MUTUAL_POINTS_PER_YUAN,
                    "amountYuan": points / MUTUAL_POINTS_PER_YUAN,
                }
                for points in MUTUAL_RECHARGE_PACKAGES
            ],
        }

    def create_mutual_recharge_order(self, user_id: str, points: int) -> dict:
        config = self._mutual_help_config()
        if config.get("available") is False:
            raise HTTPException(status_code=503, detail="互助积分配置暂时不可用")
        if not config.get("rechargeEnabled", False):
            raise HTTPException(status_code=403, detail="充值功能当前未开放")
        if points not in MUTUAL_RECHARGE_PACKAGES:
            raise HTTPException(status_code=400, detail="请选择有效的充值档位")
        user = self.repo.get_user(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")
        now = now_iso()
        now_dt = parse_iso(now)
        payment_mode = "wechat_pay" if settings.app_env == "production" or settings.wechat_pay_enabled else "test"
        with MEMBERSHIP_PAYMENT_LOCK:
            state = self._load()
            changed = self._close_expired_mutual_recharge_orders(state, now_dt)
            pending = sorted(
                (
                    item for item in state.mutual_recharge_orders
                    if item.userId == user_id
                    and item.points == points
                    and item.status == "pending"
                    and item.paymentChannel == payment_mode
                ),
                key=lambda item: item.createdAt,
                reverse=True,
            )
            reused = bool(pending)
            order = pending[0] if pending else MutualRechargeOrder(
                id=new_id("mutual_recharge"),
                userId=user_id,
                points=points,
                amountFen=points * 100 // MUTUAL_POINTS_PER_YUAN,
                paymentChannel=payment_mode,
                createdAt=now,
                updatedAt=now,
            )
            if not reused:
                state.mutual_recharge_orders.append(order)
                changed = True
            self._ensure_mutual_point_account(state, user_id)
            if changed:
                self._save(state)
        return {
            "order": order.model_dump(),
            "pendingOrder": {
                **order.model_dump(),
                "expiresAt": self._mutual_recharge_pending_expires_at(order).isoformat(),
            },
            "paymentMode": payment_mode,
            "testMode": payment_mode == "test",
            "reused": reused,
        }

    def create_mutual_recharge_payment(self, order_id: str, user_id: str) -> dict:
        config = self._mutual_help_config()
        if config.get("available") is False:
            raise HTTPException(status_code=503, detail="互助积分配置暂时不可用")
        if not config.get("rechargeEnabled", False):
            raise HTTPException(status_code=403, detail="充值功能当前未开放")
        user = self.repo.get_user(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")
        with MEMBERSHIP_PAYMENT_LOCK:
            state = self._load()
            order = next((item for item in state.mutual_recharge_orders if item.id == order_id), None)
            if not order:
                raise HTTPException(status_code=404, detail="积分充值订单不存在")
            if order.userId != user_id:
                raise HTTPException(status_code=403, detail="无权支付该订单")
            if order.status == "paid":
                return {"order": order.model_dump(), "paymentRequired": False, "account": self._ensure_mutual_point_account(state, user_id).model_dump()}
            if self._mutual_recharge_pending_expires_at(order) <= parse_iso(now_iso()):
                order.status = "closed"
                order.updatedAt = now_iso()
                self._save(state)
                raise HTTPException(status_code=409, detail="订单已超时关闭，请重新发起充值")
            if order.status != "pending" or order.paymentChannel != "wechat_pay":
                raise HTTPException(status_code=409, detail="当前订单不能发起微信支付")
        try:
            client = WechatPayClient()
            prepay_id = client.create_jsapi_prepay(
                openid=user.openid,
                out_trade_no=order.id,
                total_fen=order.amountFen,
                description="互助积分充值",
            )
            payment = client.build_jsapi_payment(prepay_id)
        except WechatPayError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return {
            "order": order.model_dump(),
            "pendingOrder": {
                **order.model_dump(),
                "expiresAt": self._mutual_recharge_pending_expires_at(order).isoformat(),
            },
            "paymentRequired": True,
            "payment": payment,
        }

    def confirm_test_mutual_recharge_payment(self, order_id: str, transaction_id: str) -> dict:
        if settings.app_env == "production" or settings.wechat_pay_enabled:
            raise HTTPException(status_code=403, detail="当前支付模式禁止测试确认付款")
        transaction_id = str(transaction_id or "").strip()
        if not transaction_id:
            raise HTTPException(status_code=400, detail="支付流水不能为空")
        with MEMBERSHIP_PAYMENT_LOCK:
            state = self._load()
            order = next((item for item in state.mutual_recharge_orders if item.id == order_id), None)
            if not order:
                raise HTTPException(status_code=404, detail="积分充值订单不存在")
            return self._complete_mutual_recharge_order(state, order, transaction_id)

    def _complete_mutual_recharge_order(self, state: AppState, order: MutualRechargeOrder, transaction_id: str) -> dict:
        duplicate = next(
            (item for item in state.mutual_recharge_orders if item.paymentTransactionId == transaction_id and item.id != order.id),
            None,
        )
        if duplicate:
            raise HTTPException(status_code=409, detail="支付流水已被使用")
        if order.status == "paid":
            if order.paymentTransactionId != transaction_id:
                raise HTTPException(status_code=409, detail="订单已由其他支付流水确认")
            account = self._ensure_mutual_point_account(state, order.userId)
            return {"order": order.model_dump(), "account": account.model_dump(), "duplicate": True}
        if order.status not in {"pending", "closed"}:
            raise HTTPException(status_code=409, detail="订单状态不能确认付款")
        now = now_iso()
        account = self._ensure_mutual_point_account(state, order.userId)
        order.status = "paid"
        order.paymentTransactionId = transaction_id
        order.paidAt = now
        order.updatedAt = now
        points_result = self.points_core.grant(
            state,
            order.userId,
            order.points,
            ledger_type="recharge",
            reason="充值互助积分",
            idempotency_key=f"recharge:{order.id}",
            account_type=DEFAULT_POINTS_ACCOUNT_TYPE,
            source_type="mutual_recharge_order",
            source_id=order.id,
            related_order_id=order.id,
            metadata={"paymentTransactionId": transaction_id},
        )
        account = points_result["account"]
        ledger = points_result["ledger"]
        self._save(state)
        return {
            "order": order.model_dump(),
            "account": account.model_dump(),
            "ledger": ledger.model_dump(),
            "duplicate": points_result["duplicate"],
        }

    def list_points_ledgers(
        self,
        user_id: str,
        *,
        account_type: str = DEFAULT_POINTS_ACCOUNT_TYPE,
        limit: int = 100,
    ) -> list[dict]:
        state = self._load()
        self._ensure_points_user(user_id)
        self.points_core.ensure_account(state, user_id, account_type=account_type)
        self._save(state)
        return [
            item.model_dump()
            for item in self.points_core.list_ledgers(
                state,
                user_id,
                account_type=account_type,
                limit=limit,
            )
        ]

    def grant_points(
        self,
        user_id: str,
        points: int,
        *,
        reason: str,
        idempotency_key: str,
        ledger_type: str = "grant",
        account_type: str = DEFAULT_POINTS_ACCOUNT_TYPE,
        source_type: str | None = None,
        source_id: str | None = None,
        metadata: dict | None = None,
    ) -> dict:
        self._ensure_points_user(user_id)
        with MEMBERSHIP_PAYMENT_LOCK:
            state = self._load()
            result = self.points_core.grant(
                state,
                user_id,
                points,
                ledger_type=ledger_type,
                reason=reason,
                idempotency_key=idempotency_key,
                account_type=account_type,
                source_type=source_type,
                source_id=source_id,
                metadata=metadata,
            )
            self._save(state)
        return self._points_result_to_dict(result)

    def consume_points(
        self,
        user_id: str,
        points: int,
        *,
        reason: str,
        idempotency_key: str,
        ledger_type: str = "consume",
        account_type: str = DEFAULT_POINTS_ACCOUNT_TYPE,
        source_type: str | None = None,
        source_id: str | None = None,
        metadata: dict | None = None,
    ) -> dict:
        self._ensure_points_user(user_id)
        with MEMBERSHIP_PAYMENT_LOCK:
            state = self._load()
            result = self.points_core.consume(
                state,
                user_id,
                points,
                ledger_type=ledger_type,
                reason=reason,
                idempotency_key=idempotency_key,
                account_type=account_type,
                source_type=source_type,
                source_id=source_id,
                metadata=metadata,
            )
            self._save(state)
        return self._points_result_to_dict(result)

    def transfer_points(
        self,
        from_user_id: str,
        to_user_id: str,
        points: int,
        *,
        operation_key: str,
        debit_reason: str,
        credit_reason: str,
        account_type: str = DEFAULT_POINTS_ACCOUNT_TYPE,
        debit_ledger_type: str = "transfer_debit",
        credit_ledger_type: str = "transfer_credit",
        source_type: str | None = None,
        source_id: str | None = None,
        metadata: dict | None = None,
    ) -> dict:
        self._ensure_points_user(from_user_id)
        self._ensure_points_user(to_user_id)
        with MEMBERSHIP_PAYMENT_LOCK:
            state = self._load()
            result = self.points_core.transfer(
                state,
                from_user_id,
                to_user_id,
                points,
                operation_key=operation_key,
                debit_reason=debit_reason,
                credit_reason=credit_reason,
                account_type=account_type,
                debit_ledger_type=debit_ledger_type,
                credit_ledger_type=credit_ledger_type,
                source_type=source_type,
                source_id=source_id,
                metadata=metadata,
            )
            self._save(state)
        return {
            "fromAccount": result["fromAccount"].model_dump(),
            "toAccount": result["toAccount"].model_dump(),
            "debitLedger": result["debitLedger"].model_dump(),
            "creditLedger": result["creditLedger"].model_dump(),
            "duplicate": result["duplicate"],
        }

    def _ensure_points_user(self, user_id: str) -> None:
        if not self.repo.get_user(str(user_id or "").strip()):
            raise HTTPException(status_code=404, detail="用户不存在")

    @staticmethod
    def _points_result_to_dict(result: dict) -> dict:
        return {
            "account": result["account"].model_dump(),
            "ledger": result["ledger"].model_dump(),
            "duplicate": result["duplicate"],
        }

    def record_mutual_help_activity(
        self,
        user_id: str,
        event_type: str,
        task_id: str,
        task_kind: str = "ordinary",
        idempotency_key: str = "",
    ) -> dict:
        if event_type not in {"published", "completed"}:
            raise HTTPException(status_code=400, detail="互助活动类型无效")
        if not self.repo.get_user(user_id):
            raise HTTPException(status_code=404, detail="用户不存在")
        task_id = str(task_id or "").strip()
        if not task_id:
            raise HTTPException(status_code=400, detail="任务 ID 不能为空")
        key = (str(idempotency_key or "").strip() or f"{event_type}:{user_id}:{task_id}")[:160]
        state = self._load()
        existing = next((item for item in state.mutual_activity_events if item.idempotencyKey == key), None)
        if existing:
            return {"event": existing.model_dump(), "duplicate": True}
        event = MutualActivityEvent(
            id=new_id("mutual_activity"),
            eventType=event_type,
            userId=user_id,
            taskId=task_id,
            taskKind=str(task_kind or "ordinary"),
            idempotencyKey=key,
            createdAt=now_iso(),
        )
        state.mutual_activity_events.append(event)
        self._save(state)
        return {"event": event.model_dump(), "duplicate": False}

    def get_mutual_help_operations(self) -> dict:
        state = self._load()
        now = datetime.now(tz=SHANGHAI)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        seven_day_start = today_start - timedelta(days=6)

        def in_scope(value: str | None, start: datetime | None) -> bool:
            if start is None:
                return True
            try:
                return parse_iso(value) >= start
            except Exception:
                return False

        def summarize(start: datetime | None) -> dict:
            events = [item for item in state.mutual_activity_events if in_scope(item.createdAt, start)]
            orders = [
                item for item in state.mutual_recharge_orders
                if item.status == "paid" and in_scope(item.paidAt or item.createdAt, start)
            ]
            return {
                "publishedTasks": sum(1 for item in events if item.eventType == "published"),
                "completedTasks": sum(1 for item in events if item.eventType == "completed"),
                "rechargeOrders": len(orders),
                "rechargePoints": sum(int(item.points or 0) for item in orders),
                "rechargeRevenueFen": sum(int(item.amountFen or 0) for item in orders),
            }

        return {
            "config": self._mutual_help_config(),
            "periods": {
                "today": summarize(today_start),
                "sevenDays": summarize(seven_day_start),
                "total": summarize(None),
            },
            "generatedAt": now.isoformat(),
        }

    def create_membership_order(self, user_id: str, plan_code: str = SALES_SCRM_PLAN_CODE) -> dict:
        self.require_customer_info_chain_enabled()
        if not self.customer_info_chain_payment_required():
            raise HTTPException(status_code=409, detail="当前为免支付模式，无需购买客户信息链会员")
        if not self.repo.get_user(user_id):
            raise HTTPException(status_code=404, detail="用户不存在")
        if plan_code != SALES_SCRM_PLAN_CODE:
            raise HTTPException(status_code=400, detail="会员方案不存在")
        now = now_iso()
        now_dt = parse_iso(now)
        payment_mode = "wechat_pay" if settings.app_env == "production" or settings.wechat_pay_enabled else "test"
        reused = False
        with MEMBERSHIP_PAYMENT_LOCK:
            state = self._load()
            state_changed = self._close_expired_membership_orders(state, now_dt)
            recent_pending = sorted(
                (
                    item
                    for item in state.membership_orders
                    if (
                        item.userId == user_id
                        and item.planCode == plan_code
                        and item.status == "pending"
                        and item.paymentChannel == payment_mode
                    )
                ),
                key=lambda item: item.createdAt,
                reverse=True,
            )
            if recent_pending:
                order = recent_pending[0]
                reused = True
            else:
                relation = next((item for item in state.referral_relations if item.inviteeUserId == user_id), None)
                order = MembershipOrder(
                    id=new_id("membership_order"),
                    userId=user_id,
                    planCode=plan_code,
                    amountFen=SALES_SCRM_MONTHLY_PRICE_FEN,
                    status="pending",
                    paymentChannel=payment_mode,
                    referralRelationId=relation.id if relation else None,
                    createdAt=now,
                    updatedAt=now,
                )
                state.membership_orders.append(order)
                state_changed = True
            if state_changed:
                self._save(state)
        self._invalidate_customer_intelligence_cache(user_id)
        return {
            "order": order.model_dump(),
            "pendingOrder": self._membership_pending_order_payload(order, now_dt),
            "paymentRequired": True,
            "paymentMode": payment_mode,
            "testMode": payment_mode == "test",
            "reused": reused,
        }

    def create_wechat_membership_payment(self, order_id: str, user_id: str) -> dict:
        self.require_customer_info_chain_enabled()
        if not self.customer_info_chain_payment_required():
            raise HTTPException(status_code=409, detail="当前为免支付模式，无需发起会员支付")
        user = self.repo.get_user(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")
        with MEMBERSHIP_PAYMENT_LOCK:
            state = self._load()
            order = next((item for item in state.membership_orders if item.id == order_id), None)
            if not order:
                raise HTTPException(status_code=404, detail="会员订单不存在")
            if order.userId != user_id:
                raise HTTPException(status_code=403, detail="无权支付该订单")
            if order.status == "paid":
                return {"order": order.model_dump(), "paymentRequired": False, "membership": self.get_membership_status(user_id)}
            if self._close_expired_membership_order(state, order, parse_iso(now_iso())):
                raise HTTPException(status_code=409, detail="订单已超时关闭，请重新发起支付")
            if order.status != "pending":
                raise HTTPException(status_code=409, detail="订单状态不能发起支付")
            if order.paymentChannel != "wechat_pay":
                raise HTTPException(status_code=409, detail="当前订单不是微信支付订单")
        try:
            client = WechatPayClient()
            prepay_id = client.create_jsapi_prepay(
                openid=user.openid,
                out_trade_no=order.id,
                total_fen=order.amountFen,
                description="客户信息链会员",
            )
            payment = client.build_jsapi_payment(prepay_id)
        except WechatPayError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return {
            "order": order.model_dump(),
            "pendingOrder": self._membership_pending_order_payload(order, parse_iso(now_iso())),
            "paymentRequired": True,
            "payment": payment,
        }

    def confirm_test_membership_payment(self, order_id: str, transaction_id: str) -> dict:
        if settings.app_env == "production" or settings.wechat_pay_enabled:
            raise HTTPException(status_code=403, detail="当前支付模式禁止测试确认付款")
        transaction_id = str(transaction_id or "").strip()
        if not transaction_id:
            raise HTTPException(status_code=400, detail="支付流水不能为空")
        with MEMBERSHIP_PAYMENT_LOCK:
            state = self._load()
            order = next((item for item in state.membership_orders if item.id == order_id), None)
            if not order:
                raise HTTPException(status_code=404, detail="会员订单不存在")
            if self._close_expired_membership_order(state, order, parse_iso(now_iso())):
                raise HTTPException(status_code=409, detail="订单已超时关闭，请重新发起支付")
            return self._complete_membership_order(state, order, transaction_id)

    def handle_wechat_pay_success(self, transaction: dict) -> dict:
        if not isinstance(transaction, dict):
            raise HTTPException(status_code=400, detail="支付回调交易数据无效")
        out_trade_no = str(transaction.get("out_trade_no") or "").strip()
        transaction_id = str(transaction.get("transaction_id") or "").strip()
        if not out_trade_no or not transaction_id:
            raise HTTPException(status_code=400, detail="支付回调缺少订单号或微信流水号")
        if str(transaction.get("appid") or "") != settings.wechat_miniapp_appid:
            raise HTTPException(status_code=400, detail="支付回调 AppID 不匹配")
        if str(transaction.get("mchid") or "") != settings.wechat_pay_mch_id:
            raise HTTPException(status_code=400, detail="支付回调商户号不匹配")
        if str(transaction.get("trade_state") or "") != "SUCCESS":
            raise HTTPException(status_code=400, detail="支付回调不是成功状态")
        amount = transaction.get("amount") if isinstance(transaction.get("amount"), dict) else {}
        try:
            total_fen = int(amount.get("total"))
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail="支付回调金额无效") from exc
        if str(amount.get("currency") or "") != "CNY":
            raise HTTPException(status_code=400, detail="支付回调币种无效")
        payer = transaction.get("payer") if isinstance(transaction.get("payer"), dict) else {}
        openid = str(payer.get("openid") or "")
        with MEMBERSHIP_PAYMENT_LOCK:
            state = self._load()
            order = next((item for item in state.membership_orders if item.id == out_trade_no), None)
            mutual_order = None
            if not order:
                mutual_order = next((item for item in state.mutual_recharge_orders if item.id == out_trade_no), None)
                if not mutual_order:
                    raise HTTPException(status_code=404, detail="会员或互助积分订单不存在")
                user = self.repo.get_user(mutual_order.userId)
                if mutual_order.paymentChannel != "wechat_pay":
                    raise HTTPException(status_code=409, detail="订单支付渠道不匹配")
                if not user or user.openid != openid:
                    raise HTTPException(status_code=400, detail="支付回调用户身份不匹配")
                if mutual_order.amountFen != total_fen:
                    raise HTTPException(status_code=400, detail="支付回调金额与订单不一致")
                return self._complete_mutual_recharge_order(state, mutual_order, transaction_id)
            user = self.repo.get_user(order.userId)
            if order.paymentChannel != "wechat_pay":
                raise HTTPException(status_code=409, detail="订单支付渠道不匹配")
            if not user or user.openid != openid:
                raise HTTPException(status_code=400, detail="支付回调用户身份不匹配")
            if order.amountFen != total_fen:
                raise HTTPException(status_code=400, detail="支付回调金额与订单不一致")
            return self._complete_membership_order(state, order, transaction_id)

    def _complete_membership_order(self, state: AppState, order: MembershipOrder, transaction_id: str) -> dict:
        duplicate = next(
            (item for item in state.membership_orders if item.paymentTransactionId == transaction_id and item.id != order.id),
            None,
        )
        if duplicate:
            raise HTTPException(status_code=409, detail="支付流水已被使用")
        if order.status == "paid":
            if order.paymentTransactionId != transaction_id:
                raise HTTPException(status_code=409, detail="订单已由其他支付流水确认")
            return {"order": order.model_dump(), "membership": self.get_membership_status(order.userId), "duplicate": True}
        if order.status not in {"pending", "closed"}:
            raise HTTPException(status_code=409, detail="订单状态不能确认付款")
        now_text = now_iso()
        now_dt = parse_iso(now_text)
        active_expiries = [
            parse_iso(item.expiresAt) for item in state.membership_entitlements
            if item.userId == order.userId and item.status == "active" and parse_iso(item.expiresAt) > now_dt
        ]
        starts_at = max(active_expiries, default=now_dt)
        entitlement = MembershipEntitlement(
            id=new_id("entitlement"),
            userId=order.userId,
            sourceOrderId=order.id,
            startsAt=starts_at.isoformat(),
            expiresAt=(starts_at + timedelta(days=SALES_SCRM_PERIOD_DAYS)).isoformat(),
            createdAt=now_text,
            updatedAt=now_text,
        )
        order.status = "paid"
        order.paymentTransactionId = transaction_id
        order.paidAt = now_text
        order.updatedAt = now_text
        state.membership_entitlements.append(entitlement)
        relation = next((item for item in state.referral_relations if item.inviteeUserId == order.userId), None)
        if relation and relation.inviterUserId != order.userId:
            order.referralRelationId = relation.id
            existing_reward = next((item for item in state.referral_rewards if item.sourceOrderId == order.id), None)
            inviter_is_active = self._has_active_customer_entitlement(relation.inviterUserId)
            if not existing_reward and inviter_is_active:
                state.referral_rewards.append(
                    ReferralReward(
                        id=new_id("referral_reward"),
                        inviterUserId=relation.inviterUserId,
                        inviteeUserId=order.userId,
                        sourceOrderId=order.id,
                        ratioBasisPoints=SALES_SCRM_REWARD_BASIS_POINTS,
                        amountFen=order.amountFen * SALES_SCRM_REWARD_BASIS_POINTS // 10000,
                        status="available",
                        availableAt=now_text,
                        createdAt=now_text,
                        updatedAt=now_text,
                    )
                )
        self._save(state)
        self._invalidate_customer_intelligence_cache(order.userId)
        return {"order": order.model_dump(), "entitlement": entitlement.model_dump(), "duplicate": False}

    def refund_test_membership_payment(self, order_id: str, operator_user_id: str) -> dict:
        if settings.app_env == "production" or settings.wechat_pay_enabled:
            raise HTTPException(status_code=403, detail="当前支付模式禁止测试退款")
        if not operator_user_id:
            raise HTTPException(status_code=400, detail="操作人不能为空")
        state = self._load()
        order = next((item for item in state.membership_orders if item.id == order_id), None)
        if not order:
            raise HTTPException(status_code=404, detail="会员订单不存在")
        if order.status == "refunded":
            return {"order": order.model_dump(), "duplicate": True}
        if order.status != "paid":
            raise HTTPException(status_code=409, detail="只有已付款订单可以退款")
        now = now_iso()
        order.status = "refunded"
        order.refundedAt = now
        order.updatedAt = now
        for item in state.membership_entitlements:
            if item.sourceOrderId == order.id and item.status == "active":
                item.status = "revoked"
                item.revokedAt = now
                item.updatedAt = now
        for item in state.referral_rewards:
            if item.sourceOrderId == order.id and item.status != "revoked":
                if self._referral_reward_withdrawn_fen(item) > 0:
                    raise HTTPException(status_code=409, detail="奖励已提现，需人工处理退款")
                if self._referral_reward_reserved_fen(item) > 0:
                    withdrawal = next(
                        (
                            row for row in state.referral_withdrawals
                            if item.id in row.rewardIds
                            and self._referral_withdrawal_allocation(row, item.id, item.amountFen) > 0
                        ),
                        None,
                    )
                    if withdrawal:
                        if withdrawal.status != "pending":
                            raise HTTPException(status_code=409, detail="提现已进入微信转账，需先人工撤销后退款")
                        withdrawal.status = "rejected"
                        withdrawal.reviewedAt = now
                        withdrawal.updatedAt = now
                        self._release_referral_withdrawal_rewards(state, withdrawal, now)
                item.status = "revoked"
                item.reservedFen = 0
                item.revokedAt = now
                item.updatedAt = now
        self._save(state)
        self._invalidate_customer_intelligence_cache(order.userId)
        return {"order": order.model_dump(), "duplicate": False}

    def get_customer_intelligence(
        self,
        owner_user_id: str,
        requester_user_id: str,
        mode: str | None = None,
        force_refresh: bool = False,
    ) -> dict:
        if not requester_user_id:
            raise HTTPException(status_code=401, detail="请先登录后查看工作台")
        if requester_user_id != owner_user_id:
            raise HTTPException(status_code=403, detail="仅工作台拥有者可查看")
        if not self.customer_info_chain_enabled():
            return {
                "featureEnabled": False,
                "locked": True,
                "membership": self.get_membership_status(owner_user_id),
                "summary": {},
                "signalPreview": [],
                "upgradeMessage": "客户信息链功能当前未开放。",
            }
        membership = self.get_membership_status(owner_user_id)
        payment_required = bool(membership.get("paymentRequired", True))
        mode_key = str(mode or "").strip()
        cache_key = (owner_user_id or "", requester_user_id or "", mode_key)
        now = time.monotonic()
        cached = self._customer_intelligence_cache.get(cache_key)
        cached_matches_access = cached and bool(cached[1].get("locked", True)) == (payment_required and not membership["active"])
        cached_matches_payment_mode = cached and bool(cached[1].get("paymentRequired", True)) == payment_required
        if (
            not force_refresh
            and cached_matches_access
            and cached_matches_payment_mode
            and now - cached[0] < self._customer_intelligence_cache_ttl_seconds
        ):
            return cached[1]
        if cached:
            self._customer_intelligence_cache.pop(cache_key, None)
        dashboard = self._build_business_dashboard(owner_user_id, requester_user_id, mode)
        # The SCRM response is the source for radar tab counts. Its visitor
        # count must reflect the post-lead-decision active projection, while
        # the general business dashboard keeps the raw event count for
        # analytics compatibility.
        radar_profiles = dashboard.get("radarProfiles") or []
        dashboard_summary = dashboard.setdefault("summary", {})
        dashboard_summary["visitorCount"] = len(radar_profiles)
        dashboard_summary["loggedInVisitorCount"] = sum(
            1 for item in radar_profiles if item.get("viewerUserId")
        )
        dashboard_summary["anonymousVisitorCount"] = sum(
            1 for item in radar_profiles if not item.get("viewerUserId")
        )
        summary = dict(dashboard.get("summary") or {})
        free_summary = {
            "visitorCount": int(summary.get("visitorCount") or 0),
            "anonymousVisitorCount": int(summary.get("anonymousVisitorCount") or 0),
            "repeatVisitorCount": sum(1 for item in dashboard.get("visitorProfiles", []) if int(item.get("viewCount") or 0) >= 2),
            "newInteractionCount": int(summary.get("todayActionCount") or 0) + int(summary.get("todayEventCount") or 0),
            "feedbackResourceCount": sum(1 for item in dashboard.get("topNotes", []) if int(item.get("viewCount") or 0) > 0),
            "pendingLeadCount": int(summary.get("pendingLeadCount") or 0),
        }
        if payment_required and not membership["active"]:
            response = {
                "featureEnabled": True,
                "paymentRequired": True,
                "locked": True,
                "membership": membership,
                "summary": free_summary,
                "rangeSummaries": dashboard.get("rangeSummaries") or {},
                "signalPreview": self._masked_signal_preview(dashboard),
                "upgradeMessage": "已有客户信号，开通会员后查看身份、轨迹并持续跟进。",
            }
            self._remember_customer_intelligence_cache(cache_key, response, now)
            return response
        response = {
            "featureEnabled": True,
            "paymentRequired": payment_required,
            "locked": False,
            "membership": membership,
            "summary": free_summary,
            "dashboard": dashboard,
            "customerTimelines": self._customer_timeline_rows(dashboard),
        }
        self._remember_customer_intelligence_cache(cache_key, response, now)
        return response

    def get_customer_intelligence_summary(
        self,
        owner_user_id: str,
        requester_user_id: str,
        mode: str | None = None,
        force_refresh: bool = False,
    ) -> dict:
        """Return the radar's small, fast projection before the full dashboard.

        This deliberately does not call ``_build_business_dashboard``. The
        summary contains only counts and current-state cards; full history and
        range analytics remain on the detail dashboard request.
        """
        if not requester_user_id:
            raise HTTPException(status_code=401, detail="请先登录后查看工作台")
        if requester_user_id != owner_user_id:
            raise HTTPException(status_code=403, detail="仅工作台拥有者可查看")
        membership = self.get_membership_status(owner_user_id)
        payment_required = bool(membership.get("paymentRequired", True))
        if not self.customer_info_chain_enabled():
            return {
                "featureEnabled": False,
                "locked": True,
                "paymentRequired": payment_required,
                "membership": membership,
                "summary": {},
            }

        mode_key = str(mode or "").strip()
        cache_key = (owner_user_id or "", requester_user_id or "", mode_key)
        now = time.monotonic()
        cached = self._customer_intelligence_summary_cache.get(cache_key)
        cached_matches_access = cached and bool(cached[1].get("locked", True)) == (payment_required and not membership["active"])
        cached_matches_payment_mode = cached and bool(cached[1].get("paymentRequired", True)) == payment_required
        if (
            not force_refresh
            and cached_matches_access
            and cached_matches_payment_mode
            and now - cached[0] < self._customer_intelligence_summary_cache_ttl_seconds
        ):
            return cached[1]
        if cached:
            self._customer_intelligence_summary_cache.pop(cache_key, None)

        if payment_required and not membership["active"]:
            all_leads = self.repo.list_lead_reminders(owner_user_id)
            response = {
                "featureEnabled": True,
                "paymentRequired": True,
                "locked": True,
                "membership": membership,
                "summary": {
                    "pendingLeadCount": sum(1 for item in all_leads if item.status == "pending"),
                    "visitorCount": None,
                    "newInteractionCount": None,
                },
            }
            self._remember_customer_intelligence_summary_cache(cache_key, response, now)
            return response

        persisted_summary = None
        if not force_refresh:
            persisted_summary = self.repo.get_customer_radar_summary(owner_user_id, mode_key)
            if persisted_summary and not persisted_summary.isDirty:
                response = self._customer_radar_summary_response(
                    persisted_summary,
                    membership,
                    payment_required,
                )
                self._remember_customer_intelligence_summary_cache(cache_key, response, now)
                return response

        all_leads = self.repo.list_lead_reminders(owner_user_id)
        notes = [item for item in self.repo.list_user_notes(owner_user_id, include_deleted=False) if item.status != "deleted"]
        if mode_key == "property":
            notes = [item for item in notes if self._is_property_note(item)]
        elif mode_key == "groupbuy":
            notes = [item for item in notes if self._is_groupbuy_note(item)]
        elif mode_key == "service":
            notes = [item for item in notes if self._is_service_note(item)]
        note_ids = {item.id for item in notes}
        note_source_ids = note_ids | {item.sourceCardId for item in notes if item.sourceCardId}
        actions_by_note = self.repo.list_customer_actions_for_notes(note_ids)
        actions = [action for rows in actions_by_note.values() for action in rows if action.ownerUserId == owner_user_id]
        projected_lead_ids = {
            str((action.projectionRefs or {}).get("leadReminderId") or "")
            for action in actions
            if (action.projectionRefs or {}).get("leadReminderId")
        }
        leads = [item for item in all_leads if item.id in projected_lead_ids or item.cardId in note_source_ids]
        note_event_rows = self.repo.list_view_events_for_cards(note_source_ids)
        note_view_events = {
            note.id: note_event_rows.get(note.sourceCardId or note.id, [])
            for note in notes
        }
        showcases = [
            showcase
            for showcase in self.repo.list_showcase_pages(owner_user_id)
            if any(item.noteId in note_ids for item in showcase.items)
        ]
        showcase_ids = {item.id for item in showcases}
        showcase_event_rows = self.repo.list_showcase_events_for_showcases(showcase_ids)
        showcase_events = [
            event
            for showcase_id in showcase_ids
            for event in showcase_event_rows.get(showcase_id, [])
            if event.ownerUserId == owner_user_id
            and (event.eventType != "note_click" or event.noteId in note_ids)
        ]
        raw_summary = {
            "propertyCount": len(notes),
            "showcaseOpenCount": sum(1 for item in showcase_events if item.eventType == "view"),
            "visitorCount": 0,
            "loggedInVisitorCount": 0,
            "anonymousVisitorCount": 0,
            "noteClickCount": sum(1 for rows in note_view_events.values() for item in rows if item.viewType != "share") + sum(1 for item in showcase_events if item.eventType == "note_click"),
            "consultCount": sum(1 for item in showcase_events if item.eventType in {"phone_click", "wechat_copy"}) + sum(1 for item in actions if item.actionKey in {"lead-contact", "appointment", "consult-click"}),
            "shareCount": sum(1 for item in showcase_events if item.eventType == "share") + sum(1 for rows in note_view_events.values() for item in rows if item.viewType == "share"),
            "pendingLeadCount": sum(1 for item in leads if item.status == "pending"),
            "customerCount": len(leads),
            "orderCount": 0,
            "pendingOrderCount": 0,
            "todayEventCount": 0,
            "todayActionCount": 0,
            "showcaseCount": len(showcases),
            "publishedShowcaseCount": sum(1 for item in showcases if item.status == "published"),
        }
        dashboard = {"summary": raw_summary}
        dashboard = self._attach_opportunity_radar(
            owner_user_id,
            dashboard,
            notes,
            showcase_events,
            actions,
            leads,
            note_view_events,
            suppression_leads=all_leads,
            synchronize_summary_counts=True,
        )
        opportunity_summary = dashboard.get("opportunitySummary") or {}
        response = {
            "featureEnabled": True,
            "paymentRequired": payment_required,
            "locked": False,
            "membership": membership,
            "summary": {
                "pending": sum(1 for item in leads if item.status == "pending"),
                "visitors": len(dashboard.get("radarProfiles") or []),
                "following": len(dashboard.get("followingProfiles") or []),
                "abandoned": len(dashboard.get("abandonedProfiles") or []),
                "highIntent": int(opportunity_summary.get("highIntentCount") or 0),
                "interactions": int(raw_summary["noteClickCount"] + raw_summary["consultCount"]),
                "revival": int(opportunity_summary.get("revivalCount") or 0),
                "filtered": 0,
            },
            "source": "lightweight_radar_projection",
        }
        self._save_customer_radar_summary(
            owner_user_id,
            mode_key,
            response,
            existing=persisted_summary,
        )
        self._remember_customer_intelligence_summary_cache(cache_key, response, now)
        return response

    @staticmethod
    def _customer_identity_aliases(value: object) -> set[str]:
        text = str(value or "").strip()
        if not text:
            return set()
        aliases = {text}
        match = re.match(r"^(?:user|anon):(.*)$", text)
        if match and match.group(1):
            aliases.add(match.group(1))
        else:
            aliases.update({f"user:{text}", f"anon:{text}"})
        return aliases

    def _customer_identity_matches(self, item: dict, target: object) -> bool:
        target_aliases = self._customer_identity_aliases(target)
        if not target_aliases:
            return False
        values = [
            item.get("id"),
            item.get("customerId"),
            item.get("viewerUserId"),
            item.get("anonymousId"),
            item.get("visitorIdentityId"),
            item.get("leadReminderId"),
        ]
        return any(
            target_aliases.intersection(self._customer_identity_aliases(value))
            for value in values
            if value
        )

    def _raw_customer_identity_matches(
        self,
        owner_user_id: str,
        target: object,
        *,
        visitor_identity_id: str | None = None,
        viewer_user_id: str | None = None,
        anonymous_id: str | None = None,
        fallback_id: str | None = None,
    ) -> bool:
        target_aliases = self._customer_identity_aliases(target)
        if not target_aliases:
            return False
        values = [
            visitor_identity_id,
            self._stable_visitor_identity_id(owner_user_id, viewer_user_id, anonymous_id, fallback_id),
            self._dashboard_identity_key(viewer_user_id, anonymous_id, fallback_id),
            viewer_user_id,
            anonymous_id,
            fallback_id,
        ]
        return any(
            target_aliases.intersection(self._customer_identity_aliases(value))
            for value in values
            if value
        )

    def _load_customer_detail_sources(self, owner_user_id: str, mode: str | None) -> dict:
        notes = self.repo.list_user_notes(owner_user_id, include_deleted=False)
        if mode == "property":
            notes = [item for item in notes if self._is_property_note(item)]
        elif mode == "groupbuy":
            notes = [item for item in notes if self._is_groupbuy_note(item)]
        elif mode == "service":
            notes = [item for item in notes if self._is_service_note(item)]
        note_by_id = {item.id: item for item in notes}
        note_ids = set(note_by_id)
        note_source_ids = note_ids | {item.sourceCardId for item in notes if item.sourceCardId}
        note_event_rows = self.repo.list_view_events_for_cards(note_source_ids)
        note_view_events = {
            note.id: note_event_rows.get(note.sourceCardId or note.id, [])
            for note in notes
        }
        showcases = self.repo.list_showcase_pages(owner_user_id)
        if mode == "property":
            showcases = [item for item in showcases if any(showcase_item.noteId in note_ids for showcase_item in item.items)]
        elif mode in {"groupbuy", "service"}:
            showcases = [item for item in showcases if any(showcase_item.noteId in note_ids for showcase_item in item.items)]
        showcase_ids = {item.id for item in showcases}
        showcase_event_rows = self.repo.list_showcase_events_for_showcases(showcase_ids)
        showcase_events = [
            event
            for showcase in showcases
            for event in showcase_event_rows.get(showcase.id, [])
            if event.ownerUserId == owner_user_id
            and (mode not in {"groupbuy", "service"} or not event.noteId or event.noteId in note_ids)
        ]
        actions_by_note = self.repo.list_customer_actions_for_notes(note_ids)
        actions = [
            action
            for rows in actions_by_note.values()
            for action in rows
            if action.ownerUserId == owner_user_id
        ]
        leads = self.repo.list_lead_reminders(owner_user_id)
        if mode == "property":
            projected_lead_ids = {
                str((action.projectionRefs or {}).get("leadReminderId") or "")
                for action in actions
                if (action.projectionRefs or {}).get("leadReminderId")
            }
            leads = [item for item in leads if item.id in projected_lead_ids or item.cardId in note_source_ids]
        elif mode in {"groupbuy", "service"}:
            leads = [item for item in leads if item.cardId in note_source_ids]
        return {
            "notes": notes,
            "noteById": note_by_id,
            "noteViewEvents": note_view_events,
            "showcaseById": {item.id: item for item in showcases},
            "showcaseIds": showcase_ids,
            "showcaseEvents": showcase_events,
            "actions": actions,
            "leads": leads,
        }

    def _resolve_customer_detail_direct(
        self,
        owner_user_id: str,
        target_values: list[str],
        mode: str | None,
    ) -> dict | None:
        sources = self._load_customer_detail_sources(owner_user_id, mode)
        matched_showcase_events = [
            event
            for event in sources["showcaseEvents"]
            if any(
                self._raw_customer_identity_matches(
                    owner_user_id,
                    target,
                    visitor_identity_id=event.visitorIdentityId,
                    viewer_user_id=event.viewerUserId,
                    anonymous_id=event.anonymousId,
                    fallback_id=event.id,
                )
                for target in target_values
            )
        ]
        matched_note_view_events: dict[str, list[ViewEvent]] = {}
        for note_id, events in sources["noteViewEvents"].items():
            matched = [
                event
                for event in events
                if any(
                    self._raw_customer_identity_matches(
                        owner_user_id,
                        target,
                        visitor_identity_id=event.visitorIdentityId,
                        viewer_user_id=event.viewerUserId,
                        anonymous_id=event.anonymousId,
                        fallback_id=event.id,
                    )
                    for target in target_values
                )
            ]
            if matched:
                matched_note_view_events[note_id] = matched
        matched_actions = [
            action
            for action in sources["actions"]
            if any(
                self._raw_customer_identity_matches(
                    owner_user_id,
                    target,
                    visitor_identity_id=action.visitorIdentityId,
                    viewer_user_id=action.viewerUserId,
                    anonymous_id=action.anonymousId,
                    fallback_id=action.id,
                )
                for target in target_values
            )
        ]
        matched_leads = []
        for lead in sources["leads"]:
            if any(str(target) == lead.id for target in target_values):
                matched_leads.append(lead)
                continue
            if any(
                self._raw_customer_identity_matches(
                    owner_user_id,
                    target,
                    visitor_identity_id=lead.visitorIdentityId,
                    viewer_user_id=lead.viewerUserId,
                    fallback_id=lead.id,
                )
                for target in target_values
            ):
                matched_leads.append(lead)

        if not matched_showcase_events and not matched_note_view_events and not matched_actions and not matched_leads:
            return None

        profiles = self._build_opportunity_profiles(
            owner_user_id,
            sources["noteById"],
            {note.id: note for note in sources["notes"] if note.sourceCardId},
            matched_showcase_events,
            matched_actions,
            matched_leads,
            matched_note_view_events,
        )
        profile = next(
            (
                item
                for item in profiles
                if any(self._customer_identity_matches(item, target) for target in target_values)
                or any(str(target) == item.get("visitorIdentityId") for target in target_values)
            ),
            None,
        )
        owner_lead = next((item for item in matched_leads if item.ownerUserId == owner_user_id), None)
        if not owner_lead and profile and profile.get("leadReminderId"):
            candidate = self.repo.get_lead_reminder(profile["leadReminderId"])
            if candidate and candidate.ownerUserId == owner_user_id:
                owner_lead = candidate
        if not profile and not owner_lead:
            return None
        if not profile:
            profile = {
                "id": owner_lead.visitorIdentityId or self._stable_visitor_identity_id(owner_user_id, owner_lead.viewerUserId, None, owner_lead.id),
                "visitorIdentityId": owner_lead.visitorIdentityId or self._stable_visitor_identity_id(owner_user_id, owner_lead.viewerUserId, None, owner_lead.id),
                "viewerUserId": owner_lead.viewerUserId,
                "anonymousId": "",
                "anonymous": False,
                "nickname": owner_lead.nickname,
                "avatarUrl": owner_lead.avatarUrl or "",
                "phone": owner_lead.customerPhone or "",
                "wechat": owner_lead.customerWechat or "",
                "email": owner_lead.customerEmail or "",
                "budgetText": owner_lead.budgetText or "",
                "customerTags": owner_lead.customerTags or [],
                "leadReminderId": owner_lead.id,
                "viewCount": owner_lead.viewCount,
                "noteIds": [],
                "noteTitles": [],
                "lastActivityAt": owner_lead.updatedAt or owner_lead.createdAt,
                "visitorIdentityType": "customer",
                "visitorIdentityLabel": "微信客户",
                "visitorIdentityGroup": "customer",
                "intentLevel": owner_lead.intentLevel or "待判断",
                "intentLabel": f"{owner_lead.intentLevel}意向" if owner_lead.intentLevel else "待判断",
                "intentExplanation": "已有客户跟进记录",
                "suggestedAction": "查看详情并决定是否跟进",
                "followupWindow": "可稍后跟进",
                "followupScript": "您好，我来跟进一下之前的资料。",
            }

        # A showcase-level view may not carry noteId because the visitor
        # opened the published page rather than a single material. Resolve
        # the page snapshot back to its owner-scoped notes so the detail page
        # can show the real source and ensure a follow-up record safely.
        matched_source_note_ids: list[str] = []

        def add_source_note_id(value: object) -> None:
            note_id = str(value or "").strip()
            if note_id and note_id not in matched_source_note_ids:
                matched_source_note_ids.append(note_id)

        for note_id in matched_note_view_events:
            add_source_note_id(note_id)
        for action in matched_actions:
            add_source_note_id(action.noteId)
        for lead in matched_leads:
            add_source_note_id(lead.cardId)
        for event in matched_showcase_events:
            add_source_note_id(event.noteId)
            if not event.noteId:
                showcase = sources["showcaseById"].get(event.showcaseId)
                for item in (showcase.items if showcase else []):
                    add_source_note_id(item.noteId)

        profile.setdefault("noteIds", [])
        profile.setdefault("noteTitles", [])
        for raw_note_id in matched_source_note_ids:
            note = sources["noteById"].get(raw_note_id) or self._find_note_by_lead_source(raw_note_id)
            if not note or note.ownerUserId != owner_user_id or note.status == "deleted":
                continue
            if note.id not in profile["noteIds"]:
                profile["noteIds"].append(note.id)
            if note.title and note.title not in profile["noteTitles"]:
                profile["noteTitles"].append(note.title)

        timeline_events = []
        for event in [*matched_showcase_events, *[item for rows in matched_note_view_events.values() for item in rows]]:
            timeline_events.append({"type": "view", "title": "查看资料", "createdAt": getattr(event, "createdAt", None) or getattr(event, "viewedAt", None)})
        for action in matched_actions:
            timeline_events.append({"type": "action", "title": action.actionLabel, "createdAt": action.createdAt})
        timeline_events = sorted(timeline_events, key=lambda item: item.get("createdAt") or "", reverse=True)[:12]
        return {
            "customer": profile,
            "timeline": {
                "customerId": profile.get("visitorIdentityId") or profile.get("id"),
                "displayName": profile.get("nickname") or "匿名访客",
                "identityType": profile.get("visitorIdentityType") or "customer",
                "phone": profile.get("phone") or "",
                "wechat": profile.get("wechat") or "",
                "email": profile.get("email") or "",
                "reason": profile.get("intentExplanation") or "有新的资料行为",
                "nextAction": profile.get("suggestedAction") or "查看详情并决定是否跟进",
                "events": timeline_events,
            },
            "lead": owner_lead,
        }

    def _resolve_customer_detail_from_lead(
        self,
        owner_user_id: str,
        customer_id: str,
        lead_id: str,
    ) -> dict | None:
        """Build a lead detail from one row without rebuilding the radar.

        Radar cards already carry the owner-scoped lead ID. Reading that row
        and its source note is the hot path for opening detail; the complete
        intelligence projection is reserved for legacy/no-lead routes.
        """
        lead = self.repo.get_lead_reminder(lead_id)
        if not lead or lead.ownerUserId != owner_user_id:
            return None
        target_aliases = self._customer_identity_aliases(customer_id)
        lead_aliases = set()
        for value in (lead.id, lead.viewerUserId, lead.visitorIdentityId):
            lead_aliases.update(self._customer_identity_aliases(value))
        if customer_id and not target_aliases.intersection(lead_aliases):
            return None

        note = self.repo.get_user_note(lead.cardId) or self._find_note_by_lead_source(lead.cardId)
        note_id = note.id if note else ""
        source_id = (note.sourceCardId if note else None) or note_id or lead.cardId
        known_viewer = self.repo.get_user(lead.viewerUserId) if lead.viewerUserId else None
        viewer_contacts = self._viewer_contact_fields(lead.viewerUserId) if known_viewer else {"phone": "", "wechat": "", "email": ""}
        identity_type = "customer" if known_viewer else "anonymous"
        visitor_identity_id = lead.visitorIdentityId or self._stable_visitor_identity_id(
            owner_user_id,
            lead.viewerUserId if known_viewer else None,
            None if known_viewer else lead.viewerUserId,
            lead.id,
        )
        display_name = lead.nickname or (known_viewer.nickname if known_viewer else "匿名访客")
        events = self.repo.list_view_events_for_card(
            source_id,
            viewer_user_id=lead.viewerUserId if known_viewer else None,
            anonymous_id=None if known_viewer else lead.viewerUserId,
            visitor_identity_id=lead.visitorIdentityId,
            limit=50,
        ) if source_id else []
        identity_targets = [lead.id, lead.viewerUserId, lead.visitorIdentityId]
        matched_events = [
            event for event in events
            if any(
                self._raw_customer_identity_matches(
                    owner_user_id,
                    target,
                    visitor_identity_id=event.visitorIdentityId,
                    viewer_user_id=event.viewerUserId,
                    anonymous_id=event.anonymousId,
                    fallback_id=event.id,
                )
                for target in identity_targets
                if target
            )
        ]
        actions = self.repo.list_customer_actions_for_note(
            note_id,
            viewer_user_id=lead.viewerUserId if known_viewer else None,
            anonymous_id=None if known_viewer else lead.viewerUserId,
            visitor_identity_id=lead.visitorIdentityId,
            limit=50,
        ) if note_id else []
        matched_actions = [
            action for action in actions
            if any(
                self._raw_customer_identity_matches(
                    owner_user_id,
                    target,
                    visitor_identity_id=action.visitorIdentityId,
                    viewer_user_id=action.viewerUserId,
                    anonymous_id=action.anonymousId,
                    fallback_id=action.id,
                )
                for target in identity_targets
                if target
            )
        ]
        note_ids = [note_id] if note_id else []
        note_titles = [note.title] if note and note.title else []
        timeline_events = [
            {"type": "view", "title": "查看资料", "createdAt": event.viewedAt}
            for event in matched_events
        ] + [
            {"type": "action", "title": action.actionLabel, "createdAt": action.createdAt}
            for action in matched_actions
        ]
        timeline_events.sort(key=lambda item: item.get("createdAt") or "", reverse=True)
        profile = {
            "id": visitor_identity_id,
            "visitorIdentityId": visitor_identity_id,
            "viewerUserId": lead.viewerUserId if known_viewer else "",
            "anonymousId": "" if known_viewer else lead.viewerUserId,
            "anonymous": not bool(known_viewer),
            "nickname": display_name,
            "avatarUrl": lead.avatarUrl or (known_viewer.avatarUrl if known_viewer else "") or "",
            "phone": lead.customerPhone or viewer_contacts["phone"] or "",
            "wechat": lead.customerWechat or viewer_contacts["wechat"] or "",
            "email": lead.customerEmail or viewer_contacts["email"] or "",
            "budgetText": lead.budgetText or "",
            "customerTags": lead.customerTags or [],
            "leadReminderId": lead.id,
            "viewCount": max(int(lead.viewCount or 0), len(matched_events)),
            "noteClickCount": sum(1 for action in matched_actions if action.actionKey == "note-click"),
            "noteIds": note_ids,
            "noteTitles": note_titles,
            "noteCoverUrls": [note.coverUrl] if note and note.coverUrl else [],
            "lastActivityAt": lead.lastViewedAt or lead.updatedAt or lead.createdAt,
            "visitorIdentityType": identity_type,
            "visitorIdentityLabel": "微信客户" if known_viewer else "匿名访客",
            "visitorIdentityGroup": "customer" if known_viewer else "anonymous",
            "intentLevel": lead.intentLevel or "待判断",
            "intentLabel": f"{lead.intentLevel}意向" if lead.intentLevel else "待判断",
            "intentExplanation": "已有客户跟进记录",
            "suggestedAction": "查看详情并决定下一步",
            "followupWindow": "可立即跟进",
            "followupScript": "您好，我来跟进一下之前的资料。",
        }
        return {
            "customer": profile,
            "timeline": {
                "customerId": visitor_identity_id,
                "displayName": display_name,
                "identityType": identity_type,
                "phone": profile["phone"],
                "wechat": profile["wechat"],
                "email": profile["email"],
                "reason": profile["intentExplanation"],
                "nextAction": profile["suggestedAction"],
                "events": timeline_events[:12],
            },
            "lead": lead,
        }

    def get_customer_detail(
        self,
        owner_user_id: str,
        requester_user_id: str,
        customer_id: str,
        mode: str | None = None,
        lead_id: str | None = None,
    ) -> dict:
        """Return one owner-scoped customer projection for the detail page."""
        if not requester_user_id:
            raise HTTPException(status_code=401, detail="请先登录后查看客户详情")
        if requester_user_id != owner_user_id:
            raise HTTPException(status_code=403, detail="仅工作台拥有者可查看客户详情")
        # Older mini-program builds encoded the route once and the API helper
        # encoded it again. FastAPI removes only the outer query encoding, so
        # normalize the remaining layer before matching owner-scoped IDs.
        target_id = unquote(str(customer_id or "").strip())
        requested_lead_id = unquote(str(lead_id or "").strip())
        if not target_id and not requested_lead_id:
            raise HTTPException(status_code=400, detail="客户身份不能为空")
        target_values = [value for value in (target_id, requested_lead_id) if value]

        if requested_lead_id:
            # A radar card already carries a concrete lead row. Resolve the
            # access decision and this row directly; do not rebuild every
            # note/event/showcase projection just to open one customer.
            membership = self.get_membership_status(owner_user_id)
            payment_required = bool(membership.get("paymentRequired", True))
            if membership.get("featureEnabled") is False:
                return {
                    "featureEnabled": False,
                    "paymentRequired": payment_required,
                    "locked": True,
                    "membership": membership,
                    "messageSummary": {"hasMessages": False, "unreadCount": 0, "threadCount": 0, "latestThreadId": "", "latestMessage": None, "messages": []},
                }
            if payment_required and membership.get("active") is not True:
                return {
                    "featureEnabled": True,
                    "paymentRequired": True,
                    "locked": True,
                    "membership": membership,
                    "messageSummary": {"hasMessages": False, "unreadCount": 0, "threadCount": 0, "latestThreadId": "", "latestMessage": None, "messages": []},
                }
            lead_candidate = self.repo.get_lead_reminder(requested_lead_id)
            if lead_candidate and lead_candidate.ownerUserId == owner_user_id:
                candidate_aliases = set()
                for value in (lead_candidate.id, lead_candidate.viewerUserId, lead_candidate.visitorIdentityId):
                    candidate_aliases.update(self._customer_identity_aliases(value))
                if target_id and not self._customer_identity_aliases(target_id).intersection(candidate_aliases):
                    raise HTTPException(status_code=404, detail="客户详情不存在")
                direct_lead = self._resolve_customer_detail_from_lead(owner_user_id, target_id, requested_lead_id)
                if direct_lead:
                    return {
                        "featureEnabled": True,
                        "paymentRequired": payment_required,
                        "locked": False,
                        "membership": membership,
                        "customer": direct_lead["customer"],
                        "timeline": direct_lead["timeline"],
                        "lead": direct_lead["lead"].model_dump(),
                        "messageSummary": self._build_customer_message_summary(owner_user_id, direct_lead["customer"]),
                    }

        intelligence = self.get_customer_intelligence(owner_user_id, requester_user_id, mode)
        if intelligence.get("locked") is not False:
            return intelligence

        direct = self._resolve_customer_detail_direct(owner_user_id, target_values, mode)
        if direct:
            message_summary = self._build_customer_message_summary(owner_user_id, direct["customer"])
            return {
                "featureEnabled": True,
                "paymentRequired": bool(intelligence.get("paymentRequired", True)),
                "locked": False,
                "membership": intelligence.get("membership") or {},
                "customer": direct["customer"],
                "timeline": direct["timeline"],
                "lead": direct["lead"].model_dump() if direct.get("lead") else None,
                "messageSummary": message_summary,
            }

        dashboard = intelligence.get("dashboard") or {}
        timelines = intelligence.get("customerTimelines") or []
        target_values = [value for value in (target_id, requested_lead_id) if value]
        profile = None
        for source in ("radarProfiles", "visitorProfiles", "followingProfiles", "abandonedProfiles", "opportunityAlerts"):
            for item in dashboard.get(source) or []:
                if any(self._customer_identity_matches(item, value) for value in target_values):
                    profile = item
                    break
            if profile:
                break

        owner_lead = None
        if requested_lead_id:
            candidate = self.repo.get_lead_reminder(requested_lead_id)
            candidate_aliases = self._customer_identity_aliases(candidate.viewerUserId) if candidate else set()
            candidate_aliases.update(self._customer_identity_aliases(candidate.id) if candidate else set())
            target_aliases = self._customer_identity_aliases(target_id)
            if candidate and candidate.ownerUserId == owner_user_id and (not target_id or target_aliases.intersection(candidate_aliases)):
                owner_lead = candidate
        if not owner_lead and profile and profile.get("leadReminderId"):
            candidate = self.repo.get_lead_reminder(profile.get("leadReminderId"))
            if candidate and candidate.ownerUserId == owner_user_id:
                owner_lead = candidate

        timeline = next(
            (
                item
                for item in timelines
                if any(self._customer_identity_matches(item, value) for value in target_values)
            ),
            {},
        )
        if not timeline and profile:
            timeline = next(
                (
                    item
                    for item in timelines
                    if any(
                        self._customer_identity_matches(item, value)
                        for value in (
                            profile.get("id"),
                            profile.get("viewerUserId"),
                            profile.get("anonymousId"),
                        )
                        if value
                    )
                ),
                {},
            )

        if not profile and not owner_lead:
            raise HTTPException(status_code=404, detail="客户详情不存在")

        if not profile:
            profile = {
                "id": self._dashboard_identity_key(owner_lead.viewerUserId),
                "visitorIdentityId": owner_lead.visitorIdentityId or self._stable_visitor_identity_id(owner_user_id, owner_lead.viewerUserId, None, owner_lead.id),
                "viewerUserId": owner_lead.viewerUserId,
                "anonymousId": "",
                "anonymous": False,
                "nickname": owner_lead.nickname,
                "avatarUrl": owner_lead.avatarUrl or "",
                "phone": owner_lead.customerPhone or "",
                "wechat": owner_lead.customerWechat or "",
                "email": owner_lead.customerEmail or "",
                "budgetText": owner_lead.budgetText or "",
                "customerTags": owner_lead.customerTags or [],
                "leadReminderId": owner_lead.id,
                "viewCount": owner_lead.viewCount,
                "noteIds": [],
                "noteTitles": [],
                "lastActivityAt": owner_lead.updatedAt or owner_lead.createdAt,
                "visitorIdentityType": "customer",
                "visitorIdentityLabel": "微信客户",
                "visitorIdentityGroup": "customer",
                "intentLevel": owner_lead.intentLevel or "待判断",
                "intentLabel": f"{owner_lead.intentLevel}意向" if owner_lead.intentLevel else "待判断",
                "intentExplanation": "已有客户跟进记录",
                "suggestedAction": "查看详情并决定是否跟进",
                "followupWindow": "可稍后跟进",
                "followupScript": "您好，我来跟进一下之前的资料。",
            }

        message_summary = self._build_customer_message_summary(owner_user_id, profile)
        return {
            "featureEnabled": True,
            "paymentRequired": bool(intelligence.get("paymentRequired", True)),
            "locked": False,
            "membership": intelligence.get("membership") or {},
            "customer": profile,
            "timeline": timeline,
            "lead": owner_lead.model_dump() if owner_lead else None,
            "messageSummary": message_summary,
        }

    def _build_customer_message_summary(self, owner_user_id: str, profile: dict) -> dict:
        """Attach only securely attributable owner/buyer messages to detail.

        Anonymous radar identities have no stable buyer account and must not
        be matched to a message by nickname, phone, text, or similar guesses.
        """
        if str(profile.get("visitorIdentityType") or "").strip() != "customer":
            return {"hasMessages": False, "unreadCount": 0, "threadCount": 0, "latestThreadId": "", "latestMessage": None, "messages": []}
        viewer_user_id = str(profile.get("viewerUserId") or "").strip()
        if not viewer_user_id or viewer_user_id == owner_user_id or not self.repo.get_user(viewer_user_id):
            return {"hasMessages": False, "unreadCount": 0, "threadCount": 0, "latestThreadId": "", "latestMessage": None, "messages": []}

        summaries: list[dict] = []
        unread_count = 0
        threads = [
            thread
            for thread in self.repo.list_message_threads_for_user(owner_user_id)
            if thread.status == "active"
            and thread.ownerUserId == owner_user_id
            and thread.buyerUserId == viewer_user_id
        ]
        for thread in threads:
            unread_count += int((thread.unreadByUser or {}).get(owner_user_id, 0))
            note = self.repo.get_user_note(thread.noteId)
            for record in self.repo.list_message_records_for_thread(thread.id)[-3:]:
                summaries.append({
                    "id": record.id,
                    "threadId": thread.id,
                    "content": record.content,
                    "createdAt": record.createdAt,
                    "senderUserId": record.senderUserId,
                    "senderRole": "owner" if record.senderUserId == owner_user_id else "customer",
                    "noteTitle": note.title if note else thread.title,
                })
        summaries.sort(key=lambda item: item.get("createdAt") or "", reverse=True)
        latest = summaries[0] if summaries else None
        return {
            "hasMessages": bool(summaries),
            "unreadCount": unread_count,
            "threadCount": len(threads),
            "latestThreadId": latest.get("threadId", "") if latest else "",
            "latestMessage": latest,
            "messages": summaries[:3],
        }

    def _masked_signal_preview(self, dashboard: dict) -> list[dict]:
        rows = []
        for item in (dashboard.get("visitorProfiles") or [])[:3]:
            rows.append({
                "identityLabel": "某位访客",
                "signal": item.get("intentExplanation") or item.get("reasonText") or "查看了你的资料",
                "viewCount": int(item.get("viewCount") or 0),
                "noteCount": len(item.get("noteIds") or []),
                "hasContact": bool(item.get("displayPhone") or item.get("displayWechat")),
            })
        return rows

    def _customer_timeline_rows(self, dashboard: dict) -> list[dict]:
        rows = []
        timeline_sources = (
            (dashboard.get("visitorProfiles") or [])
            + (dashboard.get("followingProfiles") or [])
            + (dashboard.get("abandonedProfiles") or [])
        )
        for item in timeline_sources:
            events = []
            if item.get("lastViewedAt"):
                events.append({"type": "view", "title": "最近查看资料", "createdAt": item.get("lastViewedAt")})
            rows.append({
                "customerId": item.get("visitorIdentityId") or item.get("id") or item.get("viewerUserId") or item.get("anonymousId"),
                "displayName": item.get("nickname") or "匿名访客",
                "identityType": item.get("visitorIdentityType") or "customer",
                "phone": item.get("phone") or item.get("displayPhone"),
                "wechat": item.get("wechat") or item.get("displayWechat"),
                "email": item.get("email") or item.get("displayEmail"),
                "reason": item.get("intentExplanation") or item.get("reasonText") or "有新的资料行为",
                "nextAction": item.get("suggestedAction") or "查看详情并决定是否跟进",
                "events": sorted(events, key=lambda row: row.get("createdAt") or "", reverse=True),
            })
        return rows

    def _invite_code_for_user(self, user_id: str) -> str:
        signature = hmac.new(
            (settings.h5_auth_secret or "teamBuy-h5-dev-secret").encode("utf-8"),
            user_id.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()[:12]
        body = base64.urlsafe_b64encode(user_id.encode("utf-8")).decode("ascii").rstrip("=")
        return f"REF-{body}-{signature}"

    def _user_id_from_invite_code(self, invite_code: str) -> str:
        text = str(invite_code or "").strip()
        parts = text.split("-")
        if len(parts) != 3 or parts[0] != "REF":
            raise HTTPException(status_code=400, detail="邀请码无效")
        try:
            user_id = base64.urlsafe_b64decode(self._pad_h5_ticket_body(parts[1])).decode("utf-8")
        except Exception as exc:
            raise HTTPException(status_code=400, detail="邀请码无效") from exc
        if not hmac.compare_digest(self._invite_code_for_user(user_id), text):
            raise HTTPException(status_code=400, detail="邀请码无效")
        return user_id

    def bind_referral(self, invitee_user_id: str, invite_code: str) -> dict:
        invitee = self.repo.get_user(invitee_user_id)
        if not invitee:
            raise HTTPException(status_code=404, detail="被邀请用户不存在")
        inviter_user_id = self._user_id_from_invite_code(invite_code)
        if inviter_user_id == invitee_user_id:
            raise HTTPException(status_code=400, detail="不能邀请自己")
        if not self.repo.get_user(inviter_user_id):
            raise HTTPException(status_code=404, detail="邀请人不存在")
        state = self._load()
        existing = next((item for item in state.referral_relations if item.inviteeUserId == invitee_user_id), None)
        if existing:
            if existing.inviterUserId != inviter_user_id:
                raise HTTPException(status_code=409, detail="邀请关系已经绑定")
            return {"relation": existing.model_dump(), "duplicate": True}
        self._assert_referral_has_no_cycle(state, inviter_user_id, invitee_user_id)
        now = now_iso()
        relation = ReferralRelation(
            id=new_id("referral"),
            inviterUserId=inviter_user_id,
            inviteeUserId=invitee_user_id,
            createdAt=now,
            updatedAt=now,
        )
        state.referral_relations.append(relation)
        self._save(state)
        return {"relation": relation.model_dump(), "duplicate": False}

    def _ensure_share_referral(
        self,
        state: AppState,
        invitee_user_id: str,
        inviter_user_id: str,
        source: str = "share_link",
    ) -> tuple[ReferralRelation, bool, bool]:
        """Create a first-touch share attribution without blocking an existing one.

        The relation is deliberately recorded even when the inviter is not a paid
        member yet. Membership is checked when the invitee's payment is confirmed,
        so a later inviter renewal can qualify later payments without retroactive
        rewards.
        """
        existing = next((item for item in state.referral_relations if item.inviteeUserId == invitee_user_id), None)
        if existing:
            return existing, True, existing.inviterUserId != inviter_user_id
        self._assert_referral_has_no_cycle(state, inviter_user_id, invitee_user_id)
        now = now_iso()
        relation = ReferralRelation(
            id=new_id("referral_relation"),
            inviterUserId=inviter_user_id,
            inviteeUserId=invitee_user_id,
            source=source,
            createdAt=now,
            updatedAt=now,
        )
        state.referral_relations.append(relation)
        return relation, False, False

    def bind_referral_from_share(
        self,
        invitee_user_id: str,
        inviter_user_id: str,
        source: str = "share_link",
    ) -> dict:
        invitee_user_id = str(invitee_user_id or "").strip()
        inviter_user_id = str(inviter_user_id or "").strip()
        if not invitee_user_id or not inviter_user_id:
            raise HTTPException(status_code=400, detail="分享归因缺少用户信息")
        if invitee_user_id == inviter_user_id:
            raise HTTPException(status_code=400, detail="不能归因给自己")
        if not self.repo.get_user(invitee_user_id):
            raise HTTPException(status_code=404, detail="被分享用户不存在")
        if not self.repo.get_user(inviter_user_id):
            raise HTTPException(status_code=404, detail="分享者不存在")
        state = self._load()
        relation, duplicate, locked = self._ensure_share_referral(
            state,
            invitee_user_id,
            inviter_user_id,
            "share_link" if source != "same_style" else "same_style",
        )
        if not duplicate:
            self._save(state)
        return {"relation": relation.model_dump(), "duplicate": duplicate, "locked": locked}

    def _assert_referral_has_no_cycle(self, state: AppState, inviter_user_id: str, invitee_user_id: str) -> None:
        parent_by_invitee = {item.inviteeUserId: item.inviterUserId for item in state.referral_relations}
        current = inviter_user_id
        visited: set[str] = set()
        while current and current not in visited:
            if current == invitee_user_id:
                raise HTTPException(status_code=400, detail="不能形成循环邀请")
            visited.add(current)
            current = parent_by_invitee.get(current, "")

    def referral_withdrawal_min_amount_fen(self) -> int:
        configured = (
            settings.wechat_transfer_min_amount_fen
            if settings.app_env.lower() == "production"
            else settings.wechat_transfer_test_min_amount_fen
        )
        return max(1, int(configured))

    @staticmethod
    def referral_withdrawal_daily_limit() -> int:
        return max(1, int(settings.wechat_transfer_daily_withdrawal_limit))

    def referral_withdrawal_rules(self) -> dict:
        return {
            "minimumWithdrawalFen": self.referral_withdrawal_min_amount_fen(),
            "dailyWithdrawalLimit": self.referral_withdrawal_daily_limit(),
            "withdrawalWindowText": "每日 00:00–24:00 均可提交提现申请",
            "reviewTimeText": "提交后进入平台审核，审核通过后发起微信转账",
            "arrivalTimeText": "以微信实际到账时间为准，用户确认后基本秒到",
            "feeText": "当前提现手续费为 0 元",
            "failureText": "转账失败或撤销成功后，冻结佣金会退回可提现余额",
        }

    @staticmethod
    def _referral_reward_breakdown(reward: ReferralReward) -> dict[str, int]:
        """Return ledger portions while remaining compatible with old rows."""
        amount = max(0, int(reward.amountFen or 0))
        withdrawn = max(0, int(reward.withdrawnFen or 0))
        reserved = max(0, int(reward.reservedFen or 0))
        if reward.status == "withdrawn" and withdrawn == 0:
            withdrawn = amount
        elif reward.status == "reserved" and reserved == 0:
            reserved = max(0, amount - withdrawn)
        reserved = min(reserved, max(0, amount - withdrawn))
        available = max(0, amount - withdrawn - reserved) if reward.status in {"available", "reserved"} else 0
        return {
            "available": available,
            "reserved": reserved,
            "withdrawn": withdrawn,
            "total": amount,
        }

    @classmethod
    def _referral_reward_available_fen(cls, reward: ReferralReward) -> int:
        return cls._referral_reward_breakdown(reward)["available"]

    @classmethod
    def _referral_reward_reserved_fen(cls, reward: ReferralReward) -> int:
        return cls._referral_reward_breakdown(reward)["reserved"]

    @classmethod
    def _referral_reward_withdrawn_fen(cls, reward: ReferralReward) -> int:
        return cls._referral_reward_breakdown(reward)["withdrawn"]

    @staticmethod
    def _referral_withdrawal_allocation(withdrawal: ReferralWithdrawal, reward_id: str, reward_amount_fen: int) -> int:
        if withdrawal.rewardAllocations:
            return max(0, int(withdrawal.rewardAllocations.get(reward_id, 0)))
        return max(0, int(reward_amount_fen)) if reward_id in withdrawal.rewardIds else 0

    @classmethod
    def _release_referral_withdrawal_rewards(
        cls,
        state: AppState,
        withdrawal: ReferralWithdrawal,
        now: str,
    ) -> None:
        for reward in state.referral_rewards:
            allocation = cls._referral_withdrawal_allocation(withdrawal, reward.id, reward.amountFen)
            if not allocation:
                continue
            reserved = cls._referral_reward_reserved_fen(reward)
            reward.reservedFen = max(0, reserved - allocation)
            breakdown = cls._referral_reward_breakdown(reward)
            if reward.status != "revoked":
                reward.status = "reserved" if reward.reservedFen else (
                    "withdrawn" if breakdown["withdrawn"] >= breakdown["total"] else "available"
                )
            reward.updatedAt = now

    def _referral_withdrawals_today(self, state: AppState, user_id: str) -> int:
        today = datetime.now(tz=SHANGHAI).date().isoformat()
        counted_statuses = {"pending", "approved", "waiting_user_confirm", "processing", "paid"}
        count = 0
        for item in state.referral_withdrawals:
            if item.userId != user_id or item.status not in counted_statuses:
                continue
            try:
                if date_key(item.createdAt) == today:
                    count += 1
            except (TypeError, ValueError, OverflowError):
                continue
        return count

    @staticmethod
    def _referral_withdrawal_out_bill_no(withdrawal_id: str) -> str:
        # WeChat only accepts alphanumeric merchant bill numbers.  Keeping this
        # deterministic gives retries/query operations one stable idempotency key.
        return f"wd{hashlib.sha256(withdrawal_id.encode('utf-8')).hexdigest()[:30]}"

    def get_referral_center(self, user_id: str) -> dict:
        self.require_customer_info_chain_enabled()
        state = self._load()
        users_by_id = {item.id: item for item in state.users}
        if user_id not in users_by_id:
            raise HTTPException(status_code=404, detail="用户不存在")
        relations = [item for item in state.referral_relations if item.inviterUserId == user_id]
        rewards = sorted([item for item in state.referral_rewards if item.inviterUserId == user_id], key=lambda item: item.createdAt, reverse=True)
        rewards_by_invitee: dict[str, list[ReferralReward]] = {}
        for item in rewards:
            rewards_by_invitee.setdefault(item.inviteeUserId, []).append(item)
        totals = {status: 0 for status in ["pending", "available", "reserved", "withdrawn", "revoked"]}
        for item in rewards:
            if item.status in {"pending", "revoked"}:
                totals[item.status] += item.amountFen
                continue
            breakdown = self._referral_reward_breakdown(item)
            totals["available"] += breakdown["available"]
            totals["reserved"] += breakdown["reserved"]
            totals["withdrawn"] += breakdown["withdrawn"]
        paid_user_ids = {
            item.inviteeUserId for item in rewards if item.status in {"available", "reserved", "withdrawn"}
        }
        direct_referrals = []
        for relation in sorted(relations, key=lambda item: (item.createdAt, item.id), reverse=True):
            invitee = users_by_id.get(relation.inviteeUserId)
            invitee_rewards = rewards_by_invitee.get(relation.inviteeUserId, [])
            pending_rewards = [item for item in invitee_rewards if item.status == "pending"]
            paid_rewards = [item for item in invitee_rewards if item.status in {"available", "reserved", "withdrawn"}]
            revoked_rewards = [item for item in invitee_rewards if item.status == "revoked"]
            latest_reward = invitee_rewards[0] if invitee_rewards else None
            if paid_rewards:
                relation_status = "paid"
                reward_status = latest_reward.status if latest_reward else "pending"
                reward_amount_fen = sum(max(0, int(item.amountFen or 0)) for item in paid_rewards)
            elif pending_rewards:
                relation_status = "pending"
                reward_status = latest_reward.status if latest_reward else "pending"
                reward_amount_fen = sum(max(0, int(item.amountFen or 0)) for item in pending_rewards)
            elif revoked_rewards:
                relation_status = "revoked"
                reward_status = "revoked"
                reward_amount_fen = sum(max(0, int(item.amountFen or 0)) for item in revoked_rewards)
            else:
                relation_status = "bound"
                reward_status = None
                reward_amount_fen = 0
            direct_referrals.append(
                {
                    "id": relation.id,
                    "nickname": mask_nickname(invitee.nickname) if invitee and invitee.nickname else "好友",
                    "createdAt": relation.createdAt,
                    "source": relation.source,
                    "relationStatus": relation_status,
                    "rewardStatus": reward_status,
                    "rewardAmountFen": reward_amount_fen,
                }
            )
        reward_rows = []
        for item in rewards:
            invitee = users_by_id.get(item.inviteeUserId)
            reward_rows.append(
                {
                    **item.model_dump(),
                    "inviteeNickname": mask_nickname(invitee.nickname) if invitee and invitee.nickname else "直接推广好友",
                }
            )
        return {
            "inviteCode": self._invite_code_for_user(user_id),
            "attributionMode": "share_link",
            "membershipRequired": True,
            "eligibleForRewards": self._is_paid_customer_member(user_id),
            "rewardEligibilityText": "好友付费时，你必须仍是有效会员；会员到期期间不产生该笔奖励。",
            "inviteeCount": len(relations),
            "paidInviteeCount": len(paid_user_ids),
            "rewardRatio": 0.5,
            "feeFen": 0,
            "minimumWithdrawalFen": self.referral_withdrawal_min_amount_fen(),
            "dailyWithdrawalLimit": self.referral_withdrawal_daily_limit(),
            "withdrawalRules": self.referral_withdrawal_rules(),
            "merchantTransferMchId": settings.wechat_pay_mch_id,
            "totals": totals,
            "rewards": reward_rows,
            "directReferrals": direct_referrals,
            "withdrawals": sorted(
                [item.model_dump() for item in state.referral_withdrawals if item.userId == user_id],
                key=lambda item: (item.get("createdAt") or "", item.get("id") or ""),
                reverse=True,
            ),
            "secondLevelRewardEnabled": False,
        }

    def create_referral_withdrawal(self, user_id: str, amount_fen: int) -> dict:
        state = self._load()
        minimum_amount_fen = self.referral_withdrawal_min_amount_fen()
        if amount_fen < minimum_amount_fen:
            raise HTTPException(
                status_code=400,
                detail=f"最低提现金额为 {minimum_amount_fen / 100:.2f} 元",
            )
        daily_limit = self.referral_withdrawal_daily_limit()
        if self._referral_withdrawals_today(state, user_id) >= daily_limit:
            raise HTTPException(status_code=400, detail=f"每日最多提现 {daily_limit} 次，请次日再试")
        available = sorted(
            [
                item for item in state.referral_rewards
                if item.inviterUserId == user_id
                and self._referral_reward_available_fen(item) > 0
            ],
            key=lambda item: item.createdAt,
        )
        if amount_fen <= 0 or sum(self._referral_reward_available_fen(item) for item in available) < amount_fen:
            raise HTTPException(status_code=400, detail="可提现金额不足")
        selected = []
        allocations: dict[str, int] = {}
        selected_total = 0
        for item in available:
            if selected_total >= amount_fen:
                break
            allocation = min(self._referral_reward_available_fen(item), amount_fen - selected_total)
            selected.append(item)
            allocations[item.id] = allocation
            selected_total += allocation
        now = now_iso()
        withdrawal = ReferralWithdrawal(
            id=new_id("withdrawal"),
            userId=user_id,
            amountFen=amount_fen,
            rewardIds=[item.id for item in selected],
            rewardAllocations=allocations,
            createdAt=now,
            updatedAt=now,
        )
        for item in selected:
            item.reservedFen = self._referral_reward_reserved_fen(item) + allocations[item.id]
            item.status = "reserved"
            item.updatedAt = now
        state.referral_withdrawals.append(withdrawal)
        self._save(state)
        return withdrawal.model_dump()

    def list_referral_withdrawals(self, status: str | None = None) -> list[dict]:
        state = self._load()
        user_labels = {item.id: item.nickname or item.id for item in state.users}
        rows = [
            item for item in state.referral_withdrawals
            if not status or item.status == status
        ]
        rows.sort(key=lambda item: (item.createdAt, item.id), reverse=True)
        return [
            {
                **item.model_dump(),
                "userNickname": user_labels.get(item.userId, item.userId),
            }
            for item in rows
        ]

    def _mark_referral_withdrawal_paid(
        self,
        state: AppState,
        withdrawal: ReferralWithdrawal,
        transfer: dict,
        now: str,
    ) -> None:
        withdrawal.status = "paid"
        withdrawal.paidAt = now
        withdrawal.transferState = "SUCCESS"
        withdrawal.transferBillNo = str(transfer.get("transfer_bill_no") or "").strip() or withdrawal.transferBillNo
        withdrawal.failureReason = None
        withdrawal.updatedAt = now
        for reward in state.referral_rewards:
            allocation = self._referral_withdrawal_allocation(withdrawal, reward.id, reward.amountFen)
            if not allocation:
                continue
            reserved = self._referral_reward_reserved_fen(reward)
            reward.reservedFen = max(0, reserved - allocation)
            reward.withdrawnFen = self._referral_reward_withdrawn_fen(reward) + allocation
            breakdown = self._referral_reward_breakdown(reward)
            reward.status = "withdrawn" if breakdown["withdrawn"] >= breakdown["total"] else (
                "reserved" if reward.reservedFen else "available"
            )
            if reward.status == "withdrawn":
                reward.withdrawnAt = now
            reward.updatedAt = now

    def approve_referral_withdrawal(self, withdrawal_id: str) -> dict:
        state = self._load()
        withdrawal = next((item for item in state.referral_withdrawals if item.id == withdrawal_id), None)
        if not withdrawal:
            raise HTTPException(status_code=404, detail="提现记录不存在")
        if withdrawal.status in {"paid", "waiting_user_confirm", "processing"}:
            return withdrawal.model_dump()
        if withdrawal.status != "pending":
            raise HTTPException(status_code=409, detail="当前提现记录不能审核发起")
        if withdrawal.amountFen < self.referral_withdrawal_min_amount_fen():
            raise HTTPException(status_code=400, detail="提现金额低于当前环境最低提现金额")
        user = self.repo.get_user(withdrawal.userId)
        if not user:
            raise HTTPException(status_code=404, detail="提现用户不存在")
        rewards = [item for item in state.referral_rewards if item.id in withdrawal.rewardIds]
        if len(rewards) != len(withdrawal.rewardIds) or any(item.status != "reserved" for item in rewards):
            raise HTTPException(status_code=409, detail="提现奖励已失效或未完成预占")

        out_bill_no = withdrawal.outBillNo or self._referral_withdrawal_out_bill_no(withdrawal.id)
        transfer = WechatPayClient().create_merchant_transfer(
            openid=user.openid,
            out_bill_no=out_bill_no,
            amount_fen=withdrawal.amountFen,
            transfer_remark="推广佣金",
            job_type="推广用户",
            reward_description="会员推广佣金",
        )
        transfer_state = str(transfer.get("state") or "").strip().upper()
        if not transfer_state:
            raise WechatPayError("微信商家转账未返回单据状态")
        now = now_iso()
        withdrawal.reviewedAt = now
        withdrawal.outBillNo = out_bill_no
        withdrawal.transferBillNo = str(transfer.get("transfer_bill_no") or "").strip() or None
        withdrawal.transferState = transfer_state
        withdrawal.packageInfo = str(transfer.get("package_info") or "").strip() or None
        withdrawal.updatedAt = now
        if transfer_state == "SUCCESS":
            self._mark_referral_withdrawal_paid(state, withdrawal, transfer, now)
        elif transfer_state in {"FAIL", "CANCELLED"}:
            withdrawal.status = "cancelled" if transfer_state == "CANCELLED" else "failed"
            withdrawal.failureReason = str(transfer.get("fail_reason") or "微信转账未成功")
            self._release_referral_withdrawal_rewards(state, withdrawal, now)
        elif transfer_state == "WAIT_USER_CONFIRM":
            withdrawal.status = "waiting_user_confirm"
        else:
            withdrawal.status = "processing"
        self._save(state)
        return withdrawal.model_dump()

    def query_referral_withdrawal(self, withdrawal_id: str) -> dict:
        state = self._load()
        withdrawal = next((item for item in state.referral_withdrawals if item.id == withdrawal_id), None)
        if not withdrawal:
            raise HTTPException(status_code=404, detail="提现记录不存在")
        if not withdrawal.outBillNo:
            raise HTTPException(status_code=409, detail="提现尚未发起微信转账，无需查单")
        transfer = WechatPayClient().query_merchant_transfer(out_bill_no=withdrawal.outBillNo)
        result = self.handle_wechat_transfer_notification(transfer)
        result["source"] = "wechat_query"
        return result

    def settle_referral_withdrawal_manually(
        self,
        withdrawal_id: str,
        note: str = "已核实微信到账",
    ) -> dict:
        """Close a legacy withdrawal only after an operator verifies arrival.

        Older production rows may have been paid before the merchant-transfer
        bill number/state machine was deployed. They cannot be reconciled by
        WeChat query, so this is an explicit, audited operator path rather
        than an automatic status guess.
        """
        state = self._load()
        withdrawal = next((item for item in state.referral_withdrawals if item.id == withdrawal_id), None)
        if not withdrawal:
            raise HTTPException(status_code=404, detail="提现记录不存在")
        if withdrawal.status == "paid":
            return {"withdrawal": withdrawal.model_dump(), "duplicate": True, "source": "manual"}
        if withdrawal.status in {"failed", "cancelled", "rejected"}:
            raise HTTPException(status_code=409, detail="失败、撤销或拒绝的提现不能人工标记到账")
        now = now_iso()
        withdrawal.reviewedAt = withdrawal.reviewedAt or now
        withdrawal.settlementSource = "manual"
        withdrawal.settlementNote = str(note or "已核实微信到账")[:200]
        self._mark_referral_withdrawal_paid(
            state,
            withdrawal,
            {"transfer_bill_no": withdrawal.transferBillNo},
            now,
        )
        self._save(state)
        return {"withdrawal": withdrawal.model_dump(), "duplicate": False, "source": "manual"}

    def cancel_referral_withdrawal(self, withdrawal_id: str, reason: str = "运营人工撤销") -> dict:
        state = self._load()
        withdrawal = next((item for item in state.referral_withdrawals if item.id == withdrawal_id), None)
        if not withdrawal:
            raise HTTPException(status_code=404, detail="提现记录不存在")
        if withdrawal.status in {"paid", "failed", "cancelled", "rejected"}:
            return {"withdrawal": withdrawal.model_dump(), "duplicate": True}
        now = now_iso()
        if withdrawal.status == "pending":
            withdrawal.status = "cancelled"
            withdrawal.transferState = "CANCELLED"
            withdrawal.failureReason = str(reason or "运营人工撤销")[:200]
            withdrawal.updatedAt = now
            self._release_referral_withdrawal_rewards(state, withdrawal, now)
            self._save(state)
            return {"withdrawal": withdrawal.model_dump(), "duplicate": False, "source": "local_cancel"}
        if not withdrawal.outBillNo:
            raise HTTPException(status_code=409, detail="提现缺少微信商户单号，不能撤销")
        if withdrawal.transferState in {"SUCCESS", "FAIL", "CANCELLED"}:
            return {"withdrawal": withdrawal.model_dump(), "duplicate": True}
        if withdrawal.transferState == "CANCELING":
            return {"withdrawal": withdrawal.model_dump(), "duplicate": True}
        if withdrawal.transferState == "TRANSFERING":
            raise HTTPException(status_code=409, detail="用户已确认收款，当前不能撤销")
        transfer = WechatPayClient().cancel_merchant_transfer(out_bill_no=withdrawal.outBillNo)
        if reason:
            transfer = {**transfer, "fail_reason": str(reason)[:200]}
        result = self.handle_wechat_transfer_notification(transfer)
        result["source"] = "wechat_cancel"
        return result

    def handle_wechat_transfer_notification(self, transfer: dict) -> dict:
        out_bill_no = str(transfer.get("out_bill_no") or "").strip()
        if not out_bill_no:
            raise HTTPException(status_code=400, detail="微信转账回调缺少商户单号")
        state = self._load()
        withdrawal = next(
            (item for item in state.referral_withdrawals if item.outBillNo == out_bill_no),
            None,
        )
        if not withdrawal:
            return {"ignored": True, "outBillNo": out_bill_no}
        transfer_amount = transfer.get("transfer_amount")
        if transfer_amount is not None and int(transfer_amount) != withdrawal.amountFen:
            raise HTTPException(status_code=409, detail="微信转账回调金额不一致")
        user = self.repo.get_user(withdrawal.userId)
        callback_openid = str(transfer.get("openid") or "").strip()
        if user and callback_openid and callback_openid != user.openid:
            raise HTTPException(status_code=409, detail="微信转账回调用户不一致")
        transfer_state = str(transfer.get("state") or "").strip().upper()
        now = now_iso()
        withdrawal.transferState = transfer_state or withdrawal.transferState
        withdrawal.transferBillNo = str(transfer.get("transfer_bill_no") or "").strip() or withdrawal.transferBillNo
        if withdrawal.status in {"paid", "failed", "cancelled", "rejected"}:
            return {"withdrawal": withdrawal.model_dump(), "duplicate": True}
        if transfer_state == "SUCCESS":
            self._mark_referral_withdrawal_paid(state, withdrawal, transfer, now)
        elif transfer_state in {"FAIL", "CANCELLED"}:
            withdrawal.status = "cancelled" if transfer_state == "CANCELLED" else "failed"
            withdrawal.failureReason = str(transfer.get("fail_reason") or "微信转账未成功")
            withdrawal.updatedAt = now
            self._release_referral_withdrawal_rewards(state, withdrawal, now)
        elif transfer_state == "WAIT_USER_CONFIRM":
            withdrawal.status = "waiting_user_confirm"
            withdrawal.updatedAt = now
        else:
            withdrawal.status = "processing"
            withdrawal.updatedAt = now
        self._save(state)
        return {"withdrawal": withdrawal.model_dump(), "duplicate": False}

    def generate_same_style(self, payload: SameStyleGenerateRequest) -> dict:
        owner = self.repo.get_user(payload.ownerUserId)
        if not owner:
            raise HTTPException(status_code=404, detail="用户不存在")
        if payload.mode not in {"reuse_content", "use_own_content"}:
            raise HTTPException(status_code=400, detail="生成方式不合法")
        existing = self.repo.find_same_style_generation(owner.id, payload.idempotencyKey)
        if existing:
            return {"generation": existing.model_dump(), "duplicate": True, "reused": False}
        if payload.mode == "reuse_content" and (payload.sourceNoteId or payload.sourceShowcaseId):
            reusable = self.repo.find_latest_same_style_generation(
                owner.id,
                payload.mode,
                source_note_id=payload.sourceNoteId,
                source_showcase_id=payload.sourceShowcaseId,
            )
            if reusable and self._same_style_generation_target_available(reusable, owner.id):
                return {"generation": reusable.model_dump(), "duplicate": True, "reused": True}
        generated_note_id = None
        generated_showcase_id = None
        template_id = None
        source_owner_user_id = None
        if payload.mode == "reuse_content":
            if not payload.sourceNoteId and not payload.sourceShowcaseId:
                raise HTTPException(status_code=400, detail="请选择要复用的公开资料或合集")
            source_note = self.repo.get_user_note(payload.sourceNoteId) if payload.sourceNoteId else None
            source_showcase = self.repo.get_showcase_page(payload.sourceShowcaseId) if payload.sourceShowcaseId else None
            if payload.sourceNoteId and (not source_note or source_note.status == "deleted"):
                raise HTTPException(status_code=404, detail="公开资料不存在")
            if payload.sourceShowcaseId and (not source_showcase or source_showcase.status != "published"):
                raise HTTPException(status_code=404, detail="公开合集不存在")
            source_owner_user_id = source_note.ownerUserId if source_note else source_showcase.ownerUserId
            result = self.clone_property_same(
                PropertySameCloneRequest(
                    ownerUserId=owner.id,
                    sourceType="note" if source_note else "showcase",
                    sourceId=payload.sourceNoteId or payload.sourceShowcaseId,
                    phone=owner.phone,
                    wechat=owner.wechat,
                    ownerName=owner.nickname,
                )
            )
            generated_note_id = result.get("note", {}).get("id")
            generated_showcase_id = result.get("showcase", {}).get("id")
        else:
            if not payload.ownNoteIds:
                raise HTTPException(status_code=400, detail="请选择自己的资料")
            notes = []
            for note_id in payload.ownNoteIds:
                note = self.repo.get_user_note(note_id)
                if not note or note.ownerUserId != owner.id or note.status == "deleted":
                    raise HTTPException(status_code=403, detail="只能选择自己的有效资料")
                notes.append(note)
            source_showcase = self.repo.get_showcase_page(payload.sourceShowcaseId) if payload.sourceShowcaseId else None
            if source_showcase and source_showcase.status != "published":
                raise HTTPException(status_code=404, detail="来源模板不存在")
            source_owner_user_id = source_showcase.ownerUserId if source_showcase else None
            template_id = source_showcase.templateId if source_showcase else "featured_window"
            now = now_iso()
            showcase = ShowcasePage(
                id=new_id("showcase"),
                ownerUserId=owner.id,
                status="draft",
                name=f"{owner.nickname}的精选资料",
                description="多条资料，一页发客户。",
                templateId=template_id,
                contactConfig={"phone": owner.phone, "wechat": owner.wechat},
                items=[ShowcaseItem(noteId=item.id, sortOrder=index) for index, item in enumerate(notes)],
                createdAt=now,
                updatedAt=now,
            )
            self.repo.save_showcase_page(showcase)
            self._invalidate_showcase_list_cache(owner.id)
            generated_showcase_id = showcase.id
        now = now_iso()
        relation = None
        relation_duplicate = False
        if source_owner_user_id and source_owner_user_id != owner.id:
            referral_state = AppState(referral_relations=self.repo.list_referral_relations())
            relation, relation_duplicate, _ = self._ensure_share_referral(
                referral_state,
                owner.id,
                source_owner_user_id,
                "same_style",
            )
        generation = SameStyleGeneration(
            id=new_id("same_style"),
            ownerUserId=owner.id,
            mode=payload.mode,
            sourceNoteId=payload.sourceNoteId,
            sourceShowcaseId=payload.sourceShowcaseId,
            sourceTemplateId=template_id,
            generatedNoteId=generated_note_id,
            generatedShowcaseId=generated_showcase_id,
            referralRelationId=relation.id if relation else None,
            idempotencyKey=payload.idempotencyKey,
            createdAt=now,
            updatedAt=now,
        )
        self.repo.save_same_style_generation(
            generation,
            referral_relation=relation if relation and not relation_duplicate else None,
        )
        return {"generation": generation.model_dump(), "duplicate": False}

    def _same_style_generation_target_available(self, generation: SameStyleGeneration, owner_user_id: str) -> bool:
        if generation.generatedNoteId:
            note = self.repo.get_user_note(generation.generatedNoteId)
            return bool(note and note.ownerUserId == owner_user_id and note.status != "deleted")
        if generation.generatedShowcaseId:
            showcase = self.repo.get_showcase_page(generation.generatedShowcaseId)
            return bool(showcase and showcase.ownerUserId == owner_user_id)
        return False

    def _h5_ticket_encode(self, payload: dict) -> str:
        encoded = base64.urlsafe_b64encode(json.dumps(payload, ensure_ascii=True, separators=(",", ":")).encode("utf-8"))
        return encoded.decode("ascii").rstrip("=")

    def _h5_ticket_signature(self, body: str) -> str:
        secret = (settings.h5_auth_secret or "teamBuy-h5-dev-secret").encode("utf-8")
        return hmac.new(secret, body.encode("utf-8"), hashlib.sha256).hexdigest()

    def _split_h5_ticket(self, ticket: str) -> tuple[str, str]:
        text = (ticket or "").strip()
        if "." not in text:
            raise HTTPException(status_code=401, detail="H5 登录票据无效")
        body, signature = text.rsplit(".", 1)
        if not body or not signature:
            raise HTTPException(status_code=401, detail="H5 登录票据无效")
        return body, signature

    def _pad_h5_ticket_body(self, body: str) -> bytes:
        padding = "=" * (-len(body) % 4)
        return f"{body}{padding}".encode("ascii")

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

        sales_profile = dict(user.salesProfile or {})
        profile_fields = {
            "displayName": payload.displayName,
            "jobTitle": payload.jobTitle,
            "company": payload.company,
            "city": payload.city,
            "wechatQrUrl": payload.wechatQrUrl,
            "email": payload.email,
            "website": payload.website,
        }
        for key, value in profile_fields.items():
            if value is not None:
                cleaned = strip_unicode_surrogates(value).strip()[:240]
                if key in {"website", "wechatQrUrl"} and cleaned:
                    parsed = urlparse(cleaned)
                    if parsed.scheme != "https" or not parsed.netloc:
                        raise HTTPException(status_code=400, detail="个人资料中的网址和二维码必须使用HTTPS")
                sales_profile[key] = cleaned
        sales_profile.update(
            {
                "displayName": sales_profile.get("displayName") or user.nickname,
                "avatarUrl": user.avatarUrl,
                "phone": user.phone or "",
                "wechat": user.wechat or "",
            }
        )
        user.salesProfile = sales_profile

        user.updatedAt = now_iso()
        self.repo.save_user(user)
        return user

    def get_wecom_bind_status(self, user_id: str) -> dict:
        user = self.repo.get_user(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")
        existing_binding = self._find_wecom_external_binding_for_owner(user.id, user.openid)
        if not existing_binding:
            return {
                "status": "unbound",
                "bound": False,
                "ownerUserId": user.id,
                "ownerOpenid": user.openid,
            }
        return {
            "status": "bound",
            "bound": True,
            "ownerUserId": user.id,
            "ownerOpenid": user.openid,
            "externalUserId": existing_binding.externalUserId,
            "bindSource": existing_binding.bindSource,
        }

    def create_wecom_bind_intent(self, user_id: str) -> dict:
        user = self.repo.get_user(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")
        existing_binding = self._find_wecom_external_binding_for_owner(user.id, user.openid)
        if existing_binding:
            return {
                "status": "bound",
                "bound": True,
                "ownerUserId": user.id,
                "ownerOpenid": user.openid,
                "externalUserId": existing_binding.externalUserId,
                "bindSource": existing_binding.bindSource,
                "bindMessage": "",
            }
        existing_intent = self._find_active_wecom_bind_intent_for_owner(user.id)
        if existing_intent:
            bind_code = self._wecom_bind_code_from_intent(existing_intent)
            if bind_code:
                expires_at = self._wecom_bind_intent_expires_at(existing_intent)
                return {
                    "status": "pending",
                    "bound": False,
                    "intentId": existing_intent.id,
                    "bindCode": bind_code,
                    "bindMessage": self._wecom_bind_message(bind_code),
                    "ownerUserId": user.id,
                    "ownerOpenid": user.openid,
                    "expiresAt": expires_at.isoformat(),
                    "ttlSeconds": max(60, settings.wecom_bind_intent_ttl_seconds),
                    "reused": True,
                }
        now = now_iso()
        bind_code = self._new_wecom_bind_code()
        expires_at = datetime.now(tz=SHANGHAI) + timedelta(seconds=max(60, settings.wecom_bind_intent_ttl_seconds))
        intent = WecomIdentityBinding(
            id=f"wecom_bind_intent_{new_id('intent')}",
            sourceType=WECOM_BIND_INTENT_SOURCE,
            externalUserId=f"pending:{user.id}:{bind_code}:{uuid4().hex}",
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
            "status": "pending",
            "bound": False,
            "intentId": intent.id,
            "bindCode": bind_code,
            "bindMessage": self._wecom_bind_message(bind_code),
            "ownerUserId": user.id,
            "ownerOpenid": user.openid,
            "expiresAt": expires_at.isoformat(),
            "ttlSeconds": max(60, settings.wecom_bind_intent_ttl_seconds),
            "reused": False,
        }

    def issue_wecom_bind_card_token(self, external_user_id: str, welcome_code: str) -> dict:
        """Create a short-lived bearer token for the welcome mini-program card.

        The add-contact callback has no mini-program openid.  The card click is
        therefore the explicit user action that supplies the openid, while the
        token keeps the external contact identity bound to this exact welcome
        event.  Only the hash is persisted; the raw token is sent to WeCom and
        is never stored or logged.
        """
        external_user_id = str(external_user_id or "").strip()
        welcome_code = str(welcome_code or "").strip()
        if not external_user_id or not welcome_code:
            raise HTTPException(status_code=400, detail="添加客户事件缺少绑定字段")

        existing_binding = self.repo.get_wecom_identity_binding(WECOM_EXTERNAL_BINDING_SOURCE, external_user_id)
        if existing_binding and self.repo.get_user(existing_binding.ownerUserId):
            return {"status": "already_bound", "externalUserId": external_user_id}

        welcome_code_hash = hashlib.sha256(welcome_code.encode("utf-8")).hexdigest()
        existing_token = self.repo.get_pending_wecom_bind_card_token(welcome_code_hash)
        if existing_token:
            return {
                "status": "issued",
                "tokenId": existing_token.id,
                "token": None,
                "externalUserId": external_user_id,
                "page": None,
                "alreadyIssued": True,
            }

        raw_token = secrets.token_urlsafe(32)
        now = datetime.now(tz=SHANGHAI)
        expires_at = now + timedelta(seconds=max(60, settings.wecom_bind_card_ttl_seconds))
        token = WecomBindCardToken(
            id=f"wecom_bind_card_{new_id('token')}",
            tokenHash=hashlib.sha256(raw_token.encode("utf-8")).hexdigest(),
            welcomeCodeHash=welcome_code_hash,
            externalUserId=external_user_id,
            status="issued",
            deliveryStatus="pending",
            expiresAt=expires_at.isoformat(),
            createdAt=now.isoformat(),
            updatedAt=now.isoformat(),
        )
        self.repo.save_wecom_bind_card_token(token)
        page = f"/pages/wecom-bind/index?token={quote(raw_token, safe='')}"
        return {
            "status": "issued",
            "tokenId": token.id,
            "token": raw_token,
            "externalUserId": external_user_id,
            "page": page,
            "expiresAt": token.expiresAt,
            "alreadyIssued": False,
        }

    def mark_wecom_bind_card_delivery(self, token_id: str, status: str) -> dict | None:
        token = next((item for item in self.repo.load().wecom_bind_card_tokens if item.id == token_id), None)
        if not token:
            return None
        now = now_iso()
        updated = token.model_copy(
            update={
                "deliveryStatus": status if status in {"sent", "failed"} else token.deliveryStatus,
                "status": "invalid" if status == "failed" else token.status,
                "updatedAt": now,
            }
        )
        self.repo.save_wecom_bind_card_token(updated)
        return updated.model_dump(mode="json")

    def bind_wecom_contact_card(self, raw_token: str, user_id: str) -> dict:
        raw_token = str(raw_token or "").strip()
        if len(raw_token) < 20 or len(raw_token) > 200:
            raise HTTPException(status_code=400, detail="绑定卡片无效")
        user = self.repo.get_user(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")

        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        token = self.repo.get_wecom_bind_card_token(token_hash)
        if not token:
            raise HTTPException(status_code=410, detail="绑定卡片已失效")
        existing_binding = self.repo.get_wecom_identity_binding(WECOM_EXTERNAL_BINDING_SOURCE, token.externalUserId)
        if existing_binding:
            if existing_binding.ownerUserId == user.id or existing_binding.ownerOpenid == user.openid:
                return {
                    "status": "already_bound",
                    "ownerUserId": user.id,
                    "ownerOpenid": user.openid,
                    "externalUserId": token.externalUserId,
                }
            raise HTTPException(status_code=409, detail="该资料助手已绑定其他账号")

        consumed = self.repo.consume_wecom_bind_card_token(
            token_hash,
            owner_user_id=user.id,
            owner_openid=user.openid,
            now=now_iso(),
        )
        if not consumed:
            raise HTTPException(status_code=410, detail="绑定卡片已使用或已失效")
        self._save_wecom_identity_binding(
            external_user_id=consumed.externalUserId,
            owner_user_id=user.id,
            import_batch_id=None,
            bind_source=WECOM_BIND_CARD_SOURCE,
        )
        return {
            "status": "bound",
            "ownerUserId": user.id,
            "ownerOpenid": user.openid,
            "externalUserId": consumed.externalUserId,
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
        bind_result = self._consume_wecom_bind_code_from_raw_messages(raw_messages)
        raw_messages = bind_result["remainingMessages"]
        if bind_result["consumedMessages"]:
            self._persist_consumed_bind_raw_messages(bind_result["consumedMessages"])
        if not raw_messages:
            return {
                "message": bind_result["message"] or "没有新的企业微信客服消息需要导入",
                "importBatchIds": [],
                "deduplicatedCount": len(existing_wecom_msg_ids),
                "bindResult": bind_result["result"],
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
            "bindResult": bind_result["result"],
            "notifications": [item.model_dump() for item in notifications],
        }

    def _persist_consumed_bind_raw_messages(self, messages: list[RawMessage]) -> None:
        self.repo.save_raw_messages(messages)

    def _persist_property_batch_import_artifacts(self, batch: ImportBatch, batch_messages: list[RawMessage], notification) -> None:
        self.repo.save_raw_messages(batch_messages)
        self.repo.save_import_batch(batch)
        self.repo.save_import_notification(notification)

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
            property_batch_result = self._try_create_import_property_batch(owner_user_id, content_object, batch.id, batch.rawMessageIds)
            if property_batch_result:
                count = property_batch_result["createdCount"]
                notes = property_batch_result["notes"]
                batch.titleCandidate = f"批量房源 {count}套"
                batch.generatedNoteId = notes[0].id if notes else None
                batch.status = "claimed"
                batch.claimedByUserId = owner_user_id
                batch.errorMessage = None
                batch.updatedAt = now_iso()
                showcase = self._create_property_batch_showcase(
                    owner_user_id,
                    notes,
                    "\n".join(block for block in content_object.textBlocks if str(block or "").strip()),
                    source="wecom_property_batch",
                    import_batch_id=batch.id,
                )
                skill_run = SkillRun(
                    id=new_id("skill_run"),
                    skillId="property-batch-import",
                    status="success",
                    inputSnapshot={
                        **content_object.model_dump(),
                        "importBatchId": batch.id,
                        "rawMessageIds": batch.rawMessageIds,
                        "detectedCount": count,
                        "showcaseId": showcase.id,
                        "mediaWarningCount": media_warning_count,
                    },
                    outputRef=showcase.id,
                    modelProvider="rule",
                    startedAt=batch.createdAt,
                    endedAt=now_iso(),
                )
                notification = self.notification_service.build_notification(
                    batch,
                    channel=notification_channel,
                    media_warning_count=media_warning_count,
                )
                notification.actions = [
                    {"key": "open-showcase", "label": "查看房源合集", "path": f"/pages/showcase-edit/index?id={showcase.id}"},
                    {"key": "open-result", "label": "查看首套房源", "path": f"/pages/note-edit/index?id={batch.generatedNoteId}" if batch.generatedNoteId else ""},
                ]
                self._persist_property_batch_import_artifacts(batch, batch_messages, notification)
                self.repo.save_skill_run(skill_run)
                return notification
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
            shareState="private",
            revision=1,
            title=note_draft.title,
            summary=note_draft.summary,
            body=note_draft.body,
            contentBlocks=self._normalize_note_content_blocks(
                getattr(note_draft, "contentBlocks", None),
                body=note_draft.body,
                media=[item.model_dump() for item in note_draft.media],
            ),
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

    def _find_note_by_idempotency(self, owner_user_id: str, idempotency_key: str | None) -> UserNote | None:
        key = self._clean_optional_text(idempotency_key)
        if not key:
            return None
        existing = next(
            (
                item
                for item in self.repo.list_user_notes(owner_user_id, include_deleted=True)
                if item.idempotencyKey == key
            ),
            None,
        )
        if existing and existing.status == "deleted":
            raise HTTPException(status_code=409, detail="幂等键已用于已删除资料，请生成新的幂等键")
        return existing

    def _find_notes_by_idempotency(self, owner_user_id: str, idempotency_key: str | None) -> list[UserNote]:
        key = self._clean_optional_text(idempotency_key)
        if not key:
            return []
        return [
            item
            for item in self.repo.list_user_notes(owner_user_id, include_deleted=True)
            if item.idempotencyKey == key and item.status != "deleted"
        ]

    def _mark_new_intake(
        self,
        note: UserNote,
        intake_id: str | None,
        idempotency_key: str | None,
        intake_state: str,
    ) -> UserNote:
        note.shareState = "private"
        # Creation establishes the first revision; edits and publishing are the
        # operations that advance it. This keeps idempotent retries stable.
        note.revision = max(int(note.revision or 0), 1)
        note.intakeId = self._clean_optional_text(intake_id)
        note.idempotencyKey = self._clean_optional_text(idempotency_key)
        config = dict(note.visibilityConfig or {})
        config["intakeState"] = intake_state
        config["shareState"] = note.shareState
        config["revision"] = note.revision
        note.visibilityConfig = self._normalize_note_visibility_config(config)
        return note

    def _mark_note_content_edit(self, note: UserNote, intake_state: str = "editing") -> UserNote:
        """Move any edited note back behind the publication boundary.

        Not every edit comes through PUT /notes/{id}; OCR, type confirmation,
        organizing and scenario generation also mutate the public projection.
        Keeping this transition in one helper prevents a side route from
        leaving a newly changed version publicly visible.
        """
        # A claimed/imported note may still carry the legacy ``draft``
        # lifecycle value even after the owner has edited it.  Editing is the
        # transition into the usable owner-owned state; publication remains a
        # separate shareState boundary below.
        if note.status == "draft":
            note.status = "active"
        note.revision = max(int(note.revision or 0), 0) + 1
        if note.shareState == "published":
            note.shareState = "private"
        config = dict(note.visibilityConfig or {})
        config["revision"] = note.revision
        config["shareState"] = note.shareState
        config["intakeState"] = intake_state
        note.visibilityConfig = self._normalize_note_visibility_config(config)
        return note

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
        existing = self._find_note_by_idempotency(owner_user_id, payload.idempotencyKey)
        if existing:
            return existing
        if input_mode == "paste_text" and not raw_text:
            raise HTTPException(status_code=400, detail="请先粘贴资料文案")
        note = (
            self._create_manual_note_from_text(owner_user_id, card_type, raw_text, title, payload.intakeId, payload.idempotencyKey)
            if input_mode == "paste_text"
            else self._create_blank_manual_note(owner_user_id, card_type, title, payload.intakeId, payload.idempotencyKey)
        )
        self._invalidate_card_list_cache(owner_user_id)
        return note

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
        existing_showcase = next(
            (
                item
                for item in self.repo.list_showcase_pages(owner_user_id)
                if payload.idempotencyKey
                and item.idempotencyKey == self._clean_optional_text(payload.idempotencyKey)
            ),
            None,
        )
        if existing_showcase:
            existing_notes = [
                note
                for item in existing_showcase.items
                if (note := self.repo.get_user_note(item.noteId)) and note.status != "deleted"
            ]
            return {
                "noteIds": [item.id for item in existing_notes],
                "notes": [item.model_dump() for item in existing_notes],
                "createdCount": len(existing_notes),
                "showcaseId": existing_showcase.id,
                "showcase": self._showcase_owner_payload(existing_showcase),
            }
        batch_key = self._clean_optional_text(payload.idempotencyKey)
        existing = [
            note
            for note in self.repo.list_user_notes(owner_user_id, include_deleted=True)
            if batch_key
            and note.status != "deleted"
            and (note.idempotencyKey == batch_key or note.idempotencyKey.startswith(f"{batch_key}:"))
        ]
        if existing:
            showcase = self._create_property_batch_showcase(
                owner_user_id,
                existing,
                raw_text=payload.rawText,
                source="manual_property_batch_retry",
                intake_id=payload.intakeId,
                idempotency_key=payload.idempotencyKey,
            )
            showcase = next(
                (
                    item for item in self.repo.list_showcase_pages(owner_user_id)
                    if str((item.displayConfig or {}).get("idempotencyKey") or "") == str(payload.idempotencyKey or "")
                ),
                None,
            )
            return {
                "noteIds": [item.id for item in existing],
                "notes": [item.model_dump() for item in existing],
                "createdCount": len(existing),
                "showcaseId": showcase.id if showcase else None,
                "showcase": self._showcase_owner_payload(showcase) if showcase else None,
            }
        raw_text = strip_unicode_surrogates(payload.rawText or "").strip()
        candidates = [item for item in payload.candidates if item.selected]
        if not candidates:
            raise HTTPException(status_code=400, detail="请至少选择一套房源")
        notes = [
            self._create_property_note_from_batch_candidate(
                owner_user_id,
                raw_text,
                item.model_dump(),
                intake_id=payload.intakeId,
                idempotency_key=payload.idempotencyKey,
            )
            for item in candidates
        ]
        showcase = self._create_property_batch_showcase(
            owner_user_id,
            notes,
            raw_text,
            source="manual_property_batch",
            intake_id=payload.intakeId,
            idempotency_key=payload.idempotencyKey,
        )
        self._invalidate_card_list_cache(owner_user_id)
        return {
            "noteIds": [item.id for item in notes],
            "notes": [item.model_dump() for item in notes],
            "createdCount": len(notes),
            "showcaseId": showcase.id,
            "showcase": self._showcase_owner_payload(showcase),
        }

    def _parse_property_batch_text(self, raw_text: str) -> dict:
        normalized_text = self._normalize_property_batch_text(raw_text)
        lines = [line.strip() for line in re.split(r"[\r\n]+", normalized_text) if line.strip()]
        common_private = self._property_batch_common_private_data(raw_text)
        public_tags = self._property_batch_public_tags(raw_text)
        private_tags = self._property_batch_private_tags(raw_text, common_private)
        candidates: list[dict] = []
        current_base = ""
        current_area = ""
        current_features: list[str] = []
        for line in lines:
            clean = re.sub(r"^[0-9一二三四五六七八九十]+[）)、，,、.．]\s*", "", line).strip()
            if not clean or re.search(r"1[3-9]\d{9}", clean) and len(clean) < 40:
                continue
            if self._property_batch_is_area_header(clean):
                current_area = clean
                current_base = ""
                current_features = self._property_features_from_text(clean)
                continue
            if self._property_batch_is_building_line(clean):
                current_base = self._property_batch_base_from_area_and_building(current_area, clean)
                current_features = self._unique_strings([*self._property_features_from_text(current_area), *self._property_features_from_text(clean)])
                continue
            if not current_base or self._line_has_property_address_signal(clean):
                direct = self._property_candidate_from_direct_line(clean, public_tags, private_tags, common_private, len(candidates))
                if direct:
                    candidates.append(direct)
                    current_base = ""
                    current_features = []
                    continue
            if current_base:
                unit = self._property_candidate_from_unit_line(current_base, clean, public_tags, private_tags, common_private, current_features, len(candidates))
                if unit:
                    candidates.append(unit)
                    continue
            if re.search(r"(苑|园|府|里|城|公寓|小区|花园).{0,12}(号|栋|幢|座|室|户|房)", clean) and not re.search(r"1[3-9]\d{9}", clean):
                current_base = clean
                current_features = self._property_features_from_text(clean)
        extra_candidates = self._parse_property_batch_extra_candidates(
            lines,
            public_tags,
            private_tags,
            common_private,
            len(candidates),
        )
        if len(extra_candidates) >= 2 and len(extra_candidates) > len(candidates):
            candidates = extra_candidates
        elif not candidates:
            candidates = extra_candidates
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

    def _normalize_property_batch_text(self, raw_text: str) -> str:
        keycap_digits = {
            "0️⃣": "0",
            "1️⃣": "1",
            "2️⃣": "2",
            "3️⃣": "3",
            "4️⃣": "4",
            "5️⃣": "5",
            "6️⃣": "6",
            "7️⃣": "7",
            "8️⃣": "8",
            "9️⃣": "9",
        }
        text = raw_text or ""
        for source, target in keycap_digits.items():
            text = text.replace(source, target)
        text = text.replace("\ufe0f", "").replace("\u20e3", "")
        return text

    def _property_batch_is_area_header(self, line: str) -> bool:
        if re.search(r"\d{3,5}", line) or re.search(r"1[3-9]\d{9}", line):
            return False
        if len(line) > 80:
            return False
        has_location = bool(re.search(r"(广场|地铁|医院|国际|公寓|大厦|书院路|开福寺|碧沙湖|湘雅|华创|保利|蓝弯)", line))
        has_multiple_places = len([item for item in re.split(r"[，,、\s]+", line) if item.strip()]) >= 2
        return has_location and has_multiple_places

    def _property_batch_is_building_line(self, line: str) -> bool:
        return bool(re.fullmatch(r"\d{3,5}(?:[东西南北]栋|栋|幢|座|室|房)?", line.strip()))

    def _property_batch_base_from_area_and_building(self, area: str, building: str) -> str:
        primary_area = re.split(r"[，,、\s]+", area or "")[0].strip()
        return " · ".join(item for item in [primary_area, building.strip()] if item).strip() or building.strip()

    def _line_has_property_address_signal(self, line: str) -> bool:
        return bool(
            re.search(r"\d{1,5}(?:弄|号|栋|幢|座|室|户|房|楼)", line)
            or re.search(r"(苑|园|府|里|城|公寓|小区|花园|大厦|国际|广场)", line)
        )

    def _property_batch_common_private_data(self, raw_text: str) -> dict:
        phones = self._unique_strings(re.findall(r"1[3-9]\d{9}", raw_text))
        wechat_match = re.search(r"(?:微信|v|V|➕微信|加微信)[：:\s➕+]*([A-Za-z0-9_-]{5,30})", raw_text)
        v_match = re.search(r"\b(1[3-9]\d{9}v)\b", raw_text, re.IGNORECASE)
        same_phone_wechat = bool(re.search(r"微信同号|微信号同手机号|手机同微信", raw_text))
        commission_match = re.search(r"(中介费\s*[%％]?\s*\d+%?|中介费\s*\d+[%％]|佣金.{0,24}?\d+[%％]|租高有红包|红包)", raw_text)
        restrictions = []
        if re.search(r"带小孩|孕妇|老人", raw_text):
            restrictions.append("带小孩/孕妇/老人不租")
        return {
            "upstreamPhones": phones,
            "upstreamWechat": (
                wechat_match.group(1)
                if wechat_match
                else phones[0]
                if same_phone_wechat and phones
                else v_match.group(1)
                if v_match
                else ""
            ),
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

    def _clean_property_batch_line(self, line: str) -> str:
        clean = re.sub(r"^[^\w\u4e00-\u9fff\d]+", "", line).strip()
        clean = re.sub(r"^[0-9一二三四五六七八九十]+[）)、，,、.．]\s*", "", clean).strip()
        clean = re.sub(r"^(?:太阳|玫瑰|发财|红包)\]", "", clean).strip()
        return re.sub(r"\s+", " ", clean).strip(" -—━")

    def _parse_property_batch_extra_candidates(
        self,
        lines: list[str],
        public_tags: list[str],
        private_tags: list[str],
        private_data: dict,
        start_index: int,
    ) -> list[dict]:
        candidates: list[dict] = []
        current_layout = ""
        current_base = ""
        pending: dict = {}

        def append_candidate(base: str, unit: str, price: str, source_text: str = "") -> None:
            base = self._property_base_title(base.strip(" ，,。"))
            unit = (unit or current_layout or "房源").strip(" ，,。")
            price = re.sub(r"[^\d]", "", price or "")
            if not base or not price or re.search(r"1[3-9]\d{9}", base):
                return
            features = self._property_features_from_text(source_text or base)
            candidates.append(
                self._property_candidate_payload(
                    base,
                    unit,
                    price,
                    public_tags,
                    private_tags,
                    private_data,
                    features,
                    start_index + len(candidates),
                )
            )

        def flush_pending() -> None:
            if pending.get("base") and pending.get("price"):
                append_candidate(
                    pending.get("base", ""),
                    pending.get("layout") or current_layout or "房源",
                    pending.get("price", ""),
                    pending.get("text", ""),
                )
            pending.clear()

        layout_pattern = r"大南厅|朝南大平层一室一厅|正规一室一厅|复式一房|loft两房|loft一房|公寓一房|大厅一室户|[东西南北]?一室一厅|[东西南北]?一室户|[东西南北]?一室|[东西南北]?一房|[两二]房(?:1厅)?|三房|小复式一厅|朝阳大一室户|朝阳一室户|一室户"
        for raw_line in lines:
            line = self._clean_property_batch_line(raw_line)
            if not line or re.search(r"1[3-9]\d{9}", line):
                continue
            if re.fullmatch(r"[🏠\s]*(一房|两房|二房|三房)[^\d]*", raw_line.strip()):
                current_layout = re.sub(r"[^\u4e00-\u9fff]", "", raw_line)
                continue

            community_match = re.search(r"(?:小区|项目)[：:]\s*(.+)", line)
            if community_match:
                flush_pending()
                value = community_match.group(1).strip()
                pending["base"] = re.sub(rf"\s*({layout_pattern}).*", "", value).strip() or value
                layout_match = re.search(layout_pattern, value)
                if layout_match:
                    pending["layout"] = layout_match.group(0)
                pending["text"] = line
                current_base = pending["base"]
                continue

            layout_field_match = re.search(r"户型[：:]\s*(.+)", line)
            if layout_field_match and pending.get("base"):
                layout_value = layout_field_match.group(1).strip()
                pending["layout"] = layout_value
                pending["text"] = f"{pending.get('text', '')} {line}".strip()
                continue

            price_field_match = re.search(r"(?:价格|💰)[：:\s]*[^\d]{0,4}(\d{3,5})(?:\s*-\s*(\d{3,5}))?", line)
            if price_field_match and pending.get("base"):
                pending["price"] = price_field_match.group(1)
                pending["text"] = f"{pending.get('text', '')} {line}".strip()
                flush_pending()
                current_base = ""
                continue

            pending_plain_price_match = re.search(r"^(\d{3,5})(?:\s*-\s*(\d{3,5}))?", line)
            if pending_plain_price_match and pending.get("base"):
                pending["price"] = pending_plain_price_match.group(1)
                pending["text"] = f"{pending.get('text', '')} {line}".strip()
                flush_pending()
                current_base = ""
                continue

            named_block_match = re.search(rf"^(.{{2,32}}?)\s+({layout_pattern})(?:\s|$)", line)
            if named_block_match and not re.search(r"\d{3,5}", line):
                flush_pending()
                pending["base"] = named_block_match.group(1).strip()
                pending["layout"] = named_block_match.group(2).strip()
                pending["text"] = line
                current_base = pending["base"]
                continue

            named_no_layout_match = re.search(r"^(.{2,24}?)(?:\s+(?:有网络|余\d+间)|\|)", line)
            if named_no_layout_match and not re.search(r"\d{3,5}", line):
                flush_pending()
                pending["base"] = named_no_layout_match.group(1).strip()
                pending["layout"] = current_layout or "房源"
                pending["text"] = line
                current_base = pending["base"]
                continue

            direct_layout_match = re.search(rf"(.{{2,50}}?)\s*({layout_pattern}).{{0,18}}?(\d{{3,5}})(?:元|/月|🈳|空|。|$)", line)
            if direct_layout_match:
                flush_pending()
                append_candidate(direct_layout_match.group(1), direct_layout_match.group(2), direct_layout_match.group(3), line)
                current_base = ""
                continue

            room_price_match = re.search(r"^(\d{1,4}室)(?:\s*)(\d{3,5})(.*)$", line)
            if room_price_match and current_base:
                append_candidate(current_base, room_price_match.group(1), room_price_match.group(2), line)
                continue

            plain_price_match = re.search(r"(.{2,50}?)(\d{3,5})(?:元/月|元|/月|🈳|空|$)", line)
            if plain_price_match and re.search(r"(小区|苑|园|府|城|公寓|大厦|名门|瑞府|雅苑|新城|路|弄|村|宅|号|栋|房|室)", line):
                flush_pending()
                base = plain_price_match.group(1)
                append_candidate(base, current_layout or "房源", plain_price_match.group(2), line)
                current_base = ""
                continue

            price_only_match = re.fullmatch(r"(\d{3,5})", line)
            if price_only_match and current_base:
                append_candidate(current_base, current_layout or "房源", price_only_match.group(1), line)
                current_base = ""
                continue

            if re.search(r"(小区|苑|园|府|城|公寓|大厦|路|弄|村|宅|号|栋)$", line) or re.search(r"(村|小区|新村).{0,12}\d+号$", line):
                current_base = line

        flush_pending()
        return candidates

    def _property_candidate_from_unit_line(self, base: str, line: str, public_tags: list[str], private_tags: list[str], private_data: dict, base_features: list[str], index: int) -> dict | None:
        if re.search(r"1[3-9]\d{9}", line):
            return None
        match = re.search(r"(.{1,24}?)(?:[\s，,]*|[一\-—:：])(\d{3,5})(?:元|/月)?(?:[（(][^）)]*[）)])?(?:[，,。]|已空|以空|空置|$)", line)
        if not match:
            return None
        unit_name = match.group(1).strip(" ，,")
        price = match.group(2)
        base_title = self._property_base_title(base)
        return self._property_candidate_payload(base_title, unit_name, price, public_tags, private_tags, private_data, base_features, index)

    def _property_candidate_from_direct_line(self, line: str, public_tags: list[str], private_tags: list[str], private_data: dict, index: int) -> dict | None:
        if re.search(r"1[3-9]\d{9}", line):
            return None
        layout_pattern = r"朝南次卧|北次阁楼|主卧独卫|大厅一室户|[东西南北]?次一室户|[东西南北]?一室一厅|[东西南北]?一室户|[东西南北]?次卧|主卧|[A-Z]?[东西南北]?一房|阁楼|两房|一室户|[A-Z]室"
        match = re.search(rf"(.{{2,40}}?)({layout_pattern})(?:[^\d]{{0,12}})(\d{{3,5}})(?:元|/月)?(?:[（(][^）)]*[）)])?", line)
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

    def _create_property_note_from_batch_candidate(
        self,
        owner_user_id: str,
        raw_text: str,
        candidate: dict,
        intake_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> UserNote:
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
                "recognitionConfidence": {
                    "level": "high",
                    "source": "property_batch_parser",
                    "matchedFields": ["community", "layout", "price"],
                },
                "privateData": candidate.get("privateData") or {},
                "privateTags": candidate.get("privateTags") or [],
                "batchImport": {"candidateId": candidate.get("candidateId"), "rawTextLength": len(raw_text)},
            }
        )
        candidate_key = self._clean_optional_text(idempotency_key)
        if candidate_key:
            candidate_key = f"{candidate_key}:{candidate.get('candidateId') or 'item'}"
        note = UserNote(
            id=new_id("note"),
            ownerUserId=owner_user_id,
            importBatchId=None,
            sourceCardId=None,
            status="active",
            shareState="private",
            intakeId=intake_id,
            idempotencyKey=candidate_key,
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
        self._apply_owner_public_contact_to_property_note(note)
        self._mark_new_intake(note, intake_id, candidate_key, "captured")
        self.repo.save_user_note(note)
        return note

    def _create_property_batch_showcase(
        self,
        owner_user_id: str,
        notes: list[UserNote],
        raw_text: str,
        source: str,
        import_batch_id: str | None = None,
        intake_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> ShowcasePage:
        now = now_iso()
        valid_notes = [note for note in notes if note.ownerUserId == owner_user_id and note.status != "deleted"]
        name = f"批量房源合集 {len(valid_notes)}套"
        first_location = self._property_batch_showcase_location(valid_notes)
        if first_location:
            name = f"{first_location}房源合集 {len(valid_notes)}套"
        showcase = ShowcasePage(
            id=new_id("showcase"),
            ownerUserId=owner_user_id,
            status="draft",
            name=name,
            description=f"从本次批量房源导入自动生成，已整理 {len(valid_notes)} 套房源，可继续编辑后发客户。",
            bannerUrl=next((note.coverUrl for note in valid_notes if note.coverUrl), None),
            sceneType="property",
            templateId="property_batch_collection",
            intakeId=intake_id,
            idempotencyKey=self._clean_optional_text(idempotency_key),
            shareTitle=name,
            contactConfig=self._normalize_showcase_contact_config(
                {
                    "contactText": "想了解房源细节，欢迎直接联系我。",
                    "showPhone": False,
                    "showWechat": False,
                }
            ),
            displayConfig=self._normalize_showcase_display_config(
                {
                    "activeCategory": "房源",
                    "showSearch": True,
                    "showTags": True,
                    "layoutMode": "list",
                    "primaryColor": "#1677ff",
                    "propertyFilters": self._property_batch_showcase_filters(valid_notes),
                    "source": source,
                    "importBatchId": import_batch_id,
                    "intakeId": intake_id,
                    "idempotencyKey": idempotency_key,
                    "rawTextLength": len(raw_text or ""),
                }
            ),
            items=[
                ShowcaseItem(
                    noteId=note.id,
                    sortOrder=index,
                    sectionTitle="本次导入",
                    displayTitle=note.title,
                    visible=True,
                    fieldConfig={"source": source, "importBatchId": import_batch_id},
                )
                for index, note in enumerate(valid_notes)
            ],
            createdAt=now,
            updatedAt=now,
        )
        showcase.displayConfig["source"] = source
        showcase.displayConfig["importBatchId"] = import_batch_id
        showcase.displayConfig["rawTextLength"] = len(raw_text or "")
        self.repo.save_showcase_page(showcase)
        self._invalidate_showcase_list_cache(owner_user_id)
        return showcase

    def _property_batch_showcase_location(self, notes: list[UserNote]) -> str:
        for note in notes:
            config = note.visibilityConfig if isinstance(note.visibilityConfig, dict) else {}
            structured = config.get("structuredData") if isinstance(config.get("structuredData"), dict) else {}
            for key in ("community", "businessArea", "address", "buildingRoom"):
                value = self._clean_optional_text(structured.get(key))
                if value:
                    return value[:12]
        return ""

    def _property_batch_showcase_filters(self, notes: list[UserNote]) -> list[dict]:
        rows: list[dict] = []
        for key, label in [("area", "区域"), ("layout", "户型"), ("price", "价格")]:
            counts: dict[str, int] = defaultdict(int)
            for note in notes:
                value = self._property_filter_value(note, key)
                if value:
                    counts[value] += 1
            options = [
                {"label": value, "value": value, "count": count}
                for value, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:8]
            ]
            if options:
                rows.append({"key": key, "label": label, "options": options})
        return rows

    def _property_filter_value(self, note: UserNote, key: str) -> str:
        config = note.visibilityConfig if isinstance(note.visibilityConfig, dict) else {}
        data = config.get("structuredData") if isinstance(config.get("structuredData"), dict) else {}
        if key == "area":
            return self._clean_optional_text(data.get("businessArea")) or self._clean_optional_text(data.get("address")) or self._clean_optional_text(data.get("community")) or ""
        if key == "layout":
            return self._property_layout_bucket(str(data.get("layout") or data.get("unitName") or note.title or ""))
        if key == "price":
            return self._property_price_bucket(str(data.get("price") or ""))
        return ""

    def _property_layout_bucket(self, text: str) -> str:
        value = str(text or "")
        if "三房" in value or "三室" in value or "3房" in value or "3室" in value:
            return "三房"
        if "两房" in value or "二房" in value or "两室" in value or "二室" in value or "2房" in value or "2室" in value:
            return "两房"
        if "主卧" in value:
            return "主卧"
        if "次卧" in value:
            return "次卧"
        if "一室一厅" in value:
            return "一室一厅"
        if "一房" in value or "一室" in value or "1房" in value or "1室" in value or "单间" in value:
            return "一房/单间"
        if "loft" in value.lower() or "复式" in value:
            return "Loft/复式"
        return ""

    def _property_price_bucket(self, text: str) -> str:
        prices = [int(value) for value in re.findall(r"\d{3,5}", str(text or ""))]
        if not prices:
            return ""
        price = min(prices)
        if price < 1000:
            return "1000以下"
        if price < 1500:
            return "1000-1500"
        if price < 2000:
            return "1500-2000"
        if price < 3000:
            return "2000-3000"
        return "3000以上"

    def create_quick_note_capture(self, payload: QuickNoteCaptureRequest) -> UserNote:
        owner_user_id = payload.ownerUserId.strip()
        raw_text = strip_unicode_surrogates(payload.rawText).strip()
        title = strip_unicode_surrogates(payload.title or "").strip()
        if not self.repo.get_user(owner_user_id):
            raise HTTPException(status_code=404, detail="用户不存在")
        if not raw_text:
            raise HTTPException(status_code=400, detail="请先输入内容")
        existing = self._find_note_by_idempotency(owner_user_id, payload.idempotencyKey)
        if existing:
            return existing
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
        self._mark_new_intake(note, payload.intakeId, payload.idempotencyKey, "captured")
        skill_run = SkillRun.model_validate(note_result.skillRun.model_dump())
        skill_run.outputRef = note.id
        skill_run.inputSnapshot = {
            **skill_run.inputSnapshot,
            "entryMode": "quick_note",
        }
        self.repo.save_user_note(note)
        self.repo.save_skill_run(skill_run)
        self._invalidate_card_list_cache(owner_user_id)
        return note

    def create_link_note_capture(self, payload: LinkCaptureRequest) -> UserNote:
        owner_user_id = payload.ownerUserId.strip()
        source_url = strip_unicode_surrogates(payload.url or "").strip()
        manual_title = strip_unicode_surrogates(payload.title or "").strip()
        if not self.repo.get_user(owner_user_id):
            raise HTTPException(status_code=404, detail="用户不存在")
        existing = self._find_note_by_idempotency(owner_user_id, payload.idempotencyKey)
        if existing:
            return existing
        try:
            preview = fetch_link_preview(source_url)
        except ValueError as exc:
            message = str(exc)
            if message in {"只支持公开的 https:// 网页链接", "链接域名无法访问", "不支持内网或本机链接"}:
                raise HTTPException(status_code=400, detail=message) from exc
            parsed = urlparse(source_url)
            preview = {
                "url": source_url,
                "title": "",
                "description": "",
                "coverUrl": "",
                "sourceName": parsed.hostname or "网页链接",
                "sourceLabel": "公众号文章" if parsed.hostname == "mp.weixin.qq.com" else "网页链接",
                "parseStatus": "fetch_failed",
            }
        except httpx.HTTPError:
            parsed = urlparse(source_url)
            preview = {
                "url": source_url,
                "title": "",
                "description": "",
                "coverUrl": "",
                "sourceName": parsed.hostname or "网页链接",
                "sourceLabel": "公众号文章" if parsed.hostname == "mp.weixin.qq.com" else "网页链接",
                "parseStatus": "fetch_failed",
            }

        title = manual_title or preview["title"] or preview["sourceName"] or "已收藏链接"
        media = [ContentMediaPayload(
            id=new_id("link"),
            type="link",
            url=preview["url"],
            title=title,
            description=preview["description"] or None,
            coverUrl=preview["coverUrl"] or None,
            source="manual",
            status="ready",
        )]
        content_object = ContentObjectPayload(
            sourceType="web_link",
            title=title,
            links=[ContentLinkPayload(
                url=preview["url"],
                title=title,
                description=preview["description"] or None,
                coverUrl=preview["coverUrl"] or None,
            )],
            media=media,
            metadata={"entryMode": "link_capture", "linkPreview": preview},
            sourceRefs=[new_id("manual_link")],
        )
        note_result = self.skill_router_service.run_link_bookmark(owner_user_id, content_object)
        note = self._build_user_note_from_note_draft(note_result.noteDraft)
        note.status = "active"
        note.title = title
        note.summary = preview["description"] or "已收藏，待整理。"
        note.body = "\n".join(item for item in [preview["description"], preview["url"]] if item)
        note.coverUrl = preview["coverUrl"] or None
        config = dict(note.visibilityConfig or {})
        structured_data = dict(config.get("structuredData") or {})
        structured_data["parseStatus"] = preview["parseStatus"]
        config.update({
            "entryMode": "link_capture",
            "sourceUrl": preview["url"],
            "sourceName": preview["sourceName"],
            "sourceLabel": preview["sourceLabel"],
            "structuredData": structured_data,
        })
        note.visibilityConfig = config
        self._mark_new_intake(note, payload.intakeId, payload.idempotencyKey, "captured")
        skill_run = SkillRun.model_validate(note_result.skillRun.model_dump())
        skill_run.outputRef = note.id
        self.repo.save_user_note(note)
        self.repo.save_skill_run(skill_run)
        self._invalidate_card_list_cache(owner_user_id)
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

    def _create_manual_note_from_text(
        self,
        owner_user_id: str,
        card_type: str,
        raw_text: str,
        title: str,
        intake_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> UserNote:
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
        self._mark_new_intake(note, intake_id, idempotency_key, "captured")
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

    def _create_blank_manual_note(
        self,
        owner_user_id: str,
        card_type: str,
        title: str,
        intake_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> UserNote:
        now = now_iso()
        defaults = {
            "property_listing": ("未命名房源", "补充房源字段后即可发给客户"),
            "groupbuy_product": ("", ""),
            "business_card": ("我的电子名片", ""),
            "service_offer": ("", ""),
            "text_note": ("", ""),
        }
        default_title, default_summary = defaults[card_type]
        user = self.repo.get_user(owner_user_id)
        seed_config = {"structuredData": {"headline": "", "serviceKeywords": [], "bio": "", "featuredNoteIds": []}} if card_type == "business_card" else {}
        note = UserNote(
            id=new_id("note"),
            ownerUserId=owner_user_id,
            importBatchId=None,
            sourceCardId=None,
            status="active",
            shareState="private",
            revision=0,
            title=title or default_title,
            summary=default_summary,
            body="" if card_type in {"text_note", "groupbuy_product", "service_offer", "business_card"} else "手动创建，可继续补充内容。",
            coverUrl=user.avatarUrl if card_type == "business_card" and user and user.avatarUrl else None,
            media=[],
            categoryIds=[],
            phone=None,
            locationText=None,
            sourceRefs=[],
            visibilityConfig=seed_config,
            createdAt=now,
            updatedAt=now,
        )
        note = self._apply_manual_selected_note_type(note, card_type, input_mode="blank")
        self._mark_new_intake(note, intake_id, idempotency_key, "editing")
        self.repo.save_user_note(note)
        return note

    def _build_user_note_from_note_draft(self, note_draft: UserNoteDraftPayload) -> UserNote:
        now = now_iso()
        note = UserNote(
            id=new_id("note"),
            ownerUserId=note_draft.ownerUserId or "unclaimed",
            importBatchId=None,
            sourceCardId=None,
            status="active",
            title=note_draft.title,
            summary=note_draft.summary,
            body=note_draft.body,
            contentBlocks=self._normalize_note_content_blocks(
                getattr(note_draft, "contentBlocks", None),
                body=note_draft.body,
                media=[item.model_dump() for item in note_draft.media],
            ),
            coverUrl=note_draft.coverUrl,
            media=[item.model_dump() for item in note_draft.media],
            categoryIds=note_draft.categoryIds,
            phone=note_draft.phone,
            locationText=note_draft.locationText,
            sourceRefs=note_draft.sourceRefs,
            shareState="private",
            revision=0,
            visibilityConfig=note_draft.visibilityConfig,
            createdAt=now,
            updatedAt=now,
        )
        self._apply_owner_public_contact_to_property_note(note)
        return note

    def _apply_owner_public_contact_to_property_note(self, note: UserNote) -> None:
        config = self._normalize_note_visibility_config(note.visibilityConfig)
        if config.get("cardType") != "property_listing":
            note.visibilityConfig = config
            return
        owner = self.repo.get_user(note.ownerUserId)
        structured_data = dict(config.get("structuredData") or {})
        conversion_config = self._normalize_conversion_config("property_listing", config.get("conversionConfig"))
        phone = self._clean_optional_text(owner.phone if owner else "")
        wechat = self._clean_optional_text(owner.wechat if owner else "")
        if phone:
            if not structured_data.get("phone"):
                structured_data["phone"] = phone
            if not structured_data.get("contact"):
                structured_data["contact"] = phone
            if not structured_data.get("contactPhone"):
                structured_data["contactPhone"] = phone
            note.phone = structured_data.get("phone") or phone
            conversion_config["showContactPhone"] = True
        else:
            note.phone = None
            conversion_config["showContactPhone"] = False
        if wechat:
            if not structured_data.get("wechat"):
                structured_data["wechat"] = wechat
            if not structured_data.get("contactWechat"):
                structured_data["contactWechat"] = wechat
            conversion_config["enablePrivateConsultation"] = True
        config["structuredData"] = structured_data
        config["conversionConfig"] = conversion_config
        config["showPhone"] = bool(phone)
        note.visibilityConfig = config

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
        self._apply_owner_public_contact_to_property_note(note)
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

    def save_wecom_archive_messages(
        self,
        corp_id: str,
        messages: list[dict],
        *,
        advance_cursor: bool = True,
        refresh_media_on_duplicate: bool = False,
    ) -> dict:
        existing_msg_ids = self.repo.existing_wecom_archive_msg_ids(
            {item.get("msgid") or item.get("msgId") for item in messages if item.get("msgid") or item.get("msgId")}
        )
        now = now_iso()
        archive_messages: list[WecomArchiveMessage] = []
        max_seq = 0
        skipped = 0
        refreshed = 0
        for index, item in enumerate(messages):
            msg_id = item.get("msgid") or item.get("msgId")
            if msg_id and msg_id in existing_msg_ids:
                if refresh_media_on_duplicate and item.get("mediaRefs"):
                    existing = self.repo.get_wecom_archive_message_by_msg_id(msg_id)
                    decrypted_payload = item.get("decryptedPayload")
                    if existing and isinstance(decrypted_payload, dict):
                        existing.rawPayload = item
                        existing.decryptedPayload = decrypted_payload
                        existing.mediaRefs = item.get("mediaRefs") or []
                        existing.processError = None
                        self.repo.save_wecom_archive_messages([existing])
                        refreshed += 1
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
            if advance_cursor:
                self.advance_wecom_archive_cursor(corp_id, max_seq, {"savedCount": len(archive_messages)}, status="success")
        cursor = self.repo.get_wecom_archive_cursor(corp_id)
        return {
            "savedCount": len(archive_messages),
            "skippedDuplicateCount": skipped,
            "refreshedMediaCount": refreshed,
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
                bind_result = self._consume_wecom_bind_code_from_archive_messages(primary.fromUser, group_messages)
                if bind_result["consumedMessages"]:
                    processed_at = now_iso()
                    for message in bind_result["consumedMessages"]:
                        message.generatedNoteId = "wecom_bind_code"
                        message.processedAt = processed_at
                        message.processError = None
                    self.repo.save_wecom_archive_messages(bind_result["consumedMessages"])
                group_messages = bind_result["remainingMessages"]
                if not group_messages:
                    processed.append(
                        {
                            "archiveMessageIds": [message.id for message in bind_result["consumedMessages"]],
                            "bindResult": bind_result["result"],
                        }
                    )
                    continue
                primary = group_messages[0]
                content_object = self._build_archive_content_object(group_messages)
                media_result = self._download_and_attach_archive_media(content_object, archive_client)
                content_object = self._enrich_internal_miniapp_content(content_object)
                owner_user_id = self._resolve_owner_user_id_for_external(primary.fromUser)
                property_batch_result = self._try_create_import_property_batch(
                    owner_user_id,
                    content_object,
                    None,
                    [item.id for item in group_messages],
                )
                if property_batch_result:
                    count = property_batch_result["createdCount"]
                    notes = property_batch_result["notes"]
                    batch = self._build_archive_import_batch(primary, f"批量房源 {count}套", group_messages)
                    batch.generatedNoteId = notes[0].id if notes else None
                    batch.status = "claimed"
                    batch.claimedByUserId = owner_user_id
                    batch.updatedAt = now_iso()
                    for note in notes:
                        note.importBatchId = batch.id
                        note.sourceRefs = [item.id for item in group_messages]
                        note.updatedAt = now_iso()
                        self.repo.save_user_note(note)
                    self._invalidate_card_list_cache(owner_user_id)
                    showcase = self._create_property_batch_showcase(
                        owner_user_id,
                        notes,
                        "\n".join(block for block in content_object.textBlocks if str(block or "").strip()),
                        source="wecom_archive_property_batch",
                        import_batch_id=batch.id,
                    )
                    skill_run = SkillRun(
                        id=new_id("skill_run"),
                        skillId="property-batch-import",
                        status="success",
                        inputSnapshot={
                            **content_object.model_dump(),
                            "wecomArchiveMessageIds": [item.id for item in group_messages],
                            "archiveSeqs": [item.seq for item in group_messages],
                            "archiveMsgIds": [item.msgId for item in group_messages],
                            "archiveMedia": media_result,
                            "detectedCount": count,
                            "showcaseId": showcase.id,
                        },
                        outputRef=showcase.id,
                        modelProvider="rule",
                        startedAt=batch.createdAt,
                        endedAt=now_iso(),
                    )
                    processed_at = now_iso()
                    for message in group_messages:
                        message.generatedNoteId = batch.generatedNoteId
                        message.generatedCardId = None
                        message.processedAt = processed_at
                        message.processError = None
                    self.repo.save_import_batch(batch)
                    self.repo.save_skill_run(skill_run)
                    self.repo.save_wecom_archive_messages(group_messages)
                    notification = self.notification_service.build_notification(batch, channel="wecom")
                    notification.resultPath = self.build_import_claim_link(batch.id)["pagePath"]
                    notification.actions = [
                        {"key": "open-showcase", "label": "查看房源合集", "path": f"/pages/showcase-edit/index?id={showcase.id}"},
                        {"key": "open-result", "label": "查看首套房源", "path": f"/pages/note-edit/index?id={batch.generatedNoteId}" if batch.generatedNoteId else notification.resultPath},
                    ]
                    self.repo.save_import_notification(notification)
                    processed.append(
                        {
                            "archiveMessageId": primary.id,
                            "archiveMessageIds": [item.id for item in group_messages],
                            "seq": primary.seq,
                            "seqs": [item.seq for item in group_messages],
                            "noteId": batch.generatedNoteId,
                            "cardId": None,
                            "showcaseId": showcase.id,
                            "propertyBatchCount": count,
                            "media": media_result,
                            "notification": notification.model_dump(),
                        }
                    )
                    continue
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
                self._invalidate_card_list_cache(owner_user_id)
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
            "remappedCount": 0,
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
            fresh_media_by_source_ref: dict[str, str] = {}
            archive_messages = self.repo.list_wecom_archive_messages_by_generated_note_id(note.id)
            archive_messages = [item for item in archive_messages if item.decryptedPayload]
            if archive_messages:
                fresh_content = self._build_archive_content_object(archive_messages)
                fresh_media_by_source_ref = {
                    item.sourceRef: item.mediaId
                    for item in fresh_content.media
                    if item.sourceRef and item.mediaId
                }
            for item in note.media:
                if not isinstance(item, dict):
                    continue
                media_id = item.get("mediaId")
                media_type = item.get("type") if item.get("type") in {"image", "video", "file"} else "file"
                fresh_media_id = fresh_media_by_source_ref.get(str(item.get("sourceRef") or ""))
                if fresh_media_id and fresh_media_id != media_id:
                    item["mediaId"] = fresh_media_id
                    media_id = fresh_media_id
                    note_changed = True
                    result["remappedCount"] += 1
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
            self._mark_note_content_edit(note, "editing")
            note.updatedAt = now_iso()
            self.repo.save_user_note(note)
            self._invalidate_card_list_cache(note.ownerUserId)
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
            if not groups or not self._can_merge_archive_message(groups[-1][0], message):
                groups.append([message])
                continue
            groups[-1].append(message)
        return groups

    def _can_merge_archive_message(self, first: WecomArchiveMessage, current: WecomArchiveMessage) -> bool:
        if first.msgType == "note" or current.msgType == "note":
            return False
        if first.fromUser != current.fromUser:
            return False
        if self._archive_conversation_key(first) != self._archive_conversation_key(current):
            return False
        return self._archive_message_timestamp(current) - self._archive_message_timestamp(first) <= WINDOW_SECONDS

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

    def _try_create_import_property_batch(
        self,
        owner_user_id: str,
        content_object: ContentObjectPayload,
        import_batch_id: str | None,
        source_refs: list[str],
    ) -> dict | None:
        if owner_user_id == "unclaimed" or not self.repo.get_user(owner_user_id):
            return None
        raw_text = "\n".join(block for block in content_object.textBlocks if str(block or "").strip()).strip()
        if not raw_text or not self._looks_like_property_batch_text(raw_text):
            return None
        parsed = self._parse_property_batch_text(raw_text)
        candidates = [item for item in parsed.get("candidates", []) if item.get("selected")]
        if len(candidates) < 2:
            return None
        notes: list[UserNote] = []
        for candidate in candidates:
            note = self._create_property_note_from_batch_candidate(owner_user_id, raw_text, candidate)
            note.importBatchId = import_batch_id
            note.sourceRefs = source_refs
            note.updatedAt = now_iso()
            self.repo.save_user_note(note)
            notes.append(note)
        return {
            "createdCount": len(notes),
            "notes": notes,
            "parseResult": parsed,
        }

    def _looks_like_property_batch_text(self, raw_text: str) -> bool:
        normalized_text = self._normalize_property_batch_text(raw_text)
        lines = [line.strip() for line in re.split(r"[\r\n]+", normalized_text) if line.strip()]
        numbered_count = sum(1 for line in lines if re.match(r"^[0-9一二三四五六七八九十]+[）)、，,、.．]", line))
        rent_line_count = sum(
            1
            for line in lines
            if re.search(r"(次卧|主卧|次一室户|一室一厅|一室户|一房|两房|三房|阁楼|独卫|大厅|号房).{0,16}\d{3,5}(?:元|/月|已空|以空|，|,|。|（|\(|$)", line)
        )
        table_room_price_count = sum(1 for line in lines if re.search(r"^\d{1,3}号房[一\-—:：]?\d{3,5}", line))
        building_line_count = sum(1 for line in lines if self._property_batch_is_building_line(line))
        area_header_count = sum(1 for line in lines if self._property_batch_is_area_header(line))
        table_style_count = min(table_room_price_count, building_line_count + area_header_count)
        structured_field_count = sum(1 for line in lines if re.search(r"(小区|户型|价格)[：:]", line))
        room_price_count = sum(1 for line in lines if re.search(r"^\D{0,8}\d{1,4}室\d{3,5}", self._clean_property_batch_line(line)))
        address_group_count = sum(1 for line in lines if re.search(r"(村|小区|新村|路|弄|宅).{0,16}\d+号$", self._clean_property_batch_line(line)))
        has_contact = bool(re.search(r"1[3-9]\d{9}", raw_text))
        has_property_context = bool(re.search(r"(挂牌|房源|直租|看房|中介费|佣金|小区|户型|民水民电|居住证|地铁|苑|园|府|里|城|公寓|大厦|广场|号|栋|幢|室|户|号房)", normalized_text))
        element_score = 0
        if has_property_context:
            element_score += 1
        if numbered_count >= 2:
            element_score += 1
        if rent_line_count >= 2:
            element_score += 2
        elif rent_line_count == 1:
            element_score += 1
        if table_style_count >= 2:
            element_score += 3
        elif table_style_count == 1:
            element_score += 1
        if structured_field_count >= 4:
            element_score += 3
        elif structured_field_count >= 2:
            element_score += 1
        if room_price_count >= 2 and address_group_count >= 2:
            element_score += 3
        if has_contact:
            element_score += 1
        if re.search(r"\d{2,5}(?:弄|号|栋|幢|室|户|房|楼)", normalized_text):
            element_score += 1
        if re.search(r"(中介费|佣金|看房|搬空|已空|以空|空置|朋友圈.*视频|视频|禁.*宠|不养宠)", raw_text):
            element_score += 1
        return has_property_context and element_score >= 5

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
        public_data = self._sanitize_public_config_value(self._public_clone_structured_data(structured))
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
        blocked_fragments = {
            "contact", "phone", "wechat", "landlord", "upstream", "channel", "supplier", "cost", "profit",
            "internal", "inventory", "purchase", "commission", "password", "lockpassword", "rawtext",
            "customer", "visitor", "analytics", "followup", "relayentries", "orderrecords",
            "微信", "电话", "房东", "上游", "渠道", "供应商", "成本", "利润", "库存", "采购", "佣金", "密码", "客户", "访客", "跟进",
        }

        def clean(value, key=""):
            lowered = str(key).replace("_", "").lower()
            if any(fragment in lowered for fragment in blocked_fragments):
                return None, False
            if isinstance(value, dict):
                result = {}
                for child_key, child_value in value.items():
                    cleaned, keep = clean(child_value, child_key)
                    if keep:
                        result[child_key] = cleaned
                return result, True
            if isinstance(value, list):
                result = []
                for child in value:
                    cleaned, keep = clean(child)
                    if keep:
                        result.append(cleaned)
                return result, True
            return value, isinstance(value, (str, int, float, bool)) or value is None

        cleaned, _ = clean(data)
        return cleaned if isinstance(cleaned, dict) else {}

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
        return self.skill_router_service.is_image_primary_import(content_object) and any(
            item.url for item in content_object.media
        )

    def _build_image_import_note_result(
        self,
        owner_user_id: str,
        content_object: ContentObjectPayload,
    ) -> RunContentToNoteResponse:
        first_image = next(item for item in content_object.media if item.type == "image" and item.url)
        visibility_config = self._image_note_visibility_config(first_image.url or "", first_image.title)
        structured_data = dict(visibility_config.get("structuredData") or {})
        caption = "\n".join(self.skill_router_service.meaningful_import_text_blocks(content_object)).strip()
        structured_data["images"] = [item.url for item in content_object.media if item.type == "image" and item.url]
        structured_data["rawText"] = caption
        if caption:
            structured_data["caption"] = caption
        structured_data["sourceRefs"] = content_object.sourceRefs or content_object.rawMessageIds
        visibility_config["structuredData"] = structured_data
        now = now_iso()
        body = caption or "图片已保存。你可以直接手动补充正文和字段，也可以点击识别图片文字后再整理。"
        summary = caption[:120] if caption else "图片已保存，可按需识别文字。"
        note = UserNoteDraftPayload(
            ownerUserId=owner_user_id,
            title=self._image_import_title(content_object, first_image),
            summary=summary,
            body=body,
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
        caption = "\n".join(self.skill_router_service.meaningful_import_text_blocks(content_object)).strip()
        if caption:
            return self.skill_router_service._truncate(caption, 40)
        image_title = str(first_image.title or "").strip()
        if image_title:
            return image_title
        title = str(content_object.title or "").strip()
        if title and title not in {"未命名素材", "企业微信image归档", "收到image素材，媒体稍后转存。"}:
            return title
        return "图片资料"

    def _should_light_bookmark(self, content_object: ContentObjectPayload) -> bool:
        if content_object.sourceType != "link_article" or not content_object.links:
            return False
        text = "\n".join(content_object.textBlocks)
        deep_keywords = ["整理链接", "链接总结", "文章总结", "整理文章", "总结文章", "提炼", "做笔记"]
        return not any(keyword in text for keyword in deep_keywords)

    def _new_wecom_bind_code(self) -> str:
        active_codes = {
            self._wecom_bind_code_from_intent(item)
            for item in self._active_wecom_bind_intents()
        }
        for _ in range(10):
            code = f"TB-{uuid4().hex[:6].upper()}"
            if code not in active_codes:
                return code
        return f"TB-{uuid4().hex[:6].upper()}"

    def _wecom_bind_message(self, bind_code: str) -> str:
        return (
            "你好，我刚添加了“资料整理助手”，请帮我把我的微信账号和资料库绑定起来。\n\n"
            f"绑定口令：{bind_code}\n\n"
            "绑定完成后，我发给你的图片、文件和链接会自动整理到我的小程序资料库。"
        )

    def _find_wecom_bind_code(self, text: str | None) -> str | None:
        match = WECOM_BIND_CODE_PATTERN.search(text or "")
        return match.group(0).upper() if match else None

    def _wecom_bind_code_from_intent(self, intent: WecomIdentityBinding) -> str | None:
        parts = (intent.externalUserId or "").split(":")
        if len(parts) >= 3 and parts[0] == "pending":
            return parts[2].upper()
        return None

    def _consume_wecom_bind_code(
        self,
        bind_code: str | None,
        external_user_id: str | None,
    ) -> dict | None:
        if not bind_code or not external_user_id or external_user_id == "archive_unknown":
            return None
        code = bind_code.upper()
        existing = self.repo.get_wecom_identity_binding(WECOM_EXTERNAL_BINDING_SOURCE, external_user_id)
        if existing:
            return {
                "status": "already_bound",
                "bindCode": code,
                "ownerUserId": existing.ownerUserId,
            }
        matches = [
            item
            for item in self._active_wecom_bind_intents()
            if self._wecom_bind_code_from_intent(item) == code
        ]
        if len(matches) != 1:
            return {"status": "not_found_or_expired", "bindCode": code}
        intent = matches[0]
        owner = self.repo.get_user(intent.ownerUserId)
        if not owner:
            return {"status": "owner_missing", "bindCode": code}
        now = now_iso()
        self._save_wecom_identity_binding(
            external_user_id=external_user_id,
            owner_user_id=owner.id,
            import_batch_id=None,
            bind_source="bind_code",
        )
        consumed = intent.model_copy(
            update={
                "bindSource": WECOM_BIND_INTENT_CONSUMED,
                "lastImportBatchId": external_user_id,
                "updatedAt": now,
            }
        )
        self.repo.save_wecom_identity_binding(consumed)
        return {
            "status": "bound",
            "bindCode": code,
            "ownerUserId": owner.id,
            "ownerOpenid": owner.openid,
        }

    def _consume_wecom_bind_code_from_raw_messages(self, messages: list[RawMessage]) -> dict:
        remaining: list[RawMessage] = []
        consumed: list[RawMessage] = []
        result: dict | None = None
        for message in messages:
            code = None
            if message.msgType == "text":
                code = self._find_wecom_bind_code(str(message.content.get("text") or ""))
            if code:
                consumed.append(message)
                result = result or self._consume_wecom_bind_code(code, message.externalUserId)
                continue
            remaining.append(message)
        return {
            "remainingMessages": remaining,
            "consumedMessages": consumed,
            "result": result,
            "message": "资料助手绑定成功，后续发送资料会自动入库" if result and result.get("status") in {"bound", "already_bound"} else None,
        }

    def _consume_wecom_bind_code_from_archive_messages(
        self,
        external_user_id: str | None,
        messages: list[WecomArchiveMessage],
    ) -> dict:
        remaining: list[WecomArchiveMessage] = []
        consumed: list[WecomArchiveMessage] = []
        result: dict | None = None
        for message in messages:
            parsed = self.content_object_adapter.from_wecom_archive_message(message)
            code = next(
                (self._find_wecom_bind_code(block) for block in parsed.textBlocks if self._find_wecom_bind_code(block)),
                None,
            )
            if code:
                consumed.append(message)
                result = result or self._consume_wecom_bind_code(code, external_user_id or message.fromUser)
                continue
            remaining.append(message)
        return {
            "remainingMessages": remaining,
            "consumedMessages": consumed,
            "result": result,
        }

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
        # The historical intent fallback is retained for local low-concurrency
        # tests only.  Production must never infer an identity from a pending
        # mini-program screen; the contact welcome card is the explicit proof.
        if str(settings.app_env or "").lower() == "production":
            return "unclaimed"
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

    def _find_wecom_external_binding_for_owner(self, owner_user_id: str, owner_openid: str | None = None) -> WecomIdentityBinding | None:
        for item in sorted(self.repo.load().wecom_identity_bindings, key=lambda row: row.updatedAt, reverse=True):
            if item.sourceType != WECOM_EXTERNAL_BINDING_SOURCE:
                continue
            if item.ownerUserId == owner_user_id or (owner_openid and item.ownerOpenid == owner_openid):
                return item
        return None

    def _find_active_wecom_bind_intent_for_owner(self, owner_user_id: str) -> WecomIdentityBinding | None:
        for item in self._active_wecom_bind_intents():
            if item.ownerUserId == owner_user_id and self._wecom_bind_code_from_intent(item):
                return item
        return None

    def _wecom_bind_intent_expires_at(self, intent: WecomIdentityBinding) -> datetime:
        ttl_seconds = max(60, settings.wecom_bind_intent_ttl_seconds)
        try:
            base = parse_iso(intent.updatedAt).astimezone(SHANGHAI)
        except Exception:
            base = datetime.now(tz=SHANGHAI)
        return base + timedelta(seconds=ttl_seconds)

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
        storage_service: MediaStorageService | None = None,
        preserve_share_format: bool = False,
        preserve_source_format: bool = False,
    ) -> str:
        if not content:
            raise HTTPException(status_code=400, detail="媒体内容不能为空")
        normalized_type = "video" if media_type == "video" else "image" if media_type == "image" else str(media_type or "file")
        max_bytes = {
            "image": settings.media_max_image_bytes,
            "video": settings.media_max_video_bytes,
            "pdf": settings.media_max_pdf_bytes,
        }.get(normalized_type)
        if max_bytes and len(content) > max_bytes:
            raise HTTPException(status_code=413, detail="媒体超过服务器允许的大小")
        original_sha256 = hashlib.sha256(content).hexdigest()
        if not preserve_share_format:
            existing = self.repo.get_media_asset_by_original_hash(normalized_type, original_sha256)
            if existing:
                self._save_media_asset_ref(existing, owner_user_id, ref_type, ref_id or media_id, usage)
                return existing.url
        if preserve_source_format and normalized_type == "image":
            processed = self.media_processing_service.process_source_image(
                content,
                content_type=content_type,
                filename=filename,
            )
        elif preserve_share_format and normalized_type == "image":
            processed = self.media_processing_service.process_share_image(content, filename)
        else:
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
        target_storage = storage_service or self.media_storage_service
        # The content hash, rather than the caller's temporary media id, is the
        # object key. This makes concurrent uploads of the same processed bytes
        # converge on one physical object as well as one MediaAsset row.
        storage_media_id = f"asset_{normalized_type}_{storage_sha256}"
        url = target_storage.store_bytes(
            media_id=storage_media_id,
            media_type=normalized_type,
            content=processed.content,
            content_type=processed.content_type,
            # The hash is the full identity; do not let the user's filename
            # create a second extension/path for the same processed bytes.
            filename=None,
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
        saved = self.repo.save_media_asset(asset)
        if not saved:
            # A second process may have passed the pre-check before the first
            # process committed. The database unique indexes are the final
            # arbiter; reuse the winner and never create a second asset row.
            existing = self.repo.get_media_asset_by_original_hash(normalized_type, original_sha256)
            existing = existing or self.repo.get_media_asset_by_storage_hash(normalized_type, storage_sha256)
            if existing:
                if url != existing.url:
                    target_storage.delete_url(url)
                self._save_media_asset_ref(existing, owner_user_id, ref_type, ref_id or media_id, usage)
                return existing.url
            raise RuntimeError("媒体资产去重冲突后未找到已保存的资产")
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
        normalized_owner = self._clean_optional_text(owner_user_id)
        normalized_type = self._clean_optional_text(ref_type) or "media"
        normalized_usage = self._clean_optional_text(usage) or "media"
        if any(
            ref.ownerUserId == normalized_owner
            and ref.refType == normalized_type
            and ref.usage == normalized_usage
            for ref in self.repo.list_media_asset_refs(asset_id=asset.id, ref_type=normalized_type, ref_id=ref_id)
        ):
            return
        now = now_iso()
        ref = MediaAssetRef(
            id=new_id("media_ref"),
            assetId=asset.id,
            ownerUserId=normalized_owner,
            refType=normalized_type,
            refId=ref_id,
            usage=normalized_usage,
            createdAt=now,
            updatedAt=now,
        )
        self.repo.save_media_asset_ref(ref)

    def _sync_share_snapshot_media_ref(self, url: str, owner_user_id: str, entity_id: str) -> None:
        asset = self.repo.get_media_asset_by_url(url)
        if not asset:
            return
        self._save_media_asset_ref(asset, owner_user_id, "share_snapshot", entity_id, "current")

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
        intake_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict:
        if not self.repo.get_user(owner_user_id):
            raise HTTPException(status_code=404, detail="用户不存在")
        existing = self._find_note_by_idempotency(owner_user_id, idempotency_key)
        if existing:
            return {
                "note": existing.model_dump(),
                "ocr": self._ocr_response_payload_from_data(
                    ((existing.visibilityConfig or {}).get("structuredData") or {}).get("ocr") or {}
                ),
            }
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
            contentBlocks=[
                {
                    "id": media[0].get("id") or new_id("content_block"),
                    "type": "image",
                    "mediaId": media[0].get("id"),
                    "url": stored_url,
                    "sortOrder": 0,
                }
            ],
            coverUrl=stored_url,
            media=media,
            categoryIds=[],
            phone=None,
            locationText=None,
            sourceRefs=[],
            shareState="private",
            revision=0,
            intakeId=self._clean_optional_text(intake_id),
            idempotencyKey=self._clean_optional_text(idempotency_key),
            visibilityConfig=self._image_note_visibility_config(stored_url, filename),
            createdAt=now,
            updatedAt=now,
        )
        self._mark_new_intake(note, intake_id, idempotency_key, "captured")
        self.repo.save_user_note(note)
        self._invalidate_card_list_cache(owner_user_id)
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

    def mark_ocr_note_queued(self, note_id: str, owner_user_id: str, task_id: str | None = None) -> dict:
        note = self.get_user_note(note_id, owner_user_id)
        config = self._normalize_note_visibility_config(note.visibilityConfig)
        structured = dict(config.get("structuredData") or {})
        ocr_data = dict(structured.get("ocr") or {})
        ocr_data.update(
            {
                "status": "queued",
                "text": ocr_data.get("text") or "",
                "provider": ocr_data.get("provider") or "",
                "configured": bool(ocr_data.get("configured")),
                "confidence": ocr_data.get("confidence"),
                "details": {
                    **(ocr_data.get("details") if isinstance(ocr_data.get("details"), dict) else {}),
                    "reason": "图片已加入识别队列，后台正在处理。",
                    "taskId": task_id,
                },
            }
        )
        structured["ocr"] = ocr_data
        config["structuredData"] = structured
        config["sourceType"] = "ocr"
        config["cardType"] = "image_ocr"
        note.visibilityConfig = config
        note.summary = "图片已保存，正在识别文字。"
        note.body = "图片已保存，后台正在识别文字。识别完成后会自动更新结果。"
        self._mark_note_content_edit(note, "editing")
        note.updatedAt = now_iso()
        self.repo.save_user_note(note)
        return {
            "note": note.model_dump(),
            "ocr": self._ocr_response_payload_from_data(ocr_data),
        }

    def recognize_ocr_note_image(self, note_id: str, owner_user_id: str) -> dict:
        note = self.get_user_note(note_id, owner_user_id)
        image_content, image_name = self._load_note_image_bytes(note)
        if self.property_table_ocr_service.looks_like_property_table_image(image_content):
            return self.recognize_property_table_ocr_note_image(note_id, owner_user_id)
        ocr_result = self.ocr_service.extract_text(image_content, image_name)
        recognized_text = ocr_result.text.strip()
        if not recognized_text:
            note.visibilityConfig = self._ocr_visibility_config(note.visibilityConfig, ocr_result, recognized_text)
            self._mark_note_content_edit(note, "editing")
            note.updatedAt = now_iso()
            self.repo.save_user_note(note)
            return {
                "note": note.model_dump(),
                "ocr": self._ocr_response_payload(ocr_result, recognized_text),
            }
        property_batch_result = self._try_create_ocr_property_batch(note, owner_user_id, recognized_text, ocr_result)
        if property_batch_result:
            return property_batch_result
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
        self._mark_note_content_edit(note, "editing")
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

    def recognize_property_table_ocr_note_image(self, note_id: str, owner_user_id: str) -> dict:
        note = self.get_user_note(note_id, owner_user_id)
        image_content, image_name = self._load_note_image_bytes(note)
        ocr_result = self.property_table_ocr_service.extract_text(image_content, image_name)
        recognized_text = ocr_result.text.strip()
        if not recognized_text:
            note.visibilityConfig = self._ocr_visibility_config(note.visibilityConfig, ocr_result, recognized_text)
            self._mark_note_content_edit(note, "editing")
            note.updatedAt = now_iso()
            self.repo.save_user_note(note)
            return {
                "note": note.model_dump(),
                "ocr": self._ocr_response_payload(ocr_result, recognized_text),
            }
        property_batch_result = self._try_create_ocr_property_table_batch(note, owner_user_id, recognized_text, ocr_result)
        if property_batch_result:
            return property_batch_result
        note.visibilityConfig = self._ocr_visibility_config(note.visibilityConfig, ocr_result, recognized_text)
        note.summary = "图片表格已识别，但未达到自动拆分阈值。"
        note.body = recognized_text
        self._mark_note_content_edit(note, "editing")
        note.updatedAt = now_iso()
        self.repo.save_user_note(note)
        return {
            "note": note.model_dump(),
            "ocr": self._ocr_response_payload(ocr_result, recognized_text),
        }

    def _try_create_ocr_property_batch(self, note: UserNote, owner_user_id: str, recognized_text: str, ocr_result) -> dict | None:
        if not recognized_text or not self._looks_like_property_batch_text(recognized_text):
            return None
        parsed = self._parse_property_batch_text(recognized_text)
        candidates = [item for item in parsed.get("candidates", []) if item.get("selected")]
        if len(candidates) < 2:
            return None
        if self._ocr_property_batch_needs_manual_review(recognized_text, candidates, ocr_result):
            return None
        now = now_iso()
        note.visibilityConfig = self._ocr_visibility_config(note.visibilityConfig, ocr_result, recognized_text)
        note.summary = f"图片已识别，并拆出 {len(candidates)} 套房源。"
        note.body = recognized_text
        note.status = "active"
        self._mark_note_content_edit(note, "editing")
        note.updatedAt = now
        self.repo.save_user_note(note)
        notes = [self._create_property_note_from_batch_candidate(owner_user_id, recognized_text, candidate) for candidate in candidates]
        source_refs = [note.id, *note.sourceRefs]
        image_url = note.coverUrl or self._first_note_image_url(note)
        for item in notes:
            item.sourceRefs = self._unique_strings([*source_refs, *item.sourceRefs])
            config = dict(item.visibilityConfig or {})
            config["sourceType"] = "ocr_property_batch"
            config["ocrSourceNoteId"] = note.id
            structured = dict(config.get("structuredData") or {})
            if image_url:
                structured["images"] = self._unique_strings([image_url, *(structured.get("images") or [])])
            structured["ocrSourceNoteId"] = note.id
            config["structuredData"] = structured
            config["tags"] = self._unique_strings([*config.get("tags", []), "图片识别"])
            item.visibilityConfig = self._normalize_note_visibility_config(config)
            item.coverUrl = image_url or item.coverUrl
            item.media = note.media or item.media
            item.updatedAt = now_iso()
            self.repo.save_user_note(item)
        showcase = self._create_property_batch_showcase(
            owner_user_id,
            notes,
            recognized_text,
            source="ocr_property_batch",
            import_batch_id=None,
        )
        skill_run = SkillRun(
            id=new_id("skill_run"),
            skillId="ocr-property-batch-import",
            status="success",
            inputSnapshot={
                "sourceNoteId": note.id,
                "recognizedTextLength": len(recognized_text),
                "detectedCount": len(notes),
                "showcaseId": showcase.id,
                "ocr": {
                    "provider": ocr_result.provider,
                    "configured": ocr_result.configured,
                    "confidence": ocr_result.confidence,
                    "textLength": len(recognized_text),
                },
            },
            outputRef=showcase.id,
            modelProvider="rule",
            startedAt=now,
            endedAt=now_iso(),
        )
        self.repo.save_skill_run(skill_run)
        return {
            "note": note.model_dump(),
            "ocr": self._ocr_response_payload(ocr_result, recognized_text),
            "propertyBatch": {
                "createdCount": len(notes),
                "noteIds": [item.id for item in notes],
                "notes": [item.model_dump() for item in notes],
                "showcaseId": showcase.id,
                "showcase": self._showcase_owner_payload(showcase),
                "parseResult": parsed,
            },
        }

    def _try_create_ocr_property_table_batch(self, note: UserNote, owner_user_id: str, recognized_text: str, ocr_result) -> dict | None:
        parsed = self._parse_property_table_ocr_text(recognized_text)
        candidates = [item for item in parsed.get("candidates", []) if item.get("selected")]
        if len(candidates) < 8:
            return None
        now = now_iso()
        note.visibilityConfig = self._ocr_visibility_config(note.visibilityConfig, ocr_result, recognized_text)
        note.summary = f"图片表格已识别，并拆出 {len(candidates)} 套房源。"
        note.body = recognized_text
        note.status = "active"
        self._mark_note_content_edit(note, "editing")
        note.updatedAt = now
        self.repo.save_user_note(note)
        notes = [self._create_property_note_from_batch_candidate(owner_user_id, recognized_text, candidate) for candidate in candidates]
        source_refs = [note.id, *note.sourceRefs]
        image_url = note.coverUrl or self._first_note_image_url(note)
        for item in notes:
            item.sourceRefs = self._unique_strings([*source_refs, *item.sourceRefs])
            config = dict(item.visibilityConfig or {})
            config["sourceType"] = "ocr_property_table"
            config["ocrSourceNoteId"] = note.id
            structured = dict(config.get("structuredData") or {})
            if image_url:
                structured["images"] = self._unique_strings([image_url, *(structured.get("images") or [])])
            structured["ocrSourceNoteId"] = note.id
            config["structuredData"] = structured
            config["tags"] = self._unique_strings([*config.get("tags", []), "图片表格识别"])
            item.visibilityConfig = self._normalize_note_visibility_config(config)
            item.coverUrl = image_url or item.coverUrl
            item.media = note.media or item.media
            item.updatedAt = now_iso()
            self.repo.save_user_note(item)
        showcase = self._create_property_batch_showcase(
            owner_user_id,
            notes,
            recognized_text,
            source="ocr_property_table",
            import_batch_id=None,
        )
        skill_run = SkillRun(
            id=new_id("skill_run"),
            skillId="ocr-property-table-import",
            status="success",
            inputSnapshot={
                "sourceNoteId": note.id,
                "recognizedTextLength": len(recognized_text),
                "detectedCount": len(notes),
                "showcaseId": showcase.id,
                "ocr": {
                    "provider": ocr_result.provider,
                    "configured": ocr_result.configured,
                    "confidence": ocr_result.confidence,
                    "textLength": len(recognized_text),
                    "details": ocr_result.details,
                },
            },
            outputRef=showcase.id,
            modelProvider="rule",
            startedAt=now,
            endedAt=now_iso(),
        )
        self.repo.save_skill_run(skill_run)
        return {
            "note": note.model_dump(),
            "ocr": self._ocr_response_payload(ocr_result, recognized_text),
            "propertyBatch": {
                "createdCount": len(notes),
                "noteIds": [item.id for item in notes],
                "notes": [item.model_dump() for item in notes],
                "showcaseId": showcase.id,
                "showcase": self._showcase_owner_payload(showcase),
                "parseResult": parsed,
            },
        }

    def _parse_property_table_ocr_text(self, recognized_text: str) -> dict:
        common_private = self._property_batch_common_private_data(recognized_text)
        public_tags = self._property_batch_public_tags(recognized_text)
        private_tags = self._property_batch_private_tags(recognized_text, common_private)
        candidates: list[dict] = []
        for raw_line in re.split(r"[\r\n]+", recognized_text or ""):
            candidate = self._property_table_candidate_from_row(raw_line, public_tags, private_tags, common_private, len(candidates))
            if candidate:
                candidates.append(candidate)
        unique: list[dict] = []
        seen: set[str] = set()
        for item in candidates:
            key = f"{item.get('buildingRoom')}|{item.get('layout')}|{item.get('price')}"
            if key in seen:
                continue
            seen.add(key)
            item["candidateId"] = f"property_candidate_{len(unique) + 1}"
            unique.append(item)
        return {
            "detectedCount": len(unique),
            "candidates": unique,
            "rawText": recognized_text,
            "privacySummary": {
                "publicTags": public_tags,
                "privateTags": private_tags,
                "upstreamPhones": common_private.get("upstreamPhones", []),
                "upstreamWechat": common_private.get("upstreamWechat", ""),
                "commission": common_private.get("commission", ""),
            },
        }

    def _property_table_candidate_from_row(self, raw_line: str, public_tags: list[str], private_tags: list[str], private_data: dict, index: int) -> dict | None:
        line = self._normalize_property_batch_text(raw_line or "")
        line = re.sub(r"[|｜]+", " ", line)
        line = re.sub(r"\s+", " ", line).strip()
        if not line or re.search(r"(区域|商圈|房源地址|户型|月租|联系电话|房源更新|佣金)", line):
            return None
        price_match = re.search(r"(\d{1,2}\s*[,，]\s*\d{3}(?:\s*\.\s*\d{1,2})?|\d{3,5}(?:\s*\.\s*\d{1,2})?)\s*$", line)
        if not price_match:
            return None
        price_raw = price_match.group(1).replace(",", "").replace("，", "").replace(" ", "")
        price = re.sub(r"[^\d]", "", price_raw.split(".", 1)[0])
        if not price or len(price) < 3:
            return None
        left = line[: price_match.start()].strip()
        layout_match = re.search(r"(\d+\s*室\s*\d+\s*厅\s*\d+\s*卫|\d+\s*室\s*\d+\s*卫|\d+\s*室\s*\d+\s*厅|[一二三四五六七八九十]+室[一二三四五六七八九十]*厅?[一二三四五六七八九十]*卫?)", left)
        if not layout_match:
            return None
        layout = re.sub(r"\s+", "", layout_match.group(1))
        prefix = left[: layout_match.start()].strip()
        prefix = re.sub(r"\s+", " ", prefix)
        if not prefix:
            return None
        parts = [item for item in prefix.split(" ") if item]
        area = ""
        business_area = ""
        address_parts: list[str] = []
        if len(parts) >= 2 and re.search(r"(区|县|市)$", parts[1]) and not re.search(r"(区|县|市)$", parts[0]):
            business_area = parts[0]
            area = parts[1]
            address_parts = parts[2:]
        else:
            if parts and (re.search(r"(区|县|市)$", parts[0]) or parts[0] in {"星沙", "经开区"}):
                area = parts[0]
                parts = parts[1:]
            if parts and not re.search(r"(号|栋|幢|座|室|房|公寓|大厦|广场|花园|小区|城|府|苑|园|里)", parts[0]):
                business_area = parts[0]
                parts = parts[1:]
            address_parts = parts
        address = " ".join(address_parts).strip() or prefix
        community = self._property_base_title(re.sub(r"\d{1,5}(?:号|栋|幢|座|室|房).*$", "", address).strip() or address)
        title = f"{community} · {address}".strip(" ·")
        features = self._property_features_from_text(line)
        candidate = self._property_candidate_payload(
            title,
            layout,
            price,
            public_tags,
            private_tags,
            private_data,
            features,
            index,
        )
        candidate["community"] = community
        candidate["buildingRoom"] = address
        candidate["businessArea"] = business_area
        candidate["area"] = area
        candidate["summary"] = " / ".join(self._unique_strings([layout, area, business_area, *features, *public_tags]))
        return candidate

    def _ocr_property_batch_needs_manual_review(self, recognized_text: str, candidates: list[dict], ocr_result) -> bool:
        details = getattr(ocr_result, "details", {}) if ocr_result else {}
        provider = getattr(ocr_result, "provider", "") if ocr_result else ""
        if provider == "mock":
            return False
        table_like = bool(re.search(r"(房源更新|区域|商圈|房源佣金|联系电话)", recognized_text or ""))
        if not table_like:
            return False
        line_count = int(details.get("lineCount") or len([line for line in recognized_text.splitlines() if line.strip()]))
        return line_count >= 12 and len(candidates) < 8

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
                public_base_url=settings.public_base_url,
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
        payload = {
            "type": "image",
            "url": url,
            "title": filename or "图片资料",
        }
        asset = self.repo.get_media_asset_by_url(url)
        if asset:
            payload.update(
                {
                    "mediaAssetId": asset.id,
                    "originalSha256": asset.originalSha256,
                    "storageSha256": asset.storageSha256,
                }
            )
        return payload

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

    def _ocr_response_payload_from_data(self, ocr_data: dict) -> dict:
        return {
            "status": ocr_data.get("status") or "pending",
            "text": ocr_data.get("text") or "",
            "provider": ocr_data.get("provider") or "",
            "configured": bool(ocr_data.get("configured")),
            "confidence": ocr_data.get("confidence"),
            "details": ocr_data.get("details") if isinstance(ocr_data.get("details"), dict) else {},
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
            if local_path.stat().st_size > settings.media_max_image_bytes:
                raise HTTPException(status_code=400, detail="图片超过服务器允许的大小")
            return local_path.read_bytes(), local_path.name
        if image_url.startswith("http://") or image_url.startswith("https://"):
            try:
                with httpx.stream("GET", image_url, timeout=15, follow_redirects=False) as response:
                    response.raise_for_status()
                    content_length = response.headers.get("content-length")
                    try:
                        declared_length = int(content_length) if content_length else None
                    except ValueError:
                        declared_length = None
                    if declared_length and declared_length > settings.media_max_image_bytes:
                        raise ValueError("图片超过服务器允许的大小")
                    chunks: list[bytes] = []
                    total = 0
                    for chunk in response.iter_bytes():
                        total += len(chunk)
                        if total > settings.media_max_image_bytes:
                            raise ValueError("图片超过服务器允许的大小")
                        chunks.append(chunk)
                    content = b"".join(chunks)
            except Exception as exc:
                raise HTTPException(status_code=400, detail=f"图片读取失败：{exc}") from exc
            return content, Path(urlparse(image_url).path).name or "ocr-image"
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
                # Claiming changes ownership only; the imported draft remains
                # private until the new owner explicitly publishes it.
                note.shareState = "private"
                config = dict(note.visibilityConfig or {})
                config["shareState"] = note.shareState
                config["intakeState"] = config.get("intakeState") or "captured"
                note.visibilityConfig = self._normalize_note_visibility_config(config)
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
            or settings.wecom_kf_callback_token
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
        cache_key = (
            owner_user_id,
            keyword or "",
            category_id or "",
            source_type or "",
            system_category or "",
            tag or "",
            topic_id or "",
            sort or "updated",
            bool(include_deleted),
        )
        cached = self._note_list_cache.get(cache_key)
        now = time.monotonic()
        if cached and now - cached[0] < self._note_list_cache_ttl_seconds:
            return cached[1]
        notes = self.repo.list_user_notes(
            owner_user_id=owner_user_id,
            keyword=None,
            category_id=category_id,
            include_deleted=include_deleted,
        )
        filtered = self._filter_user_notes(notes, keyword, source_type, system_category, tag, topic_id)
        same_style_by_note_id = {}
        for generation in self.repo.list_same_style_generations(owner_user_id):
            if generation.generatedNoteId and generation.generatedNoteId not in same_style_by_note_id:
                same_style_by_note_id[generation.generatedNoteId] = generation
        if sort == "collected":
            base_sort = lambda item: item.createdAt
        else:
            base_sort = lambda item: item.updatedAt
        filtered = sorted(
            filtered,
            key=lambda item: (
                bool(same_style_by_note_id.get(item.id)),
                same_style_by_note_id.get(item.id).createdAt if same_style_by_note_id.get(item.id) else base_sort(item),
            ),
            reverse=True,
        )
        note_ids = {item.id for item in filtered}
        stats_ids = {item.sourceCardId or item.id for item in filtered}
        view_events_by_card = self.repo.list_view_events_for_cards(stats_ids)
        relays_by_card = self.repo.list_relay_entries_for_cards(stats_ids, relay_status="active")
        actions_by_note = self.repo.list_customer_actions_for_notes(note_ids)
        leads_by_owner = {
            owner_id: self.repo.list_lead_reminders(owner_id)
            for owner_id in {item.ownerUserId for item in filtered}
        }
        payload = [
            self._user_note_list_payload(
                item,
                view_events_by_card=view_events_by_card,
                relays_by_card=relays_by_card,
                actions_by_note=actions_by_note,
                leads_by_owner=leads_by_owner,
                same_style_generation=same_style_by_note_id.get(item.id),
            )
            for item in filtered
        ]
        self._note_list_cache[cache_key] = (now, payload)
        if len(self._note_list_cache) > self._note_list_cache_max_entries:
            expired_before = now - self._note_list_cache_ttl_seconds
            self._note_list_cache = {
                key: value
                for key, value in self._note_list_cache.items()
                if value[0] >= expired_before
            }
            if len(self._note_list_cache) > self._note_list_cache_max_entries:
                oldest_keys = sorted(self._note_list_cache, key=lambda key: self._note_list_cache[key][0])
                for old_key in oldest_keys[:len(self._note_list_cache) - self._note_list_cache_max_entries]:
                    self._note_list_cache.pop(old_key, None)
        return payload

    def get_business_card_summary(self, owner_user_id: str) -> dict:
        if not self.repo.get_user(owner_user_id):
            raise HTTPException(status_code=404, detail="用户不存在")
        notes = self.repo.list_user_notes(owner_user_id=owner_user_id, include_deleted=False)
        business_cards = [
            note for note in notes
            if ((note.visibilityConfig or {}).get("cardType") == "business_card")
        ]
        business_card = max(
            business_cards,
            key=lambda item: item.updatedAt or item.createdAt or "",
            default=None,
        )
        legacy_cards = self.repo.list_cards(owner_user_id=owner_user_id)
        legacy_card_ids = {card.id for card in legacy_cards}
        total_resources = len(legacy_cards) + sum(
            1 for note in notes if not note.sourceCardId or note.sourceCardId not in legacy_card_ids
        )
        payload = None
        if business_card:
            config = dict(business_card.visibilityConfig or {})
            config.pop("marketingRoute", None)
            payload = {
                "id": business_card.id,
                "sourceNoteId": business_card.id,
                "title": business_card.title,
                "coverUrl": business_card.coverUrl or "",
                "createdAt": business_card.createdAt,
                "updatedAt": business_card.updatedAt,
                "revision": business_card.revision,
                "status": business_card.status,
                "sourceNoteStatus": business_card.status,
                "shareState": business_card.shareState,
                "sourceNoteShareState": business_card.shareState,
                "cardType": config.get("cardType") or "business_card",
                "visibilityConfig": config,
            }
        return {
            "totalResources": total_resources,
            "businessCard": payload,
        }

    def _user_note_list_payload(
        self,
        note: UserNote,
        *,
        view_events_by_card: dict[str, list[ViewEvent]] | None = None,
        relays_by_card: dict[str, list[RelayEntry]] | None = None,
        actions_by_note: dict[str, list[CustomerAction]] | None = None,
        leads_by_owner: dict[str, list[LeadReminder]] | None = None,
        same_style_generation: SameStyleGeneration | None = None,
    ) -> dict:
        stats_id = note.sourceCardId or note.id
        payload = {
            **note.model_dump(),
            "isSameStyle": bool(same_style_generation),
            "sameStyleLabel": "同款" if same_style_generation else "",
            "sameStyleGeneratedAt": same_style_generation.createdAt if same_style_generation else None,
            "sameStyleSourceId": (
                same_style_generation.sourceNoteId or same_style_generation.sourceShowcaseId
                if same_style_generation
                else None
            ),
            "stats": (
                self._build_stats_from_events(
                    stats_id,
                    (view_events_by_card or {}).get(stats_id, []),
                    (relays_by_card or {}).get(stats_id, []),
                )
                if view_events_by_card is not None and relays_by_card is not None
                else self._build_note_stats(note)
            ),
            "customerSummary": self._build_note_customer_summary(
                note,
                actions_by_note=actions_by_note,
                leads_by_owner=leads_by_owner,
            ),
        }
        visibility_config = dict(payload.get("visibilityConfig") or {})
        visibility_config.pop("marketingRoute", None)
        payload["visibilityConfig"] = visibility_config
        return payload

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

    def _validate_share_snapshot_url(self, url: str) -> str:
        value = self._clean_optional_text(url)
        if not value or not self.media_storage_service.is_managed_url(value):
            raise HTTPException(status_code=400, detail="分享图地址不是本系统媒体地址")
        return value

    def _share_snapshot_delete_after(self, generated_at: str) -> str:
        try:
            created = parse_iso(generated_at)
        except (TypeError, ValueError):
            created = parse_iso(now_iso())
        return (created + timedelta(days=SHARE_SNAPSHOT_RETENTION_DAYS)).isoformat()

    def _build_share_snapshot(
        self,
        current: dict | None,
        history: list[dict] | None,
        *,
        entity_type: str,
        source_revision: str,
        fingerprint: str,
        url: str,
        style_id: str,
        generated_at: str,
    ) -> tuple[dict, list[dict]]:
        current_snapshot = current if isinstance(current, dict) else {}
        next_history = [item for item in (history or []) if isinstance(item, dict)]
        if current_snapshot.get("url") and current_snapshot.get("url") != url:
            retired = {
                **current_snapshot,
                "status": "retired",
                "retiredAt": generated_at,
                "deleteAfter": self._share_snapshot_delete_after(generated_at),
            }
            if not any(item.get("url") == retired.get("url") for item in next_history):
                next_history.append(retired)
        snapshot = {
            "version": 1,
            "entityType": entity_type,
            "url": url,
            "sourceRevision": str(source_revision or ""),
            "fingerprint": str(fingerprint or "")[:512],
            "styleId": str(style_id or "default")[:80],
            "generatedAt": generated_at,
            "status": "ready",
        }
        return snapshot, next_history

    def save_note_share_snapshot(self, note_id: str, payload: ShareSnapshotRequest) -> UserNote:
        note = self.get_user_note(note_id, payload.ownerUserId)
        if note.shareState != "published":
            raise HTTPException(status_code=409, detail="资料尚未发布，不能保存客户分享图")
        if str(payload.sourceRevision or "") != str(note.revision or 0):
            raise HTTPException(status_code=409, detail="资料版本已变化，请重新生成分享图")
        generated_at = self._clean_optional_text(payload.generatedAt) or now_iso()
        url = self._validate_share_snapshot_url(payload.url)
        config = dict(note.visibilityConfig or {})
        previous_url = str((config.get("shareSnapshot") or {}).get("url") or "")
        snapshot, history = self._build_share_snapshot(
            config.get("shareSnapshot"),
            config.get("shareSnapshotHistory"),
            entity_type="note",
            source_revision=str(note.revision or 0),
            fingerprint=payload.fingerprint,
            url=url,
            style_id=payload.styleId,
            generated_at=generated_at,
        )
        config["shareSnapshot"] = snapshot
        config["shareSnapshotHistory"] = history
        note.visibilityConfig = self._normalize_note_visibility_config(config)
        self.repo.save_user_note(note)
        if previous_url and previous_url != url:
            previous_asset = self.repo.get_media_asset_by_url(previous_url)
            if previous_asset:
                self.repo.delete_media_asset_refs(previous_asset.id, "share_snapshot", note_id, "current")
        self._sync_share_snapshot_media_ref(url, payload.ownerUserId, note_id)
        self._invalidate_card_list_cache(note.ownerUserId)
        return note

    def save_showcase_share_snapshot(self, showcase_id: str, payload: ShareSnapshotRequest) -> ShowcasePage:
        showcase = self.get_showcase_for_owner(showcase_id, payload.ownerUserId)
        if showcase.status != "published":
            raise HTTPException(status_code=409, detail="合集尚未发布，不能保存客户分享图")
        source_revision = f"{showcase.snapshotVersion or 0}:{showcase.updatedAt}"
        if str(payload.sourceRevision or "") != source_revision:
            raise HTTPException(status_code=409, detail="合集版本已变化，请重新生成分享图")
        generated_at = self._clean_optional_text(payload.generatedAt) or now_iso()
        url = self._validate_share_snapshot_url(payload.url)
        previous_url = str((showcase.shareSnapshot or {}).get("url") or "")
        snapshot, history = self._build_share_snapshot(
            showcase.shareSnapshot,
            showcase.shareSnapshotHistory,
            entity_type="showcase",
            source_revision=source_revision,
            fingerprint=payload.fingerprint,
            url=url,
            style_id=payload.styleId,
            generated_at=generated_at,
        )
        showcase.shareSnapshot = snapshot
        showcase.shareSnapshotHistory = history
        if isinstance(showcase.publicSnapshot, dict):
            public_snapshot = dict(showcase.publicSnapshot)
            # Keep the public payload and the owner/editor payload on the same
            # image source. Otherwise a legacy public snapshot without
            # coverUrl would compute a different v10 fingerprint even after
            # the owner regenerated the JPG.
            public_snapshot["items"] = self._public_showcase_items(showcase)
            public_snapshot["shareSnapshotUrl"] = snapshot["url"]
            public_snapshot["shareSnapshotStyleId"] = snapshot["styleId"]
            public_snapshot["shareSnapshotFingerprint"] = snapshot["fingerprint"]
            showcase.publicSnapshot = public_snapshot
        self.repo.save_showcase_page(showcase)
        if previous_url and previous_url != url:
            previous_asset = self.repo.get_media_asset_by_url(previous_url)
            if previous_asset:
                self.repo.delete_media_asset_refs(previous_asset.id, "share_snapshot", showcase_id, "current")
        self._sync_share_snapshot_media_ref(url, payload.ownerUserId, showcase_id)
        self._invalidate_showcase_list_cache(showcase.ownerUserId)
        return showcase

    def cleanup_expired_share_snapshots(self) -> dict:
        now = parse_iso(now_iso())
        state = self.repo.load()
        current_urls: set[str] = set()
        for note in self.repo.list_all_user_notes(include_deleted=True):
            snapshot = (note.visibilityConfig or {}).get("shareSnapshot")
            if isinstance(snapshot, dict) and snapshot.get("url"):
                current_urls.add(str(snapshot["url"]))
        for showcase in getattr(state, "showcase_pages", []) or []:
            snapshot = showcase.shareSnapshot if isinstance(showcase.shareSnapshot, dict) else {}
            if snapshot.get("url"):
                current_urls.add(str(snapshot["url"]))

        result = {"notes": 0, "showcases": 0, "deletedFiles": 0, "failedFiles": 0}

        def clean_history(history: list[dict] | None) -> tuple[list[dict], bool, int, int]:
            kept: list[dict] = []
            changed = False
            deleted = 0
            failed = 0
            for item in history or []:
                if not isinstance(item, dict):
                    changed = True
                    continue
                url = str(item.get("url") or "")
                try:
                    expired = bool(item.get("deleteAfter")) and parse_iso(str(item["deleteAfter"])) <= now
                except (TypeError, ValueError):
                    expired = False
                if not expired or not url or url in current_urls:
                    kept.append(item)
                    continue
                asset = self.repo.get_media_asset_by_url(url)
                if asset and self.repo.list_media_asset_refs(asset_id=asset.id):
                    # Another current attachment/entity still owns the same
                    # content. Remove only the expired history pointer.
                    changed = True
                    continue
                if self.media_storage_service.delete_url(url):
                    if asset:
                        asset.status = "deleted"
                        asset.updatedAt = now_iso()
                        self.repo.save_media_asset(asset)
                    changed = True
                    deleted += 1
                else:
                    kept.append(item)
                    failed += 1
            return kept, changed, deleted, failed

        for note in self.repo.list_all_user_notes(include_deleted=True):
            config = dict(note.visibilityConfig or {})
            history, changed, deleted, failed = clean_history(config.get("shareSnapshotHistory"))
            if not changed:
                result["failedFiles"] += failed
                continue
            config["shareSnapshotHistory"] = history
            note.visibilityConfig = self._normalize_note_visibility_config(config)
            self.repo.save_user_note(note)
            self._invalidate_card_list_cache(note.ownerUserId)
            result["notes"] += 1
            result["deletedFiles"] += deleted
            result["failedFiles"] += failed

        for showcase in getattr(state, "showcase_pages", []) or []:
            history, changed, deleted, failed = clean_history(showcase.shareSnapshotHistory)
            if not changed:
                result["failedFiles"] += failed
                continue
            showcase.shareSnapshotHistory = history
            self.repo.save_showcase_page(showcase)
            self._invalidate_showcase_list_cache(showcase.ownerUserId)
            result["showcases"] += 1
            result["deletedFiles"] += deleted
            result["failedFiles"] += failed
        return result

    def get_public_note(self, note_id: str) -> dict:
        note = self.repo.get_user_note(note_id)
        if not note:
            # Public links historically used card IDs. The old card page is
            # removed, so resolve those links to their canonical note before
            # applying the normal publication and privacy checks.
            card = self.repo.get_card(note_id)
            source_note_id = self._find_note_id_by_source_card(card.id) if card else None
            note = self.repo.get_user_note(source_note_id) if source_note_id else None
        if not note or note.status == "deleted":
            raise HTTPException(status_code=404, detail="笔记不存在")
        if note.shareState != "published":
            raise HTTPException(status_code=404, detail="资料尚未发布")
        payload = note.model_dump()
        # Public pages must use the same normalized communication defaults as
        # newly saved notes. This also keeps older notes with a sparse config
        # from silently losing their customer-page actions.
        payload["visibilityConfig"] = self._normalize_note_visibility_config(
            self._public_note_visibility_config(note.visibilityConfig)
        )
        payload["media"] = self._normalize_note_media(note.media, public_only=True)
        payload["phone"] = None
        payload["sourceRefs"] = []
        payload["importBatchId"] = None
        payload["sourceCardId"] = None
        public_snapshot = payload["visibilityConfig"].get("shareSnapshot")
        if not (
            isinstance(public_snapshot, dict)
            and public_snapshot.get("status") == "ready"
            and public_snapshot.get("url")
            and str(public_snapshot.get("sourceRevision") or "") == str(note.revision or "")
            and str(public_snapshot.get("styleId") or "") == SHARE_SNAPSHOT_STYLE_ID
        ):
            payload["visibilityConfig"].pop("shareSnapshot", None)
        self._attach_owner_sales_profile_to_public_note(note, payload)
        self._attach_business_card_featured_resources(note, payload)
        self._sanitize_public_property_note_text(payload)
        public_blocks = self._public_note_content_blocks(note, payload["media"], body=payload.get("body"))
        if payload["visibilityConfig"].get("cardType") == "property_listing":
            # Property notes have a structured public body. Never reuse the raw
            # capture text blocks here: they may contain upstream/private data.
            public_blocks = [block for block in public_blocks if block.get("type") != "text"]
            safe_body = str(payload.get("body") or "").strip()
            if safe_body:
                public_blocks.insert(0, {
                    "id": "public_text",
                    "type": "text",
                    "text": safe_body,
                    "sortOrder": 0,
                })
        for index, block in enumerate(public_blocks):
            block["sortOrder"] = index
        payload["contentBlocks"] = public_blocks
        return payload

    def publish_user_note(
        self,
        note_id: str,
        owner_user_id: str,
        expected_revision: int | None = None,
    ) -> UserNote:
        note = self.get_user_note(note_id, owner_user_id)
        if note.status == "deleted":
            raise HTTPException(status_code=404, detail="资料不存在")
        if expected_revision is not None and int(expected_revision) != int(note.revision or 0):
            raise HTTPException(status_code=409, detail="资料已被其他页面更新，请刷新后再发布")
        # Older imported notes can remain ``draft`` after capture.  Do not
        # reject a complete, owner-owned note solely because of that stale
        # lifecycle value; the public-safety gate below is authoritative.
        # Incomplete notes still fail with the same explicit safety error.
        if note.status not in {"draft", "active"}:
            raise HTTPException(status_code=400, detail="资料尚未完成，不能发布")
        if note.shareState == "published":
            return note
        self._assert_note_public_safe(note)
        if note.status == "draft":
            note.status = "active"
        note.shareState = "published"
        note.revision = max(int(note.revision or 0), 0) + 1
        config = dict(note.visibilityConfig or {})
        config["shareState"] = note.shareState
        config["revision"] = note.revision
        config["intakeState"] = "ready"
        note.visibilityConfig = self._normalize_note_visibility_config(config)
        note.updatedAt = now_iso()
        self.repo.save_user_note(note)
        self._invalidate_card_list_cache(owner_user_id)
        return note

    def revoke_user_note(self, note_id: str, owner_user_id: str) -> UserNote:
        note = self.get_user_note(note_id, owner_user_id)
        if note.shareState != "published":
            note.shareState = "revoked"
        else:
            note.shareState = "revoked"
        note.revision = max(int(note.revision or 0), 0) + 1
        config = dict(note.visibilityConfig or {})
        config["shareState"] = note.shareState
        config["revision"] = note.revision
        note.visibilityConfig = self._normalize_note_visibility_config(config)
        note.updatedAt = now_iso()
        self.repo.save_user_note(note)
        self._invalidate_showcase_snapshots_for_note(note.id, owner_user_id)
        self._invalidate_card_list_cache(owner_user_id)
        return note

    def _invalidate_showcase_snapshots_for_note(self, note_id: str, owner_user_id: str) -> None:
        for showcase in self.repo.list_showcase_pages(owner_user_id):
            if showcase.status != "published" or not any(item.noteId == note_id for item in showcase.items):
                continue
            showcase.publicSnapshot = {}
            showcase.snapshotCreatedAt = None
            showcase.updatedAt = now_iso()
            self.repo.save_showcase_page(showcase)
        self._invalidate_showcase_list_cache(owner_user_id)

    def _assert_note_public_safe(self, note: UserNote) -> None:
        config = note.visibilityConfig if isinstance(note.visibilityConfig, dict) else {}
        sensitive = re.compile(r"上游|二房东|供应商|成本|佣金|进货|密码锁|门锁密码")
        structured = config.get("structuredData") if isinstance(config.get("structuredData"), dict) else {}
        if config.get("cardType") == "property_listing":
            text = "\n".join(
                str(value or "")
                for value in (
                    note.title,
                    note.summary,
                    structured.get("community"),
                    structured.get("layout"),
                    structured.get("area"),
                    structured.get("price"),
                    structured.get("utilities"),
                    structured.get("paymentMethod"),
                    structured.get("businessArea") or structured.get("address"),
                )
            )
        else:
            block_text = "\n".join(
                str(item.get("text") or "")
                for item in self._normalize_note_content_blocks(note.contentBlocks, body=note.body, media=note.media)
                if item.get("type") == "text"
            )
            text = "\n".join([note.title or "", note.summary or "", note.body or "", block_text])
        if sensitive.search(text):
            raise HTTPException(status_code=400, detail="资料正文含有疑似私密信息，请先处理")
        for match in re.findall(r"(?<!\d)1[3-9]\d{9}(?!\d)", text):
            if match not in {str(note.phone or "").strip()}:
                raise HTTPException(status_code=400, detail="资料正文含有未确认的手机号，请先处理")

    def _attach_business_card_featured_resources(self, note: UserNote, payload: dict) -> None:
        config = payload.get("visibilityConfig") if isinstance(payload.get("visibilityConfig"), dict) else {}
        if config.get("cardType") != "business_card":
            return
        structured = config.get("structuredData") if isinstance(config.get("structuredData"), dict) else {}
        featured_ids = self._unique_strings(structured.get("featuredNoteIds") or [])[:3]
        featured: list[dict] = []
        for featured_id in featured_ids:
            item = self.repo.get_user_note(featured_id)
            if (
                not item
                or item.status != "active"
                or item.shareState != "published"
                or item.ownerUserId != note.ownerUserId
                or item.id == note.id
            ):
                continue
            item_config = self._public_note_visibility_config(item.visibilityConfig)
            item_type = str(item_config.get("cardType") or "text_note")
            public_media = self._normalize_note_media(item.media, public_only=True)
            cover_url = item.coverUrl or self._first_media_url(public_media)
            featured.append({
                "id": item.id,
                "title": item.title,
                "summary": item.summary or item.body[:120],
                "coverUrl": cover_url,
                "cardType": item_type,
            })
        payload["featuredResources"] = featured

    def _public_note_visibility_config(self, config: dict | None) -> dict:
        source = dict(config or {})
        for key in (
            "privateData",
            "privateTags",
            "analyticsData",
            "opportunityAlerts",
            "radarProfiles",
            "internalNotes",
            "shareSnapshotHistory",
            "marketingRoute",
        ):
            source.pop(key, None)
        structured = source.get("structuredData") if isinstance(source.get("structuredData"), dict) else {}
        source["structuredData"] = self._public_clone_structured_data(structured)
        return self._sanitize_public_config_value(source)

    def _sanitize_public_config_value(self, value):
        if isinstance(value, dict):
            return {key: self._sanitize_public_config_value(child) for key, child in value.items()}
        if isinstance(value, list):
            return [self._sanitize_public_config_value(child) for child in value]
        if not isinstance(value, str):
            return value
        private_markers = re.compile(r"上游|二房东|房东|渠道|供应商|成本|佣金|进货|密码锁|门锁密码")
        lines = []
        for line in value.splitlines():
            if private_markers.search(line):
                continue
            lines.append(re.sub(r"(?<!\d)1[3-9]\d{9}(?!\d)", "[联系方式已移除]", line))
        return "\n".join(lines)

    def _attach_owner_sales_profile_to_public_note(self, note: UserNote, payload: dict) -> None:
        owner = self.repo.get_user(note.ownerUserId)
        if not owner:
            return
        profile = dict(owner.salesProfile or {})
        profile.update({
            "displayName": profile.get("displayName") or owner.nickname,
            "avatarUrl": profile.get("avatarUrl") or owner.avatarUrl,
            "phone": profile.get("phone") or owner.phone or "",
            "wechat": profile.get("wechat") or owner.wechat or "",
        })
        config = payload.get("visibilityConfig") if isinstance(payload.get("visibilityConfig"), dict) else {}
        conversion = config.get("conversionConfig") if isinstance(config.get("conversionConfig"), dict) else {}
        if conversion.get("showContactPhone") is False:
            profile["phone"] = ""
        if conversion.get("enablePrivateConsultation") is False:
            profile["wechat"] = ""
            profile["wechatQrUrl"] = ""
        payload["ownerProfile"] = profile
        self._attach_owner_contact_to_public_note(note, payload)

    def _attach_owner_contact_to_public_note(self, note: UserNote, payload: dict) -> None:
        config = payload.get("visibilityConfig") if isinstance(payload.get("visibilityConfig"), dict) else {}
        if config.get("cardType") != "property_listing":
            return
        owner = self.repo.get_user(note.ownerUserId)
        if not owner:
            return
        conversion = config.get("conversionConfig") if isinstance(config.get("conversionConfig"), dict) else {}
        structured_data = dict(config.get("structuredData") or {})
        phone = self._clean_optional_text(owner.phone)
        wechat = self._clean_optional_text(owner.wechat)
        if phone and conversion.get("showContactPhone", True):
            structured_data["phone"] = phone
            structured_data["contact"] = phone
            structured_data["contactPhone"] = phone
            payload["phone"] = phone
        else:
            payload["phone"] = None
        if wechat and conversion.get("enablePrivateConsultation", True):
            structured_data["wechat"] = wechat
            structured_data["contactWechat"] = wechat
        config["structuredData"] = structured_data
        payload["visibilityConfig"] = config

    def _sanitize_public_property_note_text(self, payload: dict) -> None:
        config = payload.get("visibilityConfig") if isinstance(payload.get("visibilityConfig"), dict) else {}
        if config.get("cardType") != "property_listing":
            return
        structured_data = config.get("structuredData") if isinstance(config.get("structuredData"), dict) else {}
        safe_parts = [
            structured_data.get("community") or payload.get("title"),
            structured_data.get("layout"),
            structured_data.get("area"),
            structured_data.get("price"),
            structured_data.get("utilities"),
            structured_data.get("paymentMethod"),
            structured_data.get("businessArea") or structured_data.get("address"),
        ]
        safe_text = " / ".join(str(item).strip() for item in safe_parts if str(item or "").strip())
        payload["body"] = safe_text or payload.get("summary") or payload.get("title") or ""

    def list_showcases(self, owner_user_id: str) -> list[dict]:
        now = time.monotonic()
        cached = self._showcase_list_cache.get(owner_user_id)
        if cached and now - cached[0] < self._showcase_list_cache_ttl_seconds:
            return list(cached[1])
        if not self.repo.get_user(owner_user_id):
            raise HTTPException(status_code=404, detail="用户不存在")
        same_style_by_showcase_id = {}
        for generation in self.repo.list_same_style_generations(owner_user_id):
            if generation.generatedShowcaseId and generation.generatedShowcaseId not in same_style_by_showcase_id:
                same_style_by_showcase_id[generation.generatedShowcaseId] = generation
        rows = []
        for item in self.repo.list_showcase_pages(owner_user_id):
            generation = same_style_by_showcase_id.get(item.id)
            row = self._showcase_owner_payload(item)
            row.update({
                "isSameStyle": bool(generation),
                "sameStyleLabel": "同款" if generation else "",
                "sameStyleGeneratedAt": generation.createdAt if generation else None,
                "sameStyleSourceId": (
                    generation.sourceNoteId or generation.sourceShowcaseId
                    if generation
                    else None
                ),
            })
            rows.append(row)
        rows.sort(
            key=lambda item: (
                bool(item.get("isSameStyle")),
                item.get("sameStyleGeneratedAt") or item.get("updatedAt") or item.get("createdAt") or "",
            ),
            reverse=True,
        )
        self._showcase_list_cache[owner_user_id] = (now, rows)
        if len(self._showcase_list_cache) > self._showcase_list_cache_max_entries:
            expired_before = now - self._showcase_list_cache_ttl_seconds
            self._showcase_list_cache = {
                key: value for key, value in self._showcase_list_cache.items()
                if value[0] >= expired_before
            }
            if len(self._showcase_list_cache) > self._showcase_list_cache_max_entries:
                oldest_keys = sorted(self._showcase_list_cache, key=lambda key: self._showcase_list_cache[key][0])
                for old_key in oldest_keys[:len(self._showcase_list_cache) - self._showcase_list_cache_max_entries]:
                    self._showcase_list_cache.pop(old_key, None)
        return list(rows)

    def create_showcase(self, payload: ShowcasePageRequest) -> ShowcasePage:
        self._ensure_showcase_owner(payload.ownerUserId)
        now = now_iso()
        scene_type = self._resolve_showcase_scene(payload.ownerUserId, payload)
        template_id = normalize_template_id(scene_type, payload.templateId)
        showcase = ShowcasePage(
            id=new_id("showcase"),
            ownerUserId=payload.ownerUserId,
            status="draft",
            name=self._clean_showcase_name(payload.name),
            description=self._clean_optional_text(payload.description),
            bannerUrl=self._clean_optional_text(payload.bannerUrl),
            sceneType=scene_type,
            templateId=template_id,
            shareTitle=self._clean_optional_text(payload.shareTitle),
            contactConfig=self._normalize_showcase_contact_config(payload.contactConfig),
            displayConfig={**self._normalize_showcase_display_config(payload.displayConfig), "sceneType": scene_type},
            items=self._normalize_showcase_items(payload.ownerUserId, payload.items, scene_type),
            publishedAt=None,
            createdAt=now,
            updatedAt=now,
        )
        self.repo.save_showcase_page(showcase)
        self._invalidate_showcase_list_cache(payload.ownerUserId)
        self._invalidate_customer_intelligence_cache(payload.ownerUserId)
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
        scene_type = self._resolve_showcase_scene(payload.ownerUserId, payload)
        showcase.name = self._clean_showcase_name(payload.name)
        showcase.description = self._clean_optional_text(payload.description)
        showcase.bannerUrl = self._clean_optional_text(payload.bannerUrl)
        showcase.sceneType = scene_type
        showcase.templateId = normalize_template_id(scene_type, payload.templateId)
        showcase.shareTitle = self._clean_optional_text(payload.shareTitle)
        showcase.contactConfig = self._normalize_showcase_contact_config(payload.contactConfig)
        showcase.displayConfig = {**self._normalize_showcase_display_config(payload.displayConfig), "sceneType": scene_type}
        showcase.items = self._normalize_showcase_items(payload.ownerUserId, payload.items, scene_type)
        showcase.updatedAt = now_iso()
        self.repo.save_showcase_page(showcase)
        self._invalidate_showcase_list_cache(payload.ownerUserId)
        self._invalidate_customer_intelligence_cache(payload.ownerUserId)
        return showcase

    def publish_showcase(self, showcase_id: str, owner_user_id: str) -> ShowcasePage:
        showcase = self.get_showcase_for_owner(showcase_id, owner_user_id)
        valid_items = self._valid_showcase_items(showcase)
        if not self._clean_optional_text(showcase.name):
            raise HTTPException(status_code=400, detail="展示页名称不能为空")
        if not valid_items:
            raise HTTPException(status_code=400, detail="请至少选择一条有效资料后再发布")
        now = now_iso()
        for item in valid_items:
            note = self.repo.get_user_note(item.noteId)
            if not note or note.status == "deleted":
                continue
            if note.shareState != "published":
                self._assert_note_public_safe(note)
                note.shareState = "published"
                note.revision = max(int(note.revision or 0), 0) + 1
                note.visibilityConfig = self._normalize_note_visibility_config(
                    {
                        **(note.visibilityConfig or {}),
                        "shareState": note.shareState,
                        "revision": note.revision,
                        "intakeState": "ready",
                    }
                )
                note.updatedAt = now
                self.repo.save_user_note(note)
        showcase.status = "published"
        showcase.items = valid_items
        showcase.publishedAt = showcase.publishedAt or now
        showcase.updatedAt = now
        next_version = (showcase.snapshotVersion or 0) + 1
        showcase.publicSnapshot = self._build_showcase_public_snapshot(showcase, now, next_version)
        showcase.snapshotVersion = next_version
        showcase.snapshotCreatedAt = now
        self.repo.save_showcase_page(showcase)
        self._invalidate_showcase_list_cache(owner_user_id)
        self._invalidate_customer_intelligence_cache(owner_user_id)
        return showcase

    def archive_showcase(self, showcase_id: str, owner_user_id: str) -> ShowcasePage:
        showcase = self.get_showcase_for_owner(showcase_id, owner_user_id)
        showcase.status = "archived"
        showcase.updatedAt = now_iso()
        self.repo.save_showcase_page(showcase)
        self._invalidate_showcase_list_cache(owner_user_id)
        self._invalidate_customer_intelligence_cache(owner_user_id)
        return showcase

    def delete_showcase(self, showcase_id: str, owner_user_id: str) -> dict:
        self.get_showcase_for_owner(showcase_id, owner_user_id)
        self.repo.delete_showcase_page(showcase_id)
        self._invalidate_showcase_list_cache(owner_user_id)
        self._invalidate_customer_intelligence_cache(owner_user_id)
        return {"deletedShowcaseId": showcase_id}

    def record_showcase_event(
        self,
        showcase_id: str,
        payload: ShowcaseEventRequest,
        authenticated_user_id: str | None = None,
    ) -> dict:
        showcase = self.repo.get_showcase_page(showcase_id)
        if not showcase or showcase.status != "published":
            raise HTTPException(status_code=404, detail="展示页不存在或未发布")
        event_type = str(payload.eventType or "").strip()
        if event_type not in {"view", "note_click", "phone_click", "wechat_copy", "share"}:
            raise HTTPException(status_code=400, detail="展示页事件类型无效")
        payload = self._normalize_public_view_payload(payload, showcase.ownerUserId, authenticated_user_id)
        viewer_user_id = self._clean_optional_text(payload.viewerUserId)
        if event_type != "share" and viewer_user_id and viewer_user_id == showcase.ownerUserId:
            return {"recorded": False, "ignored": "owner_event"}
        note_id = self._clean_optional_text(payload.noteId)
        if note_id and note_id not in {item.noteId for item in self._valid_showcase_items(showcase)}:
            note_id = None
        now = now_iso()
        event_id = self._existing_showcase_session_event_id(showcase.id, payload) or new_id("showcase_event")
        event = ShowcaseEvent(
            id=event_id,
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
            visitorIdentityId=self._stable_visitor_identity_id(showcase.ownerUserId, viewer_user_id, payload.anonymousId, event_id),
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
        if event_type in CUSTOMER_INTELLIGENCE_SHOWCASE_EVENTS:
            self._invalidate_customer_intelligence_cache(showcase.ownerUserId)
        return {"recorded": True, "eventId": event.id}

    def get_showcase_analytics(self, showcase_id: str, owner_user_id: str) -> dict:
        showcase = self.get_showcase_for_owner(showcase_id, owner_user_id)
        return self._build_showcase_analytics(showcase)

    def get_public_showcase(self, showcase_id: str) -> dict:
        showcase = self.repo.get_showcase_page(showcase_id)
        if not showcase or showcase.status != "published":
            raise HTTPException(status_code=404, detail="展示页不存在或未发布")
        snapshot = showcase.publicSnapshot if isinstance(showcase.publicSnapshot, dict) else {}
        scene_type = normalize_scene_type(showcase.sceneType, (showcase.displayConfig or {}).get("activeCategory"))
        if snapshot and isinstance(snapshot.get("items"), list) and snapshot.get("templateId") == normalize_template_id(scene_type, showcase.templateId):
            public_snapshot = dict(snapshot)
            if public_snapshot.get("shareSnapshotStyleId") != SHARE_SNAPSHOT_STYLE_ID:
                public_snapshot["shareSnapshotUrl"] = ""
                public_snapshot["shareSnapshotStyleId"] = ""
                public_snapshot["shareSnapshotFingerprint"] = ""
            return public_snapshot
        now = now_iso()
        next_version = (showcase.snapshotVersion or 0) + 1
        snapshot = self._build_showcase_public_snapshot(showcase, now, next_version)
        showcase.publicSnapshot = snapshot
        showcase.snapshotVersion = next_version
        showcase.snapshotCreatedAt = now
        self.repo.save_showcase_page(showcase)
        return snapshot

    def _build_showcase_public_snapshot(self, showcase: ShowcasePage, snapshot_at: str, snapshot_version: int) -> dict:
        scene_type = normalize_scene_type(showcase.sceneType, (showcase.displayConfig or {}).get("activeCategory"))
        share_snapshot = showcase.shareSnapshot if isinstance(showcase.shareSnapshot, dict) else {}
        share_snapshot_url = (
            share_snapshot.get("url")
            if share_snapshot.get("status") == "ready"
            and str(share_snapshot.get("sourceRevision") or "") == f"{snapshot_version}:{showcase.updatedAt}"
            and str(share_snapshot.get("styleId") or "") == SHARE_SNAPSHOT_STYLE_ID
            else ""
        )
        share_snapshot_style_id = SHARE_SNAPSHOT_STYLE_ID if share_snapshot_url else ""
        share_snapshot_fingerprint = share_snapshot.get("fingerprint") if share_snapshot_url else ""
        return {
            "id": showcase.id,
            "name": showcase.name,
            "description": showcase.description,
            "bannerUrl": showcase.bannerUrl,
            "sceneType": scene_type,
            "templateId": normalize_template_id(scene_type, showcase.templateId),
            "shareTitle": showcase.shareTitle or showcase.name,
            "contactConfig": showcase.contactConfig,
            "displayConfig": showcase.displayConfig,
            "items": self._public_showcase_items(showcase),
            "publishedAt": showcase.publishedAt,
            "updatedAt": showcase.updatedAt,
            "snapshotVersion": snapshot_version,
            "snapshotCreatedAt": snapshot_at,
            "snapshotSource": "published_snapshot",
            "shareSnapshotUrl": share_snapshot_url,
            "shareSnapshotStyleId": share_snapshot_style_id,
            "shareSnapshotFingerprint": share_snapshot_fingerprint,
        }

    def _ensure_showcase_owner(self, owner_user_id: str) -> None:
        if not self.repo.get_user(owner_user_id):
            raise HTTPException(status_code=404, detail="用户不存在")

    def _showcase_owner_payload(self, showcase: ShowcasePage) -> dict:
        payload = showcase.model_dump()
        scene_type = normalize_scene_type(showcase.sceneType, (showcase.displayConfig or {}).get("activeCategory"))
        payload["sceneType"] = scene_type
        payload["allowedTemplateIds"] = list(allowed_template_ids(scene_type))
        payload["defaultTemplateId"] = default_template_id(scene_type)
        # Keep the legacy property-batch identifier in owner responses for
        # existing workflows; rendering and public snapshots use its alias.
        payload["templateId"] = showcase.templateId if showcase.templateId == "property_batch_collection" else normalize_template_id(scene_type, showcase.templateId)
        # The editor and the share-card prewarmer need the first real image of
        # each selected item, including images stored in media rather than in
        # the legacy coverUrl field. Keep the original item fields intact and
        # only enrich the owner response with render metadata.
        payload["items"] = [
            {
                **item.model_dump(),
                "coverUrl": self._first_note_image_url(note) if note else "",
            }
            for item in showcase.items
            for note in [self.repo.get_user_note(item.noteId)]
        ]
        payload["itemCount"] = len(self._valid_showcase_items(showcase))
        payload["sharePath"] = f"/pages/showcase-view/index?id={showcase.id}"
        analytics = self._build_showcase_analytics(showcase, compact=True)
        payload["analytics"] = analytics if self._has_customer_intelligence(showcase.ownerUserId) else {
            "locked": True,
            "summary": analytics.get("summary") or {},
            "recentViewers": [],
            "recentEvents": [],
            "topShares": [],
        }
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

    def _build_business_dashboard(self, owner_user_id: str, requester_user_id: str | None = None, mode: str | None = None) -> dict:
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
        note_card_ids = {item.sourceCardId for item in notes if item.sourceCardId}
        note_source_ids = note_ids | note_card_ids
        note_event_rows = self.repo.list_view_events_for_cards(note_source_ids)
        note_view_events: dict[str, list[ViewEvent]] = {
            note.id: note_event_rows.get(note.sourceCardId or note.id, [])
            for note in notes
        }
        showcases = self.repo.list_showcase_pages(owner_user_id)
        if mode in {"groupbuy", "service"}:
            showcases = [
                item
                for item in showcases
                if any(showcase_item.noteId in note_ids for showcase_item in item.items)
            ]
        showcase_by_id = {item.id: item for item in showcases}
        showcase_ids = {item.id for item in showcases}
        showcase_event_rows = self.repo.list_showcase_events_for_showcases(showcase_ids)
        showcase_events = [
            event
            for showcase_id in showcase_ids
            for event in showcase_event_rows.get(showcase_id, [])
            if event.ownerUserId == owner_user_id
            and (mode not in {"groupbuy", "service"} or not event.noteId or event.noteId in note_ids)
        ]
        actions_by_note = self.repo.list_customer_actions_for_notes(note_ids)
        actions = [
            action
            for rows in actions_by_note.values()
            for action in rows
            if action.ownerUserId == owner_user_id
        ]
        all_leads = self.repo.list_lead_reminders(owner_user_id)
        leads = all_leads
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
            "visitorProfiles": self._business_dashboard_visitor_profiles(owner_user_id, showcase_events, actions, leads, showcase_by_id, note_by_id),
        }
        return self._attach_opportunity_radar(
            owner_user_id,
            dashboard,
            notes,
            showcase_events,
            actions,
            leads,
            note_view_events,
            suppression_leads=all_leads,
        )

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
        note_source_ids = note_ids | {item.sourceCardId for item in notes if item.sourceCardId}
        actions_by_note = self.repo.list_customer_actions_for_notes(note_ids)
        actions = [
            action
            for rows in actions_by_note.values()
            for action in rows
            if action.ownerUserId == owner_user_id
        ]
        projected_lead_ids = {
            str((action.projectionRefs or {}).get("leadReminderId") or "")
            for action in actions
            if (action.projectionRefs or {}).get("leadReminderId")
        }
        all_leads = self.repo.list_lead_reminders(owner_user_id)
        leads = [item for item in all_leads if item.id in projected_lead_ids or item.cardId in note_source_ids]
        note_stats = {note.id: self._build_note_stats(note) for note in notes}
        note_event_rows = self.repo.list_view_events_for_cards(note_source_ids)
        note_view_events: dict[str, list[ViewEvent]] = {
            note.id: note_event_rows.get(note.sourceCardId or note.id, [])
            for note in notes
        }
        showcases = [
            showcase
            for showcase in self.repo.list_showcase_pages(owner_user_id)
            if any(item.noteId in note_ids for item in showcase.items)
        ]
        showcase_by_id = {item.id: item for item in showcases}
        showcase_ids = {item.id for item in showcases}
        showcase_event_rows = self.repo.list_showcase_events_for_showcases(showcase_ids)
        showcase_events = [
            event
            for showcase_id in showcase_ids
            for event in showcase_event_rows.get(showcase_id, [])
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
        note_share_count = 0
        today_note_share_count = 0
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
                if event.viewType == "share":
                    note_share_count += 1
                    if event.dateKey == today:
                        today_note_share_count += 1
                    continue
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
                sum(1 for event in note_view_events.get(note.id, []) if event.dateKey == today and event.viewType != "share")
                + int(today_note_clicks.get(note.id) or 0)
            )
            today_visitor_count = len({
                self._dashboard_identity_key(event.viewerUserId, event.anonymousId, event.id)
                for event in note_view_events.get(note.id, [])
                if event.dateKey == today and event.viewType != "share"
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
            "shareCount": package_share_count + note_share_count,
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
            "shareCount": today_package_share_count + today_note_share_count,
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
        last7_keys = {
            (datetime.now(SHANGHAI).date() - timedelta(days=offset)).isoformat()
            for offset in range(7)
        }

        def summarize_period(period_keys: set[str]) -> dict:
            period_showcase_events = [event for event in showcase_events if event.dateKey in period_keys]
            period_note_events = [
                event
                for events in note_view_events.values()
                for event in events
                if event.dateKey in period_keys
            ]
            period_note_open_events = [event for event in period_note_events if event.viewType != "share"]
            period_note_share_events = [event for event in period_note_events if event.viewType == "share"]
            period_visitor_keys = {
                self._dashboard_identity_key(event.viewerUserId, event.anonymousId, event.id)
                for event in period_showcase_events
                if event.eventType == "view"
            }
            period_visitor_keys.update(
                self._dashboard_identity_key(event.viewerUserId, event.anonymousId, event.id)
                for event in period_note_open_events
            )
            period_actions = [action for action in actions if date_key(action.createdAt) in period_keys]
            period_contact_count = sum(
                1 for action in period_actions if action.actionKey in {"lead-contact", "appointment", "consult-click"}
            )
            period_pending_leads = [
                lead for lead in pending_leads if date_key(lead.createdAt) in period_keys
            ]
            share_source_ids = {
                event.shareId
                for event in period_showcase_events + period_note_share_events
                if event.shareId
            }
            return {
                "propertyCount": sum(1 for note in notes if date_key(note.createdAt) in period_keys),
                "updatedPropertyCount": sum(1 for note in notes if date_key(note.updatedAt) in period_keys),
                "showcaseOpenCount": sum(1 for event in period_showcase_events if event.eventType == "view"),
                "visitorCount": len(period_visitor_keys),
                "loggedInVisitorCount": sum(1 for key in period_visitor_keys if key.startswith("user:")),
                "anonymousVisitorCount": sum(1 for key in period_visitor_keys if not key.startswith("user:")),
                "noteClickCount": len(period_note_open_events) + sum(
                    1 for event in period_showcase_events if event.eventType == "note_click" and event.noteId in note_ids
                ),
                "consultCount": sum(
                    1 for event in period_showcase_events if event.eventType in {"phone_click", "wechat_copy"}
                ) + period_contact_count,
                "shareCount": sum(1 for event in period_showcase_events if event.eventType == "share") + len(period_note_share_events),
                "shareSourceCount": len(share_source_ids),
                "pendingLeadCount": len(period_pending_leads),
                "customerCount": len({
                    self._dashboard_identity_key(action.viewerUserId, action.anonymousId, action.id)
                    for action in period_actions
                } | period_visitor_keys),
                "orderCount": 0,
                "pendingOrderCount": 0,
                "todayEventCount": len(period_showcase_events),
                "todayActionCount": len(period_actions),
                "showcaseCount": len(showcases),
                "publishedShowcaseCount": sum(1 for item in showcases if item.status == "published"),
            }

        range_summaries = {
            "today": today_summary,
            "last7": summarize_period(last7_keys),
            "total": summary,
        }
        property_showcase_events = [
            event
            for event in showcase_events
            if event.eventType != "note_click" or event.noteId in note_ids
        ]
        visitor_profiles = self._business_dashboard_visitor_profiles(owner_user_id, property_showcase_events, actions, leads, showcase_by_id, note_by_id)
        visitor_profiles = self._merge_property_note_view_profiles(owner_user_id, visitor_profiles, notes, note_view_events)
        latest_actions = self._business_dashboard_latest_actions(actions, note_by_id)
        latest_actions = self._merge_pending_lead_actions(latest_actions, pending_leads, notes)
        dashboard = {
            "summary": summary,
            "todaySummary": today_summary,
            "rangeSummaries": range_summaries,
            "entries": self._business_dashboard_entries(summary),
            "recentVisitors": self._property_dashboard_recent_visitors(notes, note_stats, property_showcase_events, showcase_by_id),
            "topNotes": property_rows[:8],
            "propertyBreakdown": property_rows,
            "topShares": self._business_dashboard_top_shares(share_rows, property_showcase_events),
            "latestActions": latest_actions,
            "showcaseBreakdown": self._business_dashboard_showcase_breakdown(showcases, property_showcase_events),
            "visitorProfiles": visitor_profiles,
        }
        return self._attach_opportunity_radar(
            owner_user_id,
            dashboard,
            notes,
            property_showcase_events,
            actions,
            leads,
            note_view_events,
            suppression_leads=all_leads,
        )

    def _attach_opportunity_radar(
        self,
        owner_user_id: str,
        dashboard: dict,
        notes: list[UserNote],
        showcase_events: list[ShowcaseEvent],
        actions: list[CustomerAction],
        leads: list[LeadReminder],
        note_view_events: dict[str, list[ViewEvent]] | None = None,
        suppression_leads: list[LeadReminder] | None = None,
        synchronize_summary_counts: bool = False,
    ) -> dict:
        note_by_id = {item.id: item for item in notes}
        note_by_card_id: dict[str, UserNote] = {}
        for note in notes:
            note_by_card_id[note.id] = note
            if note.sourceCardId:
                note_by_card_id[note.sourceCardId] = note
        # A follow-up decision belongs to the owner/customer relationship, not
        # to the currently selected card scene.  The status tabs remain
        # scene-scoped through ``leads``, while suppression consults every
        # owner lead so an abandoned/following identity cannot be rebuilt from
        # historical events after switching scenes.
        resolved_leads = [
            item
            for item in (suppression_leads if suppression_leads is not None else leads)
            if item.status in LEAD_INBOX_RESOLVED_STATUSES
        ]
        active_leads = [item for item in leads if item.status not in LEAD_INBOX_RESOLVED_STATUSES]
        abandoned_leads = [item for item in leads if item.status == "paused"]
        viewer_contact_cache: dict[str, dict[str, str]] = {}
        profiles = self._build_opportunity_profiles(
            owner_user_id,
            note_by_id,
            note_by_card_id,
            showcase_events,
            actions,
            active_leads,
            note_view_events or {},
            viewer_contact_cache=viewer_contact_cache,
        )
        if resolved_leads:
            # A resolved inbox action is a deliberate owner decision for the
            # customer, not just a flag on one lead row. Remove the identity
            # from both radar worklists while keeping all source events and
            # lead history available to customer detail/history.
            profiles = [
                profile
                for profile in profiles
                if not any(
                    self._raw_customer_identity_matches(
                        owner_user_id,
                        closed_lead.visitorIdentityId or closed_lead.viewerUserId,
                        visitor_identity_id=profile.get("visitorIdentityId"),
                        viewer_user_id=profile.get("viewerUserId"),
                        anonymous_id=profile.get("anonymousId"),
                        fallback_id=profile.get("id"),
                    )
                    or self._raw_customer_identity_matches(
                        owner_user_id,
                        closed_lead.viewerUserId,
                        visitor_identity_id=profile.get("visitorIdentityId"),
                        viewer_user_id=profile.get("viewerUserId"),
                        anonymous_id=profile.get("anonymousId"),
                        fallback_id=profile.get("id"),
                    )
                    for closed_lead in resolved_leads
                )
            ]
        # The customer-intelligence response uses the active profile count so
        # its radar tab cannot resurrect a handled visitor. The general
        # business dashboard keeps its historical event-based visitor count,
        # so existing analytics consumers retain their meaning.
        active_visitor_profiles = profiles
        if synchronize_summary_counts:
            dashboard_summary = dashboard.setdefault("summary", {})
            dashboard_summary["visitorCount"] = len(active_visitor_profiles)
            dashboard_summary["loggedInVisitorCount"] = sum(
                1 for item in active_visitor_profiles if item.get("viewerUserId")
            )
            dashboard_summary["anonymousVisitorCount"] = sum(
                1 for item in active_visitor_profiles if not item.get("viewerUserId")
            )
        following_leads = [item for item in leads if item.status == "following"]
        following_profiles = self._build_opportunity_profiles(
            owner_user_id,
            note_by_id,
            note_by_card_id,
            showcase_events,
            actions,
            following_leads,
            note_view_events or {},
            viewer_contact_cache=viewer_contact_cache,
        )
        following_lead_ids = {item.id for item in following_leads}
        following_profiles = [
            profile for profile in following_profiles
            if profile.get("leadReminderId") in following_lead_ids
        ]
        for profile in following_profiles:
            lead = next(
                (item for item in following_leads if item.id == profile.get("leadReminderId")),
                None,
            )
            if lead:
                profile["leadStatus"] = lead.status
                profile["leadStatusText"] = self._lead_status_text(lead.status)
                profile["nextFollowUpAt"] = lead.nextFollowUpAt or ""

        abandoned_profiles = self._build_opportunity_profiles(
            owner_user_id,
            note_by_id,
            note_by_card_id,
            showcase_events,
            actions,
            abandoned_leads,
            note_view_events or {},
            viewer_contact_cache=viewer_contact_cache,
        )
        abandoned_lead_ids = {item.id for item in abandoned_leads}
        abandoned_profiles = [
            profile for profile in abandoned_profiles
            if profile.get("leadReminderId") in abandoned_lead_ids
        ]
        for profile in abandoned_profiles:
            lead = next(
                (item for item in abandoned_leads if item.id == profile.get("leadReminderId")),
                None,
            )
            if lead:
                profile["leadStatus"] = lead.status
                profile["leadStatusText"] = self._lead_status_text(lead.status)
                profile["abandonedAt"] = lead.closedAt or lead.updatedAt or lead.createdAt
                profile["conclusionReason"] = lead.conclusionReason or "放弃跟进"
                profile["nextFollowUpAt"] = lead.nextFollowUpAt or ""
        alerts = self._build_opportunity_alerts(profiles)
        content_insights = self._build_content_insights(notes, profiles)
        revival_alerts = [item for item in alerts if item.get("alertType") == "revival"]
        today = date_key(now_iso())
        dashboard["radarProfiles"] = profiles[:20]
        dashboard["opportunityAlerts"] = alerts[:8]
        dashboard["followingProfiles"] = following_profiles[:20]
        dashboard["abandonedProfiles"] = abandoned_profiles[:20]
        dashboard["contentInsights"] = content_insights[:8]
        dashboard["revivalAlerts"] = revival_alerts[:6]
        dashboard["opportunitySummary"] = {
            "highIntentCount": sum(1 for item in profiles if item.get("intentLevel") == "高"),
            "mediumIntentCount": sum(1 for item in profiles if item.get("intentLevel") == "中"),
            "todayHighIntentCount": sum(1 for item in profiles if item.get("intentLevel") == "高" and item.get("lastActivityDateKey") == today),
            "todayVisitorCount": (dashboard.get("todaySummary") or {}).get("visitorCount", (dashboard.get("summary") or {}).get("todayEventCount", 0)),
            "pendingFollowupCount": (dashboard.get("summary") or {}).get("pendingLeadCount", 0),
            "activeVisitorCount": len(profiles),
            "followingFollowupCount": len(following_profiles),
            "abandonedFollowupCount": len(abandoned_profiles),
            "opportunityCount": len(alerts),
            "revivalCount": len(revival_alerts),
            "topContentTitle": content_insights[0]["title"] if content_insights else "",
        }
        return dashboard

    def _build_opportunity_profiles(
        self,
        owner_user_id: str,
        note_by_id: dict[str, UserNote],
        note_by_card_id: dict[str, UserNote],
        showcase_events: list[ShowcaseEvent],
        actions: list[CustomerAction],
        leads: list[LeadReminder],
        note_view_events: dict[str, list[ViewEvent]],
        viewer_contact_cache: dict[str, dict[str, str]] | None = None,
    ) -> list[dict]:
        profiles: dict[str, dict] = {}
        viewer_contact_cache = viewer_contact_cache if viewer_contact_cache is not None else {}

        def ensure_profile(
            viewer_user_id: str | None,
            anonymous_id: str | None,
            fallback_id: str,
            nickname: str | None,
            avatar_url: str | None,
            visitor_identity_id: str | None = None,
        ) -> dict:
            key = visitor_identity_id or self._stable_visitor_identity_id(owner_user_id, viewer_user_id, anonymous_id, fallback_id)
            if key in profiles:
                return profiles[key]
            viewer_key = self._clean_optional_text(viewer_user_id)
            if viewer_key:
                if viewer_key not in viewer_contact_cache:
                    viewer_contact_cache[viewer_key] = self._viewer_contact_fields(viewer_key)
                viewer_contact = viewer_contact_cache[viewer_key]
            else:
                viewer_contact = {"phone": "", "wechat": "", "email": ""}
            profile = {
                    "id": key,
                    "visitorIdentityId": key,
                    "viewerUserId": viewer_user_id or "",
                    "anonymousId": anonymous_id or "",
                    "anonymous": not bool(viewer_user_id),
                    "nickname": self._dashboard_display_name(nickname, viewer_user_id),
                    "avatarUrl": avatar_url or "",
                    "phone": viewer_contact["phone"],
                    "wechat": viewer_contact["wechat"],
                    "email": viewer_contact["email"],
                    "budgetText": "",
                    "customerTags": [],
                    "leadReminderId": "",
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
                }
            profiles[key] = profile
            return profile

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
            profile = ensure_profile(event.viewerUserId, event.anonymousId, event.id, event.nickname, event.avatarUrl, event.visitorIdentityId or self._event_visitor_identity_id(owner_user_id, event))
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
                profile = ensure_profile(event.viewerUserId, event.anonymousId, event.id, event.nickname, event.avatarUrl, event.visitorIdentityId or self._event_visitor_identity_id(owner_user_id, event))
                profile["viewCount"] += 1
                profile["durationSeconds"] = max(profile["durationSeconds"], int(event.durationSeconds or 0))
                profile["maxScrollPercent"] = max(profile["maxScrollPercent"], int(event.maxScrollPercent or 0))
                profile["focusSections"] = self._merge_focus_sections(profile["focusSections"], event.focusSections)
                add_note(profile, note)
                touch(profile, event.viewedAt)

        for action in actions:
            profile = ensure_profile(action.viewerUserId, action.anonymousId, action.id, (action.payload or {}).get("name") or (action.payload or {}).get("nickname"), (action.payload or {}).get("avatarUrl"), action.visitorIdentityId or self._stable_visitor_identity_id(owner_user_id, action.viewerUserId, action.anonymousId, action.id))
            profile["phone"] = (action.payload or {}).get("phone") or profile.get("phone") or ""
            profile["wechat"] = (action.payload or {}).get("wechat") or profile.get("wechat") or ""
            profile["email"] = (action.payload or {}).get("email") or profile.get("email") or ""
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
            profile = ensure_profile(lead.viewerUserId, None, lead.id, lead.nickname, lead.avatarUrl, lead.visitorIdentityId or self._stable_visitor_identity_id(owner_user_id, lead.viewerUserId, None, lead.id))
            profile["hasLead"] = True
            profile["leadReminderId"] = lead.id
            profile["leadVersion"] = int(lead.version or 0)
            profile["leadStatus"] = lead.status
            profile["leadStatusText"] = self._lead_status_text(lead.status)
            # The radar projection carries only the current state and the
            # latest reminder date. Full follow-up records are detail-only.
            profile["nextFollowUpAt"] = lead.nextFollowUpAt or ""
            profile["phone"] = lead.customerPhone or profile.get("phone") or ""
            profile["wechat"] = lead.customerWechat or profile.get("wechat") or ""
            profile["email"] = lead.customerEmail or profile.get("email") or ""
            profile["budgetText"] = lead.budgetText or profile.get("budgetText") or ""
            profile["customerTags"] = lead.customerTags or profile.get("customerTags") or []
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
                "customerId": profile.get("id"),
                "visitorIdentityId": profile.get("visitorIdentityId") or profile.get("id"),
                "viewerUserId": profile.get("viewerUserId"),
                "anonymousId": profile.get("anonymousId"),
                "leadReminderId": profile.get("leadReminderId"),
                "leadVersion": profile.get("leadVersion"),
                "leadStatus": profile.get("leadStatus"),
                "leadStatusText": profile.get("leadStatusText"),
                "nextFollowUpAt": profile.get("nextFollowUpAt") or "",
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
                "noteIds": profile.get("noteIds") or [],
                "noteTitles": profile.get("noteTitles") or [],
                "focusSections": profile.get("focusSections") or [],
                "phone": profile.get("phone") or "",
                "wechat": profile.get("wechat") or "",
                "email": profile.get("email") or "",
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

    def _normalize_public_view_payload(self, payload, owner_user_id: str, authenticated_user_id: str | None):
        """Use the signed session identity for public view/event endpoints.

        Development fixtures historically submit viewerUserId directly. Keep that
        compatibility outside production, but never accept it as an identity in
        the production public browsing path. Anonymous clients may still provide
        a session key for dedupe/statistics; it never becomes a known user and is
        not eligible to consume a subscription grant.
        """
        if str(settings.app_env or "").lower() != "production":
            return payload
        user = self.repo.get_user(self._clean_optional_text(authenticated_user_id)) if authenticated_user_id else None
        if user:
            return payload.model_copy(
                update={
                    "viewerUserId": user.id,
                    "anonymousId": None,
                    "nickname": user.nickname,
                    "avatarUrl": user.avatarUrl,
                }
            )
        return payload.model_copy(
            update={
                "viewerUserId": None,
                "nickname": None,
                "avatarUrl": None,
            }
        )

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
        owner_user_id: str,
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
                key = event.visitorIdentityId or self._event_visitor_identity_id(owner_user_id, event)
                profile = merged.setdefault(
                    key,
                    {
                        "id": key,
                        "visitorIdentityId": key,
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

    def _stable_visitor_identity_id(
        self,
        owner_user_id: str,
        viewer_user_id: str | None = None,
        anonymous_id: str | None = None,
        fallback_id: str | None = None,
    ) -> str:
        """Return the owner-scoped identity shared by radar and detail.

        Logged-in viewers retain the existing user key. Anonymous viewers get
        an opaque, owner-scoped key derived from the client anonymous ID. If a
        legacy event has no anonymous ID, its persisted event ID is the only
        safe identity available; it remains stable for that record without
        merging unrelated anonymous visitors.
        """
        viewer = self._clean_optional_text(viewer_user_id)
        anonymous = self._clean_optional_text(anonymous_id)
        if viewer:
            return f"user:{viewer}"
        if anonymous:
            digest = hashlib.sha256(f"{owner_user_id}|{anonymous}".encode("utf-8")).hexdigest()[:32]
            return f"visitor:{digest}"
        return f"legacy:{self._clean_optional_text(fallback_id) or new_id('visitor')}"

    def _event_visitor_identity_id(self, owner_user_id: str, event) -> str:
        return self._clean_optional_text(getattr(event, "visitorIdentityId", None)) or self._stable_visitor_identity_id(
            owner_user_id,
            getattr(event, "viewerUserId", None),
            getattr(event, "anonymousId", None),
            getattr(event, "id", None),
        )

    def _viewer_contact_fields(self, viewer_user_id: str | None) -> dict[str, str]:
        viewer_id = self._clean_optional_text(viewer_user_id)
        if not viewer_id:
            return {"phone": "", "wechat": "", "email": ""}
        viewer = self.repo.get_user(viewer_id)
        if not viewer:
            return {"phone": "", "wechat": "", "email": ""}
        sales_profile = viewer.salesProfile if isinstance(viewer.salesProfile, dict) else {}
        return {
            "phone": self._clean_optional_text(viewer.phone) or "",
            "wechat": self._clean_optional_text(viewer.wechat) or "",
            "email": self._clean_optional_text(sales_profile.get("email")) or "",
        }

    def _dashboard_display_name(self, nickname: str | None, viewer_user_id: str | None = None) -> str:
        cleaned = str(nickname or "").strip()
        if cleaned:
            return cleaned
        return "微信客户" if viewer_user_id else "匿名客户"

    def _business_dashboard_contact_lookup(
        self,
        owner_user_id: str,
        actions: list[CustomerAction],
        leads: list[LeadReminder],
    ) -> dict[str, dict]:
        lookup: dict[str, dict] = {}
        for lead in leads:
            key = lead.visitorIdentityId or self._stable_visitor_identity_id(owner_user_id, lead.viewerUserId, None, lead.id)
            row = lookup.setdefault(key, {})
            row.update(
                {
                    "viewerUserId": lead.viewerUserId,
                    "nickname": lead.nickname or row.get("nickname") or "微信客户",
                    "avatarUrl": lead.avatarUrl or row.get("avatarUrl") or "",
                    "phone": lead.customerPhone or row.get("phone") or "",
                    "wechat": lead.customerWechat or row.get("wechat") or "",
                    "email": lead.customerEmail or row.get("email") or "",
                    "budgetText": lead.budgetText or row.get("budgetText") or "",
                    "intentLevel": lead.intentLevel or row.get("intentLevel") or "待判断",
                    "customerTags": lead.customerTags or row.get("customerTags") or [],
                    "leadReminderId": lead.id,
                    "lastActivityAt": lead.updatedAt or lead.lastViewedAt or row.get("lastActivityAt") or "",
                }
            )
        for action in actions:
            key = action.visitorIdentityId or self._stable_visitor_identity_id(owner_user_id, action.viewerUserId, action.anonymousId, action.id)
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
                    "email": payload.get("email") or row.get("email") or "",
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
        owner_user_id: str,
        showcase_events: list[ShowcaseEvent],
        actions: list[CustomerAction],
        leads: list[LeadReminder],
        showcase_by_id: dict[str, ShowcasePage],
        note_by_id: dict[str, UserNote],
    ) -> list[dict]:
        contact_lookup = self._business_dashboard_contact_lookup(owner_user_id, actions, leads)
        profiles: dict[str, dict] = {}
        for event in sorted(showcase_events, key=lambda item: item.createdAt):
            key = event.visitorIdentityId or self._event_visitor_identity_id(owner_user_id, event)
            contact = contact_lookup.get(key, {})
            showcase = showcase_by_id.get(event.showcaseId)
            profile = profiles.setdefault(
                key,
                {
                    "id": key,
                    "visitorIdentityId": key,
                    "viewerUserId": event.viewerUserId or contact.get("viewerUserId") or "",
                    "anonymousId": event.anonymousId or contact.get("anonymousId") or "",
                    "anonymous": not bool(event.viewerUserId),
                    "nickname": contact.get("nickname") or self._dashboard_display_name(event.nickname, event.viewerUserId),
                    "avatarUrl": contact.get("avatarUrl") or event.avatarUrl or "",
                    "phone": contact.get("phone") or "",
                    "wechat": contact.get("wechat") or "",
                    "email": contact.get("email") or "",
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
            profile["email"] = contact.get("email") or profile.get("email") or ""
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
                    "visitorIdentityId": key,
                    "viewerUserId": contact.get("viewerUserId") or "",
                    "anonymousId": contact.get("anonymousId") or "",
                    "anonymous": not bool(contact.get("viewerUserId")),
                    "nickname": contact.get("nickname") or "微信客户",
                    "avatarUrl": contact.get("avatarUrl") or "",
                    "phone": contact.get("phone") or "",
                    "wechat": contact.get("wechat") or "",
                    "email": contact.get("email") or "",
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
            profile["email"] = contact.get("email") or profile.get("email") or ""
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

    def get_business_dashboard(self, owner_user_id: str, requester_user_id: str | None = None, mode: str | None = None) -> dict:
        self.require_customer_intelligence(owner_user_id)
        return self._build_business_dashboard(owner_user_id, requester_user_id, mode)

    def _normalize_showcase_display_config(self, config: dict | None) -> dict:
        source = config if isinstance(config, dict) else {}
        group_by = str(source.get("groupBy") or "none").strip()
        if group_by not in {"none", "cardType", "tag", "custom"}:
            group_by = "none"
        return {
            "sceneType": self._clean_optional_text(source.get("sceneType")),
            "groupBy": group_by,
            "activeCategory": self._clean_optional_text(source.get("activeCategory")) or "全部",
            "showSearch": bool(source.get("showSearch", False)),
            "showTags": bool(source.get("showTags", True)),
            "layoutMode": "grid" if str(source.get("layoutMode") or "list").strip() == "grid" else "list",
            "primaryColor": str(source.get("primaryColor") or "#1677ff").strip()[:24],
            "propertyFilters": self._normalize_property_filter_groups(source.get("propertyFilters")),
        }

    def _normalize_property_filter_groups(self, groups) -> list[dict]:
        normalized: list[dict] = []
        if not isinstance(groups, list):
            return normalized
        for group in groups[:4]:
            if not isinstance(group, dict):
                continue
            key = self._clean_optional_text(group.get("key"))
            label = self._clean_optional_text(group.get("label"))
            options = []
            for option in group.get("options") or []:
                if not isinstance(option, dict):
                    continue
                value = self._clean_optional_text(option.get("value"))
                option_label = self._clean_optional_text(option.get("label")) or value
                if not value:
                    continue
                options.append(
                    {
                        "label": option_label,
                        "value": value,
                        "count": self._safe_int(option.get("count"), 0, 9999),
                    }
                )
            if key and label and options:
                normalized.append({"key": key, "label": label, "options": options[:12]})
        return normalized

    def _resolve_showcase_scene(self, owner_user_id: str, payload: ShowcasePageRequest) -> str:
        display = payload.displayConfig if isinstance(payload.displayConfig, dict) else {}
        explicit = payload.sceneType or display.get("sceneType")
        category = display.get("activeCategory")
        card_types = []
        for item in payload.items or []:
            note_id = str(getattr(item, "noteId", "") or "").strip()
            note = self.repo.get_user_note(note_id) if note_id else None
            if note:
                config = note.visibilityConfig if isinstance(note.visibilityConfig, dict) else {}
                card_types.append(str(config.get("cardType") or "text_note"))
        return normalize_scene_type(explicit, category, card_types)

    def _normalize_showcase_items(self, owner_user_id: str, items: list, scene_type: str | None = None) -> list[ShowcaseItem]:
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
            if scene_type:
                config = note.visibilityConfig if isinstance(note.visibilityConfig, dict) else {}
                card_type = str(config.get("cardType") or "text_note")
                if not scene_accepts_note(scene_type, card_type):
                    raise HTTPException(status_code=400, detail="合集类型与所选资料类型不匹配，请新建对应类型合集")
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
            if note and note.shareState == "published":
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
            "coverUrl": self._first_note_image_url(note),
            "sectionTitle": item.sectionTitle,
            "sortOrder": item.sortOrder,
            "cardType": card_type,
            "systemCategory": config.get("systemCategory", ""),
            "tags": self._note_tags(note),
            "badge": self._showcase_note_badge(card_type),
            "primaryText": self._showcase_note_primary_text(card_type, structured_data, note),
            "secondaryText": self._showcase_note_secondary_text(card_type, structured_data, note),
            "priceText": str(structured_data.get("price") or "").strip(),
            "propertyMeta": self._showcase_property_meta(card_type, structured_data, note),
            "productMeta": self._showcase_product_meta(card_type, structured_data),
            "productActionText": "查看详情/接龙" if card_type == "groupbuy_product" else "",
            "updatedAt": note.updatedAt,
        }

    def _showcase_property_meta(self, card_type: str, data: dict, note: UserNote) -> dict:
        if card_type != "property_listing":
            return {}
        temp_note = note.model_copy(
            update={
                "visibilityConfig": {
                    **(note.visibilityConfig or {}),
                    "structuredData": data,
                }
            }
        )
        return {
            "area": self._property_filter_value(temp_note, "area"),
            "layout": self._property_filter_value(temp_note, "layout"),
            "price": self._property_filter_value(temp_note, "price"),
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
        if payload.expectedRevision is not None and int(payload.expectedRevision) != int(note.revision or 0):
            raise HTTPException(status_code=409, detail="资料已被其他页面更新，请刷新后再保存")
        if not payload.title.strip():
            raise HTTPException(status_code=400, detail="标题不能为空")
        if note.status == "draft":
            # Saving from any of the five editors confirms that the owner has
            # taken over the imported draft.  Keep it private until the
            # explicit send-to-customer action publishes it.
            note.status = "active"
        body = payload.body.strip()
        note.title = payload.title.strip()
        note.summary = (payload.summary or body[:120]).strip()
        note.body = body
        note.coverUrl = payload.coverUrl
        note.media = self._normalize_note_media([item.model_dump() for item in payload.media])
        if getattr(payload, "contentBlocks", None) is not None:
            note.contentBlocks = self._normalize_note_content_blocks(
                getattr(payload, "contentBlocks", None),
                body=body,
                media=note.media,
            )
        elif (payload.visibilityConfig or {}).get("cardType") == "service_offer":
            # The service editor's structured detail text is canonical. Do not
            # retain imported content blocks, which can contain a deleted phone
            # number and make publish safety checks fail after the edit.
            note.contentBlocks = self._normalize_note_content_blocks([], body=body, media=note.media)
        elif not note.contentBlocks:
            note.contentBlocks = self._normalize_note_content_blocks([], body=body, media=note.media)
        note.categoryIds = payload.categoryIds
        note.phone = payload.phone
        note.locationText = payload.locationText
        previous_config = dict(note.visibilityConfig or {})
        next_config = dict(payload.visibilityConfig or {})
        # Marketing routing belongs to the PC operations console. Preserve an
        # existing route for operations, but never let a user editor create or
        # modify it through the normal note update endpoint.
        if "marketingRoute" in previous_config:
            next_config["marketingRoute"] = previous_config["marketingRoute"]
        else:
            next_config.pop("marketingRoute", None)
        for key in ("shareSnapshot", "shareSnapshotHistory"):
            if key not in next_config and key in previous_config:
                next_config[key] = previous_config[key]
        note.visibilityConfig = self._normalize_note_visibility_config(next_config)
        note.revision = max(int(note.revision or 0), 0) + 1
        if note.shareState == "published":
            note.shareState = "private"
        config = dict(note.visibilityConfig or {})
        config["revision"] = note.revision
        config["shareState"] = note.shareState
        config["intakeState"] = "editing"
        note.visibilityConfig = self._normalize_note_visibility_config(config)
        note.updatedAt = now_iso()
        self.repo.save_user_note(note)
        self._invalidate_card_list_cache(payload.ownerUserId)
        return note

    def _normalize_note_content_blocks(
        self,
        blocks: list | None,
        *,
        body: str = "",
        media: list | None = None,
    ) -> list[dict]:
        """Keep text/media order separate from the media storage registry.

        ``UserNote.media`` remains the deduplicated storage/reference list.  A
        content block only describes how the customer-facing body is composed.
        Old notes without blocks are upgraded on read/write as text followed by
        their existing media order.
        """
        media_items = [item for item in (media or []) if isinstance(item, dict)]
        media_by_id = {
            str(item.get("id")): item
            for item in media_items
            if item.get("id")
        }
        media_by_url = {
            str(item.get("url")): item
            for item in media_items
            if item.get("url")
        }
        source_blocks = blocks if isinstance(blocks, list) and blocks else None
        if source_blocks is None:
            source_blocks = []
            text = strip_unicode_surrogates(body or "").strip()
            if text:
                source_blocks.append({"type": "text", "text": text, "sortOrder": 0})
            source_blocks.extend(
                {
                    **item,
                    "sortOrder": item.get("sortOrder", index + (1 if text else 0)),
                }
                for index, item in enumerate(media_items)
                if item.get("type") in {"image", "pdf", "link"} and item.get("url")
            )

        normalized: list[dict] = []
        for index, raw in enumerate(source_blocks):
            if not isinstance(raw, dict):
                continue
            block_type = str(raw.get("type") or "text").strip().lower()
            if block_type == "text":
                text = strip_unicode_surrogates(raw.get("text") or raw.get("value") or "").strip()
                if not text:
                    continue
                normalized.append({
                    "id": str(raw.get("id") or f"block_text_{index}"),
                    "type": "text",
                    "text": text,
                    "sortOrder": self._safe_int(raw.get("sortOrder"), index, 9999),
                })
                continue
            if block_type not in {"image", "pdf", "link"}:
                continue
            media_item = media_by_id.get(str(raw.get("mediaId") or raw.get("id") or ""))
            media_item = media_item or media_by_url.get(str(raw.get("url") or "")) or {}
            url = self._clean_optional_text(raw.get("url") or media_item.get("url"))
            if not url:
                continue
            block_id = self._clean_optional_text(raw.get("id") or media_item.get("id")) or self._stable_attachment_id(block_type, url)
            block = {
                "id": block_id,
                "type": block_type,
                "mediaId": self._clean_optional_text(raw.get("mediaId") or media_item.get("mediaId") or media_item.get("id")),
                "url": url,
                "sortOrder": self._safe_int(raw.get("sortOrder"), index, 9999),
            }
            for key in ("name", "title", "description", "mimeType", "sizeBytes", "pageCount", "coverUrl", "source", "status"):
                value = raw.get(key, media_item.get(key))
                if value not in (None, ""):
                    block[key] = value
            normalized.append(block)
        normalized.sort(key=lambda item: (item.get("sortOrder", 0), item.get("id", "")))
        for index, item in enumerate(normalized):
            item["sortOrder"] = index
        return normalized

    def _public_note_content_blocks(self, note: UserNote, public_media: list[dict], *, body: str | None = None) -> list[dict]:
        blocks = self._normalize_note_content_blocks(
            note.contentBlocks,
            body=note.body if body is None else body,
            media=note.media,
        )
        allowed_ids = {str(item.get("id")) for item in public_media if item.get("id")}
        allowed_urls = {str(item.get("url")) for item in public_media if item.get("url")}
        result: list[dict] = []
        for block in blocks:
            if block.get("type") == "text":
                result.append(self._sanitize_public_config_value(block))
                continue
            if str(block.get("mediaId") or "") in allowed_ids or str(block.get("url") or "") in allowed_urls:
                result.append(self._sanitize_public_config_value(block))
        return result

    def _normalize_note_media(self, media: list | None, public_only: bool = False) -> list[dict]:
        normalized: list[dict] = []
        counts = {"image": 0, "pdf": 0, "link": 0}
        for index, raw in enumerate(media or []):
            if not isinstance(raw, dict):
                continue
            item = dict(raw)
            media_type = str(item.get("type") or "image").lower()
            if public_only and media_type not in PUBLIC_ATTACHMENT_TYPES:
                continue
            if media_type == "link":
                parsed = urlparse(str(item.get("url") or ""))
                if parsed.scheme != "https" or not parsed.netloc:
                    if public_only:
                        continue
                    raise HTTPException(status_code=400, detail="外部链接必须使用HTTPS")
            url = self._clean_optional_text(item.get("url"))
            if not url:
                continue
            if media_type in counts:
                counts[media_type] += 1
            item.update({
                "id": self._clean_optional_text(item.get("id")) or self._stable_attachment_id(media_type, url),
                "type": media_type,
                "url": url,
                "sortOrder": self._safe_int(item.get("sortOrder"), index, 9999),
                "status": str(item.get("status") or "ready"),
                "source": str(item.get("source") or "upload"),
            })
            normalized.append(item)
        if counts["image"] > 9:
            raise HTTPException(status_code=400, detail="每份资料最多9张图片")
        if counts["pdf"] > 5:
            raise HTTPException(status_code=400, detail="每份资料最多5份PDF")
        if counts["link"] > 5:
            raise HTTPException(status_code=400, detail="每份资料最多5条外部链接")
        if sum(counts.values()) > 12:
            raise HTTPException(status_code=400, detail="每份资料最多12个公开附件")
        return sorted(normalized, key=lambda row: row.get("sortOrder", 0))

    def _stable_attachment_id(self, media_type: str, url: str) -> str:
        digest = hashlib.sha256(f"{media_type}:{url}".encode("utf-8")).hexdigest()[:20]
        return f"att_{digest}"

    def duplicate_user_note(self, note_id: str, owner_user_id: str) -> UserNote:
        source = self.get_user_note(note_id, owner_user_id)
        now = now_iso()
        copy_note = source.model_copy(deep=True)
        copy_note.id = new_id("note")
        copy_note.sourceCardId = None
        copy_note.importBatchId = None
        copy_note.title = f"{source.title} 副本"
        copy_note.status = "active"
        copy_note.shareState = "private"
        copy_note.revision = max(int(source.revision or 0), 1)
        copy_note.intakeId = None
        copy_note.idempotencyKey = None
        config = self._normalize_note_visibility_config(copy_note.visibilityConfig)
        config["cardState"] = "editing"
        config["shareState"] = copy_note.shareState
        config["revision"] = copy_note.revision
        config["intakeState"] = "editing"
        copy_note.visibilityConfig = config
        copy_note.createdAt = now
        copy_note.updatedAt = now
        self.repo.save_user_note(copy_note)
        self._invalidate_card_list_cache(owner_user_id)
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
        self._invalidate_showcase_list_cache(owner.id)
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
        public_source = self.get_public_note(source.id)
        source_config = public_source.get("visibilityConfig") if isinstance(public_source.get("visibilityConfig"), dict) else {}
        source_structured = source_config.get("structuredData") if isinstance(source_config.get("structuredData"), dict) else {}
        structured_data = self._public_clone_structured_data(source_structured)
        phone = self._clean_optional_text(payload.phone) or owner.phone
        wechat = self._clean_optional_text(payload.wechat)
        media = self._clone_note_media(source)
        cover_url = source.coverUrl or self._first_media_url(media)
        now = now_iso()
        source_refs = self._unique_strings([*source.sourceRefs, source.id, source_showcase_id or ""])
        card_type = str(source_config.get("cardType") or "property_listing")
        if card_type == "business_card":
            structured_data = {"headline": "", "serviceKeywords": [], "bio": "", "featuredNoteIds": []}
            media = []
            cover_url = None
            source_refs = []
            source_config = {
                "schemaVersion": 2,
                "cardType": "business_card",
                "displayConfig": {"styleId": ((source_config.get("displayConfig") or {}).get("styleId") or "business_blue")},
            }
        visibility_config = self._normalize_note_visibility_config(
            {
                **source_config,
                "cardType": card_type,
                "cardState": "editing",
                "sourceType": "property_same_clone",
                "structuredData": structured_data,
                "conversionConfig": self._clone_conversion_config(card_type, source_config, phone, wechat),
                "privateData": {},
            }
        )
        visibility_config["shareState"] = "private"
        visibility_config["intakeState"] = "editing"
        visibility_config["revision"] = 1
        source_owner = self.repo.get_user(source.ownerUserId)
        title = self._sanitize_same_style_text(public_source.get("title") or source.title, source, source_owner)
        summary = self._sanitize_same_style_text(public_source.get("summary") or source.summary, source, source_owner)
        body = self._sanitize_same_style_text(public_source.get("body") or source.body, source, source_owner)
        location_text = source.locationText
        if card_type == "business_card":
            title = f"{owner.nickname}的电子名片"
            summary = ""
            body = ""
            location_text = None
        note = UserNote(
            id=new_id("note"),
            ownerUserId=owner.id,
            importBatchId=None,
            sourceCardId=None,
            status="active",
            shareState="private",
            revision=1,
            title=title,
            summary=summary,
            body=body,
            coverUrl=cover_url,
            media=media,
            categoryIds=[],
            phone=None,
            locationText=location_text,
            sourceRefs=source_refs,
            visibilityConfig=visibility_config,
            createdAt=now,
            updatedAt=now,
        )
        self.repo.save_user_note(note)
        self._invalidate_card_list_cache(owner.id)
        self._register_media_refs_for_urls([cover_url, *[item.get("url") for item in media if isinstance(item, dict)]], owner.id, "note", note.id, "clone_media")
        self._record_property_same_peer_signal(
            source_note_id=source.id,
            source_showcase_id=source_showcase_id,
            clone_owner=owner,
            payload=payload,
            clone_type="note",
            generated_ref_id=note.id,
            source=source,
        )
        return note

    def _sanitize_same_style_text(
        self,
        value: str | None,
        source: UserNote,
        source_owner: User | None = None,
    ) -> str:
        text = str(value or "")
        source_owner = source_owner or self.repo.get_user(source.ownerUserId)
        exact_values = [source.phone]
        if source_owner:
            exact_values.extend([source_owner.phone, source_owner.wechat])
            profile = source_owner.salesProfile or {}
            exact_values.extend([profile.get("phone"), profile.get("wechat")])
        for raw in exact_values:
            cleaned = self._clean_optional_text(raw)
            if cleaned:
                text = text.replace(cleaned, "[联系方式已移除]")
        return re.sub(r"(?<!\d)1[3-9]\d{9}(?!\d)", "[联系方式已移除]", text)

    def _record_property_same_peer_signal(
        self,
        source_note_id: str,
        source_showcase_id: str | None,
        clone_owner: User,
        payload: PropertySameCloneRequest,
        clone_type: str,
        generated_ref_id: str,
        source: UserNote | None = None,
    ) -> None:
        source = source or self.repo.get_user_note(source_note_id)
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
        for index, item in enumerate(media):
            item["id"] = new_id("att")
            item["sortOrder"] = index
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
        normalized["schemaVersion"] = 2
        normalized.setdefault("cardType", "link" if normalized.get("contentMode") == "bookmark" else "text_note")
        normalized.setdefault("cardState", "collected")
        structured_data = normalized.get("structuredData")
        normalized["structuredData"] = structured_data if isinstance(structured_data, dict) else {}
        normalized["conversionConfig"] = self._normalize_conversion_config(
            normalized.get("cardType", "text_note"),
            normalized.get("conversionConfig", {}),
        )
        normalized["conversionConfig"]["enableLightScrm"] = True
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
        if card_type == "business_card":
            defaults = dict(SERVICE_CONVERSION_DEFAULTS)
            defaults["collectLeads"] = True
            defaults["enableAppointment"] = False
            return defaults
        if card_type == "service_offer":
            defaults = dict(SERVICE_CONVERSION_DEFAULTS)
            defaults["enableAppointment"] = False
            return defaults
        # Every public material uses the same customer-page communication
        # baseline. Scene-specific actions (viewing appointments, relay,
        # payment) remain opt-in in their own card types.
        defaults = dict(SERVICE_CONVERSION_DEFAULTS)
        defaults["enableAppointment"] = False
        defaults["enableGroupRelay"] = False
        defaults["enablePaymentPlaceholder"] = False
        defaults["enableSharePoster"] = False
        return defaults

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
        self._mark_note_content_edit(note, "editing")
        note.updatedAt = now_iso()
        self.repo.save_user_note(note)
        self._invalidate_card_list_cache(owner_user_id)
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
        self._mark_note_content_edit(note, "editing")
        note.updatedAt = now_iso()
        self.repo.save_user_note(note)
        self._invalidate_card_list_cache(owner_user_id)
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
        self._apply_owner_public_contact_to_property_note(note)
        self._mark_note_content_edit(note, "editing")
        note.updatedAt = now_iso()
        self.repo.save_user_note(note)
        self._invalidate_card_list_cache(payload.ownerUserId)
        return note

    def _build_confirmed_structured_data(self, note: UserNote, config: dict, card_type: str) -> dict:
        current = dict(config.get("structuredData") or {})
        miniapp = current.get("miniapp") if isinstance(current.get("miniapp"), dict) else None
        preserved = {"miniapp": miniapp} if miniapp else {}
        images = self._note_image_urls(note)
        if card_type == "property_listing":
            recognized = self._recognized_structured_data_for_type(note, card_type)
            if recognized:
                return {
                    **preserved,
                    **recognized,
                    "propertyStatus": recognized.get("propertyStatus") or current.get("propertyStatus") or "active",
                    "images": images or recognized.get("images", []),
                    "rawText": recognized.get("rawText") or current.get("rawText") or note.body,
                }
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
            recognized = self._recognized_structured_data_for_type(note, card_type)
            if recognized:
                return {
                    **preserved,
                    **recognized,
                    "skuConfig": recognized.get("skuConfig") if isinstance(recognized.get("skuConfig"), dict) else {},
                    "images": images or recognized.get("images", []),
                    "rawText": recognized.get("rawText") or current.get("rawText") or note.body,
                }
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
                "headline": current.get("headline") or note.summary or "",
                "serviceKeywords": current.get("serviceKeywords") if isinstance(current.get("serviceKeywords"), list) else [],
                "bio": current.get("bio") or note.body or "",
                "featuredNoteIds": current.get("featuredNoteIds") if isinstance(current.get("featuredNoteIds"), list) else [],
            }
        if card_type == "service_offer":
            has_new_detail = "detailText" in current
            placeholder_values = {
                "未命名服务方案",
                "未命名服务",
                "手动创建，可继续补充内容。",
                "补充服务内容和预约方式后即可发给客户",
                "让客户快速理解价值",
            }

            def service_text(value) -> str:
                text = str(value or "").strip()
                return "" if text in placeholder_values else text

            detail_parts = []
            for value in (
                current.get("detailText"),
                current.get("serviceContent"),
                current.get("targetAudience"),
                current.get("serviceProcess"),
                current.get("caseHighlights"),
                current.get("appointmentNote"),
            ):
                normalized = service_text(value)
                if normalized and normalized not in detail_parts:
                    detail_parts.append(normalized)
            if not detail_parts and not has_new_detail:
                body = service_text(note.body)
                if body:
                    detail_parts.append(body)
            return {
                **preserved,
                "serviceName": service_text(current.get("serviceName") or note.title),
                "headline": service_text(current.get("headline") or note.summary),
                "detailText": "\n\n".join(detail_parts),
                "serviceScope": service_text(current.get("serviceScope") or current.get("serviceArea")),
                "pricingOrTerms": service_text(
                    current.get("pricingOrTerms") or current.get("cooperationTerms") or current.get("pricingNote")
                ),
                "primaryAction": "consult",
            }
        return {
            **preserved,
            "rawText": current.get("rawText") or note.body,
            "images": images,
        }

    def _recognized_structured_data_for_type(self, note: UserNote, card_type: str) -> dict:
        content_object = ContentObjectPayload(
            sourceType="manual_text",
            title=note.title or None,
            textBlocks=[note.body or note.summary or note.title or ""],
            media=[
                ContentMediaPayload(type=str(item.get("type") or "image"), url=item.get("url"), title=item.get("title"))
                for item in (note.media or [])
                if isinstance(item, dict) and item.get("url")
            ],
            metadata={"entryMode": "confirm_type"},
            sourceRefs=note.sourceRefs or [],
        )
        try:
            note_result = self.skill_router_service.run_content_to_note(note.ownerUserId, content_object)
        except Exception:
            return {}
        config = note_result.noteDraft.visibilityConfig or {}
        if config.get("cardType") != card_type:
            return {}
        structured_data = config.get("structuredData")
        return structured_data if isinstance(structured_data, dict) else {}

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
        self._mark_note_content_edit(note, "editing")
        note.updatedAt = now_iso()
        self.repo.save_user_note(note)
        return note

    def remove_note_from_topic(self, note_id: str, topic_id: str, owner_user_id: str) -> UserNote:
        note = self.get_user_note(note_id, owner_user_id)
        config = self._normalize_note_visibility_config(note.visibilityConfig)
        config["topicIds"] = [item for item in config.get("topicIds", []) if item != topic_id]
        config["topics"] = [item for item in config.get("topics", []) if item.get("id") != topic_id]
        note.visibilityConfig = config
        self._mark_note_content_edit(note, "editing")
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
        self._invalidate_card_list_cache(owner_user_id)
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
        note = self._require_published_note(note_id)
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
        note = self._require_published_note(note_id)
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
            visitorIdentityId=self._stable_visitor_identity_id(note.ownerUserId, payload.viewerUserId, payload.anonymousId, new_id("legacy_action")),
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
        self._invalidate_customer_intelligence_cache(note.ownerUserId)
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

    def _require_published_note(self, note_id: str) -> UserNote:
        note = self._get_active_note(note_id)
        if note.shareState != "published":
            raise HTTPException(status_code=404, detail="资料尚未发布")
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
            email = str(data.get("email") or data.get("mail") or "").strip()
            if not phone and not wechat and not email:
                raise HTTPException(status_code=400, detail="请填写电话、微信或邮箱")
            return {
                "name": str(data.get("name") or "").strip(),
                "phone": phone,
                "wechat": wechat,
                "email": email,
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
            logs.insert(
                0,
                LeadFollowUpLog(
                    id=new_id("log"),
                    content=log_content,
                    createdAt=now,
                    action=action.actionKey,
                    actionLabel=action.actionLabel or action.actionKey,
                    note=log_content,
                    nextFollowUpAt=self._appointment_follow_up_at(action.payload) if action.actionKey == "appointment" else (existing.nextFollowUpAt if existing else None),
                ),
            )
        reminder = LeadReminder(
            id=existing.id if existing else new_id("lead"),
            ownerUserId=note.ownerUserId,
            cardId=source_card_id,
            viewerUserId=viewer_key,
            visitorIdentityId=action.visitorIdentityId or self._stable_visitor_identity_id(note.ownerUserId, request.viewerUserId, request.anonymousId, action.id),
            nickname=nickname,
            avatarUrl=request.avatarUrl or (existing.avatarUrl if existing else None),
            status="pending" if not existing else existing.status,
            note=self._merge_lead_note(existing.note if existing else None, action),
            customerPhone=action.payload.get("phone") or (existing.customerPhone if existing else None),
            customerWechat=action.payload.get("wechat") or (existing.customerWechat if existing else None),
            customerEmail=action.payload.get("email") or (existing.customerEmail if existing else None),
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
        self._invalidate_customer_intelligence_cache(note.ownerUserId)
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
        created_message = None
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
            created_message = self._append_message(thread, user_id, content)
            thread = self.repo.get_message_thread(thread.id) or thread
        result = self._build_message_thread_row(thread, user_id)
        if created_message:
            result["message"] = created_message.model_dump()
        return result

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
        self._invalidate_card_list_cache(owner_user_id)
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

    def _invalidate_card_list_cache(self, owner_user_id: str | None = None) -> None:
        if not owner_user_id:
            self._card_list_cache.clear()
            self._note_list_cache.clear()
            return
        self._card_list_cache = {key: value for key, value in self._card_list_cache.items() if key[0] != owner_user_id}
        self._note_list_cache = {key: value for key, value in self._note_list_cache.items() if key[0] != owner_user_id}

    def _invalidate_showcase_list_cache(self, owner_user_id: str | None = None) -> None:
        if not owner_user_id:
            self._showcase_list_cache.clear()
            return
        self._showcase_list_cache.pop(owner_user_id, None)

    def _invalidate_customer_intelligence_cache(self, owner_user_id: str | None = None) -> None:
        if not owner_user_id:
            self._customer_intelligence_cache.clear()
            self._customer_intelligence_summary_cache.clear()
            self.repo.mark_customer_radar_summaries_dirty()
            return
        self._customer_intelligence_cache = {
            key: value for key, value in self._customer_intelligence_cache.items()
            if key[0] != owner_user_id
        }
        self._customer_intelligence_summary_cache = {
            key: value for key, value in self._customer_intelligence_summary_cache.items()
            if key[0] != owner_user_id
        }
        self.repo.mark_customer_radar_summaries_dirty(owner_user_id)

    @staticmethod
    def _customer_radar_summary_id(owner_user_id: str, mode: str) -> str:
        return f"customer_radar_summary:{owner_user_id}:{mode or 'all'}"

    @staticmethod
    def _customer_radar_summary_response(
        summary: CustomerRadarSummary,
        membership: dict,
        payment_required: bool,
    ) -> dict:
        return {
            "featureEnabled": True,
            "paymentRequired": payment_required,
            "locked": False,
            "membership": membership,
            "summary": {
                "pending": int(summary.pendingCount or 0),
                "visitors": int(summary.visitorCount or 0),
                "following": int(summary.followingCount or 0),
                "abandoned": int(summary.abandonedCount or 0),
                "highIntent": int(summary.highIntentCount or 0),
                "interactions": int(summary.interactionCount or 0),
                "revival": int(summary.revivalCount or 0),
                "filtered": int(summary.filteredCount or 0),
            },
            "source": "customer_radar_summary",
        }

    def _save_customer_radar_summary(
        self,
        owner_user_id: str,
        mode: str,
        response: dict,
        existing: CustomerRadarSummary | None = None,
    ) -> None:
        counts = response.get("summary") or {}
        now = now_iso()
        summary = CustomerRadarSummary(
            id=self._customer_radar_summary_id(owner_user_id, mode),
            ownerUserId=owner_user_id,
            mode=mode,
            pendingCount=int(counts.get("pending") or 0),
            visitorCount=int(counts.get("visitors") or 0),
            followingCount=int(counts.get("following") or 0),
            abandonedCount=int(counts.get("abandoned") or 0),
            highIntentCount=int(counts.get("highIntent") or 0),
            interactionCount=int(counts.get("interactions") or 0),
            revivalCount=int(counts.get("revival") or 0),
            filteredCount=int(counts.get("filtered") or 0),
            isDirty=False,
            refreshedAt=now,
            createdAt=existing.createdAt if existing else now,
            updatedAt=now,
        )
        self.repo.save_customer_radar_summary(summary)

    def _remember_customer_intelligence_cache(
        self,
        cache_key: tuple[str, str, str],
        response: dict,
        saved_at: float,
    ) -> None:
        self._customer_intelligence_cache[cache_key] = (saved_at, response)
        if len(self._customer_intelligence_cache) <= self._customer_intelligence_cache_max_entries:
            return
        expired_before = saved_at - self._customer_intelligence_cache_ttl_seconds
        self._customer_intelligence_cache = {
            key: value for key, value in self._customer_intelligence_cache.items()
            if value[0] >= expired_before
        }
        if len(self._customer_intelligence_cache) > self._customer_intelligence_cache_max_entries:
            oldest_keys = sorted(self._customer_intelligence_cache, key=lambda key: self._customer_intelligence_cache[key][0])
            for old_key in oldest_keys[:len(self._customer_intelligence_cache) - self._customer_intelligence_cache_max_entries]:
                self._customer_intelligence_cache.pop(old_key, None)

    def _remember_customer_intelligence_summary_cache(
        self,
        cache_key: tuple[str, str, str],
        response: dict,
        saved_at: float,
    ) -> None:
        self._customer_intelligence_summary_cache[cache_key] = (saved_at, response)
        if len(self._customer_intelligence_summary_cache) <= self._customer_intelligence_summary_cache_max_entries:
            return
        expired_before = saved_at - self._customer_intelligence_summary_cache_ttl_seconds
        self._customer_intelligence_summary_cache = {
            key: value for key, value in self._customer_intelligence_summary_cache.items()
            if value[0] >= expired_before
        }
        if len(self._customer_intelligence_summary_cache) > self._customer_intelligence_summary_cache_max_entries:
            oldest_keys = sorted(
                self._customer_intelligence_summary_cache,
                key=lambda key: self._customer_intelligence_summary_cache[key][0],
            )
            for old_key in oldest_keys[:len(self._customer_intelligence_summary_cache) - self._customer_intelligence_summary_cache_max_entries]:
                self._customer_intelligence_summary_cache.pop(old_key, None)

    def list_view_history(self, viewer_user_id: str, limit: int = 30) -> list[dict]:
        viewer_id = str(viewer_user_id or "").strip()
        if not viewer_id:
            return []
        safe_limit = max(1, min(int(limit or 30), 50))
        notes = self.repo.list_all_user_notes(include_deleted=False)
        cards = self.repo.list_cards()
        notes_by_id = {note.id: note for note in notes}
        notes_by_source_card = {
            note.sourceCardId: note
            for note in notes
            if note.sourceCardId
        }
        cards_by_id = {card.id: card for card in cards}
        history: list[dict] = []
        seen_targets: set[tuple[str, str]] = set()

        # A user only needs the newest distinct targets. Bound the source
        # events as well so a long-lived account does not make the profile tab
        # scan its entire view history on every return.
        event_limit = min(1000, max(safe_limit * 10, 50))
        for event in self.repo.list_view_events_for_viewer(viewer_id, limit=event_limit):
            target_note = notes_by_id.get(event.cardId) or notes_by_source_card.get(event.cardId)
            if target_note:
                if target_note.ownerUserId != viewer_id and target_note.status != "deleted" and target_note.shareState == "published":
                    target = ("note", target_note.id)
                    if target in seen_targets:
                        continue
                    seen_targets.add(target)
                    history.append(
                        {
                            "id": target_note.id,
                            "targetType": "note",
                            "title": target_note.title or "未命名资料",
                            "summary": target_note.summary or "",
                            "coverUrl": self._first_note_image_url(target_note),
                            "viewedAt": event.viewedAt,
                        }
                    )
                    if len(history) >= safe_limit:
                        break
                continue

            target_card = cards_by_id.get(event.cardId)
            if not target_card or target_card.ownerUserId == viewer_id or target_card.status != "published":
                continue
            target = ("card", target_card.id)
            if target in seen_targets:
                continue
            seen_targets.add(target)
            history.append(
                {
                    "id": target_card.id,
                    "targetType": "card",
                    "title": target_card.title or "未命名资料",
                    "summary": target_card.detailText or target_card.projectName or "",
                    "coverUrl": target_card.coverUrl or "",
                    "viewedAt": event.viewedAt,
                }
            )
            if len(history) >= safe_limit:
                break
        return history

    def _list_cards_page_fast(
        self,
        owner_user_id: str,
        limit: int,
        offset: int,
        cache_key: tuple,
        now: float,
    ) -> list[dict]:
        """Build only the requested library window for the unfiltered path.

        Cards and standalone notes are independently ordered streams.  The
        first ``offset + limit`` rows from each stream are sufficient to find
        that window after merging them, while linked source notes are fetched
        only for the candidate legacy cards.
        """
        window_size = max(1, offset + limit)
        cards = self.repo.list_cards(owner_user_id=owner_user_id, limit=window_size, offset=0)
        notes = self.repo.list_standalone_user_notes(
            owner_user_id=owner_user_id,
            limit=window_size,
            offset=0,
        )
        linked_notes = self.repo.list_user_notes_by_source_card_ids(
            owner_user_id,
            {item.id for item in cards},
        )
        notes_by_id = {item.id: item for item in [*notes, *linked_notes]}
        notes = list(notes_by_id.values())
        notes_by_source_card = {
            note.sourceCardId: note
            for note in notes
            if note.sourceCardId
        }
        backed_note_ids = {note.id for note in notes_by_source_card.values()}
        stats_ids = {item.id for item in cards}
        stats_ids.update(note.sourceCardId or note.id for note in notes)
        view_events_by_card = self.repo.list_view_events_for_cards(stats_ids)
        relays_by_card = self.repo.list_relay_entries_for_cards(stats_ids, relay_status="active")
        note_ids = {note.id for note in notes}
        actions_by_note = self.repo.list_customer_actions_for_notes(note_ids)
        leads_by_owner = {owner_user_id: self.repo.list_lead_reminders(owner_user_id)}

        def card_stats(card_id: str) -> dict:
            return self._build_stats_from_events(
                card_id,
                view_events_by_card.get(card_id, []),
                relays_by_card.get(card_id, []),
            )

        rows = []
        for item in cards:
            source_note = notes_by_source_card.get(item.id)
            source_note_config = source_note.visibilityConfig if source_note else {}
            source_note_cover_url = self._first_note_image_url(source_note) if source_note else ""
            rows.append(
                {
                    **item.model_dump(),
                    "coverUrl": item.coverUrl or source_note_cover_url,
                    "cardType": source_note_config.get("cardType"),
                    "systemCategory": source_note_config.get("systemCategory"),
                    "visibilityConfig": source_note_config,
                    "stats": card_stats(item.id),
                    "sourceNoteId": source_note.id if source_note else None,
                    "shareState": source_note.shareState if source_note else None,
                    "sourceNoteShareState": source_note.shareState if source_note else None,
                    "sourceNoteStatus": source_note.status if source_note else None,
                    "revision": source_note.revision if source_note else None,
                    "customerSummary": self._build_note_customer_summary(
                        source_note,
                        actions_by_note=actions_by_note,
                        leads_by_owner=leads_by_owner,
                    ) if source_note else {},
                }
            )
        rows.extend(
            self._note_card_rows(
                owner_user_id,
                None,
                None,
                backed_note_ids,
                notes=notes,
                view_events_by_card=view_events_by_card,
                relays_by_card=relays_by_card,
                actions_by_note=actions_by_note,
                leads_by_owner=leads_by_owner,
            )
        )
        rows.sort(key=lambda item: item.get("updatedAt") or item.get("createdAt") or "", reverse=True)
        page = rows[offset:offset + limit]
        self._card_list_cache[cache_key] = (now, page)
        return page

    def list_cards(self, owner_user_id: str | None = None, keyword: str | None = None, category_id: str | None = None, limit: int | None = None, offset: int = 0) -> list[dict]:
        page_mode = bool(owner_user_id and limit is not None and not keyword and not category_id)
        safe_limit = max(1, min(int(limit), 50)) if limit is not None else None
        safe_offset = max(int(offset or 0), 0)
        cache_key = (
            owner_user_id or "",
            keyword or "",
            category_id or "",
            "page",
            safe_limit,
            safe_offset,
        ) if page_mode else (owner_user_id or "", keyword or "", category_id or "")
        cached = self._card_list_cache.get(cache_key)
        now = time.monotonic()
        if cached and now - cached[0] < self._card_list_cache_ttl_seconds:
            rows = cached[1]
            if page_mode:
                return rows
            return rows[safe_offset:safe_offset + safe_limit] if safe_limit else rows[safe_offset:]
        if page_mode:
            return self._list_cards_page_fast(
                owner_user_id,
                safe_limit,
                safe_offset,
                cache_key,
                now,
            )
        cards = self.repo.list_cards(owner_user_id=owner_user_id, keyword=keyword, category_id=category_id)
        notes = (
            self.repo.list_user_notes(owner_user_id=owner_user_id, keyword=None, category_id=category_id, include_deleted=False)
            if owner_user_id
            else self.repo.list_all_user_notes(include_deleted=False)
        )
        if keyword:
            lowered = keyword.lower().strip()
            query_digits = re.sub(r"\D+", "", lowered)
            notes = [item for item in notes if self._note_matches_keyword(item, lowered, query_digits)]
        notes_by_source_card = {
            note.sourceCardId: note
            for note in notes
            if note.sourceCardId
        }
        backed_note_ids = {note.id for note in notes_by_source_card.values()}
        stats_ids = {item.id for item in cards}
        stats_ids.update(note.sourceCardId or note.id for note in notes)
        view_events_by_card = self.repo.list_view_events_for_cards(stats_ids)
        relays_by_card = self.repo.list_relay_entries_for_cards(stats_ids, relay_status="active")
        note_ids = {note.id for note in notes}
        actions_by_note = self.repo.list_customer_actions_for_notes(note_ids)
        leads_by_owner = {
            owner_id: self.repo.list_lead_reminders(owner_id)
            for owner_id in {note.ownerUserId for note in notes}
        }

        def card_stats(card_id: str) -> dict:
            return self._build_stats_from_events(
                card_id,
                view_events_by_card.get(card_id, []),
                relays_by_card.get(card_id, []),
            )

        rows = []
        for item in cards:
            source_note = notes_by_source_card.get(item.id)
            source_note_config = source_note.visibilityConfig if source_note else {}
            source_note_cover_url = self._first_note_image_url(source_note) if source_note else ""
            rows.append(
                {
                    **item.model_dump(),
                    "coverUrl": item.coverUrl or source_note_cover_url,
                    "cardType": source_note_config.get("cardType"),
                    "systemCategory": source_note_config.get("systemCategory"),
                    "visibilityConfig": source_note_config,
                    "stats": card_stats(item.id),
                    "sourceNoteId": source_note.id if source_note else None,
                    "shareState": source_note.shareState if source_note else None,
                    "sourceNoteShareState": source_note.shareState if source_note else None,
                    "sourceNoteStatus": source_note.status if source_note else None,
                    "revision": source_note.revision if source_note else None,
                    "customerSummary": self._build_note_customer_summary(
                        source_note,
                        actions_by_note=actions_by_note,
                        leads_by_owner=leads_by_owner,
                    ) if source_note else {},
                }
            )
        rows.extend(
            self._note_card_rows(
                owner_user_id,
                keyword,
                category_id,
                backed_note_ids,
                notes=notes,
                view_events_by_card=view_events_by_card,
                relays_by_card=relays_by_card,
                actions_by_note=actions_by_note,
                leads_by_owner=leads_by_owner,
            )
        )
        rows.sort(key=lambda item: item.get("updatedAt") or item.get("createdAt") or "", reverse=True)
        self._card_list_cache[cache_key] = (now, rows)
        if len(self._card_list_cache) > self._card_list_cache_max_entries:
            expired_before = now - self._card_list_cache_ttl_seconds
            self._card_list_cache = {
                key: value for key, value in self._card_list_cache.items()
                if value[0] >= expired_before
            }
            if len(self._card_list_cache) > self._card_list_cache_max_entries:
                oldest_keys = sorted(self._card_list_cache, key=lambda key: self._card_list_cache[key][0])
                for old_key in oldest_keys[:len(self._card_list_cache) - self._card_list_cache_max_entries]:
                    self._card_list_cache.pop(old_key, None)
        return rows[safe_offset:safe_offset + safe_limit] if safe_limit else rows[safe_offset:]

    def _note_card_rows(
        self,
        owner_user_id: str | None,
        keyword: str | None,
        category_id: str | None,
        backed_note_ids: set[str],
        *,
        notes: list[UserNote] | None = None,
        view_events_by_card: dict[str, list[ViewEvent]] | None = None,
        relays_by_card: dict[str, list[RelayEntry]] | None = None,
        actions_by_note: dict[str, list[CustomerAction]] | None = None,
        leads_by_owner: dict[str, list[LeadReminder]] | None = None,
    ) -> list[dict]:
        if not owner_user_id:
            return []
        notes = notes if notes is not None else self.repo.list_user_notes(
            owner_user_id=owner_user_id,
            keyword=None,
            category_id=category_id,
            include_deleted=False,
        )
        view_events_by_card = view_events_by_card or {}
        relays_by_card = relays_by_card or {}
        actions_by_note = actions_by_note or {}
        leads_by_owner = leads_by_owner or {}
        rows: list[dict] = []
        for note in notes:
            if note.id in backed_note_ids or note.sourceCardId:
                continue
            config = note.visibilityConfig or {}
            card_type = config.get("cardType") or ("link" if config.get("contentMode") == "bookmark" else "text_note")
            system_category = self._note_card_category_name(card_type, config.get("systemCategory"))
            cover_url = note.coverUrl or self._first_note_image_url(note)
            stats_id = note.sourceCardId or note.id
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
                    "stats": self._build_stats_from_events(
                        stats_id,
                        view_events_by_card.get(stats_id, []),
                        relays_by_card.get(stats_id, []),
                    ),
                    "sourceNoteId": note.id,
                    "shareState": note.shareState,
                    "sourceNoteShareState": note.shareState,
                    "sourceNoteStatus": note.status,
                    "revision": note.revision,
                    "customerSummary": self._build_note_customer_summary(
                        note,
                        actions_by_note=actions_by_note,
                        leads_by_owner=leads_by_owner,
                    ),
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
        self._invalidate_card_list_cache(owner_user_id)
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
        self._invalidate_card_list_cache(owner_user_id)
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
        self._invalidate_card_list_cache(payload.ownerUserId)
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
        self._invalidate_card_list_cache(payload.ownerUserId)
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
        self._invalidate_card_list_cache(user_id)
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
        self._invalidate_card_list_cache(user_id)
        return copy_card

    def record_view(
        self,
        card_id: str,
        payload: RecordViewRequest,
        authenticated_user_id: str | None = None,
    ) -> ViewEvent:
        card = self.repo.get_card(card_id)
        if not card:
            raise HTTPException(status_code=404, detail="卡片不存在")
        payload = self._normalize_public_view_payload(payload, card.ownerUserId, authenticated_user_id)
        is_share_event = self._clean_optional_text(payload.eventType) == "share"
        if not is_share_event and payload.viewerUserId and payload.viewerUserId == card.ownerUserId:
            now = now_iso()
            return ViewEvent(
                id=new_id("view_ignored"),
                cardId=card_id,
                viewerUserId=payload.viewerUserId,
                viewType="logged_in",
                anonymousId=payload.anonymousId,
                visitorIdentityId=self._stable_visitor_identity_id(card.ownerUserId, payload.viewerUserId, payload.anonymousId, "ignored"),
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
        event_id = self._existing_view_session_event_id(card_id, payload) or new_id("view")
        event = ViewEvent(
            id=event_id,
            cardId=card_id,
            viewerUserId=payload.viewerUserId,
            viewType="share" if is_share_event else "logged_in" if payload.viewerUserId else "anonymous",
            anonymousId=payload.anonymousId,
            visitorIdentityId=self._stable_visitor_identity_id(card.ownerUserId, payload.viewerUserId, payload.anonymousId, event_id),
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
        self._invalidate_card_list_cache(card.ownerUserId)
        self._invalidate_customer_intelligence_cache(card.ownerUserId)
        return event

    def record_note_view(
        self,
        note_id: str,
        payload: RecordViewRequest,
        authenticated_user_id: str | None = None,
    ) -> ViewEvent:
        note = self._require_published_note(note_id)
        event_card_id = note.sourceCardId or note.id
        payload = self._normalize_public_view_payload(payload, note.ownerUserId, authenticated_user_id)
        is_share_event = self._clean_optional_text(payload.eventType) == "share"
        if not is_share_event and payload.viewerUserId and payload.viewerUserId == note.ownerUserId:
            now = now_iso()
            return ViewEvent(
                id=new_id("view_ignored"),
                cardId=event_card_id,
                viewerUserId=payload.viewerUserId,
                viewType="logged_in",
                anonymousId=payload.anonymousId,
                visitorIdentityId=self._stable_visitor_identity_id(note.ownerUserId, payload.viewerUserId, payload.anonymousId, "ignored"),
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
        event_id = self._existing_view_session_event_id(event_card_id, payload) or new_id("view")
        event = ViewEvent(
            id=event_id,
            cardId=event_card_id,
            viewerUserId=payload.viewerUserId,
            viewType="share" if is_share_event else "logged_in" if payload.viewerUserId else "anonymous",
            anonymousId=payload.anonymousId,
            visitorIdentityId=self._stable_visitor_identity_id(note.ownerUserId, payload.viewerUserId, payload.anonymousId, event_id),
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
        self._invalidate_card_list_cache(note.ownerUserId)
        self._invalidate_customer_intelligence_cache(note.ownerUserId)
        return event

    def record_note_interaction(self, note_id: str, payload: NoteInteractionEventRequest) -> dict:
        note = self._require_published_note(note_id)
        event_type = str(payload.eventType or "").strip().lower()
        if event_type not in NOTE_INTERACTION_TYPES:
            raise HTTPException(status_code=400, detail="不支持的资料互动事件")
        if payload.viewerUserId and payload.viewerUserId == note.ownerUserId:
            return {"recorded": False, "ignoredReason": "owner_preview"}
        attachment = None
        if payload.attachmentId:
            public_media = self._normalize_note_media(note.media, public_only=True)
            attachment = next((item for item in public_media if item.get("id") == payload.attachmentId), None)
            if not attachment:
                raise HTTPException(status_code=400, detail="附件不属于当前资料")
            expected = {"image_open": "image", "pdf_open": "pdf", "link_open": "link"}.get(event_type)
            if expected and attachment.get("type") != expected:
                raise HTTPException(status_code=400, detail="附件类型与事件不匹配")
        elif event_type in {"image_open", "pdf_open", "link_open"}:
            raise HTTPException(status_code=400, detail="附件事件必须提供附件ID")
        session_id = self._clean_optional_text(payload.sessionId)
        interaction_ref = payload.attachmentId or self._clean_optional_text((payload.metadata or {}).get("featuredNoteId")) or "-"
        dedupe_key = f"interaction:{event_type}:{interaction_ref}:{session_id or '-'}"
        if session_id:
            existing = self.repo.list_customer_actions_for_note(note.id)
            if any((item.projectionRefs or {}).get("dedupeKey") == dedupe_key for item in existing):
                return {"recorded": False, "duplicate": True}
        now = now_iso()
        action_key = event_type.replace("_", "-")
        labels = {
            "image_open": "查看图片", "pdf_open": "打开PDF", "link_open": "点击链接", "source_open": "查看原文",
            "contact_click": "点击咨询", "phone_click": "点击拨号", "wechat_qr_open": "查看二维码", "featured_note_open": "打开精选资料", "map_open": "打开地图",
        }
        action = CustomerAction(
            id=new_id("customer_action"),
            ownerUserId=note.ownerUserId,
            noteId=note.id,
            sourceCardId=note.sourceCardId,
            viewerUserId=payload.viewerUserId,
            anonymousId=payload.anonymousId,
            actionKey=action_key,
            actionLabel=labels[event_type],
            payload={
                "attachmentId": payload.attachmentId,
                "shareId": payload.shareId,
                "shareFromUserId": payload.shareFromUserId,
                "scene": payload.scene,
                "metadata": payload.metadata,
            },
            projectionRefs={"dedupeKey": dedupe_key} if session_id else {},
            createdAt=now,
            updatedAt=now,
        )
        self.repo.save_customer_action(action)
        self._invalidate_card_list_cache(note.ownerUserId)
        if event_type in CUSTOMER_INTELLIGENCE_NOTE_EVENTS:
            self._invalidate_customer_intelligence_cache(note.ownerUserId)
        return {"recorded": True, "event": action.model_dump(), "attachment": attachment}

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
        if not reminder_status:
            reminders = [item for item in reminders if item.status != "deleted"]
        return [self._build_lead_reminder_row(item) for item in reminders]

    def get_lead_reminder_detail(self, reminder_id: str, owner_user_id: str) -> dict:
        reminder = self.repo.get_lead_reminder(reminder_id)
        if not reminder:
            raise HTTPException(status_code=404, detail="线索不存在")
        if reminder.ownerUserId != owner_user_id:
            raise HTTPException(status_code=403, detail="仅发布者可查看线索")
        return self._build_lead_reminder_row(reminder)

    def _compact_followup_profile(
        self,
        owner_user_id: str,
        customer_id: str,
        mode: str | None,
        profile_hint: dict | None,
    ) -> tuple[dict, UserNote] | None:
        """Resolve a first-time radar visitor from its compact card projection.

        The radar card already names the owner-scoped identity and source note.
        Reusing those two facts avoids the much more expensive full dashboard
        build that the legacy no-lead path used for every first action.
        """
        hint = profile_hint if isinstance(profile_hint, dict) else {}
        source_note_id = self._clean_optional_text(hint.get("sourceNoteId"))
        visitor_identity_id = self._clean_optional_text(
            hint.get("visitorIdentityId") or customer_id
        )
        if not source_note_id or not visitor_identity_id:
            return None
        note = self.repo.get_user_note(source_note_id)
        if not note or note.ownerUserId != owner_user_id or note.status == "deleted":
            return None
        if mode == "property" and not self._is_property_note(note):
            return None
        if mode == "groupbuy" and not self._is_groupbuy_note(note):
            return None
        if mode == "service" and not self._is_service_note(note):
            return None

        viewer_user_id = self._clean_optional_text(hint.get("viewerUserId")) or ""
        anonymous_id = self._clean_optional_text(hint.get("anonymousId")) or ""
        viewer_contacts = self._viewer_contact_fields(viewer_user_id)
        display_name = self._clean_optional_text(hint.get("nickname")) or (
            "微信客户" if viewer_user_id else "匿名访客"
        )
        last_activity_at = self._clean_optional_text(hint.get("lastActivityAt")) or now_iso()
        return (
            {
                "id": visitor_identity_id,
                "visitorIdentityId": visitor_identity_id,
                "viewerUserId": viewer_user_id,
                "anonymousId": anonymous_id,
                "anonymous": not bool(viewer_user_id),
                "nickname": display_name,
                "avatarUrl": self._clean_optional_text(hint.get("avatarUrl")) or "",
                "phone": viewer_contacts["phone"],
                "wechat": viewer_contacts["wechat"],
                "email": viewer_contacts["email"],
                "budgetText": "",
                "customerTags": [],
                "viewCount": max(0, int(hint.get("viewCount") or 0)),
                "lastActivityAt": last_activity_at,
                "noteIds": [note.id],
                "noteTitles": [note.title] if note.title else [],
                "intentLevel": None,
            },
            note,
        )

    def ensure_customer_followup(
        self,
        owner_user_id: str,
        requester_user_id: str,
        customer_id: str,
        mode: str | None = None,
        lead_id: str | None = None,
        initial_status: str = "pending",
        initial_conclusion_reason: str | None = None,
        initial_log_content: str | None = None,
        operation_id: str | None = None,
        profile_hint: dict | None = None,
        initial_tags: list[str] | None = None,
        initial_next_follow_up_at: str | None = None,
        initial_note: str | None = None,
    ) -> dict:
        """Create or reuse one owner-scoped follow-up record for a customer."""
        if initial_status not in LEAD_REMINDER_STATUSES:
            raise HTTPException(status_code=400, detail="线索状态无效")
        if requester_user_id != owner_user_id:
            raise HTTPException(status_code=403, detail="仅工作台拥有者可建立跟进档案")
        self.require_customer_intelligence(owner_user_id)
        normalized_initial_tags = (
            None
            if initial_tags is None
            else list(dict.fromkeys(
                self._clean_optional_text(item)
                for item in initial_tags
                if self._clean_optional_text(item)
            ))
        )
        normalized_initial_next_follow_up_at = self._clean_optional_text(initial_next_follow_up_at)
        normalized_initial_note = self._clean_optional_text(initial_note)
        compact = self._compact_followup_profile(owner_user_id, customer_id, mode, profile_hint)
        note = None
        detail = None
        if compact:
            profile, note = compact
        else:
            detail = self.get_customer_detail(
                owner_user_id,
                requester_user_id,
                customer_id,
                mode,
                lead_id,
            )
            if detail.get("locked") is not False:
                raise HTTPException(status_code=403, detail="当前账号不能建立跟进档案")
            profile = detail.get("customer") or {}
        visitor_identity_id = self._clean_optional_text(
            profile.get("visitorIdentityId") or customer_id
        )
        viewer_user_id = self._clean_optional_text(profile.get("viewerUserId"))
        anonymous_id = self._clean_optional_text(profile.get("anonymousId"))
        viewer_key = viewer_user_id or anonymous_id or visitor_identity_id
        stable_lead_id = "lead_customer_" + hashlib.sha256(
            f"{owner_user_id}|{visitor_identity_id or viewer_key}".encode("utf-8")
        ).hexdigest()[:32]
        identity_values = {
            value
            for value in (visitor_identity_id, viewer_user_id, anonymous_id, viewer_key)
            if value
        }

        existing_by_id = self.repo.get_lead_reminder(stable_lead_id)
        existing = next(
            (
                item
                for item in self.repo.list_lead_reminders(owner_user_id)
                if item.status != "deleted"
                if identity_values.intersection(
                    {
                        value
                        for value in (item.visitorIdentityId, item.viewerUserId)
                        if value
                    }
                )
            ),
            None,
        )
        if not existing and existing_by_id and existing_by_id.ownerUserId == owner_user_id and existing_by_id.status != "deleted":
            existing = existing_by_id
        if not existing and detail and detail.get("lead"):
            detail_lead_id = str((detail.get("lead") or {}).get("id") or "").strip()
            existing = self.repo.get_lead_reminder(detail_lead_id) if detail_lead_id else None
            if existing and existing.status == "deleted":
                existing = None
        if existing:
            return {"created": False, "lead": self._build_lead_reminder_row(existing)}

        if not note:
            for raw_note_id in profile.get("noteIds") or []:
                candidate = self.repo.get_user_note(str(raw_note_id))
                if candidate and candidate.ownerUserId == owner_user_id and candidate.status != "deleted":
                    note = candidate
                    break
                candidate = self._find_note_by_lead_source(str(raw_note_id))
                if candidate and candidate.ownerUserId == owner_user_id and candidate.status != "deleted":
                    note = candidate
                    break
        if not note:
            raise HTTPException(status_code=409, detail="当前客户暂时没有可关联的来源资料")

        now = now_iso()
        lead = LeadReminder(
            id=stable_lead_id,
            ownerUserId=owner_user_id,
            # A compact radar action already resolved the concrete note. Keep
            # that note ID as the lead source so the response can be built with
            # one direct lookup instead of scanning every note for a card ID.
            cardId=note.id if compact else (note.sourceCardId or note.id),
            viewerUserId=viewer_key,
            visitorIdentityId=visitor_identity_id,
            nickname=self._clean_optional_text(profile.get("nickname")) or "客户",
            avatarUrl=self._clean_optional_text(profile.get("avatarUrl")) or None,
            status=initial_status,
            note=(
                normalized_initial_note
                or (
                    "已开始跟进。"
                    if initial_status in {"following", "contacted"}
                    else "已放弃跟进。"
                    if initial_status == "paused"
                    else "来自客户雷达，等待首次联系。"
                )
            ),
            customerPhone=self._clean_optional_text(profile.get("phone")) or None,
            customerWechat=self._clean_optional_text(profile.get("wechat")) or None,
            customerEmail=self._clean_optional_text(profile.get("email")) or None,
            budgetText=self._clean_optional_text(profile.get("budgetText")) or None,
            intentLevel=self._clean_optional_text(profile.get("intentLevel")) or None,
            customerTags=(
                normalized_initial_tags
                if normalized_initial_tags is not None
                else list(profile.get("customerTags") or [])
            ),
            viewCount=max(0, int(profile.get("viewCount") or 0)),
            lastViewedAt=self._clean_optional_text(profile.get("lastActivityAt")) or None,
            contactedAt=now if initial_status == "contacted" else None,
            closedAt=now if initial_status in LEAD_CLOSED_STATUSES else None,
            conclusionReason=(
                initial_conclusion_reason
                if initial_status in LEAD_CLOSED_STATUSES
                else None
            ),
            nextFollowUpAt=normalized_initial_next_follow_up_at,
            followUpLogs=(
                [
                    LeadFollowUpLog(
                        id=new_id("log"),
                        content=(
                            normalized_initial_note
                            or initial_log_content
                            or "已记录跟进"
                        ),
                        createdAt=now,
                        action=(
                            "abandon"
                            if initial_status == "paused"
                            else "start"
                            if initial_status in {"following", "contacted"}
                            else "create"
                        ),
                        actionLabel=initial_log_content,
                        tags=(
                            normalized_initial_tags
                            if normalized_initial_tags is not None
                            else list(profile.get("customerTags") or [])
                        ),
                        note=normalized_initial_note,
                        nextFollowUpAt=normalized_initial_next_follow_up_at,
                    )
                ]
                if initial_log_content or normalized_initial_note or normalized_initial_tags is not None or initial_next_follow_up_at is not None
                else []
            ),
            version=1,
            lastOperationId=self._clean_optional_text(operation_id) or None,
            createdAt=now,
            updatedAt=now,
        )
        self.repo.save_lead_reminder(lead)
        self._invalidate_customer_intelligence_cache(owner_user_id)
        return {"created": True, "lead": self._build_lead_reminder_row(lead)}

    def act_on_customer_followup(
        self,
        owner_user_id: str,
        requester_user_id: str,
        customer_id: str,
        action: str,
        mode: str | None = None,
        lead_id: str | None = None,
        operation_id: str | None = None,
        expected_version: int | None = None,
        profile_hint: dict | None = None,
        follow_up_tags: list[str] | None = None,
        log_content: str | None = None,
        next_follow_up_at: str | None = None,
    ) -> dict:
        """Atomically persist one radar action and return the committed row.

        The client may remove a card optimistically, but this method is the
        source of truth. A retry with the same operation ID is idempotent, and
        a stale expected version is rejected instead of silently overwriting a
        newer operator action.
        """
        action_key = str(action or "").strip().lower()
        action_config = {
            "start": {
                "status": "following",
                "logContent": "已开始跟进",
            },
            "continue": {
                "logContent": "已继续跟进",
            },
            "abandon": {
                "status": "paused",
                "conclusionReason": "放弃跟进",
                "logContent": "已放弃跟进",
            },
            "restore": {
                "status": "pending",
                "logContent": "已恢复跟进",
            },
        }.get(action_key)
        if not action_config:
            raise HTTPException(status_code=400, detail="客户跟进动作无效")

        if requester_user_id != owner_user_id:
            raise HTTPException(status_code=403, detail="仅工作台拥有者可操作跟进档案")
        operation_id = self._clean_optional_text(operation_id) or None
        requested_lead_id = str(lead_id or "").strip()
        normalized_tags = (
            None
            if follow_up_tags is None
            else list(dict.fromkeys(
                self._clean_optional_text(item)
                for item in follow_up_tags
                if self._clean_optional_text(item)
            ))
        )
        normalized_log_content = self._clean_optional_text(log_content)
        next_follow_up_at_provided = next_follow_up_at is not None
        normalized_next_follow_up_at = self._clean_optional_text(next_follow_up_at)
        with FOLLOWUP_ACTION_LOCK:
            target_status = action_config.get("status")
            ensured = None
            if requested_lead_id:
                # The detail page already has the owner-scoped lead ID. Avoid
                # rebuilding the complete intelligence projection for a hot
                # path action such as abandon/continue.
                self.require_customer_intelligence(owner_user_id)
                reminder = self.repo.get_lead_reminder(requested_lead_id)
                if not reminder:
                    raise HTTPException(status_code=404, detail="线索不存在")
                if reminder.ownerUserId != owner_user_id:
                    raise HTTPException(status_code=403, detail="仅发布者可操作线索")
                if customer_id:
                    lead_aliases = set()
                    for value in (reminder.id, reminder.viewerUserId, reminder.visitorIdentityId):
                        lead_aliases.update(self._customer_identity_aliases(value))
                    if not self._customer_identity_aliases(customer_id).intersection(lead_aliases):
                        raise HTTPException(status_code=404, detail="客户与跟进档案不匹配")
            else:
                # First-time visitors have no lead ID, so resolve the customer
                # once and create the target state directly instead of doing
                # an HTTP-level ensure followed by an update.
                ensured = self.ensure_customer_followup(
                    owner_user_id,
                    requester_user_id,
                    customer_id,
                    mode,
                    None,
                    initial_status=target_status or "following",
                    initial_conclusion_reason=action_config.get("conclusionReason"),
                    initial_log_content=action_config.get("logContent"),
                    operation_id=operation_id,
                    profile_hint=profile_hint,
                    initial_tags=normalized_tags,
                    initial_next_follow_up_at=normalized_next_follow_up_at,
                    initial_note=normalized_log_content,
                )
                reminder_id = str((ensured.get("lead") or {}).get("id") or "").strip()
                reminder = self.repo.get_lead_reminder(reminder_id) if reminder_id else None
                if not reminder:
                    raise HTTPException(status_code=409, detail="跟进档案不存在")

            if operation_id and reminder.lastOperationId == operation_id:
                persisted = self.repo.get_lead_reminder(reminder.id) or reminder
                return {
                    "action": action_key,
                    "actionLabel": action_config.get("logContent", ""),
                    "removedFromRadar": action_key != "restore",
                    "persisted": True,
                    "idempotent": True,
                    "operationId": operation_id,
                    "followupCounts": self._customer_followup_counts(owner_user_id),
                    "lead": self._build_lead_reminder_row(persisted),
                }

            current_version = int(reminder.version or 0)
            if expected_version is not None and current_version != int(expected_version):
                raise HTTPException(status_code=409, detail="跟进状态已更新，请刷新后重试")

            if action_key == "start":
                target_status = "following"
            elif action_key == "continue":
                target_status = reminder.status if reminder.status in {"following", "contacted"} else "following"

            created = bool(ensured and ensured.get("created"))
            next_reminder = reminder.model_copy(deep=True)
            if normalized_tags is not None:
                next_reminder.customerTags = normalized_tags
            if next_follow_up_at_provided:
                next_reminder.nextFollowUpAt = normalized_next_follow_up_at
            status_changed = next_reminder.status != target_status
            if status_changed:
                next_reminder.status = target_status
                next_reminder.closedAt = None
                next_reminder.conclusionReason = None
                if target_status != "contacted":
                    next_reminder.contactedAt = None
            if not created:
                now = now_iso()
                next_reminder.followUpLogs.insert(
                    0,
                    LeadFollowUpLog(
                        id=new_id("log"),
                        content=normalized_log_content or action_config["logContent"],
                        createdAt=now,
                        action=action_key,
                        actionLabel=action_config["logContent"],
                        tags=list(next_reminder.customerTags),
                        note=normalized_log_content,
                        nextFollowUpAt=next_reminder.nextFollowUpAt,
                    ),
                )
                if action_key == "abandon":
                    next_reminder.closedAt = now
                    next_reminder.conclusionReason = action_config.get("conclusionReason")
                next_reminder.updatedAt = now
            next_reminder.version = current_version + (0 if created else 1)
            if operation_id:
                next_reminder.lastOperationId = operation_id

            if not created:
                saved = self.repo.save_lead_reminder_if_version(next_reminder, current_version)
                if not saved:
                    latest = self.repo.get_lead_reminder(reminder.id)
                    if operation_id and latest and latest.lastOperationId == operation_id:
                        next_reminder = latest
                    else:
                        raise HTTPException(status_code=409, detail="跟进状态已被其他操作更新，请刷新后重试")
            persisted = self.repo.get_lead_reminder(next_reminder.id)
            if not persisted or persisted.status != next_reminder.status or int(persisted.version or 0) != int(next_reminder.version or 0):
                raise HTTPException(status_code=500, detail="跟进状态未确认写入，请重试")
            self._invalidate_customer_intelligence_cache(owner_user_id)
        return {
            "action": action_key,
            "actionLabel": action_config.get("logContent", ""),
            "removedFromRadar": action_key != "restore",
            "persisted": True,
            "idempotent": False,
            "operationId": operation_id,
            "followupCounts": self._customer_followup_counts(owner_user_id),
            "lead": self._build_lead_reminder_row(persisted),
        }

    def _build_lead_reminder_row(self, reminder: LeadReminder) -> dict:
        row = reminder.model_dump()
        card = self.repo.get_card(reminder.cardId)
        note = self._find_note_by_lead_source(reminder.cardId)
        row["cardTitle"] = card.title if card else note.title if note else "资源已删除"
        row["cardStatus"] = card.status if card else "active" if note and note.status != "deleted" else "archived"
        row["sourceNoteId"] = note.id if note else None
        return row

    def _customer_followup_counts(self, owner_user_id: str) -> dict[str, int]:
        """Return status counts without rebuilding the customer radar."""
        reminders = self.repo.list_lead_reminders(owner_user_id)
        return {
            "pending": sum(1 for item in reminders if item.status == "pending"),
            "following": sum(1 for item in reminders if item.status == "following"),
            "contacted": sum(1 for item in reminders if item.status == "contacted"),
            "abandoned": sum(1 for item in reminders if item.status == "paused"),
        }

    def _lead_status_text(self, status: str | None) -> str:
        status_map = {
            "pending": "待联系",
            "following": "跟进中",
            "contacted": "已联系",
            "invalid": "无效",
            "paused": "已放弃跟进",
            "completed": "已完成",
            "deleted": "已清空",
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
            visitorIdentityId=existing.visitorIdentityId if existing else self._stable_visitor_identity_id(payload.ownerUserId, payload.viewerUserId, None, payload.cardId),
            nickname=payload.nickname,
            avatarUrl=payload.avatarUrl,
            status=payload.status,
            note=payload.note,
            customerPhone=existing.customerPhone if existing else None,
            customerWechat=existing.customerWechat if existing else None,
            customerEmail=existing.customerEmail if existing else None,
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
            version=(int(existing.version or 0) + 1) if existing else 1,
            lastOperationId=None,
            createdAt=existing.createdAt if existing else now,
            updatedAt=now,
        )
        self.repo.save_lead_reminder(reminder)
        self._invalidate_customer_intelligence_cache(payload.ownerUserId)
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
        if payload.customerEmail is not None:
            reminder.customerEmail = payload.customerEmail
        if payload.budgetText is not None:
            reminder.budgetText = payload.budgetText
        if payload.intentLevel is not None:
            reminder.intentLevel = payload.intentLevel
        payload_fields = getattr(payload, "model_fields_set", set())
        follow_up_tags_provided = "followUpTags" in payload_fields or payload.followUpTags is not None
        legacy_customer_tags_provided = "customerTags" in payload_fields or payload.customerTags is not None
        follow_up_tags = None
        if follow_up_tags_provided:
            follow_up_tags = [tag.strip() for tag in (payload.followUpTags or []) if tag.strip()]
            reminder.customerTags = follow_up_tags
        elif legacy_customer_tags_provided:
            follow_up_tags = [tag.strip() for tag in (payload.customerTags or []) if tag.strip()]
            reminder.customerTags = follow_up_tags
        if payload.conclusionReason is not None and reminder.status in LEAD_CLOSED_STATUSES:
            reminder.conclusionReason = payload.conclusionReason
        next_follow_up_provided = "nextFollowUpAt" in payload_fields or payload.nextFollowUpAt is not None
        if payload.nextFollowUpAt is not None:
            reminder.nextFollowUpAt = payload.nextFollowUpAt.strip() or None
        log_content = (payload.logContent or "").strip()
        # A saved follow-up is one record, even when the operator only picks a
        # tag or a next date. This keeps the historical decision auditable and
        # prevents the old text-only log from losing the selected state.
        if log_content or follow_up_tags_provided or next_follow_up_provided:
            action = (payload.followUpAction or "record").strip() or "record"
            action_label = "跟进记录" if action == "record" else action
            content = log_content or action_label
            reminder.followUpLogs.insert(
                0,
                LeadFollowUpLog(
                    id=new_id("log"),
                    content=content,
                    createdAt=now,
                    action=action,
                    actionLabel=action_label,
                    tags=list(follow_up_tags if follow_up_tags is not None else reminder.customerTags),
                    note=log_content or None,
                    nextFollowUpAt=reminder.nextFollowUpAt,
                ),
            )
        reminder.version = int(reminder.version or 0) + 1
        reminder.lastOperationId = None
        reminder.updatedAt = now
        self.repo.save_lead_reminder(reminder)
        self._invalidate_customer_intelligence_cache(reminder.ownerUserId)
        return reminder

    def delete_lead_reminder(self, reminder_id: str, owner_user_id: str) -> dict:
        reminder = self.repo.get_lead_reminder(reminder_id)
        if not reminder:
            raise HTTPException(status_code=404, detail="线索不存在")
        if reminder.ownerUserId != owner_user_id:
            raise HTTPException(status_code=403, detail="仅发布者可管理线索")
        # Keep a tombstone so the same visitor identity cannot be recreated
        # from historical view events after the owner clears the recycle bin.
        reminder.status = "deleted"
        reminder.closedAt = now_iso()
        reminder.conclusionReason = "已清空删除"
        reminder.version = int(reminder.version or 0) + 1
        reminder.lastOperationId = None
        reminder.updatedAt = reminder.closedAt
        self.repo.save_lead_reminder(reminder)
        self._invalidate_customer_intelligence_cache(owner_user_id)
        return {"deletedLeadReminderId": reminder_id}

    def _build_card_stats(self, card_id: str) -> dict:
        events = self.repo.list_view_events_for_card(card_id)
        relays = self.repo.list_relay_entries_for_card(card_id, relay_status="active")
        stats = self._build_stats_from_events(card_id, events, relays)
        stats["trend"] = self._build_card_view_trend(events)
        return stats

    def _build_card_view_trend(self, events: list[ViewEvent]) -> dict:
        """Return the small, owner-safe trend dataset used by resource operations."""
        today = datetime.now(tz=SHANGHAI).date()
        days = [today - timedelta(days=offset) for offset in range(6, -1, -1)]
        day_counts = {day.isoformat(): 0 for day in days}
        today_counts = [0] * 6
        for event in events:
            if event.viewType == "share" or not event.viewedAt:
                continue
            viewed_at = parse_iso(event.viewedAt).astimezone(SHANGHAI)
            day_key = viewed_at.date().isoformat()
            if day_key in day_counts:
                day_counts[day_key] += 1
            if viewed_at.date() == today:
                today_counts[min(viewed_at.hour // 4, 5)] += 1
        return {
            "last7": [
                {"label": day.strftime("%m-%d"), "value": day_counts[day.isoformat()]}
                for day in days
            ],
            "today": [
                {"label": f"{hour:02d}:00", "value": today_counts[index]}
                for index, hour in enumerate((0, 4, 8, 12, 16, 20))
            ],
        }

    def _build_note_stats(self, note: UserNote) -> dict:
        stats_id = note.sourceCardId or note.id
        events = self.repo.list_view_events_for_card(stats_id)
        relays = self.repo.list_relay_entries_for_card(stats_id, relay_status="active")
        return self._build_stats_from_events(stats_id, events, relays)

    def _build_note_customer_summary(
        self,
        note: UserNote | None,
        *,
        actions_by_note: dict[str, list[CustomerAction]] | None = None,
        leads_by_owner: dict[str, list[LeadReminder]] | None = None,
    ) -> dict:
        if not note:
            return {}
        actions = (
            actions_by_note.get(note.id, [])
            if actions_by_note is not None
            else self.repo.list_customer_actions_for_note(note.id)
        )
        projected_lead_ids = {
            str((action.projectionRefs or {}).get("leadReminderId") or "")
            for action in actions
            if (action.projectionRefs or {}).get("leadReminderId")
        }
        owner_leads = (
            leads_by_owner.get(note.ownerUserId, [])
            if leads_by_owner is not None
            else self.repo.list_lead_reminders(note.ownerUserId)
        )
        leads = [item for item in owner_leads if item.id in projected_lead_ids]
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
