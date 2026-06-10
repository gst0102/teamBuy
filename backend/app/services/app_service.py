from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from uuid import uuid4
from fastapi import HTTPException, status

from app.models.domain import AppState, Card, CardMedia, Category, LeadFollowUpLog, LeadReminder, MediaRetryJob, RawMessage, RelayConfig, RelayEntry, SyncCursor, User, ViewEvent
from app.schemas.auth import MockLoginRequest
from app.schemas.categories import CategoryCreateRequest
from app.schemas.cards import CardCreateRequest, CardUpdateRequest, CreateRelayRequest, LeadReminderUpdateRequest, LeadReminderUpsertRequest, RecordViewRequest
from app.services.card_parser_service import CardParserService
from app.services.helpers import mask_nickname, new_id
from app.services.import_notification_service import ImportNotificationService
from app.services.media_storage_service import MediaStorageService
from app.services.media_processing_service import MediaProcessingService
from app.services.message_aggregator import MessageAggregator
from app.services.repository import AppRepository
from app.services.time_utils import SHANGHAI, date_key, now_iso, parse_iso
from app.services.wecom_message_normalizer import WecomMessageNormalizer
from app.services.wecom_mock_service import WecomMockService


LEAD_REMINDER_STATUSES = {"pending", "contacted", "invalid", "paused", "completed"}
LEAD_CLOSED_STATUSES = {"invalid", "paused", "completed"}


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
    ):
        self.repo = repo
        self.wecom_mock_service = wecom_mock_service
        self.media_storage_service = media_storage_service
        self.media_processing_service = media_processing_service or MediaProcessingService()
        self.parser_service = parser_service
        self.aggregator = aggregator
        self.notification_service = notification_service
        self.normalizer = normalizer

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
            result.append(
                {
                    **batch.model_dump(),
                    "generatedCard": card.model_dump() if card else None,
                }
            )
        return result

    def mock_login(self, payload: MockLoginRequest) -> User:
        now = now_iso()
        openid = payload.openid or f"openid_{payload.nickname}"
        existing = self.repo.get_user_by_openid(openid)
        if existing:
            existing.nickname = payload.nickname
            existing.avatarUrl = payload.avatarUrl
            existing.phone = payload.phone
            existing.updatedAt = now
            self.repo.save_user(existing)
            return existing

        user = User(
            id=new_id("user"),
            openid=openid,
            nickname=payload.nickname,
            avatarUrl=payload.avatarUrl,
            phone=payload.phone,
            createdAt=now,
            updatedAt=now,
        )
        self.repo.save_user(user)
        return user

    def trigger_mock_import(self, external_user_id: str, conversation_id: str, fixture: str) -> dict:
        synced_messages = self.wecom_mock_service.sync_messages(external_user_id, conversation_id, fixture)
        return self.import_synced_messages(synced_messages)

    def normalize_sync_response(self, sync_response: dict, fallback_open_kfid: str | None = None) -> list[dict]:
        return self.normalizer.normalize_sync_response(sync_response, fallback_open_kfid=fallback_open_kfid)

    def trigger_sync_response_import(
        self,
        sync_response: dict,
        fallback_open_kfid: str | None = None,
        media_url_by_id: dict[str, str] | None = None,
    ) -> dict:
        synced_messages = self.normalizer.normalize_sync_response(sync_response, fallback_open_kfid=fallback_open_kfid)
        return self.import_synced_messages(synced_messages, media_url_by_id=media_url_by_id)

    def import_synced_messages(self, synced_messages: list[dict], media_url_by_id: dict[str, str] | None = None) -> dict:
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
                if not local_media_url:
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
            card = self.parser_service.build_card_draft(owner_user_id="unclaimed", batch=batch, messages=batch_messages)
            batch.generatedCardId = card.id
            batch.status = "success" if card.title else "failed"
            batch.errorMessage = None if card.title else "未能解析标题"
            batch.updatedAt = now_iso()
            notification = self.notification_service.build_notification(batch)
            self.repo.save_import_artifacts(batch, batch_messages, card, notification)

        return {
            "message": notification.message,
            "importBatchIds": [item.id for item in new_batches],
            "deduplicatedCount": len(existing_wecom_msg_ids),
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
        self.repo.save_import_batch(batch)
        self.repo.save_card(card)
        return {"importBatch": batch, "card": card}

    def list_cards(self, owner_user_id: str | None = None, keyword: str | None = None, category_id: str | None = None) -> list[dict]:
        cards = self.repo.list_cards(owner_user_id=owner_user_id, keyword=keyword, category_id=category_id)
        return [
            {
                **item.model_dump(),
                "stats": self._build_card_stats(item.id),
            }
            for item in cards
        ]

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
        rows = []
        for item in reminders:
            row = item.model_dump()
            card = self.repo.get_card(item.cardId)
            row["cardTitle"] = card.title if card else "资源已删除"
            row["cardStatus"] = card.status if card else "archived"
            rows.append(row)
        return rows

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
