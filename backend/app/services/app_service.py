from __future__ import annotations

from collections import defaultdict
from copy import deepcopy

from fastapi import HTTPException, status

from app.models.domain import AppState, Card, ImportBatch, RawMessage, RelayEntry, User, ViewEvent
from app.schemas.auth import MockLoginRequest
from app.schemas.cards import CardUpdateRequest, CreateRelayRequest, RecordViewRequest
from app.services.card_parser_service import CardParserService
from app.services.helpers import mask_nickname, new_id
from app.services.media_storage_service import MediaStorageService
from app.services.message_aggregator import MessageAggregator
from app.services.repository import JsonRepository
from app.services.time_utils import date_key, now_iso
from app.services.wecom_mock_service import WecomMockService


class AppService:
    def __init__(
        self,
        repo: JsonRepository,
        wecom_mock_service: WecomMockService,
        media_storage_service: MediaStorageService,
        parser_service: CardParserService,
        aggregator: MessageAggregator,
    ):
        self.repo = repo
        self.wecom_mock_service = wecom_mock_service
        self.media_storage_service = media_storage_service
        self.parser_service = parser_service
        self.aggregator = aggregator

    def _load(self) -> AppState:
        return self.repo.load()

    def _save(self, state: AppState) -> None:
        self.repo.save(state)

    def list_pending_imports(self) -> list[dict]:
        state = self._load()
        pending = [item for item in state.import_batches if item.status in {"pending", "success"}]
        cards = {item.id: item for item in state.cards}
        result = []
        for batch in pending:
            result.append(
                {
                    **batch.model_dump(),
                    "generatedCard": cards.get(batch.generatedCardId).model_dump() if batch.generatedCardId and cards.get(batch.generatedCardId) else None,
                }
            )
        return result

    def mock_login(self, payload: MockLoginRequest) -> User:
        state = self._load()
        now = now_iso()
        openid = payload.openid or f"openid_{payload.nickname}"
        existing = next((item for item in state.users if item.openid == openid), None)
        if existing:
            existing.nickname = payload.nickname
            existing.avatarUrl = payload.avatarUrl
            existing.phone = payload.phone
            existing.updatedAt = now
            self._save(state)
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
        state.users.append(user)
        self._save(state)
        return user

    def trigger_mock_import(self, external_user_id: str, conversation_id: str, fixture: str) -> dict:
        state = self._load()
        raw_messages: list[RawMessage] = []
        for item in self.wecom_mock_service.sync_messages(external_user_id, conversation_id, fixture):
            local_media_url = None
            media_id = item.get("mediaId")
            if media_id:
                local_media_url = self.media_storage_service.download_and_store(media_id)
            raw_message = RawMessage(
                id=new_id("msg"),
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
            state.import_batches.append(batch)
            state.raw_messages.extend(batch_messages)
            state.cards.append(card)

        self._save(state)
        return {
            "message": f"《{new_batches[0].titleCandidate}》导入成功",
            "importBatchIds": [item.id for item in new_batches],
        }

    def claim_import(self, import_id: str, user_id: str) -> dict:
        state = self._load()
        batch = next((item for item in state.import_batches if item.id == import_id), None)
        if not batch:
            raise HTTPException(status_code=404, detail="导入批次不存在")
        user = next((item for item in state.users if item.id == user_id), None)
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")
        if batch.generatedCardId is None:
            raise HTTPException(status_code=400, detail="该导入没有可认领卡片")
        card = next((item for item in state.cards if item.id == batch.generatedCardId), None)
        if not card:
            raise HTTPException(status_code=404, detail="草稿卡片不存在")

        now = now_iso()
        batch.claimedByUserId = user_id
        batch.status = "claimed"
        batch.updatedAt = now
        card.ownerUserId = user_id
        card.updatedAt = now
        self._save(state)
        return {"importBatch": batch, "card": card}

    def list_cards(self, owner_user_id: str | None = None, keyword: str | None = None, category_id: str | None = None) -> list[dict]:
        state = self._load()
        cards = state.cards
        if owner_user_id:
            cards = [item for item in cards if item.ownerUserId == owner_user_id]
        if keyword:
            cards = [item for item in cards if keyword.lower() in item.title.lower()]
        if category_id:
            cards = [item for item in cards if category_id in item.categoryIds]

        stats = self._build_stats_map(state)
        return [
            {
                **item.model_dump(),
                "stats": stats[item.id],
            }
            for item in cards
        ]

    def get_card(self, card_id: str) -> Card:
        state = self._load()
        card = next((item for item in state.cards if item.id == card_id), None)
        if not card:
            raise HTTPException(status_code=404, detail="卡片不存在")
        return card

    def update_card(self, card_id: str, payload: CardUpdateRequest) -> Card:
        state = self._load()
        card = next((item for item in state.cards if item.id == card_id), None)
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
        self._save(state)
        return card

    def publish_card(self, card_id: str, user_id: str) -> Card:
        state = self._load()
        card = next((item for item in state.cards if item.id == card_id), None)
        if not card:
            raise HTTPException(status_code=404, detail="卡片不存在")
        if card.ownerUserId != user_id:
            raise HTTPException(status_code=403, detail="仅卡片拥有者可发布")
        now = now_iso()
        card.status = "published"
        card.publishedAt = now
        card.updatedAt = now
        self._save(state)
        return card

    def duplicate_card(self, card_id: str, user_id: str) -> Card:
        state = self._load()
        source = next((item for item in state.cards if item.id == card_id), None)
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
        state.cards.append(copy_card)
        self._save(state)
        return copy_card

    def record_view(self, card_id: str, payload: RecordViewRequest) -> ViewEvent:
        state = self._load()
        card = next((item for item in state.cards if item.id == card_id), None)
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
        state.view_events.append(event)
        self._save(state)
        return event

    def get_card_stats(self, card_id: str, requester_user_id: str | None = None) -> dict:
        state = self._load()
        card = next((item for item in state.cards if item.id == card_id), None)
        if not card:
            raise HTTPException(status_code=404, detail="卡片不存在")

        stats = self._build_stats_map(state)[card_id]
        relay_entries = [item for item in state.relay_entries if item.cardId == card_id and item.status == "active"]
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
        state = self._load()
        card = next((item for item in state.cards if item.id == card_id), None)
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
        state.relay_entries.append(relay)
        self._save(state)
        return relay

    def list_relays(self, card_id: str, requester_user_id: str) -> list[dict]:
        state = self._load()
        card = next((item for item in state.cards if item.id == card_id), None)
        if not card:
            raise HTTPException(status_code=404, detail="卡片不存在")
        is_owner = requester_user_id == card.ownerUserId
        rows = []
        for item in state.relay_entries:
            if item.cardId != card_id or item.status != "active":
                continue
            payload = item.model_dump()
            if not is_owner:
                payload["nickname"] = item.maskedNickname
                payload["phone"] = None
                payload["address"] = None
            rows.append(payload)
        return rows

    def delete_relay(self, relay_id: str, operator_user_id: str) -> RelayEntry:
        state = self._load()
        relay = next((item for item in state.relay_entries if item.id == relay_id), None)
        if not relay:
            raise HTTPException(status_code=404, detail="接龙记录不存在")
        card = next((item for item in state.cards if item.id == relay.cardId), None)
        if not card or card.ownerUserId != operator_user_id:
            raise HTTPException(status_code=403, detail="仅团长可删除接龙")
        relay.status = "deleted"
        relay.updatedAt = now_iso()
        self._save(state)
        return relay

    def mark_followed(self, relay_id: str, operator_user_id: str) -> RelayEntry:
        state = self._load()
        relay = next((item for item in state.relay_entries if item.id == relay_id), None)
        if not relay:
            raise HTTPException(status_code=404, detail="接龙记录不存在")
        card = next((item for item in state.cards if item.id == relay.cardId), None)
        if not card or card.ownerUserId != operator_user_id:
            raise HTTPException(status_code=403, detail="仅团长可标记跟进")
        relay.followUpStatus = "followed"
        relay.updatedAt = now_iso()
        self._save(state)
        return relay

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

