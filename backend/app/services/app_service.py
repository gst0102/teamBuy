from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from uuid import uuid4
from fastapi import HTTPException, status

from app.models.domain import AppState, Card, MediaRetryJob, RawMessage, RelayEntry, SyncCursor, User, ViewEvent
from app.schemas.auth import MockLoginRequest
from app.schemas.cards import CardUpdateRequest, CreateRelayRequest, RecordViewRequest
from app.services.card_parser_service import CardParserService
from app.services.helpers import mask_nickname, new_id
from app.services.import_notification_service import ImportNotificationService
from app.services.media_storage_service import MediaStorageService
from app.services.message_aggregator import MessageAggregator
from app.services.repository import AppRepository
from app.services.time_utils import SHANGHAI, date_key, now_iso, parse_iso
from app.services.wecom_message_normalizer import WecomMessageNormalizer
from app.services.wecom_mock_service import WecomMockService


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
    ):
        self.repo = repo
        self.wecom_mock_service = wecom_mock_service
        self.media_storage_service = media_storage_service
        self.parser_service = parser_service
        self.aggregator = aggregator
        self.notification_service = notification_service
        self.normalizer = normalizer

    def _load(self) -> AppState:
        return self.repo.load()

    def _save(self, state: AppState) -> None:
        self.repo.save(state)

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

    def get_card(self, card_id: str) -> Card:
        card = self.repo.get_card(card_id)
        if not card:
            raise HTTPException(status_code=404, detail="卡片不存在")
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
                card.relayConfig = card.relayConfig.model_copy(update=value.model_dump())
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
        relay_payload = []
        for item in relay_entries:
            row = item.model_dump()
            if not is_owner:
                row["nickname"] = item.maskedNickname
                row["phone"] = None
                row["address"] = None
            relay_payload.append(row)
        return {
            **stats,
            "relayEntries": relay_payload,
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
        unique_logged = defaultdict(set)
        unique_anonymous = defaultdict(set)
        for event in state.view_events:
            row = stats[event.cardId]
            row["pv"] += 1
            if event.viewType == "logged_in":
                key = event.viewerUserId or event.id
                if key not in unique_logged[event.cardId]:
                    unique_logged[event.cardId].add(key)
                    row["loggedInViewers"].append(
                        {
                            "userId": event.viewerUserId,
                            "nickname": event.nickname,
                            "avatarUrl": event.avatarUrl,
                            "viewedAt": event.viewedAt,
                        }
                    )
            else:
                row["anonymousPv"] += 1
                key = event.anonymousId or event.id
                unique_anonymous[event.cardId].add(key)

        for card_id, row in stats.items():
            row["uv"] = len(unique_logged[card_id]) + len(unique_anonymous[card_id])
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
        unique_logged = set()
        unique_anonymous = set()
        for event in events:
            row["pv"] += 1
            if event.viewType == "logged_in":
                key = event.viewerUserId or event.id
                if key not in unique_logged:
                    unique_logged.add(key)
                    row["loggedInViewers"].append(
                        {
                            "userId": event.viewerUserId,
                            "nickname": event.nickname,
                            "avatarUrl": event.avatarUrl,
                            "viewedAt": event.viewedAt,
                        }
                    )
            else:
                row["anonymousPv"] += 1
                unique_anonymous.add(event.anonymousId or event.id)
        row["uv"] = len(unique_logged) + len(unique_anonymous)
        row["anonymousUv"] = len(unique_anonymous)
        return row
