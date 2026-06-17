from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from uuid import uuid4
from fastapi import HTTPException, status

from app.models.domain import AppState, Card, CardMedia, Category, ImportBatch, LeadFollowUpLog, LeadReminder, MediaRetryJob, RawMessage, RelayConfig, RelayEntry, SkillRun, SyncCursor, User, UserNote, ViewEvent, WecomArchiveCursor, WecomArchiveMessage
from app.schemas.auth import MockLoginRequest
from app.schemas.categories import CategoryCreateRequest
from app.schemas.cards import CardCreateRequest, CardUpdateRequest, CreateRelayRequest, LeadReminderUpdateRequest, LeadReminderUpsertRequest, RecordViewRequest
from app.schemas.notes import UserNoteUpdateRequest
from app.schemas.skills import ContentObjectPayload
from app.services.card_parser_service import CardParserService
from app.services.content_object_adapter import ContentObjectAdapter
from app.services.helpers import mask_nickname, new_id
from app.services.import_notification_service import ImportNotificationService
from app.services.media_storage_service import MediaStorageService
from app.services.media_processing_service import MediaProcessingService
from app.services.message_aggregator import MessageAggregator
from app.services.repository import AppRepository
from app.services.skill_router_service import SkillRouterService
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
        skill_router_service: SkillRouterService | None = None,
        content_object_adapter: ContentObjectAdapter | None = None,
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
            note_result = self.skill_router_service.run_content_to_note("unclaimed", content_object)
            card = self._build_card_from_note_draft(batch, note_result.noteDraft, content_object)
            note = self._build_user_note_from_draft(batch, note_result.noteDraft, card.id)
            batch.generatedCardId = card.id
            batch.generatedNoteId = note.id
            batch.status = "success" if card.title else "failed"
            batch.errorMessage = None if card.title else "未能解析标题"
            batch.updatedAt = now_iso()
            skill_run = SkillRun.model_validate(note_result.skillRun.model_dump())
            skill_run.outputRef = note.id if batch.status == "success" else batch.id
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

    def process_wecom_archive_messages(self, limit: int = 100) -> dict:
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
                note_result = self.skill_router_service.run_content_to_note("unclaimed", content_object)
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
                }
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
            sourceType="wecom_thread",
            title=next((item.title for item in objects if item.title), None),
            textBlocks=[block for item in objects for block in item.textBlocks],
            media=[media for item in objects for media in item.media],
            links=[link for item in objects for link in item.links],
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
        return ImportBatch(
            id=new_id("import"),
            externalUserId=message.fromUser or "archive_unknown",
            conversationId=message.roomId or ",".join(message.toList) or message.msgId or message.id,
            status="success",
            titleCandidate=title or f"企业微信{message.msgType or '消息'}归档",
            sourceType="wechat_note",
            rawMessageIds=[item.id for item in group_messages],
            startedAt=message.msgTime or now,
            endedAt=now,
            createdAt=now,
            updatedAt=now,
        )

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
        self.repo.save_import_batch(batch)
        self.repo.save_card(card)
        return {"importBatch": batch, "card": card, "note": self.repo.get_user_note(batch.generatedNoteId) if batch.generatedNoteId else None}

    def list_user_notes(
        self,
        owner_user_id: str,
        keyword: str | None = None,
        category_id: str | None = None,
        include_deleted: bool = False,
    ) -> list[dict]:
        if not self.repo.get_user(owner_user_id):
            raise HTTPException(status_code=404, detail="用户不存在")
        return [
            item.model_dump()
            for item in self.repo.list_user_notes(
                owner_user_id=owner_user_id,
                keyword=keyword,
                category_id=category_id,
                include_deleted=include_deleted,
            )
        ]

    def get_user_note(self, note_id: str, owner_user_id: str) -> UserNote:
        note = self.repo.get_user_note(note_id)
        if not note or note.status == "deleted":
            raise HTTPException(status_code=404, detail="笔记不存在")
        if note.ownerUserId != owner_user_id:
            raise HTTPException(status_code=403, detail="仅笔记拥有者可查看")
        return note

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
        note.visibilityConfig = payload.visibilityConfig
        note.updatedAt = now_iso()
        self.repo.save_user_note(note)
        return note

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

    def get_lead_reminder_detail(self, reminder_id: str, owner_user_id: str) -> dict:
        reminder = self.repo.get_lead_reminder(reminder_id)
        if not reminder:
            raise HTTPException(status_code=404, detail="线索不存在")
        if reminder.ownerUserId != owner_user_id:
            raise HTTPException(status_code=403, detail="仅发布者可查看线索")
        row = reminder.model_dump()
        card = self.repo.get_card(reminder.cardId)
        row["cardTitle"] = card.title if card else "资源已删除"
        row["cardStatus"] = card.status if card else "archived"
        return row

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
