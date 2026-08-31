from __future__ import annotations

import json
import os
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Protocol

import psycopg
from psycopg_pool import ConnectionPool
from psycopg.rows import dict_row, tuple_row

from app.core.database import normalize_database_url
from app.models.domain import (
    AppState,
    AutomationDevice,
    AutomationGroupCandidate,
    AutomationTask,
    Card,
    Category,
    CustomerRadarSummary,
    CustomerAction,
    ImportBatch,
    ImportNotification,
    LeadReminder,
    LiveQrCode,
    MessageRecord,
    MessageThread,
    MediaAsset,
    MediaAssetRef,
    MediaRetryJob,
    OpportunityLead,
    OpportunityLeadContact,
    OpportunityLeadFollowup,
    OpportunityLeadMatch,
    OpportunityLeadSave,
    OpportunityLeadSource,
    OpportunitySubscription,
    RawMessage,
    RelayEntry,
    ResourceFreeQuota,
    ResourcePointLedger,
    ResourceUnlockRecord,
    ResourceWallet,
    ResponsePackage,
    ResponsePackageEvent,
    ResponsePackageItem,
    OpportunityPushDigest,
    MembershipOrder,
    MembershipEntitlement,
    MutualPointAccount,
    MutualPointLedger,
    MutualRechargeOrder,
    MutualActivityEvent,
    ReferralRelation,
    ReferralReward,
    ReferralWithdrawal,
    SameStyleGeneration,
    SupplyDemandCard,
    SupplyDemandApplication,
    ShowcasePage,
    ShowcaseEvent,
    SkillRun,
    SyncCursor,
    SyncTask,
    SyncTaskLog,
    Topic,
    User,
    WecomBindCardToken,
    WecomBindCardAsset,
    WecomIdentityBinding,
    UserNote,
    ViewEvent,
    WecomArchiveCursor,
    WecomArchiveMessage,
    NotificationPreference,
    WechatSubscriptionGrant,
    WechatSubscriptionDelivery,
)
from app.services.text_safety import strip_unicode_surrogates
from app.services.time_utils import parse_iso


class AppRepository(Protocol):
    def load(self) -> AppState:
        ...

    def save(self, state: AppState) -> None:
        ...

    def get_user(self, user_id: str) -> User | None:
        ...

    def get_user_by_openid(self, openid: str) -> User | None:
        ...

    def save_user(self, user: User) -> None:
        ...

    def get_wecom_identity_binding(self, source_type: str, external_user_id: str) -> WecomIdentityBinding | None:
        ...

    def save_wecom_identity_binding(self, binding: WecomIdentityBinding) -> None:
        ...

    def get_wecom_bind_card_token(self, token_hash: str) -> WecomBindCardToken | None:
        ...

    def get_pending_wecom_bind_card_token(self, welcome_code_hash: str) -> WecomBindCardToken | None:
        ...

    def save_wecom_bind_card_token(self, token: WecomBindCardToken) -> None:
        ...

    def get_active_wecom_bind_card_asset(self) -> WecomBindCardAsset | None:
        ...

    def get_latest_wecom_bind_card_asset(self) -> WecomBindCardAsset | None:
        ...

    def save_wecom_bind_card_asset(self, asset: WecomBindCardAsset) -> None:
        ...

    def consume_wecom_bind_card_token(
        self,
        token_hash: str,
        owner_user_id: str,
        owner_openid: str,
        now: str,
    ) -> WecomBindCardToken | None:
        ...

    def list_import_batches(self, statuses: set[str] | None = None) -> list[ImportBatch]:
        ...

    def get_import_batch(self, import_id: str) -> ImportBatch | None:
        ...

    def save_import_batch(self, batch: ImportBatch) -> None:
        ...

    def list_user_notes(
        self,
        owner_user_id: str,
        keyword: str | None = None,
        category_id: str | None = None,
        include_deleted: bool = False,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[UserNote]:
        ...

    def list_user_notes_by_source_card_ids(
        self,
        owner_user_id: str,
        source_card_ids: set[str],
    ) -> list[UserNote]:
        ...

    def list_standalone_user_notes(
        self,
        owner_user_id: str,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[UserNote]:
        ...

    def list_all_user_notes(self, include_deleted: bool = False) -> list[UserNote]:
        ...

    def get_user_note(self, note_id: str) -> UserNote | None:
        ...

    def save_user_note(self, note: UserNote) -> None:
        ...

    def list_showcase_pages(self, owner_user_id: str) -> list[ShowcasePage]:
        ...

    def get_showcase_page(self, showcase_id: str) -> ShowcasePage | None:
        ...

    def save_showcase_page(self, showcase: ShowcasePage) -> None:
        ...

    def get_live_qr_code(self, qr_id: str) -> LiveQrCode | None:
        ...

    def get_live_qr_code_by_code(self, code: str) -> LiveQrCode | None:
        ...

    def list_live_qr_codes(self) -> list[LiveQrCode]:
        ...

    def save_live_qr_code(self, qr_code: LiveQrCode) -> None:
        ...

    def delete_live_qr_code(self, qr_id: str) -> bool:
        ...

    def record_live_qr_scan(self, code: str, scanned_at: str) -> LiveQrCode | None:
        ...

    def list_referral_relations(self) -> list[ReferralRelation]:
        ...

    def find_same_style_generation(
        self,
        owner_user_id: str,
        idempotency_key: str,
    ) -> SameStyleGeneration | None:
        ...

    def find_latest_same_style_generation(
        self,
        owner_user_id: str,
        mode: str,
        source_note_id: str | None = None,
        source_showcase_id: str | None = None,
    ) -> SameStyleGeneration | None:
        ...

    def list_same_style_generations(self, owner_user_id: str) -> list[SameStyleGeneration]:
        ...

    def save_same_style_generation(
        self,
        generation: SameStyleGeneration,
        referral_relation: ReferralRelation | None = None,
    ) -> None:
        ...

    def delete_showcase_page(self, showcase_id: str) -> None:
        ...

    def save_raw_messages(self, messages: list[RawMessage]) -> None:
        ...

    def list_raw_messages_for_batch(self, import_batch_id: str) -> list[RawMessage]:
        ...

    def existing_wecom_msg_ids(self, wecom_msg_ids: set[str]) -> set[str]:
        ...

    def save_import_artifacts(
        self,
        batch: ImportBatch,
        raw_messages: list[RawMessage],
        card: Card,
        notification: ImportNotification,
    ) -> None:
        ...

    def get_card(self, card_id: str) -> Card | None:
        ...

    def list_cards(
        self,
        owner_user_id: str | None = None,
        keyword: str | None = None,
        category_id: str | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[Card]:
        ...

    def save_card(self, card: Card) -> None:
        ...

    def delete_card(self, card_id: str) -> None:
        ...

    def list_categories(self, owner_user_id: str | None = None) -> list[Category]:
        ...

    def get_category(self, category_id: str) -> Category | None:
        ...

    def save_category(self, category: Category) -> None:
        ...

    def delete_category(self, category_id: str) -> None:
        ...

    def list_topics(self, owner_user_id: str) -> list[Topic]:
        ...

    def get_topic(self, topic_id: str) -> Topic | None:
        ...

    def save_topic(self, topic: Topic) -> None:
        ...

    def delete_topic(self, topic_id: str) -> None:
        ...

    def add_view_event(self, event: ViewEvent) -> None:
        ...

    def list_view_events_for_card(
        self,
        card_id: str,
        viewer_user_id: str | None = None,
        anonymous_id: str | None = None,
        visitor_identity_id: str | None = None,
        limit: int | None = None,
    ) -> list[ViewEvent]:
        ...

    def list_view_events_for_cards(self, card_ids: set[str]) -> dict[str, list[ViewEvent]]:
        ...

    def list_view_events_for_viewer(self, viewer_user_id: str, limit: int = 1000) -> list[ViewEvent]:
        ...

    def add_showcase_event(self, event: ShowcaseEvent) -> None:
        ...

    def list_showcase_events(self, showcase_id: str) -> list[ShowcaseEvent]:
        ...

    def list_showcase_events_for_showcases(self, showcase_ids: set[str]) -> dict[str, list[ShowcaseEvent]]:
        ...

    def get_notification_preference(self, user_id: str) -> NotificationPreference | None:
        ...

    def save_notification_preference(self, preference: NotificationPreference) -> None:
        ...

    def list_wechat_subscription_grants(self, user_id: str, template_id: str | None = None) -> list[WechatSubscriptionGrant]:
        ...

    def get_wechat_subscription_grant(self, grant_id: str) -> WechatSubscriptionGrant | None:
        ...

    def save_wechat_subscription_grant(self, grant: WechatSubscriptionGrant) -> None:
        ...

    def reserve_wechat_subscription_grant(self, user_id: str, template_id: str, now: str) -> WechatSubscriptionGrant | None:
        ...

    def release_stale_wechat_subscription_grants(self, cutoff: str, now: str) -> int:
        ...

    def list_wechat_subscription_deliveries(self, owner_user_id: str, limit: int = 100) -> list[WechatSubscriptionDelivery]:
        ...

    def get_wechat_subscription_delivery(self, delivery_id: str) -> WechatSubscriptionDelivery | None:
        ...

    def find_wechat_subscription_delivery_by_dedupe_key(self, dedupe_key: str) -> WechatSubscriptionDelivery | None:
        ...

    def save_wechat_subscription_delivery(self, delivery: WechatSubscriptionDelivery) -> None:
        ...

    def add_relay_entry(self, relay: RelayEntry) -> None:
        ...

    def get_relay_entry(self, relay_id: str) -> RelayEntry | None:
        ...

    def save_relay_entry(self, relay: RelayEntry) -> None:
        ...

    def list_relay_entries_for_card(self, card_id: str, relay_status: str | None = "active") -> list[RelayEntry]:
        ...

    def list_relay_entries_for_cards(
        self,
        card_ids: set[str],
        relay_status: str | None = "active",
    ) -> dict[str, list[RelayEntry]]:
        ...

    def list_lead_reminders(self, owner_user_id: str, status: str | None = None) -> list[LeadReminder]:
        ...

    def get_lead_reminder(self, reminder_id: str) -> LeadReminder | None:
        ...

    def get_lead_reminder_by_card_viewer(self, card_id: str, viewer_user_id: str) -> LeadReminder | None:
        ...

    def save_lead_reminder(self, reminder: LeadReminder) -> None:
        ...

    def save_lead_reminder_if_version(self, reminder: LeadReminder, expected_version: int) -> bool:
        ...

    def delete_lead_reminder(self, reminder_id: str) -> None:
        ...

    def get_customer_radar_summary(self, owner_user_id: str, mode: str = "") -> CustomerRadarSummary | None:
        ...

    def save_customer_radar_summary(self, summary: CustomerRadarSummary) -> None:
        ...

    def mark_customer_radar_summaries_dirty(self, owner_user_id: str | None = None) -> None:
        ...

    def save_customer_action(self, action: CustomerAction) -> None:
        ...

    def list_customer_actions_for_note(
        self,
        note_id: str,
        viewer_user_id: str | None = None,
        anonymous_id: str | None = None,
        visitor_identity_id: str | None = None,
        limit: int | None = None,
    ) -> list[CustomerAction]:
        ...

    def list_customer_actions_for_notes(self, note_ids: set[str]) -> dict[str, list[CustomerAction]]:
        ...

    def get_customer_action(self, action_id: str) -> CustomerAction | None:
        ...

    def save_message_thread(self, thread: MessageThread) -> None:
        ...

    def get_message_thread(self, thread_id: str) -> MessageThread | None:
        ...

    def list_message_threads_for_user(self, user_id: str) -> list[MessageThread]:
        ...

    def save_message_record(self, record: MessageRecord) -> None:
        ...

    def list_message_records_for_thread(self, thread_id: str) -> list[MessageRecord]:
        ...

    def save_import_notification(self, notification: ImportNotification) -> None:
        ...

    def list_import_notifications(self) -> list[ImportNotification]:
        ...

    def get_sync_cursor(self, open_kfid: str) -> SyncCursor | None:
        ...

    def save_sync_cursor(self, cursor: SyncCursor) -> None:
        ...

    def acquire_sync_lock(
        self,
        open_kfid: str,
        source: str,
        lock_token: str,
        now: str,
        stale_before: str,
    ) -> SyncCursor | None:
        ...

    def release_sync_lock(
        self,
        open_kfid: str,
        lock_token: str,
        status: str,
        error_message: str | None,
        now: str,
    ) -> SyncCursor | None:
        ...

    def force_release_sync_lock(self, open_kfid: str, reason: str, now: str) -> SyncCursor | None:
        ...

    def save_media_retry_job(self, job: MediaRetryJob) -> None:
        ...

    def get_media_retry_job(self, media_id: str) -> MediaRetryJob | None:
        ...

    def get_successful_media_url(self, media_id: str) -> str | None:
        ...

    def list_media_retry_jobs(self, statuses: set[str] | None = None) -> list[MediaRetryJob]:
        ...

    def get_media_asset_by_original_hash(self, media_type: str, original_sha256: str) -> MediaAsset | None:
        ...

    def get_media_asset_by_storage_hash(self, media_type: str, storage_sha256: str) -> MediaAsset | None:
        ...

    def get_media_asset_by_url(self, url: str) -> MediaAsset | None:
        ...

    def save_media_asset(self, asset: MediaAsset) -> bool:
        ...

    def save_media_asset_ref(self, ref: MediaAssetRef) -> None:
        ...

    def list_media_asset_refs(
        self,
        asset_id: str | None = None,
        ref_type: str | None = None,
        ref_id: str | None = None,
    ) -> list[MediaAssetRef]:
        ...

    def delete_media_asset_refs(
        self,
        asset_id: str,
        ref_type: str | None = None,
        ref_id: str | None = None,
        usage: str | None = None,
    ) -> int:
        ...

    def save_sync_task(self, task: SyncTask) -> None:
        ...

    def list_sync_tasks(self, statuses: set[str] | None = None, limit: int = 50) -> list[SyncTask]:
        ...

    def claim_sync_task(self, task_id: str, worker_id: str, now: str, stale_before: str) -> SyncTask | None:
        ...

    def update_sync_task(self, task: SyncTask) -> None:
        ...

    def add_sync_task_log(self, log: SyncTaskLog) -> None:
        ...

    def list_sync_task_logs(self, task_id: str | None = None, limit: int = 100) -> list[SyncTaskLog]:
        ...

    def save_skill_run(self, run: SkillRun) -> None:
        ...

    def list_skill_runs(
        self,
        status: str | None = None,
        skill_id: str | None = None,
        limit: int = 100,
    ) -> list[SkillRun]:
        ...

    def get_automation_device(self, device_id: str) -> AutomationDevice | None:
        ...

    def list_automation_devices(self, limit: int = 100) -> list[AutomationDevice]:
        ...

    def save_automation_device(self, device: AutomationDevice) -> None:
        ...

    def get_automation_task(self, task_id: str) -> AutomationTask | None:
        ...

    def find_automation_task_by_idempotency_key(self, idempotency_key: str) -> AutomationTask | None:
        ...

    def save_automation_task(self, task: AutomationTask) -> None:
        ...

    def list_automation_tasks(
        self,
        device_id: str | None = None,
        statuses: set[str] | None = None,
        limit: int = 50,
    ) -> list[AutomationTask]:
        ...

    def claim_next_automation_task(
        self,
        device_id: str,
        active_wechat_account_id: str | None,
        now: str,
        lease_expires_at: str,
        lease_token: str,
        function_ids: set[str] | None = None,
    ) -> AutomationTask | None:
        ...

    def get_automation_group_candidate(self, candidate_id: str) -> AutomationGroupCandidate | None:
        ...

    def find_automation_group_candidate_by_idempotency_key(self, idempotency_key: str) -> AutomationGroupCandidate | None:
        ...

    def save_automation_group_candidate(self, candidate: AutomationGroupCandidate) -> None:
        ...

    def list_automation_group_candidates(
        self,
        wechat_account_id: str | None = None,
        limit: int = 100,
    ) -> list[AutomationGroupCandidate]:
        ...

    def get_wecom_archive_cursor(self, corp_id: str) -> WecomArchiveCursor | None:
        ...

    def save_wecom_archive_cursor(self, cursor: WecomArchiveCursor) -> None:
        ...

    def save_wecom_archive_messages(self, messages: list[WecomArchiveMessage]) -> None:
        ...

    def existing_wecom_archive_msg_ids(self, msg_ids: set[str]) -> set[str]:
        ...

    def get_wecom_archive_message_by_msg_id(self, msg_id: str) -> WecomArchiveMessage | None:
        ...

    def get_wecom_archive_message_by_generated_note_id(self, note_id: str) -> WecomArchiveMessage | None:
        ...

    def list_wecom_archive_messages_by_generated_note_id(self, note_id: str) -> list[WecomArchiveMessage]:
        ...

    def list_wecom_archive_messages(self, limit: int = 100) -> list[WecomArchiveMessage]:
        ...

    def get_resource_wallet(self, owner_user_id: str) -> ResourceWallet | None:
        ...

    def save_resource_wallet(self, wallet: ResourceWallet) -> None:
        ...

    def save_resource_point_ledger(self, ledger: ResourcePointLedger) -> None:
        ...

    def list_resource_point_ledgers(self, owner_user_id: str, limit: int = 100) -> list[ResourcePointLedger]:
        ...

    def get_resource_free_quota(self, owner_user_id: str, quota_type: str, period_key: str) -> ResourceFreeQuota | None:
        ...

    def save_resource_free_quota(self, quota: ResourceFreeQuota) -> None:
        ...

    def find_resource_unlock_record(
        self,
        owner_user_id: str,
        action_type: str,
        target_type: str,
        target_id: str,
    ) -> ResourceUnlockRecord | None:
        ...

    def save_resource_unlock_record(self, record: ResourceUnlockRecord) -> None:
        ...

    def list_opportunity_leads(self, statuses: set[str] | None = None, keyword: str | None = None) -> list[OpportunityLead]:
        ...

    def get_opportunity_lead(self, lead_id: str) -> OpportunityLead | None:
        ...

    def save_opportunity_lead(self, lead: OpportunityLead) -> None:
        ...

    def list_opportunity_lead_sources(self, lead_id: str) -> list[OpportunityLeadSource]:
        ...

    def save_opportunity_lead_source(self, source: OpportunityLeadSource) -> None:
        ...

    def list_opportunity_lead_contacts(self, lead_id: str) -> list[OpportunityLeadContact]:
        ...

    def save_opportunity_lead_contact(self, contact: OpportunityLeadContact) -> None:
        ...

    def get_opportunity_lead_save(self, lead_id: str, user_id: str) -> OpportunityLeadSave | None:
        ...

    def save_opportunity_lead_save(self, lead_save: OpportunityLeadSave) -> None:
        ...

    def list_opportunity_lead_saves_for_user(self, user_id: str) -> list[OpportunityLeadSave]:
        ...

    def save_opportunity_lead_followup(self, followup: OpportunityLeadFollowup) -> None:
        ...

    def list_opportunity_lead_followups(self, lead_id: str, user_id: str | None = None) -> list[OpportunityLeadFollowup]:
        ...

    def get_response_package(self, package_id: str) -> ResponsePackage | None:
        ...

    def get_response_package_for_lead_user(self, lead_id: str, owner_user_id: str) -> ResponsePackage | None:
        ...

    def save_response_package(self, package: ResponsePackage) -> None:
        ...

    def list_response_package_items(self, package_id: str) -> list[ResponsePackageItem]:
        ...

    def save_response_package_item(self, item: ResponsePackageItem) -> None:
        ...

    def save_response_package_event(self, event: ResponsePackageEvent) -> None:
        ...

    def list_opportunity_subscriptions(self, owner_user_id: str) -> list[OpportunitySubscription]:
        ...

    def save_opportunity_subscription(self, subscription: OpportunitySubscription) -> None:
        ...

    def list_supply_demand_cards(
        self,
        owner_user_id: str | None = None,
        statuses: set[str] | None = None,
        keyword: str | None = None,
    ) -> list[SupplyDemandCard]:
        ...

    def get_supply_demand_card(self, card_id: str) -> SupplyDemandCard | None:
        ...

    def save_supply_demand_card(self, card: SupplyDemandCard) -> None:
        ...

    def list_supply_demand_applications(
        self,
        card_id: str | None = None,
        applicant_user_id: str | None = None,
        owner_user_id: str | None = None,
    ) -> list[SupplyDemandApplication]:
        ...

    def get_supply_demand_application(self, application_id: str) -> SupplyDemandApplication | None:
        ...

    def save_supply_demand_application(self, application: SupplyDemandApplication) -> None:
        ...

    def list_opportunity_push_digests(self, owner_user_id: str) -> list[OpportunityPushDigest]:
        ...

    def get_opportunity_push_digest(self, digest_id: str) -> OpportunityPushDigest | None:
        ...

    def save_opportunity_push_digest(self, digest: OpportunityPushDigest) -> None:
        ...

    def get_membership_records(
        self,
        user_id: str,
    ) -> tuple[list[MembershipOrder], list[MembershipEntitlement]]:
        ...


class JsonRepository:
    def __init__(self, data_file: Path):
        self.data_file = data_file
        self._automation_lock = threading.RLock()
        self.data_file.parent.mkdir(parents=True, exist_ok=True)
        if not self.data_file.exists():
            self.save(AppState())

    def load(self) -> AppState:
        payload = json.loads(self.data_file.read_text(encoding="utf-8"))
        return AppState.model_validate(payload)

    def save(self, state: AppState) -> None:
        payload = strip_unicode_surrogates(state.model_dump(mode="json"))
        self.data_file.write_text(
            AppState.model_validate(payload).model_dump_json(indent=2),
            encoding="utf-8",
        )

    def get_user(self, user_id: str) -> User | None:
        return next((item for item in self.load().users if item.id == user_id), None)

    def get_user_by_openid(self, openid: str) -> User | None:
        return next((item for item in self.load().users if item.openid == openid), None)

    def save_user(self, user: User) -> None:
        state = self.load()
        state.users = [item for item in state.users if item.id != user.id]
        state.users.append(user)
        self.save(state)

    def get_membership_records(
        self,
        user_id: str,
    ) -> tuple[list[MembershipOrder], list[MembershipEntitlement]]:
        state = self.load()
        orders = [item for item in state.membership_orders if item.userId == user_id]
        entitlements = [item for item in state.membership_entitlements if item.userId == user_id]
        return orders, entitlements

    def get_wecom_identity_binding(self, source_type: str, external_user_id: str) -> WecomIdentityBinding | None:
        return next(
            (
                item
                for item in self.load().wecom_identity_bindings
                if item.sourceType == source_type and item.externalUserId == external_user_id
            ),
            None,
        )

    def save_wecom_identity_binding(self, binding: WecomIdentityBinding) -> None:
        state = self.load()
        state.wecom_identity_bindings = [item for item in state.wecom_identity_bindings if item.id != binding.id]
        state.wecom_identity_bindings.append(binding)
        self.save(state)

    def get_wecom_bind_card_token(self, token_hash: str) -> WecomBindCardToken | None:
        return next((item for item in self.load().wecom_bind_card_tokens if item.tokenHash == token_hash), None)

    def get_pending_wecom_bind_card_token(self, welcome_code_hash: str) -> WecomBindCardToken | None:
        return next(
            (
                item
                for item in self.load().wecom_bind_card_tokens
                if item.welcomeCodeHash == welcome_code_hash
            ),
            None,
        )

    def save_wecom_bind_card_token(self, token: WecomBindCardToken) -> None:
        state = self.load()
        state.wecom_bind_card_tokens = [item for item in state.wecom_bind_card_tokens if item.id != token.id]
        state.wecom_bind_card_tokens.append(token)
        self.save(state)

    def get_active_wecom_bind_card_asset(self) -> WecomBindCardAsset | None:
        assets = [item for item in self.load().wecom_bind_card_assets if item.status == "active"]
        return max(assets, key=lambda item: item.updatedAt) if assets else None

    def get_latest_wecom_bind_card_asset(self) -> WecomBindCardAsset | None:
        assets = self.load().wecom_bind_card_assets
        return max(assets, key=lambda item: item.updatedAt) if assets else None

    def save_wecom_bind_card_asset(self, asset: WecomBindCardAsset) -> None:
        state = self.load()
        state.wecom_bind_card_assets = [item for item in state.wecom_bind_card_assets if item.id != asset.id]
        state.wecom_bind_card_assets.append(asset)
        self.save(state)

    def consume_wecom_bind_card_token(
        self,
        token_hash: str,
        owner_user_id: str,
        owner_openid: str,
        now: str,
    ) -> WecomBindCardToken | None:
        state = self.load()
        token = next((item for item in state.wecom_bind_card_tokens if item.tokenHash == token_hash), None)
        if not token or token.status != "issued" or token.deliveryStatus != "sent":
            return None
        try:
            if parse_iso(token.expiresAt) <= parse_iso(now):
                return None
        except Exception:
            return None
        consumed = token.model_copy(
            update={
                "status": "consumed",
                "usedAt": now,
                "ownerUserId": owner_user_id,
                "ownerOpenid": owner_openid,
                "updatedAt": now,
            }
        )
        state.wecom_bind_card_tokens = [item for item in state.wecom_bind_card_tokens if item.id != token.id]
        state.wecom_bind_card_tokens.append(consumed)
        self.save(state)
        return consumed

    def list_import_batches(self, statuses: set[str] | None = None) -> list[ImportBatch]:
        batches = self.load().import_batches
        return [item for item in batches if statuses is None or item.status in statuses]

    def get_import_batch(self, import_id: str) -> ImportBatch | None:
        return next((item for item in self.load().import_batches if item.id == import_id), None)

    def save_import_batch(self, batch: ImportBatch) -> None:
        state = self.load()
        state.import_batches = [item for item in state.import_batches if item.id != batch.id]
        state.import_batches.append(batch)
        self.save(state)

    def list_user_notes(
        self,
        owner_user_id: str,
        keyword: str | None = None,
        category_id: str | None = None,
        include_deleted: bool = False,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[UserNote]:
        notes = [item for item in self.load().user_notes if item.ownerUserId == owner_user_id]
        if not include_deleted:
            notes = [item for item in notes if item.status != "deleted"]
        if keyword:
            lowered = keyword.lower()
            notes = [item for item in notes if lowered in item.title.lower() or lowered in item.summary.lower()]
        if category_id:
            notes = [item for item in notes if category_id in item.categoryIds]
        notes = sorted(notes, key=lambda item: item.updatedAt, reverse=True)
        if limit is not None:
            start = max(int(offset or 0), 0)
            notes = notes[start:start + max(1, int(limit))]
        return notes

    def list_user_notes_by_source_card_ids(
        self,
        owner_user_id: str,
        source_card_ids: set[str],
    ) -> list[UserNote]:
        if not source_card_ids:
            return []
        return [
            item
            for item in self.load().user_notes
            if item.ownerUserId == owner_user_id
            and item.status != "deleted"
            and item.sourceCardId in source_card_ids
        ]

    def list_standalone_user_notes(
        self,
        owner_user_id: str,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[UserNote]:
        notes = [
            item
            for item in self.load().user_notes
            if item.ownerUserId == owner_user_id
            and item.status != "deleted"
            and not item.sourceCardId
        ]
        notes = sorted(notes, key=lambda item: item.updatedAt, reverse=True)
        if limit is not None:
            start = max(int(offset or 0), 0)
            notes = notes[start:start + max(1, int(limit))]
        return notes

    def list_all_user_notes(self, include_deleted: bool = False) -> list[UserNote]:
        notes = self.load().user_notes
        if not include_deleted:
            notes = [item for item in notes if item.status != "deleted"]
        return sorted(notes, key=lambda item: item.updatedAt, reverse=True)

    def get_user_note(self, note_id: str) -> UserNote | None:
        return next((item for item in self.load().user_notes if item.id == note_id), None)

    def save_user_note(self, note: UserNote) -> None:
        state = self.load()
        state.user_notes = [item for item in state.user_notes if item.id != note.id]
        state.user_notes.append(note)
        self.save(state)

    def list_showcase_pages(self, owner_user_id: str) -> list[ShowcasePage]:
        pages = [item for item in self.load().showcase_pages if item.ownerUserId == owner_user_id]
        return sorted(pages, key=lambda item: item.updatedAt, reverse=True)

    def get_showcase_page(self, showcase_id: str) -> ShowcasePage | None:
        return next((item for item in self.load().showcase_pages if item.id == showcase_id), None)

    def save_showcase_page(self, showcase: ShowcasePage) -> None:
        state = self.load()
        state.showcase_pages = [item for item in state.showcase_pages if item.id != showcase.id]
        state.showcase_pages.append(showcase)
        self.save(state)

    def get_live_qr_code(self, qr_id: str) -> LiveQrCode | None:
        return next((item for item in self.load().live_qr_codes if item.id == qr_id), None)

    def get_live_qr_code_by_code(self, code: str) -> LiveQrCode | None:
        return next((item for item in self.load().live_qr_codes if item.code == code), None)

    def list_live_qr_codes(self) -> list[LiveQrCode]:
        return sorted(self.load().live_qr_codes, key=lambda item: (item.updatedAt, item.id), reverse=True)

    def save_live_qr_code(self, qr_code: LiveQrCode) -> None:
        with self._automation_lock:
            state = self.load()
            state.live_qr_codes = [item for item in state.live_qr_codes if item.id != qr_code.id]
            state.live_qr_codes.append(qr_code)
            self.save(state)

    def delete_live_qr_code(self, qr_id: str) -> bool:
        with self._automation_lock:
            state = self.load()
            kept = [item for item in state.live_qr_codes if item.id != qr_id]
            if len(kept) == len(state.live_qr_codes):
                return False
            state.live_qr_codes = kept
            self.save(state)
            return True

    def record_live_qr_scan(self, code: str, scanned_at: str) -> LiveQrCode | None:
        with self._automation_lock:
            state = self.load()
            current = next(
                (item for item in state.live_qr_codes if item.code == code and item.status == "active"),
                None,
            )
            if not current:
                return None
            if current.targetExpiresAt:
                try:
                    if parse_iso(current.targetExpiresAt) <= parse_iso(scanned_at):
                        return None
                except (TypeError, ValueError):
                    pass
            updated = current.model_copy(
                update={
                    "scanCount": int(current.scanCount or 0) + 1,
                    "lastScannedAt": scanned_at,
                }
            )
            state.live_qr_codes = [item for item in state.live_qr_codes if item.id != updated.id]
            state.live_qr_codes.append(updated)
            self.save(state)
            return updated

    def list_referral_relations(self) -> list[ReferralRelation]:
        return list(self.load().referral_relations)

    def find_same_style_generation(
        self,
        owner_user_id: str,
        idempotency_key: str,
    ) -> SameStyleGeneration | None:
        return next(
            (
                item
                for item in self.load().same_style_generations
                if item.ownerUserId == owner_user_id and item.idempotencyKey == idempotency_key
            ),
            None,
        )

    def find_latest_same_style_generation(
        self,
        owner_user_id: str,
        mode: str,
        source_note_id: str | None = None,
        source_showcase_id: str | None = None,
    ) -> SameStyleGeneration | None:
        candidates = [
            item
            for item in self.load().same_style_generations
            if item.ownerUserId == owner_user_id
            and item.mode == mode
            and item.sourceNoteId == source_note_id
            and item.sourceShowcaseId == source_showcase_id
        ]
        return max(candidates, key=lambda item: (item.createdAt, item.id), default=None)

    def list_same_style_generations(self, owner_user_id: str) -> list[SameStyleGeneration]:
        return sorted(
            [item for item in self.load().same_style_generations if item.ownerUserId == owner_user_id],
            key=lambda item: (item.createdAt, item.id),
            reverse=True,
        )

    def save_same_style_generation(
        self,
        generation: SameStyleGeneration,
        referral_relation: ReferralRelation | None = None,
    ) -> None:
        state = self.load()
        if referral_relation and not any(item.id == referral_relation.id for item in state.referral_relations):
            state.referral_relations.append(referral_relation)
        state.same_style_generations = [item for item in state.same_style_generations if item.id != generation.id]
        state.same_style_generations.append(generation)
        self.save(state)

    def delete_showcase_page(self, showcase_id: str) -> None:
        state = self.load()
        state.showcase_pages = [item for item in state.showcase_pages if item.id != showcase_id]
        state.showcase_events = [item for item in state.showcase_events if item.showcaseId != showcase_id]
        self.save(state)

    def save_raw_messages(self, messages: list[RawMessage]) -> None:
        state = self.load()
        message_ids = {item.id for item in messages}
        state.raw_messages = [item for item in state.raw_messages if item.id not in message_ids]
        state.raw_messages.extend(messages)
        self.save(state)

    def list_raw_messages_for_batch(self, import_batch_id: str) -> list[RawMessage]:
        return [item for item in self.load().raw_messages if item.importBatchId == import_batch_id]

    def existing_wecom_msg_ids(self, wecom_msg_ids: set[str]) -> set[str]:
        if not wecom_msg_ids:
            return set()
        return {
            item.wecomMsgId
            for item in self.load().raw_messages
            if item.wecomMsgId and item.wecomMsgId in wecom_msg_ids
        }

    def save_import_artifacts(
        self,
        batch: ImportBatch,
        raw_messages: list[RawMessage],
        card: Card,
        notification: ImportNotification,
    ) -> None:
        state = self.load()
        state.import_batches = [item for item in state.import_batches if item.id != batch.id]
        state.import_batches.append(batch)
        message_ids = {item.id for item in raw_messages}
        state.raw_messages = [item for item in state.raw_messages if item.id not in message_ids]
        state.raw_messages.extend(raw_messages)
        state.cards = [item for item in state.cards if item.id != card.id]
        state.cards.append(card)
        state.import_notifications = [item for item in state.import_notifications if item.id != notification.id]
        state.import_notifications.append(notification)
        self.save(state)

    def get_card(self, card_id: str) -> Card | None:
        return next((item for item in self.load().cards if item.id == card_id), None)

    def list_cards(
        self,
        owner_user_id: str | None = None,
        keyword: str | None = None,
        category_id: str | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[Card]:
        cards = self.load().cards
        if owner_user_id:
            cards = [item for item in cards if item.ownerUserId == owner_user_id]
        if keyword:
            cards = [item for item in cards if keyword.lower() in item.title.lower()]
        if category_id:
            cards = [item for item in cards if category_id in item.categoryIds]
        cards = sorted(cards, key=lambda item: item.updatedAt, reverse=True)
        if limit is not None:
            start = max(int(offset or 0), 0)
            cards = cards[start:start + max(1, int(limit))]
        return cards

    def save_card(self, card: Card) -> None:
        state = self.load()
        state.cards = [item for item in state.cards if item.id != card.id]
        state.cards.append(card)
        self.save(state)

    def delete_card(self, card_id: str) -> None:
        state = self.load()
        state.cards = [item for item in state.cards if item.id != card_id]
        state.view_events = [item for item in state.view_events if item.cardId != card_id]
        state.relay_entries = [item for item in state.relay_entries if item.cardId != card_id]
        state.lead_reminders = [item for item in state.lead_reminders if item.cardId != card_id]
        state.customer_actions = [item for item in state.customer_actions if item.sourceCardId != card_id]
        self.save(state)

    def list_categories(self, owner_user_id: str | None = None) -> list[Category]:
        categories = self.load().categories
        if owner_user_id:
            categories = [item for item in categories if item.ownerUserId == owner_user_id]
        return sorted(categories, key=lambda item: (item.sortOrder, item.createdAt, item.id))

    def get_category(self, category_id: str) -> Category | None:
        return next((item for item in self.load().categories if item.id == category_id), None)

    def save_category(self, category: Category) -> None:
        state = self.load()
        state.categories = [item for item in state.categories if item.id != category.id]
        state.categories.append(category)
        self.save(state)

    def delete_category(self, category_id: str) -> None:
        state = self.load()
        state.categories = [item for item in state.categories if item.id != category_id]
        self.save(state)

    def list_topics(self, owner_user_id: str) -> list[Topic]:
        topics = [item for item in self.load().topics if item.ownerUserId == owner_user_id]
        return sorted(topics, key=lambda item: (item.updatedAt, item.id), reverse=True)

    def get_topic(self, topic_id: str) -> Topic | None:
        return next((item for item in self.load().topics if item.id == topic_id), None)

    def save_topic(self, topic: Topic) -> None:
        state = self.load()
        state.topics = [item for item in state.topics if item.id != topic.id]
        state.topics.append(topic)
        self.save(state)

    def delete_topic(self, topic_id: str) -> None:
        state = self.load()
        state.topics = [item for item in state.topics if item.id != topic_id]
        for note in state.user_notes:
            config = dict(note.visibilityConfig or {})
            topic_ids = [item for item in config.get("topicIds", []) if item != topic_id]
            topics = [item for item in config.get("topics", []) if item.get("id") != topic_id]
            config["topicIds"] = topic_ids
            config["topics"] = topics
            note.visibilityConfig = config
        self.save(state)

    def add_view_event(self, event: ViewEvent) -> None:
        state = self.load()
        state.view_events = [item for item in state.view_events if item.id != event.id]
        state.view_events.append(event)
        self.save(state)

    def list_view_events_for_card(
        self,
        card_id: str,
        viewer_user_id: str | None = None,
        anonymous_id: str | None = None,
        visitor_identity_id: str | None = None,
        limit: int | None = None,
    ) -> list[ViewEvent]:
        rows = [item for item in self.load().view_events if item.cardId == card_id]
        if viewer_user_id or anonymous_id or visitor_identity_id:
            rows = [
                item
                for item in rows
                if (viewer_user_id and item.viewerUserId == viewer_user_id)
                or (anonymous_id and item.anonymousId == anonymous_id)
                or (visitor_identity_id and item.visitorIdentityId == visitor_identity_id)
            ]
        rows.sort(key=lambda item: (item.viewedAt, item.id), reverse=True)
        return rows[: max(1, min(int(limit), 100))] if limit is not None else rows

    def list_view_events_for_cards(self, card_ids: set[str]) -> dict[str, list[ViewEvent]]:
        grouped: dict[str, list[ViewEvent]] = {card_id: [] for card_id in card_ids}
        for item in self.load().view_events:
            if item.cardId in grouped:
                grouped[item.cardId].append(item)
        return grouped

    def list_view_events_for_viewer(self, viewer_user_id: str, limit: int = 1000) -> list[ViewEvent]:
        rows = [item for item in self.load().view_events if item.viewerUserId == viewer_user_id]
        rows.sort(key=lambda item: (item.viewedAt, item.id), reverse=True)
        return rows[: max(1, min(int(limit or 1000), 1000))]

    def add_showcase_event(self, event: ShowcaseEvent) -> None:
        state = self.load()
        state.showcase_events = [item for item in state.showcase_events if item.id != event.id]
        state.showcase_events.append(event)
        self.save(state)

    def list_showcase_events(self, showcase_id: str) -> list[ShowcaseEvent]:
        return sorted(
            [item for item in self.load().showcase_events if item.showcaseId == showcase_id],
            key=lambda item: (item.createdAt, item.id),
            reverse=True,
        )

    def list_showcase_events_for_showcases(self, showcase_ids: set[str]) -> dict[str, list[ShowcaseEvent]]:
        grouped: dict[str, list[ShowcaseEvent]] = {showcase_id: [] for showcase_id in showcase_ids}
        for item in self.load().showcase_events:
            if item.showcaseId in grouped:
                grouped[item.showcaseId].append(item)
        for events in grouped.values():
            events.sort(key=lambda item: (item.createdAt, item.id), reverse=True)
        return grouped

    def get_notification_preference(self, user_id: str) -> NotificationPreference | None:
        return next((item for item in self.load().notification_preferences if item.userId == user_id), None)

    def save_notification_preference(self, preference: NotificationPreference) -> None:
        state = self.load()
        state.notification_preferences = [item for item in state.notification_preferences if item.id != preference.id and item.userId != preference.userId]
        state.notification_preferences.append(preference)
        self.save(state)

    def list_wechat_subscription_grants(self, user_id: str, template_id: str | None = None) -> list[WechatSubscriptionGrant]:
        rows = [item for item in self.load().wechat_subscription_grants if item.userId == user_id]
        if template_id:
            rows = [item for item in rows if item.templateId == template_id]
        return sorted(rows, key=lambda item: (item.authorizedAt, item.id), reverse=True)

    def get_wechat_subscription_grant(self, grant_id: str) -> WechatSubscriptionGrant | None:
        return next((item for item in self.load().wechat_subscription_grants if item.id == grant_id), None)

    def save_wechat_subscription_grant(self, grant: WechatSubscriptionGrant) -> None:
        state = self.load()
        state.wechat_subscription_grants = [item for item in state.wechat_subscription_grants if item.id != grant.id]
        state.wechat_subscription_grants.append(grant)
        self.save(state)

    def reserve_wechat_subscription_grant(self, user_id: str, template_id: str, now: str) -> WechatSubscriptionGrant | None:
        state = self.load()
        grant = next(
            (
                item for item in sorted(state.wechat_subscription_grants, key=lambda value: (value.authorizedAt, value.id))
                if item.userId == user_id and item.templateId == template_id and item.status == "available"
            ),
            None,
        )
        if not grant:
            return None
        grant.status = "reserved"
        grant.reservedAt = now
        grant.updatedAt = now
        self.save(state)
        return grant

    def release_stale_wechat_subscription_grants(self, cutoff: str, now: str) -> int:
        state = self.load()
        released = 0
        for grant in state.wechat_subscription_grants:
            if grant.status != "reserved" or not grant.reservedAt:
                continue
            try:
                stale = parse_iso(grant.reservedAt) <= parse_iso(cutoff)
            except (TypeError, ValueError, OverflowError):
                stale = True
            if not stale:
                continue
            grant.status = "available"
            grant.reservedAt = None
            grant.updatedAt = now
            released += 1
        if released:
            self.save(state)
        return released

    def list_wechat_subscription_deliveries(self, owner_user_id: str, limit: int = 100) -> list[WechatSubscriptionDelivery]:
        rows = [item for item in self.load().wechat_subscription_deliveries if item.ownerUserId == owner_user_id]
        return sorted(rows, key=lambda item: (item.createdAt, item.id), reverse=True)[:limit]

    def get_wechat_subscription_delivery(self, delivery_id: str) -> WechatSubscriptionDelivery | None:
        return next((item for item in self.load().wechat_subscription_deliveries if item.id == delivery_id), None)

    def find_wechat_subscription_delivery_by_dedupe_key(self, dedupe_key: str) -> WechatSubscriptionDelivery | None:
        return next((item for item in self.load().wechat_subscription_deliveries if item.dedupeKey == dedupe_key), None)

    def save_wechat_subscription_delivery(self, delivery: WechatSubscriptionDelivery) -> None:
        state = self.load()
        state.wechat_subscription_deliveries = [item for item in state.wechat_subscription_deliveries if item.id != delivery.id]
        state.wechat_subscription_deliveries.append(delivery)
        self.save(state)

    def add_relay_entry(self, relay: RelayEntry) -> None:
        state = self.load()
        state.relay_entries.append(relay)
        self.save(state)

    def get_relay_entry(self, relay_id: str) -> RelayEntry | None:
        return next((item for item in self.load().relay_entries if item.id == relay_id), None)

    def save_relay_entry(self, relay: RelayEntry) -> None:
        state = self.load()
        state.relay_entries = [item for item in state.relay_entries if item.id != relay.id]
        state.relay_entries.append(relay)
        self.save(state)

    def list_relay_entries_for_card(self, card_id: str, relay_status: str | None = "active") -> list[RelayEntry]:
        relays = [item for item in self.load().relay_entries if item.cardId == card_id]
        if relay_status:
            relays = [item for item in relays if item.status == relay_status]
        return relays

    def list_relay_entries_for_cards(
        self,
        card_ids: set[str],
        relay_status: str | None = "active",
    ) -> dict[str, list[RelayEntry]]:
        grouped: dict[str, list[RelayEntry]] = {card_id: [] for card_id in card_ids}
        for item in self.load().relay_entries:
            if item.cardId not in grouped or (relay_status and item.status != relay_status):
                continue
            grouped[item.cardId].append(item)
        return grouped

    def list_lead_reminders(self, owner_user_id: str, status: str | None = None) -> list[LeadReminder]:
        reminders = [item for item in self.load().lead_reminders if item.ownerUserId == owner_user_id]
        if status:
            reminders = [item for item in reminders if item.status == status]
        return sorted(reminders, key=lambda item: item.updatedAt, reverse=True)

    def get_lead_reminder(self, reminder_id: str) -> LeadReminder | None:
        return next((item for item in self.load().lead_reminders if item.id == reminder_id), None)

    def get_lead_reminder_by_card_viewer(self, card_id: str, viewer_user_id: str) -> LeadReminder | None:
        return next(
            (
                item
                for item in self.load().lead_reminders
                if item.cardId == card_id and item.viewerUserId == viewer_user_id
            ),
            None,
        )

    def save_lead_reminder(self, reminder: LeadReminder) -> None:
        state = self.load()
        state.lead_reminders = [item for item in state.lead_reminders if item.id != reminder.id]
        state.lead_reminders.append(reminder)
        self.save(state)

    def save_lead_reminder_if_version(self, reminder: LeadReminder, expected_version: int) -> bool:
        state = self.load()
        current = next((item for item in state.lead_reminders if item.id == reminder.id), None)
        if current is None or int(current.version or 0) != int(expected_version):
            return False
        state.lead_reminders = [item for item in state.lead_reminders if item.id != reminder.id]
        state.lead_reminders.append(reminder)
        self.save(state)
        return True

    def delete_lead_reminder(self, reminder_id: str) -> None:
        state = self.load()
        state.lead_reminders = [item for item in state.lead_reminders if item.id != reminder_id]
        self.save(state)

    def get_customer_radar_summary(self, owner_user_id: str, mode: str = "") -> CustomerRadarSummary | None:
        normalized_mode = str(mode or "")
        return next(
            (
                item
                for item in self.load().customer_radar_summaries
                if item.ownerUserId == owner_user_id and item.mode == normalized_mode
            ),
            None,
        )

    def save_customer_radar_summary(self, summary: CustomerRadarSummary) -> None:
        state = self.load()
        state.customer_radar_summaries = [item for item in state.customer_radar_summaries if item.id != summary.id]
        state.customer_radar_summaries.append(summary)
        self.save(state)

    def mark_customer_radar_summaries_dirty(self, owner_user_id: str | None = None) -> None:
        state = self.load()
        changed = False
        summaries = []
        for item in state.customer_radar_summaries:
            if (owner_user_id is None or item.ownerUserId == owner_user_id) and not item.isDirty:
                summaries.append(item.model_copy(update={"isDirty": True}))
                changed = True
            else:
                summaries.append(item)
        if changed:
            state.customer_radar_summaries = summaries
            self.save(state)

    def save_customer_action(self, action: CustomerAction) -> None:
        state = self.load()
        state.customer_actions = [item for item in state.customer_actions if item.id != action.id]
        state.customer_actions.append(action)
        self.save(state)

    def list_customer_actions_for_note(
        self,
        note_id: str,
        viewer_user_id: str | None = None,
        anonymous_id: str | None = None,
        visitor_identity_id: str | None = None,
        limit: int | None = None,
    ) -> list[CustomerAction]:
        actions = [item for item in self.load().customer_actions if item.noteId == note_id]
        if viewer_user_id or anonymous_id or visitor_identity_id:
            actions = [
                item
                for item in actions
                if (viewer_user_id and item.viewerUserId == viewer_user_id)
                or (anonymous_id and item.anonymousId == anonymous_id)
                or (visitor_identity_id and item.visitorIdentityId == visitor_identity_id)
            ]
        actions = sorted(actions, key=lambda item: item.createdAt, reverse=True)
        return actions[: max(1, min(int(limit), 100))] if limit is not None else actions

    def list_customer_actions_for_notes(self, note_ids: set[str]) -> dict[str, list[CustomerAction]]:
        grouped: dict[str, list[CustomerAction]] = {note_id: [] for note_id in note_ids}
        for item in self.load().customer_actions:
            if item.noteId in grouped:
                grouped[item.noteId].append(item)
        for actions in grouped.values():
            actions.sort(key=lambda item: item.createdAt, reverse=True)
        return grouped

    def get_customer_action(self, action_id: str) -> CustomerAction | None:
        return next((item for item in self.load().customer_actions if item.id == action_id), None)

    def save_message_thread(self, thread: MessageThread) -> None:
        state = self.load()
        state.message_threads = [item for item in state.message_threads if item.id != thread.id]
        state.message_threads.append(thread)
        self.save(state)

    def get_message_thread(self, thread_id: str) -> MessageThread | None:
        return next((item for item in self.load().message_threads if item.id == thread_id), None)

    def list_message_threads_for_user(self, user_id: str) -> list[MessageThread]:
        threads = [
            item
            for item in self.load().message_threads
            if user_id in item.participantUserIds or item.ownerUserId == user_id or item.buyerUserId == user_id
        ]
        return sorted(threads, key=lambda item: item.lastMessageAt or item.updatedAt, reverse=True)

    def save_message_record(self, record: MessageRecord) -> None:
        state = self.load()
        state.message_records = [item for item in state.message_records if item.id != record.id]
        state.message_records.append(record)
        self.save(state)

    def list_message_records_for_thread(self, thread_id: str) -> list[MessageRecord]:
        records = [item for item in self.load().message_records if item.threadId == thread_id]
        return sorted(records, key=lambda item: item.createdAt)

    def save_import_notification(self, notification: ImportNotification) -> None:
        state = self.load()
        state.import_notifications = [item for item in state.import_notifications if item.id != notification.id]
        state.import_notifications.append(notification)
        self.save(state)

    def list_import_notifications(self) -> list[ImportNotification]:
        return self.load().import_notifications

    def get_sync_cursor(self, open_kfid: str) -> SyncCursor | None:
        return next((item for item in self.load().sync_cursors if item.openKfid == open_kfid), None)

    def save_sync_cursor(self, cursor: SyncCursor) -> None:
        state = self.load()
        state.sync_cursors = [item for item in state.sync_cursors if item.id != cursor.id]
        state.sync_cursors.append(cursor)
        self.save(state)

    def acquire_sync_lock(
        self,
        open_kfid: str,
        source: str,
        lock_token: str,
        now: str,
        stale_before: str,
    ) -> SyncCursor | None:
        state = self.load()
        existing = next((item for item in state.sync_cursors if item.openKfid == open_kfid), None)
        is_fresh_running = (
            existing
            and existing.syncStatus == "running"
            and existing.lockedAt
            and existing.lockedAt > stale_before
        )
        if is_fresh_running:
            return None
        cursor = SyncCursor(
            id=existing.id if existing else f"sync_cursor_{open_kfid}",
            openKfid=open_kfid,
            cursor=existing.cursor if existing else None,
            hasMore=existing.hasMore if existing else False,
            lastSource=source,
            lastPayload=existing.lastPayload if existing else {},
            lastSyncedAt=existing.lastSyncedAt if existing else now,
            syncStatus="running",
            lockToken=lock_token,
            lockedAt=now,
            lastError=None,
            createdAt=existing.createdAt if existing else now,
            updatedAt=now,
        )
        state.sync_cursors = [item for item in state.sync_cursors if item.id != cursor.id]
        state.sync_cursors.append(cursor)
        self.save(state)
        return cursor

    def release_sync_lock(
        self,
        open_kfid: str,
        lock_token: str,
        status: str,
        error_message: str | None,
        now: str,
    ) -> SyncCursor | None:
        state = self.load()
        existing = next((item for item in state.sync_cursors if item.openKfid == open_kfid), None)
        if not existing or existing.lockToken != lock_token:
            return existing
        existing.syncStatus = status
        existing.lockToken = None
        existing.lockedAt = None
        existing.lastError = error_message
        existing.updatedAt = now
        state.sync_cursors = [item for item in state.sync_cursors if item.id != existing.id]
        state.sync_cursors.append(existing)
        self.save(state)
        return existing

    def force_release_sync_lock(self, open_kfid: str, reason: str, now: str) -> SyncCursor | None:
        state = self.load()
        existing = next((item for item in state.sync_cursors if item.openKfid == open_kfid), None)
        if not existing:
            return None
        existing.syncStatus = "failed"
        existing.lockToken = None
        existing.lockedAt = None
        existing.lastError = reason
        existing.updatedAt = now
        state.sync_cursors = [item for item in state.sync_cursors if item.id != existing.id]
        state.sync_cursors.append(existing)
        self.save(state)
        return existing

    def save_media_retry_job(self, job: MediaRetryJob) -> None:
        state = self.load()
        state.media_retry_jobs = [item for item in state.media_retry_jobs if item.id != job.id]
        state.media_retry_jobs.append(job)
        self.save(state)

    def get_media_retry_job(self, media_id: str) -> MediaRetryJob | None:
        return next((item for item in self.load().media_retry_jobs if item.mediaId == media_id), None)

    def get_successful_media_url(self, media_id: str) -> str | None:
        job = self.get_media_retry_job(media_id)
        if job and job.status == "success":
            return job.localMediaUrl
        return None

    def list_media_retry_jobs(self, statuses: set[str] | None = None) -> list[MediaRetryJob]:
        jobs = self.load().media_retry_jobs
        return [item for item in jobs if statuses is None or item.status in statuses]

    def get_media_asset_by_original_hash(self, media_type: str, original_sha256: str) -> MediaAsset | None:
        return next(
            (
                item
                for item in self.load().media_assets
                if item.mediaType == media_type and item.originalSha256 == original_sha256 and item.status == "active"
            ),
            None,
        )

    def get_media_asset_by_storage_hash(self, media_type: str, storage_sha256: str) -> MediaAsset | None:
        return next(
            (
                item
                for item in self.load().media_assets
                if item.mediaType == media_type and item.storageSha256 == storage_sha256 and item.status == "active"
            ),
            None,
        )

    def get_media_asset_by_url(self, url: str) -> MediaAsset | None:
        return next((item for item in self.load().media_assets if item.url == url and item.status == "active"), None)

    def save_media_asset(self, asset: MediaAsset) -> bool:
        state = self.load()
        state.media_assets = [item for item in state.media_assets if item.id != asset.id]
        state.media_assets.append(asset)
        self.save(state)
        return True

    def save_media_asset_ref(self, ref: MediaAssetRef) -> None:
        state = self.load()
        state.media_asset_refs = [item for item in state.media_asset_refs if item.id != ref.id]
        state.media_asset_refs.append(ref)
        self.save(state)

    def list_media_asset_refs(
        self,
        asset_id: str | None = None,
        ref_type: str | None = None,
        ref_id: str | None = None,
    ) -> list[MediaAssetRef]:
        refs = self.load().media_asset_refs
        if asset_id:
            refs = [item for item in refs if item.assetId == asset_id]
        if ref_type:
            refs = [item for item in refs if item.refType == ref_type]
        if ref_id:
            refs = [item for item in refs if item.refId == ref_id]
        return sorted(refs, key=lambda item: item.createdAt, reverse=True)

    def delete_media_asset_refs(
        self,
        asset_id: str,
        ref_type: str | None = None,
        ref_id: str | None = None,
        usage: str | None = None,
    ) -> int:
        state = self.load()
        kept = []
        deleted = 0
        for item in state.media_asset_refs:
            matches = item.assetId == asset_id
            matches = matches and (ref_type is None or item.refType == ref_type)
            matches = matches and (ref_id is None or item.refId == ref_id)
            matches = matches and (usage is None or item.usage == usage)
            if matches:
                deleted += 1
            else:
                kept.append(item)
        if deleted:
            state.media_asset_refs = kept
            self.save(state)
        return deleted

    def save_sync_task(self, task: SyncTask) -> None:
        state = self.load()
        state.sync_tasks = [item for item in state.sync_tasks if item.id != task.id]
        state.sync_tasks.append(task)
        self.save(state)

    def list_sync_tasks(self, statuses: set[str] | None = None, limit: int = 50) -> list[SyncTask]:
        tasks = [item for item in self.load().sync_tasks if statuses is None or item.status in statuses]
        return sorted(tasks, key=lambda item: item.createdAt, reverse=True)[:limit]

    def claim_sync_task(self, task_id: str, worker_id: str, now: str, stale_before: str) -> SyncTask | None:
        state = self.load()
        task = next((item for item in state.sync_tasks if item.id == task_id), None)
        if not task:
            return None
        is_claimable = task.status in {"queued", "retrying"} or (
            task.status == "running" and task.lockedAt and task.lockedAt <= stale_before
        )
        if not is_claimable:
            return None
        task.status = "running"
        task.lockedBy = worker_id
        task.lockedAt = now
        task.updatedAt = now
        state.sync_tasks = [item for item in state.sync_tasks if item.id != task.id]
        state.sync_tasks.append(task)
        self.save(state)
        return task

    def update_sync_task(self, task: SyncTask) -> None:
        self.save_sync_task(task)

    def add_sync_task_log(self, log: SyncTaskLog) -> None:
        state = self.load()
        state.sync_task_logs.append(log)
        self.save(state)

    def list_sync_task_logs(self, task_id: str | None = None, limit: int = 100) -> list[SyncTaskLog]:
        logs = self.load().sync_task_logs
        if task_id:
            logs = [item for item in logs if item.taskId == task_id]
        return sorted(logs, key=lambda item: item.createdAt, reverse=True)[:limit]

    def save_skill_run(self, run: SkillRun) -> None:
        state = self.load()
        state.skill_runs = [item for item in state.skill_runs if item.id != run.id]
        state.skill_runs.append(run)
        self.save(state)

    def list_skill_runs(
        self,
        status: str | None = None,
        skill_id: str | None = None,
        limit: int = 100,
    ) -> list[SkillRun]:
        runs = self.load().skill_runs
        if status:
            runs = [item for item in runs if item.status == status]
        if skill_id:
            runs = [item for item in runs if item.skillId == skill_id]
        return sorted(runs, key=lambda item: item.startedAt, reverse=True)[:limit]

    def get_automation_device(self, device_id: str) -> AutomationDevice | None:
        return next((item for item in self.load().automation_devices if item.id == device_id), None)

    def list_automation_devices(self, limit: int = 100) -> list[AutomationDevice]:
        devices = sorted(
            self.load().automation_devices,
            key=lambda item: (item.updatedAt, item.id),
            reverse=True,
        )
        return devices[:limit]

    def save_automation_device(self, device: AutomationDevice) -> None:
        with self._automation_lock:
            state = self.load()
            state.automation_devices = [item for item in state.automation_devices if item.id != device.id]
            state.automation_devices.append(device)
            self.save(state)

    def get_automation_task(self, task_id: str) -> AutomationTask | None:
        return next((item for item in self.load().automation_tasks if item.id == task_id), None)

    def find_automation_task_by_idempotency_key(self, idempotency_key: str) -> AutomationTask | None:
        key = str(idempotency_key or "").strip()
        if not key:
            return None
        return next((item for item in self.load().automation_tasks if item.idempotencyKey == key), None)

    def save_automation_task(self, task: AutomationTask) -> None:
        with self._automation_lock:
            state = self.load()
            state.automation_tasks = [item for item in state.automation_tasks if item.id != task.id]
            state.automation_tasks.append(task)
            self.save(state)

    def list_automation_tasks(
        self,
        device_id: str | None = None,
        statuses: set[str] | None = None,
        limit: int = 50,
    ) -> list[AutomationTask]:
        tasks = self.load().automation_tasks
        if device_id:
            tasks = [item for item in tasks if item.deviceId == device_id]
        if statuses:
            tasks = [item for item in tasks if item.status in statuses]
        return sorted(tasks, key=lambda item: (item.createdAt, item.id), reverse=True)[:limit]

    def claim_next_automation_task(
        self,
        device_id: str,
        active_wechat_account_id: str | None,
        now: str,
        lease_expires_at: str,
        lease_token: str,
        function_ids: set[str] | None = None,
    ) -> AutomationTask | None:
        with self._automation_lock:
            state = self.load()
            active_tasks = []
            for item in state.automation_tasks:
                if item.deviceId != device_id or item.status != "running":
                    continue
                if not item.leaseExpiresAt:
                    active_tasks.append(item)
                    continue
                try:
                    if parse_iso(item.leaseExpiresAt) > parse_iso(now):
                        active_tasks.append(item)
                except Exception:
                    active_tasks.append(item)
            if active_tasks:
                return None

            candidates = []
            for item in state.automation_tasks:
                if item.deviceId != device_id:
                    continue
                if function_ids and item.functionId not in function_ids:
                    continue
                if item.status == "pending":
                    claimable = True
                elif item.status == "running" and item.leaseExpiresAt:
                    try:
                        claimable = parse_iso(item.leaseExpiresAt) <= parse_iso(now)
                    except Exception:
                        claimable = False
                else:
                    claimable = False
                if not claimable:
                    continue
                account_matches = (
                    item.targetWechatAccountId is None
                    or item.targetWechatAccountId == active_wechat_account_id
                    or item.functionId == "wechat.switch_account"
                )
                if account_matches:
                    candidates.append(item)
            if not candidates:
                return None
            task = sorted(candidates, key=lambda item: (item.createdAt, item.id))[0]
            updated = task.model_copy(
                update={
                    "status": "running",
                    "attempts": task.attempts + 1,
                    "leaseToken": lease_token,
                    "leaseExpiresAt": lease_expires_at,
                    "startedAt": task.startedAt or now,
                    "updatedAt": now,
                }
            )
            state.automation_tasks = [item for item in state.automation_tasks if item.id != task.id]
            state.automation_tasks.append(updated)
            self.save(state)
            return updated

    def get_automation_group_candidate(self, candidate_id: str) -> AutomationGroupCandidate | None:
        return next((item for item in self.load().automation_group_candidates if item.id == candidate_id), None)

    def find_automation_group_candidate_by_idempotency_key(self, idempotency_key: str) -> AutomationGroupCandidate | None:
        key = str(idempotency_key or "").strip()
        if not key:
            return None
        return next((item for item in self.load().automation_group_candidates if item.idempotencyKey == key), None)

    def save_automation_group_candidate(self, candidate: AutomationGroupCandidate) -> None:
        with self._automation_lock:
            state = self.load()
            state.automation_group_candidates = [
                item for item in state.automation_group_candidates if item.id != candidate.id
            ]
            state.automation_group_candidates.append(candidate)
            self.save(state)

    def list_automation_group_candidates(
        self,
        wechat_account_id: str | None = None,
        limit: int = 100,
    ) -> list[AutomationGroupCandidate]:
        candidates = self.load().automation_group_candidates
        if wechat_account_id:
            candidates = [item for item in candidates if item.wechatAccountId == wechat_account_id]
        return sorted(candidates, key=lambda item: (item.savedAt, item.id), reverse=True)[:limit]

    def get_wecom_archive_cursor(self, corp_id: str) -> WecomArchiveCursor | None:
        return next((item for item in self.load().wecom_archive_cursors if item.corpId == corp_id), None)

    def save_wecom_archive_cursor(self, cursor: WecomArchiveCursor) -> None:
        state = self.load()
        state.wecom_archive_cursors = [item for item in state.wecom_archive_cursors if item.id != cursor.id]
        state.wecom_archive_cursors.append(cursor)
        self.save(state)

    def save_wecom_archive_messages(self, messages: list[WecomArchiveMessage]) -> None:
        state = self.load()
        message_ids = {item.id for item in messages}
        state.wecom_archive_messages = [item for item in state.wecom_archive_messages if item.id not in message_ids]
        state.wecom_archive_messages.extend(messages)
        self.save(state)

    def existing_wecom_archive_msg_ids(self, msg_ids: set[str]) -> set[str]:
        if not msg_ids:
            return set()
        return {
            item.msgId
            for item in self.load().wecom_archive_messages
            if item.msgId and item.msgId in msg_ids
        }

    def get_wecom_archive_message_by_msg_id(self, msg_id: str) -> WecomArchiveMessage | None:
        return next((item for item in self.load().wecom_archive_messages if item.msgId == msg_id), None)

    def get_wecom_archive_message_by_generated_note_id(self, note_id: str) -> WecomArchiveMessage | None:
        return next((item for item in self.load().wecom_archive_messages if item.generatedNoteId == note_id), None)

    def list_wecom_archive_messages_by_generated_note_id(self, note_id: str) -> list[WecomArchiveMessage]:
        return sorted(
            [item for item in self.load().wecom_archive_messages if item.generatedNoteId == note_id],
            key=lambda item: (item.seq, item.createdAt),
        )

    def list_wecom_archive_messages(self, limit: int = 100) -> list[WecomArchiveMessage]:
        messages = self.load().wecom_archive_messages
        return sorted(messages, key=lambda item: (item.seq, item.createdAt), reverse=True)[:limit]

    def get_resource_wallet(self, owner_user_id: str) -> ResourceWallet | None:
        return next((item for item in self.load().resource_wallets if item.ownerUserId == owner_user_id), None)

    def save_resource_wallet(self, wallet: ResourceWallet) -> None:
        state = self.load()
        state.resource_wallets = [item for item in state.resource_wallets if item.id != wallet.id]
        state.resource_wallets.append(wallet)
        self.save(state)

    def save_resource_point_ledger(self, ledger: ResourcePointLedger) -> None:
        state = self.load()
        state.resource_point_ledgers = [item for item in state.resource_point_ledgers if item.id != ledger.id]
        state.resource_point_ledgers.append(ledger)
        self.save(state)

    def list_resource_point_ledgers(self, owner_user_id: str, limit: int = 100) -> list[ResourcePointLedger]:
        ledgers = [item for item in self.load().resource_point_ledgers if item.ownerUserId == owner_user_id]
        return sorted(ledgers, key=lambda item: item.createdAt, reverse=True)[:limit]

    def get_resource_free_quota(self, owner_user_id: str, quota_type: str, period_key: str) -> ResourceFreeQuota | None:
        return next(
            (
                item
                for item in self.load().resource_free_quotas
                if item.ownerUserId == owner_user_id and item.quotaType == quota_type and item.periodKey == period_key
            ),
            None,
        )

    def save_resource_free_quota(self, quota: ResourceFreeQuota) -> None:
        state = self.load()
        state.resource_free_quotas = [item for item in state.resource_free_quotas if item.id != quota.id]
        state.resource_free_quotas.append(quota)
        self.save(state)

    def find_resource_unlock_record(
        self,
        owner_user_id: str,
        action_type: str,
        target_type: str,
        target_id: str,
    ) -> ResourceUnlockRecord | None:
        records = [
            item
            for item in self.load().resource_unlock_records
            if item.ownerUserId == owner_user_id
            and item.actionType == action_type
            and item.targetType == target_type
            and item.targetId == target_id
        ]
        return sorted(records, key=lambda item: item.unlockedAt, reverse=True)[0] if records else None

    def save_resource_unlock_record(self, record: ResourceUnlockRecord) -> None:
        state = self.load()
        state.resource_unlock_records = [item for item in state.resource_unlock_records if item.id != record.id]
        state.resource_unlock_records.append(record)
        self.save(state)

    def list_opportunity_leads(self, statuses: set[str] | None = None, keyword: str | None = None) -> list[OpportunityLead]:
        leads = self.load().opportunity_leads
        if statuses:
            leads = [item for item in leads if item.status in statuses]
        clean_keyword = (keyword or "").strip().lower()
        if clean_keyword:
            leads = [
                item
                for item in leads
                if clean_keyword in item.title.lower()
                or clean_keyword in item.summary.lower()
                or clean_keyword in item.content.lower()
                or clean_keyword in (item.city or "").lower()
                or clean_keyword in (item.industry or "").lower()
            ]
        return sorted(leads, key=lambda item: item.publishedAt or item.updatedAt, reverse=True)

    def get_opportunity_lead(self, lead_id: str) -> OpportunityLead | None:
        return next((item for item in self.load().opportunity_leads if item.id == lead_id), None)

    def save_opportunity_lead(self, lead: OpportunityLead) -> None:
        state = self.load()
        state.opportunity_leads = [item for item in state.opportunity_leads if item.id != lead.id]
        state.opportunity_leads.append(lead)
        self.save(state)

    def list_opportunity_lead_sources(self, lead_id: str) -> list[OpportunityLeadSource]:
        sources = [item for item in self.load().opportunity_lead_sources if item.leadId == lead_id]
        return sorted(sources, key=lambda item: item.sourceCapturedAt, reverse=True)

    def save_opportunity_lead_source(self, source: OpportunityLeadSource) -> None:
        state = self.load()
        state.opportunity_lead_sources = [item for item in state.opportunity_lead_sources if item.id != source.id]
        state.opportunity_lead_sources.append(source)
        self.save(state)

    def list_opportunity_lead_contacts(self, lead_id: str) -> list[OpportunityLeadContact]:
        contacts = [item for item in self.load().opportunity_lead_contacts if item.leadId == lead_id]
        return sorted(contacts, key=lambda item: item.createdAt, reverse=True)

    def save_opportunity_lead_contact(self, contact: OpportunityLeadContact) -> None:
        state = self.load()
        state.opportunity_lead_contacts = [item for item in state.opportunity_lead_contacts if item.id != contact.id]
        state.opportunity_lead_contacts.append(contact)
        self.save(state)

    def get_opportunity_lead_save(self, lead_id: str, user_id: str) -> OpportunityLeadSave | None:
        return next(
            (item for item in self.load().opportunity_lead_saves if item.leadId == lead_id and item.userId == user_id),
            None,
        )

    def save_opportunity_lead_save(self, lead_save: OpportunityLeadSave) -> None:
        state = self.load()
        state.opportunity_lead_saves = [item for item in state.opportunity_lead_saves if item.id != lead_save.id]
        state.opportunity_lead_saves.append(lead_save)
        self.save(state)

    def list_opportunity_lead_saves_for_user(self, user_id: str) -> list[OpportunityLeadSave]:
        saves = [item for item in self.load().opportunity_lead_saves if item.userId == user_id]
        return sorted(saves, key=lambda item: item.updatedAt, reverse=True)

    def save_opportunity_lead_followup(self, followup: OpportunityLeadFollowup) -> None:
        state = self.load()
        state.opportunity_lead_followups = [item for item in state.opportunity_lead_followups if item.id != followup.id]
        state.opportunity_lead_followups.append(followup)
        self.save(state)

    def list_opportunity_lead_followups(self, lead_id: str, user_id: str | None = None) -> list[OpportunityLeadFollowup]:
        followups = [item for item in self.load().opportunity_lead_followups if item.leadId == lead_id]
        if user_id:
            followups = [item for item in followups if item.userId == user_id]
        return sorted(followups, key=lambda item: item.createdAt, reverse=True)

    def get_response_package(self, package_id: str) -> ResponsePackage | None:
        return next((item for item in self.load().response_packages if item.id == package_id), None)

    def get_response_package_for_lead_user(self, lead_id: str, owner_user_id: str) -> ResponsePackage | None:
        packages = [
            item
            for item in self.load().response_packages
            if item.leadId == lead_id and item.ownerUserId == owner_user_id and item.status != "archived"
        ]
        return sorted(packages, key=lambda item: item.updatedAt, reverse=True)[0] if packages else None

    def save_response_package(self, package: ResponsePackage) -> None:
        state = self.load()
        state.response_packages = [item for item in state.response_packages if item.id != package.id]
        state.response_packages.append(package)
        self.save(state)

    def list_response_package_items(self, package_id: str) -> list[ResponsePackageItem]:
        items = [item for item in self.load().response_package_items if item.responsePackageId == package_id]
        return sorted(items, key=lambda item: item.sortOrder)

    def save_response_package_item(self, item: ResponsePackageItem) -> None:
        state = self.load()
        state.response_package_items = [row for row in state.response_package_items if row.id != item.id]
        state.response_package_items.append(item)
        self.save(state)

    def save_response_package_event(self, event: ResponsePackageEvent) -> None:
        state = self.load()
        state.response_package_events = [item for item in state.response_package_events if item.id != event.id]
        state.response_package_events.append(event)
        self.save(state)

    def list_opportunity_subscriptions(self, owner_user_id: str) -> list[OpportunitySubscription]:
        rows = [
            item
            for item in self.load().opportunity_subscriptions
            if item.ownerUserId == owner_user_id and item.status != "deleted"
        ]
        return sorted(rows, key=lambda item: item.updatedAt, reverse=True)

    def save_opportunity_subscription(self, subscription: OpportunitySubscription) -> None:
        state = self.load()
        state.opportunity_subscriptions = [item for item in state.opportunity_subscriptions if item.id != subscription.id]
        state.opportunity_subscriptions.append(subscription)
        self.save(state)

    def list_supply_demand_cards(
        self,
        owner_user_id: str | None = None,
        statuses: set[str] | None = None,
        keyword: str | None = None,
    ) -> list[SupplyDemandCard]:
        rows = self.load().supply_demand_cards
        if owner_user_id:
            rows = [item for item in rows if item.ownerUserId == owner_user_id]
        if statuses:
            rows = [item for item in rows if item.status in statuses]
        q = (keyword or "").strip().lower()
        if q:
            rows = [
                item
                for item in rows
                if q in f"{item.title} {item.summary} {item.city or ''} {item.industry or ''} {item.demandType}".lower()
            ]
        return sorted(rows, key=lambda item: item.updatedAt, reverse=True)

    def get_supply_demand_card(self, card_id: str) -> SupplyDemandCard | None:
        return next((item for item in self.load().supply_demand_cards if item.id == card_id), None)

    def save_supply_demand_card(self, card: SupplyDemandCard) -> None:
        state = self.load()
        state.supply_demand_cards = [item for item in state.supply_demand_cards if item.id != card.id]
        state.supply_demand_cards.append(card)
        self.save(state)

    def list_supply_demand_applications(
        self,
        card_id: str | None = None,
        applicant_user_id: str | None = None,
        owner_user_id: str | None = None,
    ) -> list[SupplyDemandApplication]:
        rows = self.load().supply_demand_applications
        if card_id:
            rows = [item for item in rows if item.cardId == card_id]
        if applicant_user_id:
            rows = [item for item in rows if item.applicantUserId == applicant_user_id]
        if owner_user_id:
            rows = [item for item in rows if item.ownerUserId == owner_user_id]
        return sorted(rows, key=lambda item: item.updatedAt, reverse=True)

    def get_supply_demand_application(self, application_id: str) -> SupplyDemandApplication | None:
        return next((item for item in self.load().supply_demand_applications if item.id == application_id), None)

    def save_supply_demand_application(self, application: SupplyDemandApplication) -> None:
        state = self.load()
        state.supply_demand_applications = [item for item in state.supply_demand_applications if item.id != application.id]
        state.supply_demand_applications.append(application)
        self.save(state)

    def list_opportunity_push_digests(self, owner_user_id: str) -> list[OpportunityPushDigest]:
        rows = [item for item in self.load().opportunity_push_digests if item.ownerUserId == owner_user_id]
        return sorted(rows, key=lambda item: item.createdAt, reverse=True)

    def get_opportunity_push_digest(self, digest_id: str) -> OpportunityPushDigest | None:
        return next((item for item in self.load().opportunity_push_digests if item.id == digest_id), None)

    def save_opportunity_push_digest(self, digest: OpportunityPushDigest) -> None:
        state = self.load()
        state.opportunity_push_digests = [item for item in state.opportunity_push_digests if item.id != digest.id]
        state.opportunity_push_digests.append(digest)
        self.save(state)


class PostgresRepository:
    TABLES = {
        "users": "users",
        "wecom_identity_bindings": "wecom_identity_bindings",
        "wecom_bind_card_tokens": "wecom_bind_card_tokens",
        "wecom_bind_card_assets": "wecom_bind_card_assets",
        "import_batches": "import_batches",
        "raw_messages": "raw_messages",
        "cards": "cards",
        "user_notes": "user_notes",
        "showcase_pages": "showcase_pages",
        "live_qr_codes": "live_qr_codes",
        "view_events": "view_events",
        "showcase_events": "showcase_events",
        "relay_entries": "relay_entries",
        "lead_reminders": "lead_reminders",
        "customer_radar_summaries": "customer_radar_summaries",
        "customer_actions": "customer_actions",
        "message_threads": "message_threads",
        "message_records": "message_records",
        "categories": "categories",
        "topics": "topics",
        "import_notifications": "import_notifications",
        "sync_cursors": "sync_cursors",
        "media_retry_jobs": "media_retry_jobs",
        "media_assets": "media_assets",
        "media_asset_refs": "media_asset_refs",
        "sync_tasks": "sync_tasks",
        "sync_task_logs": "sync_task_logs",
        "skill_runs": "skill_runs",
        "automation_devices": "automation_devices",
        "automation_tasks": "automation_tasks",
        "automation_group_candidates": "automation_group_candidates",
        "wecom_archive_cursors": "wecom_archive_cursors",
        "wecom_archive_messages": "wecom_archive_messages",
        "resource_wallets": "resource_wallets",
        "resource_point_ledgers": "resource_point_ledgers",
        "resource_free_quotas": "resource_free_quotas",
        "resource_unlock_records": "resource_unlock_records",
        "opportunity_leads": "opportunity_leads",
        "opportunity_lead_sources": "opportunity_lead_sources",
        "opportunity_lead_contacts": "opportunity_lead_contacts",
        "opportunity_lead_matches": "opportunity_lead_matches",
        "opportunity_lead_saves": "opportunity_lead_saves",
        "opportunity_lead_followups": "opportunity_lead_followups",
        "response_packages": "response_packages",
        "response_package_items": "response_package_items",
        "response_package_events": "response_package_events",
        "opportunity_subscriptions": "opportunity_subscriptions",
        "supply_demand_cards": "supply_demand_cards",
        "supply_demand_applications": "supply_demand_applications",
        "opportunity_push_digests": "opportunity_push_digests",
        "membership_orders": "membership_orders",
        "membership_entitlements": "membership_entitlements",
        "mutual_point_accounts": "mutual_point_accounts",
        "mutual_point_ledgers": "mutual_point_ledgers",
        "mutual_recharge_orders": "mutual_recharge_orders",
        "mutual_activity_events": "mutual_activity_events",
        "notification_preferences": "notification_preferences",
        "wechat_subscription_grants": "wechat_subscription_grants",
        "wechat_subscription_deliveries": "wechat_subscription_deliveries",
        "referral_relations": "referral_relations",
        "referral_rewards": "referral_rewards",
        "referral_withdrawals": "referral_withdrawals",
        "same_style_generations": "same_style_generations",
    }
    FIELD_COLUMNS = {
        "users": [
            ("openid", "text", "openid"),
            ("nickname", "text", "nickname"),
        ],
        "wecom_identity_bindings": [
            ("source_type", "text", "sourceType"),
            ("external_user_id", "text", "externalUserId"),
            ("owner_user_id", "text", "ownerUserId"),
            ("owner_openid", "text", "ownerOpenid"),
            ("bind_source", "text", "bindSource"),
            ("first_import_batch_id", "text", "firstImportBatchId"),
            ("last_import_batch_id", "text", "lastImportBatchId"),
        ],
        "wecom_bind_card_tokens": [
            ("token_hash", "text", "tokenHash"),
            ("welcome_code_hash", "text", "welcomeCodeHash"),
            ("external_user_id", "text", "externalUserId"),
            ("status", "text", "status"),
            ("delivery_status", "text", "deliveryStatus"),
            ("expires_at", "timestamptz", "expiresAt"),
            ("used_at", "timestamptz", "usedAt"),
            ("owner_user_id", "text", "ownerUserId"),
            ("owner_openid", "text", "ownerOpenid"),
        ],
        "wecom_bind_card_assets": [
            ("source_sha256", "text", "sourceSha256"),
            ("media_id", "text", "mediaId"),
            ("media_id_expires_at", "timestamptz", "mediaIdExpiresAt"),
            ("status", "text", "status"),
        ],
        "import_batches": [
            ("external_user_id", "text", "externalUserId"),
            ("conversation_id", "text", "conversationId"),
            ("claimed_by_user_id", "text", "claimedByUserId"),
            ("status", "text", "status"),
            ("title_candidate", "text", "titleCandidate"),
            ("source_type", "text", "sourceType"),
            ("generated_card_id", "text", "generatedCardId"),
            ("generated_note_id", "text", "generatedNoteId"),
            ("started_at", "timestamptz", "startedAt"),
            ("ended_at", "timestamptz", "endedAt"),
        ],
        "raw_messages": [
            ("import_batch_id", "text", "importBatchId"),
            ("wecom_msg_id", "text", "wecomMsgId"),
            ("wecom_token", "text", "wecomToken"),
            ("open_kfid", "text", "openKfid"),
            ("external_user_id", "text", "externalUserId"),
            ("conversation_id", "text", "conversationId"),
            ("msg_type", "text", "msgType"),
            ("media_id", "text", "mediaId"),
            ("received_at", "timestamptz", "receivedAt"),
        ],
        "cards": [
            ("owner_user_id", "text", "ownerUserId"),
            ("import_batch_id", "text", "importBatchId"),
            ("source_card_id", "text", "sourceCardId"),
            ("status", "text", "status"),
            ("title", "text", "title"),
            ("published_at", "timestamptz", "publishedAt"),
        ],
        "user_notes": [
            ("owner_user_id", "text", "ownerUserId"),
            ("import_batch_id", "text", "importBatchId"),
            ("source_card_id", "text", "sourceCardId"),
            ("status", "text", "status"),
            ("title", "text", "title"),
            ("share_state", "text", "shareState"),
            ("intake_id", "text", "intakeId"),
            ("idempotency_key", "text", "idempotencyKey"),
            ("revision", "integer", "revision"),
        ],
        "showcase_pages": [
            ("owner_user_id", "text", "ownerUserId"),
            ("status", "text", "status"),
            ("name", "text", "name"),
            ("intake_id", "text", "intakeId"),
            ("idempotency_key", "text", "idempotencyKey"),
            ("published_at", "timestamptz", "publishedAt"),
        ],
        "live_qr_codes": [
            ("code", "text", "code"),
            ("status", "text", "status"),
            ("scan_count", "integer", "scanCount"),
            ("last_scanned_at", "timestamptz", "lastScannedAt"),
            ("target_expires_at", "timestamptz", "targetExpiresAt"),
            ("target_updated_at", "timestamptz", "targetUpdatedAt"),
        ],
        "view_events": [
            ("card_id", "text", "cardId"),
            ("viewer_user_id", "text", "viewerUserId"),
            ("view_type", "text", "viewType"),
            ("anonymous_id", "text", "anonymousId"),
            ("visitor_identity_id", "text", "visitorIdentityId"),
            ("share_id", "text", "shareId"),
            ("share_from_user_id", "text", "shareFromUserId"),
            ("scene", "text", "scene"),
            ("referrer", "text", "referrer"),
            ("date_key", "date", "dateKey"),
            ("viewed_at", "timestamptz", "viewedAt"),
        ],
        "showcase_events": [
            ("showcase_id", "text", "showcaseId"),
            ("owner_user_id", "text", "ownerUserId"),
            ("event_type", "text", "eventType"),
            ("note_id", "text", "noteId"),
            ("share_id", "text", "shareId"),
            ("share_from_user_id", "text", "shareFromUserId"),
            ("scene", "text", "scene"),
            ("referrer", "text", "referrer"),
            ("viewer_user_id", "text", "viewerUserId"),
            ("view_type", "text", "viewType"),
            ("anonymous_id", "text", "anonymousId"),
            ("date_key", "date", "dateKey"),
        ],
        "relay_entries": [
            ("card_id", "text", "cardId"),
            ("user_id", "text", "userId"),
            ("nickname", "text", "nickname"),
            ("status", "text", "status"),
            ("follow_up_status", "text", "followUpStatus"),
        ],
        "lead_reminders": [
            ("owner_user_id", "text", "ownerUserId"),
            ("card_id", "text", "cardId"),
            ("viewer_user_id", "text", "viewerUserId"),
            ("visitor_identity_id", "text", "visitorIdentityId"),
            ("status", "text", "status"),
            ("contacted_at", "timestamptz", "contactedAt"),
            ("version", "integer", "version"),
        ],
        "customer_radar_summaries": [
            ("owner_user_id", "text", "ownerUserId"),
            ("mode", "text", "mode"),
            ("pending_count", "integer", "pendingCount"),
            ("visitor_count", "integer", "visitorCount"),
            ("following_count", "integer", "followingCount"),
            ("abandoned_count", "integer", "abandonedCount"),
            ("high_intent_count", "integer", "highIntentCount"),
            ("interaction_count", "integer", "interactionCount"),
            ("revival_count", "integer", "revivalCount"),
            ("filtered_count", "integer", "filteredCount"),
            ("is_dirty", "boolean", "isDirty"),
            ("refreshed_at", "timestamptz", "refreshedAt"),
        ],
        "customer_actions": [
            ("owner_user_id", "text", "ownerUserId"),
            ("note_id", "text", "noteId"),
            ("source_card_id", "text", "sourceCardId"),
            ("viewer_user_id", "text", "viewerUserId"),
            ("anonymous_id", "text", "anonymousId"),
            ("visitor_identity_id", "text", "visitorIdentityId"),
            ("action_key", "text", "actionKey"),
        ],
        "message_threads": [
            ("note_id", "text", "noteId"),
            ("order_action_id", "text", "orderActionId"),
            ("owner_user_id", "text", "ownerUserId"),
            ("buyer_user_id", "text", "buyerUserId"),
            ("last_message_at", "timestamptz", "lastMessageAt"),
            ("status", "text", "status"),
        ],
        "message_records": [
            ("thread_id", "text", "threadId"),
            ("sender_user_id", "text", "senderUserId"),
        ],
        "categories": [
            ("owner_user_id", "text", "ownerUserId"),
            ("name", "text", "name"),
        ],
        "topics": [
            ("owner_user_id", "text", "ownerUserId"),
            ("name", "text", "name"),
        ],
        "import_notifications": [
            ("import_batch_id", "text", "importBatchId"),
            ("external_user_id", "text", "externalUserId"),
            ("conversation_id", "text", "conversationId"),
            ("status", "text", "status"),
            ("channel", "text", "channel"),
            ("sent_at", "timestamptz", "sentAt"),
        ],
        "sync_cursors": [
            ("open_kfid", "text", "openKfid"),
            ("cursor_value", "text", "cursor"),
            ("has_more", "boolean", "hasMore"),
            ("last_source", "text", "lastSource"),
            ("last_synced_at", "timestamptz", "lastSyncedAt"),
            ("sync_status", "text", "syncStatus"),
            ("lock_token", "text", "lockToken"),
            ("locked_at", "timestamptz", "lockedAt"),
            ("last_error", "text", "lastError"),
        ],
        "media_retry_jobs": [
            ("media_id", "text", "mediaId"),
            ("media_type", "text", "mediaType"),
            ("open_kfid", "text", "openKfid"),
            ("status", "text", "status"),
            ("attempts", "integer", "attempts"),
            ("last_attempt_at", "timestamptz", "lastAttemptAt"),
        ],
        "media_assets": [
            ("media_type", "text", "mediaType"),
            ("original_sha256", "text", "originalSha256"),
            ("storage_sha256", "text", "storageSha256"),
            ("url", "text", "url"),
            ("status", "text", "status"),
        ],
        "media_asset_refs": [
            ("asset_id", "text", "assetId"),
            ("owner_user_id", "text", "ownerUserId"),
            ("ref_type", "text", "refType"),
            ("ref_id", "text", "refId"),
            ("usage", "text", "usage"),
        ],
        "sync_tasks": [
            ("name", "text", "name"),
            ("status", "text", "status"),
            ("attempts", "integer", "attempts"),
            ("max_attempts", "integer", "maxAttempts"),
            ("next_run_at", "timestamptz", "nextRunAt"),
            ("locked_by", "text", "lockedBy"),
            ("locked_at", "timestamptz", "lockedAt"),
        ],
        "sync_task_logs": [
            ("task_id", "text", "taskId"),
            ("event", "text", "event"),
        ],
        "skill_runs": [
            ("skill_id", "text", "skillId"),
            ("status", "text", "status"),
            ("output_ref", "text", "outputRef"),
            ("model_provider", "text", "modelProvider"),
            ("started_at", "timestamptz", "startedAt"),
            ("ended_at", "timestamptz", "endedAt"),
        ],
        "automation_devices": [
            ("name", "text", "name"),
            ("platform", "text", "platform"),
            ("hid_device_id", "text", "hidDeviceId"),
            ("status", "text", "status"),
            ("active_wechat_account_id", "text", "activeWechatAccountId"),
            ("last_heartbeat_at", "timestamptz", "lastHeartbeatAt"),
        ],
        "automation_tasks": [
            ("function_id", "text", "functionId"),
            ("device_id", "text", "deviceId"),
            ("target_wechat_account_id", "text", "targetWechatAccountId"),
            ("status", "text", "status"),
            ("attempts", "integer", "attempts"),
            ("lease_token", "text", "leaseToken"),
            ("lease_expires_at", "timestamptz", "leaseExpiresAt"),
            ("idempotency_key", "text", "idempotencyKey"),
            ("started_at", "timestamptz", "startedAt"),
            ("finished_at", "timestamptz", "finishedAt"),
        ],
        "automation_group_candidates": [
            ("device_id", "text", "deviceId"),
            ("wechat_account_id", "text", "wechatAccountId"),
            ("group_qr_code", "text", "groupQRCode"),
            ("group_name", "text", "groupName"),
            ("saved_at", "timestamptz", "savedAt"),
            ("join_status", "text", "joinStatus"),
            ("can_send", "boolean", "canSend"),
            ("idempotency_key", "text", "idempotencyKey"),
        ],
        "wecom_archive_cursors": [
            ("corp_id", "text", "corpId"),
            ("seq", "bigint", "seq"),
            ("status", "text", "status"),
            ("last_synced_at", "timestamptz", "lastSyncedAt"),
            ("lock_token", "text", "lockToken"),
            ("locked_at", "timestamptz", "lockedAt"),
            ("last_error", "text", "lastError"),
        ],
        "wecom_archive_messages": [
            ("corp_id", "text", "corpId"),
            ("seq", "bigint", "seq"),
            ("msg_id", "text", "msgId"),
            ("action", "text", "action"),
            ("from_user", "text", "fromUser"),
            ("room_id", "text", "roomId"),
            ("msg_time", "timestamptz", "msgTime"),
            ("msg_type", "text", "msgType"),
            ("generated_note_id", "text", "generatedNoteId"),
            ("processed_at", "timestamptz", "processedAt"),
        ],
        "resource_wallets": [
            ("owner_user_id", "text", "ownerUserId"),
            ("balance", "integer", "balance"),
            ("status", "text", "status"),
        ],
        "resource_point_ledgers": [
            ("owner_user_id", "text", "ownerUserId"),
            ("wallet_id", "text", "walletId"),
            ("ledger_type", "text", "ledgerType"),
            ("action_type", "text", "actionType"),
            ("target_type", "text", "targetType"),
            ("target_id", "text", "targetId"),
            ("created_at_source", "timestamptz", "createdAt"),
        ],
        "resource_free_quotas": [
            ("owner_user_id", "text", "ownerUserId"),
            ("quota_type", "text", "quotaType"),
            ("period_key", "text", "periodKey"),
        ],
        "resource_unlock_records": [
            ("owner_user_id", "text", "ownerUserId"),
            ("action_type", "text", "actionType"),
            ("target_type", "text", "targetType"),
            ("target_id", "text", "targetId"),
            ("unlocked_at", "timestamptz", "unlockedAt"),
            ("expires_at", "timestamptz", "expiresAt"),
        ],
        "opportunity_leads": [
            ("title", "text", "title"),
            ("city", "text", "city"),
            ("district", "text", "district"),
            ("industry", "text", "industry"),
            ("demand_type", "text", "demandType"),
            ("contact_status", "text", "contactStatus"),
            ("trust_status", "text", "trustStatus"),
            ("status", "text", "status"),
            ("published_at", "timestamptz", "publishedAt"),
            ("expires_at", "timestamptz", "expiresAt"),
        ],
        "opportunity_lead_sources": [
            ("lead_id", "text", "leadId"),
            ("source_platform", "text", "sourcePlatform"),
            ("source_captured_at", "timestamptz", "sourceCapturedAt"),
        ],
        "opportunity_lead_contacts": [
            ("lead_id", "text", "leadId"),
            ("contact_type", "text", "contactType"),
            ("verify_status", "text", "verifyStatus"),
        ],
        "opportunity_lead_matches": [
            ("lead_id", "text", "leadId"),
            ("user_id", "text", "userId"),
            ("match_score", "integer", "matchScore"),
            ("status", "text", "status"),
        ],
        "opportunity_lead_saves": [
            ("lead_id", "text", "leadId"),
            ("user_id", "text", "userId"),
            ("status", "text", "status"),
            ("reminder_at", "timestamptz", "reminderAt"),
        ],
        "opportunity_lead_followups": [
            ("lead_id", "text", "leadId"),
            ("user_id", "text", "userId"),
            ("action_type", "text", "actionType"),
        ],
        "response_packages": [
            ("owner_user_id", "text", "ownerUserId"),
            ("lead_id", "text", "leadId"),
            ("status", "text", "status"),
            ("title", "text", "title"),
            ("sent_at", "timestamptz", "sentAt"),
            ("last_viewed_at", "timestamptz", "lastViewedAt"),
        ],
        "response_package_items": [
            ("response_package_id", "text", "responsePackageId"),
            ("asset_type", "text", "assetType"),
            ("asset_id", "text", "assetId"),
            ("sort_order", "integer", "sortOrder"),
        ],
        "response_package_events": [
            ("response_package_id", "text", "responsePackageId"),
            ("event_type", "text", "eventType"),
            ("viewer_id", "text", "viewerId"),
            ("anonymous_id", "text", "anonymousId"),
        ],
        "opportunity_subscriptions": [
            ("owner_user_id", "text", "ownerUserId"),
            ("status", "text", "status"),
            ("city", "text", "city"),
            ("direction", "text", "direction"),
        ],
        "supply_demand_cards": [
            ("owner_user_id", "text", "ownerUserId"),
            ("card_type", "text", "cardType"),
            ("status", "text", "status"),
            ("title", "text", "title"),
            ("city", "text", "city"),
            ("industry", "text", "industry"),
            ("published_at", "timestamptz", "publishedAt"),
        ],
        "supply_demand_applications": [
            ("card_id", "text", "cardId"),
            ("applicant_user_id", "text", "applicantUserId"),
            ("owner_user_id", "text", "ownerUserId"),
            ("status", "text", "status"),
        ],
        "opportunity_push_digests": [
            ("owner_user_id", "text", "ownerUserId"),
            ("subscription_id", "text", "subscriptionId"),
            ("status", "text", "status"),
            ("created_at_index", "timestamptz", "createdAt"),
        ],
        "membership_orders": [
            ("user_id", "text", "userId"),
            ("status", "text", "status"),
            ("payment_transaction_id", "text", "paymentTransactionId"),
            ("paid_at", "timestamptz", "paidAt"),
        ],
        "membership_entitlements": [
            ("user_id", "text", "userId"),
            ("entitlement_key", "text", "entitlementKey"),
            ("status", "text", "status"),
            ("expires_at", "timestamptz", "expiresAt"),
        ],
        "mutual_point_accounts": [
            ("user_id", "text", "userId"),
            ("balance", "integer", "balance"),
            ("updated_at_source", "timestamptz", "updatedAt"),
        ],
        "mutual_point_ledgers": [
            ("user_id", "text", "userId"),
            ("ledger_type", "text", "ledgerType"),
            ("points_delta", "integer", "pointsDelta"),
            ("related_order_id", "text", "relatedOrderId"),
            ("created_at_source", "timestamptz", "createdAt"),
        ],
        "mutual_recharge_orders": [
            ("user_id", "text", "userId"),
            ("points", "integer", "points"),
            ("amount_fen", "integer", "amountFen"),
            ("status", "text", "status"),
            ("payment_channel", "text", "paymentChannel"),
            ("payment_transaction_id", "text", "paymentTransactionId"),
            ("paid_at", "timestamptz", "paidAt"),
        ],
        "mutual_activity_events": [
            ("event_type", "text", "eventType"),
            ("user_id", "text", "userId"),
            ("task_id", "text", "taskId"),
            ("task_kind", "text", "taskKind"),
            ("idempotency_key", "text", "idempotencyKey"),
            ("created_at_source", "timestamptz", "createdAt"),
        ],
        "notification_preferences": [
            ("user_id", "text", "userId"),
            ("important_customer_view_enabled", "boolean", "importantCustomerViewEnabled"),
            ("ordinary_anonymous_view_enabled", "boolean", "ordinaryAnonymousViewEnabled"),
            ("updated_at_source", "timestamptz", "updatedAt"),
        ],
        "wechat_subscription_grants": [
            ("user_id", "text", "userId"),
            ("template_id", "text", "templateId"),
            ("request_id", "text", "requestId"),
            ("status", "text", "status"),
            ("source", "text", "source"),
            ("authorized_at", "timestamptz", "authorizedAt"),
            ("reserved_at", "timestamptz", "reservedAt"),
            ("consumed_at", "timestamptz", "consumedAt"),
            ("invalid_at", "timestamptz", "invalidAt"),
        ],
        "wechat_subscription_deliveries": [
            ("owner_user_id", "text", "ownerUserId"),
            ("grant_id", "text", "grantId"),
            ("template_id", "text", "templateId"),
            ("resource_type", "text", "resourceType"),
            ("resource_id", "text", "resourceId"),
            ("viewer_type", "text", "viewerType"),
            ("dedupe_key", "text", "dedupeKey"),
            ("status", "text", "status"),
            ("sent_at", "timestamptz", "sentAt"),
        ],
        "referral_relations": [
            ("inviter_user_id", "text", "inviterUserId"),
            ("invitee_user_id", "text", "inviteeUserId"),
        ],
        "referral_rewards": [
            ("inviter_user_id", "text", "inviterUserId"),
            ("invitee_user_id", "text", "inviteeUserId"),
            ("source_order_id", "text", "sourceOrderId"),
            ("status", "text", "status"),
        ],
        "referral_withdrawals": [
            ("user_id", "text", "userId"),
            ("status", "text", "status"),
        ],
        "same_style_generations": [
            ("owner_user_id", "text", "ownerUserId"),
            ("idempotency_key", "text", "idempotencyKey"),
            ("source_note_id", "text", "sourceNoteId"),
        ],
    }
    INDEXES = {
        "import_batches": [
            ("idx_import_batches_status", "status"),
            ("idx_import_batches_conversation", "external_user_id, conversation_id, started_at"),
            ("idx_import_batches_claimed_by", "claimed_by_user_id"),
        ],
        "wecom_identity_bindings": [
            ("idx_wecom_identity_bindings_source_external", "source_type, external_user_id"),
            ("idx_wecom_identity_bindings_owner", "owner_user_id, updated_at"),
        ],
        "wecom_bind_card_tokens": [
            ("idx_wecom_bind_card_tokens_welcome", "welcome_code_hash"),
            ("idx_wecom_bind_card_tokens_external", "external_user_id, status"),
            ("idx_wecom_bind_card_tokens_expiry", "expires_at"),
        ],
        "wecom_bind_card_assets": [
            ("idx_wecom_bind_card_assets_status", "status, updated_at desc"),
            ("idx_wecom_bind_card_assets_expiry", "media_id_expires_at"),
        ],
        "raw_messages": [
            ("idx_raw_messages_wecom_msg_id", "wecom_msg_id"),
            ("idx_raw_messages_open_kfid_token", "open_kfid, wecom_token"),
            ("idx_raw_messages_batch", "import_batch_id"),
            ("idx_raw_messages_conversation_time", "external_user_id, conversation_id, received_at"),
            ("idx_raw_messages_type", "msg_type"),
        ],
        "cards": [
            ("idx_cards_owner_status", "owner_user_id, status, updated_at"),
            ("idx_cards_import_batch", "import_batch_id"),
            ("idx_cards_source_card", "source_card_id"),
        ],
        "user_notes": [
            ("idx_user_notes_owner_status", "owner_user_id, status, updated_at"),
            ("idx_user_notes_import_batch", "import_batch_id"),
            ("idx_user_notes_source_card", "source_card_id"),
            ("idx_user_notes_title", "title"),
        ],
        "showcase_pages": [
            ("idx_showcase_pages_owner_status", "owner_user_id, status, updated_at"),
            ("idx_showcase_pages_published", "status, published_at"),
        ],
        "live_qr_codes": [
            ("idx_live_qr_codes_code", "code"),
            ("idx_live_qr_codes_status_updated", "status, updated_at"),
        ],
        "view_events": [
            ("idx_view_events_card_time", "card_id, viewed_at"),
            ("idx_view_events_card_date", "card_id, date_key"),
            ("idx_view_events_logged_viewer", "card_id, viewer_user_id"),
            ("idx_view_events_anonymous", "card_id, anonymous_id"),
            ("idx_view_events_visitor_identity", "card_id, visitor_identity_id"),
            ("idx_view_events_share", "card_id, share_id, viewed_at"),
        ],
        "showcase_events": [
            ("idx_showcase_events_showcase_time", "showcase_id, created_at"),
            ("idx_showcase_events_owner_time", "owner_user_id, created_at"),
            ("idx_showcase_events_type", "showcase_id, event_type, created_at"),
            ("idx_showcase_events_viewer", "showcase_id, viewer_user_id"),
            ("idx_showcase_events_anonymous", "showcase_id, anonymous_id"),
            ("idx_showcase_events_share", "showcase_id, share_id, created_at"),
        ],
        "relay_entries": [
            ("idx_relay_entries_card_status", "card_id, status, created_at"),
            ("idx_relay_entries_card_follow_up", "card_id, follow_up_status"),
            ("idx_relay_entries_user", "user_id"),
        ],
        "lead_reminders": [
            ("idx_lead_reminders_owner_status", "owner_user_id, status, updated_at"),
            ("idx_lead_reminders_card_viewer", "card_id, viewer_user_id"),
        ],
        "customer_radar_summaries": [
            ("idx_customer_radar_summaries_owner_dirty", "owner_user_id, is_dirty, updated_at"),
        ],
        "customer_actions": [
            ("idx_customer_actions_note_time", "note_id, created_at"),
            ("idx_customer_actions_owner_time", "owner_user_id, created_at"),
            ("idx_customer_actions_note_viewer", "note_id, viewer_user_id, action_key"),
            ("idx_customer_actions_note_anonymous", "note_id, anonymous_id, action_key"),
        ],
        "message_threads": [
            ("idx_message_threads_owner_time", "owner_user_id, last_message_at"),
            ("idx_message_threads_buyer_time", "buyer_user_id, last_message_at"),
            ("idx_message_threads_note", "note_id"),
            ("idx_message_threads_order", "order_action_id"),
        ],
        "message_records": [
            ("idx_message_records_thread_time", "thread_id, created_at"),
        ],
        "topics": [
            ("idx_topics_owner_name", "owner_user_id, name"),
        ],
        "sync_cursors": [
            ("idx_sync_cursors_open_kfid", "open_kfid"),
            ("idx_sync_cursors_last_synced", "last_synced_at"),
        ],
        "media_retry_jobs": [
            ("idx_media_retry_jobs_status", "status, updated_at"),
            ("idx_media_retry_jobs_media_id", "media_id"),
        ],
        "media_assets": [
            ("idx_media_assets_original_hash", "media_type, original_sha256"),
            ("idx_media_assets_storage_hash", "media_type, storage_sha256"),
            ("idx_media_assets_url", "url"),
        ],
        "media_asset_refs": [
            ("idx_media_asset_refs_asset", "asset_id, created_at"),
            ("idx_media_asset_refs_ref", "ref_type, ref_id"),
            ("idx_media_asset_refs_owner", "owner_user_id, created_at"),
        ],
        "sync_tasks": [
            ("idx_sync_tasks_ready", "status, next_run_at, created_at"),
            ("idx_sync_tasks_name_status", "name, status, updated_at"),
            ("idx_sync_tasks_locked", "locked_by, locked_at"),
        ],
        "sync_task_logs": [
            ("idx_sync_task_logs_task_time", "task_id, created_at"),
        ],
        "skill_runs": [
            ("idx_skill_runs_status_time", "status, started_at"),
            ("idx_skill_runs_skill_time", "skill_id, started_at"),
            ("idx_skill_runs_output_ref", "output_ref"),
        ],
        "automation_devices": [
            ("idx_automation_devices_heartbeat", "status, last_heartbeat_at"),
        ],
        "automation_tasks": [
            ("idx_automation_tasks_device_status", "device_id, status, created_at"),
            ("idx_automation_tasks_ready", "device_id, status, created_at"),
            ("idx_automation_tasks_idempotency", "idempotency_key"),
        ],
        "automation_group_candidates": [
            ("idx_automation_group_candidates_account_time", "wechat_account_id, saved_at"),
            ("idx_automation_group_candidates_qr", "group_qr_code"),
            ("idx_automation_group_candidates_idempotency", "idempotency_key"),
        ],
        "wecom_archive_cursors": [
            ("idx_wecom_archive_cursors_corp", "corp_id"),
            ("idx_wecom_archive_cursors_status", "status, updated_at"),
        ],
        "wecom_archive_messages": [
            ("idx_wecom_archive_messages_corp_seq", "corp_id, seq"),
            ("idx_wecom_archive_messages_msg_id", "msg_id"),
            ("idx_wecom_archive_messages_type_time", "msg_type, msg_time"),
            ("idx_wecom_archive_messages_generated_note", "generated_note_id"),
        ],
        "resource_wallets": [
            ("idx_resource_wallets_owner", "owner_user_id"),
        ],
        "resource_point_ledgers": [
            ("idx_resource_point_ledgers_owner_time", "owner_user_id, created_at_source"),
            ("idx_resource_point_ledgers_target", "owner_user_id, action_type, target_type, target_id"),
        ],
        "resource_free_quotas": [
            ("idx_resource_free_quotas_owner_type", "owner_user_id, quota_type, period_key"),
        ],
        "resource_unlock_records": [
            ("idx_resource_unlock_records_target", "owner_user_id, action_type, target_type, target_id"),
            ("idx_resource_unlock_records_expiry", "expires_at"),
        ],
        "opportunity_leads": [
            ("idx_opportunity_leads_status_time", "status, published_at, updated_at"),
            ("idx_opportunity_leads_city_industry", "city, industry"),
            ("idx_opportunity_leads_expires", "expires_at"),
        ],
        "opportunity_lead_sources": [
            ("idx_opportunity_lead_sources_lead", "lead_id, source_captured_at"),
        ],
        "opportunity_lead_contacts": [
            ("idx_opportunity_lead_contacts_lead", "lead_id, verify_status"),
        ],
        "opportunity_lead_matches": [
            ("idx_opportunity_lead_matches_user_score", "user_id, match_score"),
            ("idx_opportunity_lead_matches_lead_user", "lead_id, user_id"),
        ],
        "opportunity_lead_saves": [
            ("idx_opportunity_lead_saves_user_status", "user_id, status, updated_at"),
            ("idx_opportunity_lead_saves_lead_user", "lead_id, user_id"),
        ],
        "opportunity_lead_followups": [
            ("idx_opportunity_lead_followups_lead_user", "lead_id, user_id, created_at"),
        ],
        "response_packages": [
            ("idx_response_packages_owner_time", "owner_user_id, updated_at"),
            ("idx_response_packages_lead_owner", "lead_id, owner_user_id"),
        ],
        "response_package_items": [
            ("idx_response_package_items_package", "response_package_id, sort_order"),
        ],
        "response_package_events": [
            ("idx_response_package_events_package_time", "response_package_id, created_at"),
        ],
        "opportunity_subscriptions": [
            ("idx_opportunity_subscriptions_owner_status", "owner_user_id, status, updated_at"),
        ],
        "supply_demand_cards": [
            ("idx_supply_demand_cards_status_time", "status, updated_at"),
            ("idx_supply_demand_cards_owner_status", "owner_user_id, status, updated_at"),
            ("idx_supply_demand_cards_type_status", "card_type, status, updated_at"),
        ],
        "supply_demand_applications": [
            ("idx_supply_demand_apps_card_status", "card_id, status, updated_at"),
            ("idx_supply_demand_apps_owner_status", "owner_user_id, status, updated_at"),
            ("idx_supply_demand_apps_applicant", "applicant_user_id, updated_at"),
        ],
        "opportunity_push_digests": [
            ("idx_opportunity_push_owner_status", "owner_user_id, status, created_at_index"),
        ],
        "membership_orders": [
            ("idx_membership_orders_user_status", "user_id, status, updated_at"),
            ("idx_membership_orders_transaction", "payment_transaction_id"),
        ],
        "membership_entitlements": [
            ("idx_membership_entitlements_user_expiry", "user_id, status, expires_at"),
        ],
        "mutual_point_accounts": [
            ("idx_mutual_point_accounts_user", "user_id"),
        ],
        "mutual_point_ledgers": [
            ("idx_mutual_point_ledgers_user_time", "user_id, created_at_source"),
            ("idx_mutual_point_ledgers_order", "related_order_id"),
        ],
        "mutual_recharge_orders": [
            ("idx_mutual_recharge_orders_user_status", "user_id, status, created_at"),
            ("idx_mutual_recharge_orders_transaction", "payment_transaction_id"),
        ],
        "mutual_activity_events": [
            ("idx_mutual_activity_events_type_time", "event_type, created_at_source"),
            ("idx_mutual_activity_events_user_time", "user_id, created_at_source"),
            ("idx_mutual_activity_events_idempotency", "idempotency_key"),
        ],
        "notification_preferences": [
            ("idx_notification_preferences_user", "user_id"),
        ],
        "wechat_subscription_grants": [
            ("idx_wechat_subscription_grants_user_status", "user_id, template_id, status, authorized_at"),
        ],
        "wechat_subscription_deliveries": [
            ("idx_wechat_subscription_deliveries_owner_time", "owner_user_id, created_at"),
            ("idx_wechat_subscription_deliveries_dedupe", "dedupe_key"),
            ("idx_wechat_subscription_deliveries_status", "status, updated_at"),
        ],
        "referral_relations": [
            ("idx_referral_relations_inviter", "inviter_user_id, created_at"),
        ],
        "referral_rewards": [
            ("idx_referral_rewards_inviter_status", "inviter_user_id, status, updated_at"),
            ("idx_referral_rewards_order", "source_order_id"),
        ],
        "referral_withdrawals": [
            ("idx_referral_withdrawals_user_status", "user_id, status, updated_at"),
        ],
        "same_style_generations": [
            ("idx_same_style_owner_time", "owner_user_id, created_at"),
        ],
    }

    def __init__(self, database_url: str):
        self.database_url = normalize_database_url(database_url)
        self._pool = ConnectionPool(
            self.database_url,
            min_size=1,
            max_size=8,
            timeout=5,
            open=False,
        )
        self._pool.open()
        self.init_schema()

    @contextmanager
    def _connection(self, row_factory=None):
        with self._pool.connection() as conn:
            previous_row_factory = conn.row_factory
            conn.row_factory = row_factory or tuple_row
            try:
                yield conn
            finally:
                conn.row_factory = previous_row_factory or tuple_row

    def close(self) -> None:
        self._pool.close()

    def load(self) -> AppState:
        payload: dict[str, list[dict]] = {}
        with self._connection(row_factory=dict_row) as conn:
            for state_key, table_name in self.TABLES.items():
                rows = conn.execute(f"select payload from {table_name} order by created_at, id").fetchall()
                payload[state_key] = [row["payload"] for row in rows]
        return AppState.model_validate(payload)

    def save(self, state: AppState) -> None:
        with self._connection() as conn:
            with conn.transaction():
                for state_key, table_name in self.TABLES.items():
                    items = getattr(state, state_key)
                    conn.execute(f"delete from {table_name}")
                    for item in items:
                        payload = item.model_dump(mode="json")
                        self._upsert_payload(conn, table_name, payload)

    def get_payload_by_id(self, table_name: str, item_id: str) -> dict | None:
        self._ensure_known_table(table_name)
        with self._connection(row_factory=dict_row) as conn:
            row = conn.execute(f"select payload from {table_name} where id = %s", (item_id,)).fetchone()
        return row["payload"] if row else None

    def list_import_batches_by_status(self, batch_status: str) -> list[dict]:
        return self._list_payloads(
            "import_batches",
            "status = %s",
            (batch_status,),
            "started_at desc, id desc",
        )

    def get_user(self, user_id: str) -> User | None:
        payload = self.get_payload_by_id("users", user_id)
        return User.model_validate(payload) if payload else None

    def get_user_by_openid(self, openid: str) -> User | None:
        rows = self._list_payloads("users", "openid = %s", (openid,), "created_at desc, id desc")
        return User.model_validate(rows[0]) if rows else None

    def save_user(self, user: User) -> None:
        self._save_model("users", user)

    def get_membership_records(
        self,
        user_id: str,
    ) -> tuple[list[MembershipOrder], list[MembershipEntitlement]]:
        with self._connection(row_factory=dict_row) as conn:
            order_rows = conn.execute(
                "select payload from membership_orders where user_id = %s order by created_at desc, id desc",
                (user_id,),
            ).fetchall()
            entitlement_rows = conn.execute(
                "select payload from membership_entitlements where user_id = %s order by expires_at desc, id desc",
                (user_id,),
            ).fetchall()
        return (
            [MembershipOrder.model_validate(row["payload"]) for row in order_rows],
            [MembershipEntitlement.model_validate(row["payload"]) for row in entitlement_rows],
        )

    def get_wecom_identity_binding(self, source_type: str, external_user_id: str) -> WecomIdentityBinding | None:
        rows = self._list_payloads(
            "wecom_identity_bindings",
            "source_type = %s and external_user_id = %s",
            (source_type, external_user_id),
            "updated_at desc, id desc",
        )
        return WecomIdentityBinding.model_validate(rows[0]) if rows else None

    def save_wecom_identity_binding(self, binding: WecomIdentityBinding) -> None:
        self._save_model("wecom_identity_bindings", binding)

    def get_wecom_bind_card_token(self, token_hash: str) -> WecomBindCardToken | None:
        rows = self._list_payloads(
            "wecom_bind_card_tokens",
            "token_hash = %s",
            (token_hash,),
            "updated_at desc, id desc",
        )
        return WecomBindCardToken.model_validate(rows[0]) if rows else None

    def get_pending_wecom_bind_card_token(self, welcome_code_hash: str) -> WecomBindCardToken | None:
        rows = self._list_payloads(
            "wecom_bind_card_tokens",
            "welcome_code_hash = %s",
            (welcome_code_hash,),
            "updated_at desc, id desc",
        )
        return WecomBindCardToken.model_validate(rows[0]) if rows else None

    def save_wecom_bind_card_token(self, token: WecomBindCardToken) -> None:
        self._save_model("wecom_bind_card_tokens", token)

    def get_active_wecom_bind_card_asset(self) -> WecomBindCardAsset | None:
        rows = self._list_payloads(
            "wecom_bind_card_assets",
            "status = %s",
            ("active",),
            "updated_at desc, id desc",
        )
        return WecomBindCardAsset.model_validate(rows[0]) if rows else None

    def get_latest_wecom_bind_card_asset(self) -> WecomBindCardAsset | None:
        rows = self._list_payloads(
            "wecom_bind_card_assets",
            "true",
            (),
            "updated_at desc, id desc",
        )
        return WecomBindCardAsset.model_validate(rows[0]) if rows else None

    def save_wecom_bind_card_asset(self, asset: WecomBindCardAsset) -> None:
        self._save_model("wecom_bind_card_assets", asset)

    def consume_wecom_bind_card_token(
        self,
        token_hash: str,
        owner_user_id: str,
        owner_openid: str,
        now: str,
    ) -> WecomBindCardToken | None:
        self._ensure_known_table("wecom_bind_card_tokens")
        with self._connection(row_factory=dict_row) as conn:
            with conn.transaction():
                row = conn.execute(
                    """
                    select payload
                    from wecom_bind_card_tokens
                    where token_hash = %s
                    for update
                    """,
                    (token_hash,),
                ).fetchone()
                if not row:
                    return None
                token = WecomBindCardToken.model_validate(row["payload"])
                if token.status != "issued" or token.deliveryStatus != "sent":
                    return None
                try:
                    if parse_iso(token.expiresAt) <= parse_iso(now):
                        return None
                except Exception:
                    return None
                consumed = token.model_copy(
                    update={
                        "status": "consumed",
                        "usedAt": now,
                        "ownerUserId": owner_user_id,
                        "ownerOpenid": owner_openid,
                        "updatedAt": now,
                    }
                )
                self._upsert_payload(conn, "wecom_bind_card_tokens", consumed.model_dump(mode="json"))
                return consumed

    def list_import_batches(self, statuses: set[str] | None = None) -> list[ImportBatch]:
        if statuses:
            rows = self._list_payloads(
                "import_batches",
                "status = any(%s)",
                (list(statuses),),
                "started_at desc, id desc",
            )
        else:
            rows = self._list_payloads("import_batches", "true", (), "started_at desc, id desc")
        return [ImportBatch.model_validate(row) for row in rows]

    def get_import_batch(self, import_id: str) -> ImportBatch | None:
        payload = self.get_payload_by_id("import_batches", import_id)
        return ImportBatch.model_validate(payload) if payload else None

    def save_import_batch(self, batch: ImportBatch) -> None:
        self._save_model("import_batches", batch)

    def list_user_notes(
        self,
        owner_user_id: str,
        keyword: str | None = None,
        category_id: str | None = None,
        include_deleted: bool = False,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[UserNote]:
        where_parts = ["owner_user_id = %s"]
        params: list[str] = [owner_user_id]
        if not include_deleted:
            where_parts.append("status <> 'deleted'")
        if keyword:
            where_parts.append("(title ilike %s or payload->>'summary' ilike %s)")
            params.extend([f"%{keyword}%", f"%{keyword}%"])
        if category_id:
            where_parts.append("payload->'categoryIds' ? %s")
            params.append(category_id)
        limit_sql = ""
        if limit is not None:
            safe_limit = max(1, min(int(limit), 10000))
            safe_offset = max(int(offset or 0), 0)
            limit_sql = f" limit {safe_limit} offset {safe_offset}"
        rows = self._list_payloads(
            "user_notes",
            " and ".join(where_parts),
            tuple(params),
            "updated_at desc, id desc",
            limit_sql=limit_sql,
        )
        return [UserNote.model_validate(row) for row in rows]

    def list_standalone_user_notes(
        self,
        owner_user_id: str,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[UserNote]:
        limit_sql = ""
        if limit is not None:
            safe_limit = max(1, min(int(limit), 10000))
            safe_offset = max(int(offset or 0), 0)
            limit_sql = f" limit {safe_limit} offset {safe_offset}"
        rows = self._list_payloads(
            "user_notes",
            "owner_user_id = %s and status <> 'deleted' and source_card_id is null",
            (owner_user_id,),
            "updated_at desc, id desc",
            limit_sql=limit_sql,
        )
        return [UserNote.model_validate(row) for row in rows]

    def list_user_notes_by_source_card_ids(
        self,
        owner_user_id: str,
        source_card_ids: set[str],
    ) -> list[UserNote]:
        if not source_card_ids:
            return []
        rows = self._list_payloads(
            "user_notes",
            "owner_user_id = %s and status <> 'deleted' and source_card_id = any(%s)",
            (owner_user_id, list(source_card_ids)),
            "updated_at desc, id desc",
        )
        return [UserNote.model_validate(row) for row in rows]

    def list_all_user_notes(self, include_deleted: bool = False) -> list[UserNote]:
        where = "true" if include_deleted else "status <> 'deleted'"
        rows = self._list_payloads("user_notes", where, (), "updated_at desc, id desc")
        return [UserNote.model_validate(row) for row in rows]

    def get_user_note(self, note_id: str) -> UserNote | None:
        payload = self.get_payload_by_id("user_notes", note_id)
        return UserNote.model_validate(payload) if payload else None

    def save_user_note(self, note: UserNote) -> None:
        self._save_model("user_notes", note)

    def list_showcase_pages(self, owner_user_id: str) -> list[ShowcasePage]:
        rows = self._list_payloads(
            "showcase_pages",
            "owner_user_id = %s",
            (owner_user_id,),
            "updated_at desc, id desc",
        )
        return [ShowcasePage.model_validate(row) for row in rows]

    def get_showcase_page(self, showcase_id: str) -> ShowcasePage | None:
        payload = self.get_payload_by_id("showcase_pages", showcase_id)
        return ShowcasePage.model_validate(payload) if payload else None

    def save_showcase_page(self, showcase: ShowcasePage) -> None:
        self._save_model("showcase_pages", showcase)

    def get_live_qr_code(self, qr_id: str) -> LiveQrCode | None:
        payload = self.get_payload_by_id("live_qr_codes", qr_id)
        return LiveQrCode.model_validate(payload) if payload else None

    def get_live_qr_code_by_code(self, code: str) -> LiveQrCode | None:
        rows = self._list_payloads(
            "live_qr_codes",
            "code = %s",
            (code,),
            "updated_at desc, id desc",
        )
        return LiveQrCode.model_validate(rows[0]) if rows else None

    def list_live_qr_codes(self) -> list[LiveQrCode]:
        rows = self._list_payloads("live_qr_codes", "true", (), "updated_at desc, id desc")
        return [LiveQrCode.model_validate(row) for row in rows]

    def save_live_qr_code(self, qr_code: LiveQrCode) -> None:
        self._save_model("live_qr_codes", qr_code)

    def delete_live_qr_code(self, qr_id: str) -> bool:
        self._ensure_known_table("live_qr_codes")
        with self._connection() as conn:
            result = conn.execute("delete from live_qr_codes where id = %s", (qr_id,))
        return bool(result.rowcount)

    def record_live_qr_scan(self, code: str, scanned_at: str) -> LiveQrCode | None:
        self._ensure_known_table("live_qr_codes")
        with self._connection(row_factory=dict_row) as conn:
            with conn.transaction():
                row = conn.execute(
                    """
                    update live_qr_codes
                    set scan_count = coalesce(scan_count, 0) + 1,
                        last_scanned_at = %s,
                        payload = jsonb_set(
                            jsonb_set(
                                payload,
                                '{scanCount}',
                                to_jsonb(coalesce(scan_count, 0) + 1),
                                true
                            ),
                            '{lastScannedAt}',
                            to_jsonb(%s::text),
                            true
                        )
                    where code = %s
                      and status = 'active'
                      and (target_expires_at is null or target_expires_at > %s)
                    returning payload
                    """,
                    (scanned_at, scanned_at, code, scanned_at),
                ).fetchone()
        return LiveQrCode.model_validate(row["payload"]) if row else None

    def list_referral_relations(self) -> list[ReferralRelation]:
        rows = self._list_payloads("referral_relations", "true", (), "created_at asc, id asc")
        return [ReferralRelation.model_validate(row) for row in rows]

    def find_same_style_generation(
        self,
        owner_user_id: str,
        idempotency_key: str,
    ) -> SameStyleGeneration | None:
        rows = self._list_payloads(
            "same_style_generations",
            "owner_user_id = %s and idempotency_key = %s",
            (owner_user_id, idempotency_key),
            "created_at desc, id desc",
        )
        return SameStyleGeneration.model_validate(rows[0]) if rows else None

    def find_latest_same_style_generation(
        self,
        owner_user_id: str,
        mode: str,
        source_note_id: str | None = None,
        source_showcase_id: str | None = None,
    ) -> SameStyleGeneration | None:
        where_parts = ["owner_user_id = %s", "payload->>'mode' = %s"]
        params: list[str] = [owner_user_id, mode]
        if source_note_id:
            where_parts.append("source_note_id = %s")
            params.append(source_note_id)
        else:
            where_parts.append("source_note_id is null")
        if source_showcase_id:
            where_parts.append("payload->>'sourceShowcaseId' = %s")
            params.append(source_showcase_id)
        else:
            where_parts.append("payload->>'sourceShowcaseId' is null")
        rows = self._list_payloads(
            "same_style_generations",
            " and ".join(where_parts),
            tuple(params),
            "created_at desc, id desc",
        )
        return SameStyleGeneration.model_validate(rows[0]) if rows else None

    def list_same_style_generations(self, owner_user_id: str) -> list[SameStyleGeneration]:
        rows = self._list_payloads(
            "same_style_generations",
            "owner_user_id = %s",
            (owner_user_id,),
            "created_at desc, id desc",
        )
        return [SameStyleGeneration.model_validate(row) for row in rows]

    def save_same_style_generation(
        self,
        generation: SameStyleGeneration,
        referral_relation: ReferralRelation | None = None,
    ) -> None:
        with self._connection() as conn:
            with conn.transaction():
                if referral_relation:
                    self._upsert_payload(conn, "referral_relations", referral_relation.model_dump(mode="json"))
                self._upsert_payload(conn, "same_style_generations", generation.model_dump(mode="json"))

    def delete_showcase_page(self, showcase_id: str) -> None:
        with self._connection() as conn:
            conn.execute("delete from showcase_events where showcase_id = %s", (showcase_id,))
            conn.execute("delete from showcase_pages where id = %s", (showcase_id,))

    def save_raw_messages(self, messages: list[RawMessage]) -> None:
        with self._connection() as conn:
            with conn.transaction():
                for message in messages:
                    self._upsert_payload(conn, "raw_messages", message.model_dump(mode="json"))

    def existing_wecom_msg_ids(self, wecom_msg_ids: set[str]) -> set[str]:
        if not wecom_msg_ids:
            return set()
        with self._connection(row_factory=dict_row) as conn:
            rows = conn.execute(
                "select wecom_msg_id from raw_messages where wecom_msg_id = any(%s)",
                (list(wecom_msg_ids),),
            ).fetchall()
        return {row["wecom_msg_id"] for row in rows if row["wecom_msg_id"]}

    def save_import_artifacts(
        self,
        batch: ImportBatch,
        raw_messages: list[RawMessage],
        card: Card,
        notification: ImportNotification,
    ) -> None:
        with self._connection() as conn:
            with conn.transaction():
                self._upsert_payload(conn, "import_batches", batch.model_dump(mode="json"))
                for message in raw_messages:
                    self._upsert_payload(conn, "raw_messages", message.model_dump(mode="json"))
                self._upsert_payload(conn, "cards", card.model_dump(mode="json"))
                self._upsert_payload(conn, "import_notifications", notification.model_dump(mode="json"))

    def list_raw_messages_for_batch(self, import_batch_id: str) -> list[RawMessage]:
        rows = self._list_payloads(
            "raw_messages",
            "import_batch_id = %s",
            (import_batch_id,),
            "received_at asc, id asc",
        )
        return [RawMessage.model_validate(row) for row in rows]

    def get_card(self, card_id: str) -> Card | None:
        payload = self.get_payload_by_id("cards", card_id)
        return Card.model_validate(payload) if payload else None

    def list_cards_by_owner(self, owner_user_id: str, card_status: str | None = None) -> list[dict]:
        if card_status:
            return self._list_payloads(
                "cards",
                "owner_user_id = %s and status = %s",
                (owner_user_id, card_status),
                "updated_at desc, id desc",
            )
        return self._list_payloads(
            "cards",
            "owner_user_id = %s",
            (owner_user_id,),
            "updated_at desc, id desc",
        )

    def list_cards(
        self,
        owner_user_id: str | None = None,
        keyword: str | None = None,
        category_id: str | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[Card]:
        where_parts = ["true"]
        params: list[str] = []
        if owner_user_id:
            where_parts.append("owner_user_id = %s")
            params.append(owner_user_id)
        if keyword:
            where_parts.append("title ilike %s")
            params.append(f"%{keyword}%")
        if category_id:
            where_parts.append("payload->'categoryIds' ? %s")
            params.append(category_id)
        limit_sql = ""
        if limit is not None:
            safe_limit = max(1, min(int(limit), 10000))
            safe_offset = max(int(offset or 0), 0)
            limit_sql = f" limit {safe_limit} offset {safe_offset}"
        rows = self._list_payloads(
            "cards",
            " and ".join(where_parts),
            tuple(params),
            "updated_at desc, id desc",
            limit_sql=limit_sql,
        )
        return [Card.model_validate(row) for row in rows]

    def save_card(self, card: Card) -> None:
        self._save_model("cards", card)

    def delete_card(self, card_id: str) -> None:
        with self._connection() as conn:
            conn.execute("delete from relay_entries where card_id = %s", (card_id,))
            conn.execute("delete from view_events where card_id = %s", (card_id,))
            conn.execute("delete from lead_reminders where card_id = %s", (card_id,))
            conn.execute("delete from customer_actions where source_card_id = %s", (card_id,))
            conn.execute("delete from cards where id = %s", (card_id,))

    def list_categories(self, owner_user_id: str | None = None) -> list[Category]:
        if owner_user_id:
            rows = self._list_payloads("categories", "owner_user_id = %s", (owner_user_id,), "created_at asc, id asc")
        else:
            rows = self._list_payloads("categories", "true", (), "created_at asc, id asc")
        return [Category.model_validate(row) for row in rows]

    def get_category(self, category_id: str) -> Category | None:
        payload = self.get_payload_by_id("categories", category_id)
        return Category.model_validate(payload) if payload else None

    def save_category(self, category: Category) -> None:
        self._save_model("categories", category)

    def delete_category(self, category_id: str) -> None:
        with self._connection() as conn:
            conn.execute("delete from categories where id = %s", (category_id,))

    def list_topics(self, owner_user_id: str) -> list[Topic]:
        rows = self._list_payloads("topics", "owner_user_id = %s", (owner_user_id,), "updated_at desc, id desc")
        return [Topic.model_validate(row) for row in rows]

    def get_topic(self, topic_id: str) -> Topic | None:
        payload = self.get_payload_by_id("topics", topic_id)
        return Topic.model_validate(payload) if payload else None

    def save_topic(self, topic: Topic) -> None:
        self._save_model("topics", topic)

    def delete_topic(self, topic_id: str) -> None:
        with self._connection() as conn:
            with conn.transaction():
                conn.execute("delete from topics where id = %s", (topic_id,))
                rows = self._list_payloads("user_notes", "payload->'visibilityConfig'->'topicIds' ? %s", (topic_id,), "updated_at desc")
                for payload in rows:
                    note = UserNote.model_validate(payload)
                    config = dict(note.visibilityConfig or {})
                    config["topicIds"] = [item for item in config.get("topicIds", []) if item != topic_id]
                    config["topics"] = [item for item in config.get("topics", []) if item.get("id") != topic_id]
                    note.visibilityConfig = config
                    self._upsert_payload(conn, "user_notes", note.model_dump(mode="json"))

    def list_view_events_for_card(
        self,
        card_id: str,
        viewer_user_id: str | None = None,
        anonymous_id: str | None = None,
        visitor_identity_id: str | None = None,
        limit: int | None = None,
    ) -> list[dict]:
        where_parts = ["card_id = %s"]
        params: list[str] = [card_id]
        identity_parts = []
        if viewer_user_id:
            identity_parts.append("viewer_user_id = %s")
            params.append(viewer_user_id)
        if anonymous_id:
            identity_parts.append("anonymous_id = %s")
            params.append(anonymous_id)
        if visitor_identity_id:
            identity_parts.append("visitor_identity_id = %s")
            params.append(visitor_identity_id)
        if identity_parts:
            where_parts.append("(" + " or ".join(identity_parts) + ")")
        limit_sql = ""
        if limit is not None:
            safe_limit = max(1, min(int(limit), 100))
            limit_sql = f" limit {safe_limit}"
        rows = self._list_payloads(
            "view_events",
            " and ".join(where_parts),
            tuple(params),
            "viewed_at desc, id desc",
            limit_sql=limit_sql,
        )
        return [ViewEvent.model_validate(row) for row in rows]

    def list_view_events_for_cards(self, card_ids: set[str]) -> dict[str, list[ViewEvent]]:
        if not card_ids:
            return {}
        rows = self._list_payloads(
            "view_events",
            "card_id = any(%s)",
            (list(card_ids),),
            "viewed_at desc, id desc",
        )
        grouped: dict[str, list[ViewEvent]] = {card_id: [] for card_id in card_ids}
        for row in rows:
            event = ViewEvent.model_validate(row)
            grouped.setdefault(event.cardId, []).append(event)
        return grouped

    def list_view_events_for_viewer(self, viewer_user_id: str, limit: int = 1000) -> list[ViewEvent]:
        safe_limit = max(1, min(int(limit or 1000), 1000))
        rows = self._list_payloads(
            "view_events",
            "viewer_user_id = %s",
            (viewer_user_id,),
            "viewed_at desc, id desc",
            limit_sql=f" limit {safe_limit}",
        )
        return [ViewEvent.model_validate(row) for row in rows]

    def add_view_event(self, event: ViewEvent) -> None:
        self._save_model("view_events", event)

    def add_showcase_event(self, event: ShowcaseEvent) -> None:
        self._save_model("showcase_events", event)

    def list_showcase_events(self, showcase_id: str) -> list[ShowcaseEvent]:
        rows = self._list_payloads(
            "showcase_events",
            "showcase_id = %s",
            (showcase_id,),
            "created_at desc, id desc",
        )
        return [ShowcaseEvent.model_validate(row) for row in rows]

    def list_showcase_events_for_showcases(self, showcase_ids: set[str]) -> dict[str, list[ShowcaseEvent]]:
        if not showcase_ids:
            return {}
        rows = self._list_payloads(
            "showcase_events",
            "showcase_id = any(%s)",
            (list(showcase_ids),),
            "created_at desc, id desc",
        )
        grouped: dict[str, list[ShowcaseEvent]] = {showcase_id: [] for showcase_id in showcase_ids}
        for row in rows:
            event = ShowcaseEvent.model_validate(row)
            grouped.setdefault(event.showcaseId, []).append(event)
        return grouped

    def get_notification_preference(self, user_id: str) -> NotificationPreference | None:
        rows = self._list_payloads("notification_preferences", "user_id = %s", (user_id,), "updated_at desc, id desc")
        return NotificationPreference.model_validate(rows[0]) if rows else None

    def save_notification_preference(self, preference: NotificationPreference) -> None:
        self._save_model("notification_preferences", preference)

    def list_wechat_subscription_grants(self, user_id: str, template_id: str | None = None) -> list[WechatSubscriptionGrant]:
        where = "user_id = %s"
        params: list[str] = [user_id]
        if template_id:
            where += " and template_id = %s"
            params.append(template_id)
        rows = self._list_payloads("wechat_subscription_grants", where, tuple(params), "authorized_at desc, id desc")
        return [WechatSubscriptionGrant.model_validate(row) for row in rows]

    def get_wechat_subscription_grant(self, grant_id: str) -> WechatSubscriptionGrant | None:
        payload = self.get_payload_by_id("wechat_subscription_grants", grant_id)
        return WechatSubscriptionGrant.model_validate(payload) if payload else None

    def save_wechat_subscription_grant(self, grant: WechatSubscriptionGrant) -> None:
        self._save_model("wechat_subscription_grants", grant)

    def reserve_wechat_subscription_grant(self, user_id: str, template_id: str, now: str) -> WechatSubscriptionGrant | None:
        with self._connection(row_factory=dict_row) as conn:
            with conn.transaction():
                row = conn.execute(
                    """
                    with candidate as (
                        select id
                        from wechat_subscription_grants
                        where user_id = %s and template_id = %s and status = 'available'
                        order by authorized_at asc, id asc
                        for update skip locked
                        limit 1
                    )
                    update wechat_subscription_grants as grants
                    set payload = jsonb_set(jsonb_set(grants.payload, '{status}', '"reserved"'::jsonb), '{reservedAt}', to_jsonb(%s::text)),
                        status = 'reserved',
                        reserved_at = %s::timestamptz,
                        updated_at = %s::timestamptz
                    where grants.id in (select id from candidate)
                    returning grants.payload
                    """,
                    (user_id, template_id, now, now, now),
                ).fetchone()
        return WechatSubscriptionGrant.model_validate(row["payload"]) if row else None

    def release_stale_wechat_subscription_grants(self, cutoff: str, now: str) -> int:
        with self._connection() as conn:
            with conn.transaction():
                result = conn.execute(
                    """
                    update wechat_subscription_grants
                    set payload = jsonb_set(
                        jsonb_set(payload - 'reservedAt', '{status}', '"available"'::jsonb),
                        '{updatedAt}', to_jsonb(%s::text)
                    ),
                    status = 'available',
                    reserved_at = null,
                    updated_at = %s::timestamptz
                    where status = 'reserved' and reserved_at <= %s::timestamptz
                    """,
                    (now, now, cutoff),
                )
                return result.rowcount

    def list_wechat_subscription_deliveries(self, owner_user_id: str, limit: int = 100) -> list[WechatSubscriptionDelivery]:
        rows = self._list_payloads(
            "wechat_subscription_deliveries",
            "owner_user_id = %s",
            (owner_user_id,),
            "created_at desc, id desc",
        )
        return [WechatSubscriptionDelivery.model_validate(row) for row in rows[:limit]]

    def get_wechat_subscription_delivery(self, delivery_id: str) -> WechatSubscriptionDelivery | None:
        payload = self.get_payload_by_id("wechat_subscription_deliveries", delivery_id)
        return WechatSubscriptionDelivery.model_validate(payload) if payload else None

    def find_wechat_subscription_delivery_by_dedupe_key(self, dedupe_key: str) -> WechatSubscriptionDelivery | None:
        rows = self._list_payloads("wechat_subscription_deliveries", "dedupe_key = %s", (dedupe_key,), "created_at desc, id desc")
        return WechatSubscriptionDelivery.model_validate(rows[0]) if rows else None

    def save_wechat_subscription_delivery(self, delivery: WechatSubscriptionDelivery) -> None:
        self._save_model("wechat_subscription_deliveries", delivery)

    def list_relay_entries_for_card(self, card_id: str, relay_status: str = "active") -> list[dict]:
        rows = self._list_payloads(
            "relay_entries",
            "card_id = %s and status = %s",
            (card_id, relay_status),
            "created_at desc, id desc",
        )
        return [RelayEntry.model_validate(row) for row in rows]

    def list_relay_entries_for_cards(
        self,
        card_ids: set[str],
        relay_status: str | None = "active",
    ) -> dict[str, list[RelayEntry]]:
        if not card_ids:
            return {}
        where = "card_id = any(%s)"
        params: list[object] = [list(card_ids)]
        if relay_status:
            where += " and status = %s"
            params.append(relay_status)
        rows = self._list_payloads("relay_entries", where, tuple(params), "created_at desc, id desc")
        grouped: dict[str, list[RelayEntry]] = {card_id: [] for card_id in card_ids}
        for row in rows:
            relay = RelayEntry.model_validate(row)
            grouped.setdefault(relay.cardId, []).append(relay)
        return grouped

    def add_relay_entry(self, relay: RelayEntry) -> None:
        self._save_model("relay_entries", relay)

    def get_relay_entry(self, relay_id: str) -> RelayEntry | None:
        payload = self.get_payload_by_id("relay_entries", relay_id)
        return RelayEntry.model_validate(payload) if payload else None

    def save_relay_entry(self, relay: RelayEntry) -> None:
        self._save_model("relay_entries", relay)

    def list_lead_reminders(self, owner_user_id: str, status: str | None = None) -> list[LeadReminder]:
        if status:
            rows = self._list_payloads(
                "lead_reminders",
                "owner_user_id = %s and status = %s",
                (owner_user_id, status),
                "updated_at desc, id desc",
            )
        else:
            rows = self._list_payloads(
                "lead_reminders",
                "owner_user_id = %s",
                (owner_user_id,),
                "updated_at desc, id desc",
            )
        return [LeadReminder.model_validate(row) for row in rows]

    def get_lead_reminder(self, reminder_id: str) -> LeadReminder | None:
        payload = self.get_payload_by_id("lead_reminders", reminder_id)
        return LeadReminder.model_validate(payload) if payload else None

    def get_lead_reminder_by_card_viewer(self, card_id: str, viewer_user_id: str) -> LeadReminder | None:
        rows = self._list_payloads(
            "lead_reminders",
            "card_id = %s and viewer_user_id = %s",
            (card_id, viewer_user_id),
            "updated_at desc, id desc",
        )
        return LeadReminder.model_validate(rows[0]) if rows else None

    def save_lead_reminder(self, reminder: LeadReminder) -> None:
        self._save_model("lead_reminders", reminder)

    def save_lead_reminder_if_version(self, reminder: LeadReminder, expected_version: int) -> bool:
        self._ensure_known_table("lead_reminders")
        with self._connection(row_factory=dict_row) as conn:
            with conn.transaction():
                row = conn.execute(
                    "select payload from lead_reminders where id = %s for update",
                    (reminder.id,),
                ).fetchone()
                if not row:
                    return False
                current = LeadReminder.model_validate(row["payload"])
                if int(current.version or 0) != int(expected_version):
                    return False
                self._upsert_payload(conn, "lead_reminders", reminder.model_dump(mode="json"))
                return True

    def delete_lead_reminder(self, reminder_id: str) -> None:
        with self._connection() as conn:
            conn.execute("delete from lead_reminders where id = %s", (reminder_id,))

    def get_customer_radar_summary(self, owner_user_id: str, mode: str = "") -> CustomerRadarSummary | None:
        rows = self._list_payloads(
            "customer_radar_summaries",
            "owner_user_id = %s and mode = %s",
            (owner_user_id, str(mode or "")),
            "updated_at desc, id desc",
            limit_sql=" limit 1",
        )
        return CustomerRadarSummary.model_validate(rows[0]) if rows else None

    def save_customer_radar_summary(self, summary: CustomerRadarSummary) -> None:
        self._save_model("customer_radar_summaries", summary)

    def mark_customer_radar_summaries_dirty(self, owner_user_id: str | None = None) -> None:
        self._ensure_known_table("customer_radar_summaries")
        where_sql = "" if not owner_user_id else " where owner_user_id = %s"
        params = (owner_user_id,) if owner_user_id else ()
        with self._connection() as conn:
            conn.execute(
                f"update customer_radar_summaries "
                "set is_dirty = true, payload = jsonb_set(payload, '{isDirty}', 'true'::jsonb, true), "
                "updated_at = now()"
                f"{where_sql}{' and is_dirty is distinct from true' if where_sql else ' where is_dirty is distinct from true'}",
                params,
            )

    def save_customer_action(self, action: CustomerAction) -> None:
        self._save_model("customer_actions", action)

    def list_customer_actions_for_note(
        self,
        note_id: str,
        viewer_user_id: str | None = None,
        anonymous_id: str | None = None,
        visitor_identity_id: str | None = None,
        limit: int | None = None,
    ) -> list[CustomerAction]:
        where_parts = ["note_id = %s"]
        params: list[str] = [note_id]
        identity_parts = []
        if viewer_user_id:
            identity_parts.append("viewer_user_id = %s")
            params.append(viewer_user_id)
        if anonymous_id:
            identity_parts.append("anonymous_id = %s")
            params.append(anonymous_id)
        if visitor_identity_id:
            identity_parts.append("visitor_identity_id = %s")
            params.append(visitor_identity_id)
        if identity_parts:
            where_parts.append("(" + " or ".join(identity_parts) + ")")
        limit_sql = ""
        if limit is not None:
            safe_limit = max(1, min(int(limit), 100))
            limit_sql = f" limit {safe_limit}"
        rows = self._list_payloads(
            "customer_actions",
            " and ".join(where_parts),
            tuple(params),
            "created_at desc, id desc",
            limit_sql=limit_sql,
        )
        return [CustomerAction.model_validate(row) for row in rows]

    def list_customer_actions_for_notes(self, note_ids: set[str]) -> dict[str, list[CustomerAction]]:
        if not note_ids:
            return {}
        rows = self._list_payloads(
            "customer_actions",
            "note_id = any(%s)",
            (list(note_ids),),
            "created_at desc, id desc",
        )
        grouped: dict[str, list[CustomerAction]] = {note_id: [] for note_id in note_ids}
        for row in rows:
            action = CustomerAction.model_validate(row)
            grouped.setdefault(action.noteId, []).append(action)
        return grouped

    def get_customer_action(self, action_id: str) -> CustomerAction | None:
        payload = self.get_payload_by_id("customer_actions", action_id)
        return CustomerAction.model_validate(payload) if payload else None

    def save_message_thread(self, thread: MessageThread) -> None:
        self._save_model("message_threads", thread)

    def get_message_thread(self, thread_id: str) -> MessageThread | None:
        payload = self.get_payload_by_id("message_threads", thread_id)
        return MessageThread.model_validate(payload) if payload else None

    def list_message_threads_for_user(self, user_id: str) -> list[MessageThread]:
        rows = self._list_payloads(
            "message_threads",
            "owner_user_id = %s or buyer_user_id = %s or payload->'participantUserIds' ? %s",
            (user_id, user_id, user_id),
            "coalesce(last_message_at, updated_at) desc, id desc",
        )
        return [MessageThread.model_validate(row) for row in rows]

    def save_message_record(self, record: MessageRecord) -> None:
        self._save_model("message_records", record)

    def list_message_records_for_thread(self, thread_id: str) -> list[MessageRecord]:
        rows = self._list_payloads("message_records", "thread_id = %s", (thread_id,), "created_at asc, id asc")
        return [MessageRecord.model_validate(row) for row in rows]

    def save_import_notification(self, notification: ImportNotification) -> None:
        self._save_model("import_notifications", notification)

    def list_import_notifications(self) -> list[ImportNotification]:
        rows = self._list_payloads("import_notifications", "true", (), "sent_at desc, id desc")
        return [ImportNotification.model_validate(row) for row in rows]

    def get_sync_cursor(self, open_kfid: str) -> SyncCursor | None:
        rows = self._list_payloads("sync_cursors", "open_kfid = %s", (open_kfid,), "last_synced_at desc, id desc")
        return SyncCursor.model_validate(rows[0]) if rows else None

    def save_sync_cursor(self, cursor: SyncCursor) -> None:
        self._save_model("sync_cursors", cursor)

    def acquire_sync_lock(
        self,
        open_kfid: str,
        source: str,
        lock_token: str,
        now: str,
        stale_before: str,
    ) -> SyncCursor | None:
        payload = {
            "id": f"sync_cursor_{open_kfid}",
            "openKfid": open_kfid,
            "cursor": None,
            "hasMore": False,
            "lastSource": source,
            "lastPayload": {},
            "lastSyncedAt": now,
            "syncStatus": "running",
            "lockToken": lock_token,
            "lockedAt": now,
            "lastError": None,
            "createdAt": now,
            "updatedAt": now,
        }
        with self._connection(row_factory=dict_row) as conn:
            row = conn.execute(
                """
                insert into sync_cursors (
                    id, payload, created_at, updated_at, open_kfid, cursor_value, has_more,
                    last_source, last_synced_at, sync_status, lock_token, locked_at, last_error
                )
                values (
                    %(id)s, %(payload)s::jsonb, %(created_at)s::timestamptz, %(updated_at)s::timestamptz,
                    %(open_kfid)s, null, false, %(last_source)s, %(last_synced_at)s::timestamptz,
                    'running', %(lock_token)s, %(locked_at)s::timestamptz, null
                )
                on conflict (open_kfid) do update set
                    payload = jsonb_set(
                        jsonb_set(
                            jsonb_set(
                                jsonb_set(
                                    jsonb_set(sync_cursors.payload, '{syncStatus}', '"running"'::jsonb),
                                    '{lockToken}', to_jsonb(%(lock_token)s::text)
                                ),
                                '{lockedAt}', to_jsonb(%(locked_at)s::text)
                            ),
                            '{lastError}', 'null'::jsonb
                        ),
                        '{updatedAt}', to_jsonb(%(updated_at)s::text)
                    ),
                    updated_at = %(updated_at)s::timestamptz,
                    last_source = %(last_source)s,
                    sync_status = 'running',
                    lock_token = %(lock_token)s,
                    locked_at = %(locked_at)s::timestamptz,
                    last_error = null
                where sync_cursors.sync_status is distinct from 'running'
                   or sync_cursors.locked_at is null
                   or sync_cursors.locked_at <= %(stale_before)s::timestamptz
                returning payload
                """,
                {
                    "id": payload["id"],
                    "payload": json.dumps(payload, ensure_ascii=False),
                    "created_at": now,
                    "updated_at": now,
                    "open_kfid": open_kfid,
                    "last_source": source,
                    "last_synced_at": now,
                    "lock_token": lock_token,
                    "locked_at": now,
                    "stale_before": stale_before,
                },
            ).fetchone()
        return SyncCursor.model_validate(row["payload"]) if row else None

    def release_sync_lock(
        self,
        open_kfid: str,
        lock_token: str,
        status: str,
        error_message: str | None,
        now: str,
    ) -> SyncCursor | None:
        with self._connection(row_factory=dict_row) as conn:
            row = conn.execute(
                """
                update sync_cursors set
                    payload = jsonb_set(
                        jsonb_set(
                            jsonb_set(
                                jsonb_set(
                                    jsonb_set(payload, '{syncStatus}', to_jsonb(%(status)s::text)),
                                    '{lockToken}', 'null'::jsonb
                                ),
                                '{lockedAt}', 'null'::jsonb
                            ),
                            '{lastError}', coalesce(to_jsonb(%(error_message)s::text), 'null'::jsonb)
                        ),
                        '{updatedAt}', to_jsonb(%(updated_at)s::text)
                    ),
                    updated_at = %(updated_at)s::timestamptz,
                    sync_status = %(status)s,
                    lock_token = null,
                    locked_at = null,
                    last_error = %(error_message)s
                where open_kfid = %(open_kfid)s and lock_token = %(lock_token)s
                returning payload
                """,
                {
                    "open_kfid": open_kfid,
                    "lock_token": lock_token,
                    "status": status,
                    "error_message": error_message,
                    "updated_at": now,
                },
            ).fetchone()
        return SyncCursor.model_validate(row["payload"]) if row else self.get_sync_cursor(open_kfid)

    def force_release_sync_lock(self, open_kfid: str, reason: str, now: str) -> SyncCursor | None:
        with self._connection(row_factory=dict_row) as conn:
            row = conn.execute(
                """
                update sync_cursors set
                    payload = jsonb_set(
                        jsonb_set(
                            jsonb_set(
                                jsonb_set(
                                    jsonb_set(payload, '{syncStatus}', '"failed"'::jsonb),
                                    '{lockToken}', 'null'::jsonb
                                ),
                                '{lockedAt}', 'null'::jsonb
                            ),
                            '{lastError}', to_jsonb(%(reason)s::text)
                        ),
                        '{updatedAt}', to_jsonb(%(updated_at)s::text)
                    ),
                    updated_at = %(updated_at)s::timestamptz,
                    sync_status = 'failed',
                    lock_token = null,
                    locked_at = null,
                    last_error = %(reason)s
                where open_kfid = %(open_kfid)s
                returning payload
                """,
                {
                    "open_kfid": open_kfid,
                    "reason": reason,
                    "updated_at": now,
                },
            ).fetchone()
        return SyncCursor.model_validate(row["payload"]) if row else None

    def save_media_retry_job(self, job: MediaRetryJob) -> None:
        self._save_model("media_retry_jobs", job)

    def get_media_retry_job(self, media_id: str) -> MediaRetryJob | None:
        rows = self._list_payloads("media_retry_jobs", "media_id = %s", (media_id,), "updated_at desc, id desc")
        return MediaRetryJob.model_validate(rows[0]) if rows else None

    def get_successful_media_url(self, media_id: str) -> str | None:
        rows = self._list_payloads(
            "media_retry_jobs",
            "media_id = %s and status = 'success'",
            (media_id,),
            "updated_at desc, id desc",
        )
        if not rows:
            return None
        return MediaRetryJob.model_validate(rows[0]).localMediaUrl

    def list_media_retry_jobs(self, statuses: set[str] | None = None) -> list[MediaRetryJob]:
        if statuses:
            rows = self._list_payloads(
                "media_retry_jobs",
                "status = any(%s)",
                (list(statuses),),
                "updated_at desc, id desc",
            )
        else:
            rows = self._list_payloads("media_retry_jobs", "true", (), "updated_at desc, id desc")
        return [MediaRetryJob.model_validate(row) for row in rows]

    def get_media_asset_by_original_hash(self, media_type: str, original_sha256: str) -> MediaAsset | None:
        rows = self._list_payloads(
            "media_assets",
            "media_type = %s and original_sha256 = %s and status = 'active'",
            (media_type, original_sha256),
            "updated_at desc, id desc",
        )
        return MediaAsset.model_validate(rows[0]) if rows else None

    def get_media_asset_by_storage_hash(self, media_type: str, storage_sha256: str) -> MediaAsset | None:
        rows = self._list_payloads(
            "media_assets",
            "media_type = %s and storage_sha256 = %s and status = 'active'",
            (media_type, storage_sha256),
            "updated_at desc, id desc",
        )
        return MediaAsset.model_validate(rows[0]) if rows else None

    def get_media_asset_by_url(self, url: str) -> MediaAsset | None:
        rows = self._list_payloads("media_assets", "url = %s and status = 'active'", (url,), "updated_at desc, id desc")
        return MediaAsset.model_validate(rows[0]) if rows else None

    def save_media_asset(self, asset: MediaAsset) -> bool:
        try:
            self._save_model("media_assets", asset)
        except psycopg.errors.UniqueViolation:
            return False
        return True

    def save_media_asset_ref(self, ref: MediaAssetRef) -> None:
        self._save_model("media_asset_refs", ref)

    def list_media_asset_refs(
        self,
        asset_id: str | None = None,
        ref_type: str | None = None,
        ref_id: str | None = None,
    ) -> list[MediaAssetRef]:
        where_parts = ["true"]
        params: list[str] = []
        if asset_id:
            where_parts.append("asset_id = %s")
            params.append(asset_id)
        if ref_type:
            where_parts.append("ref_type = %s")
            params.append(ref_type)
        if ref_id:
            where_parts.append("ref_id = %s")
            params.append(ref_id)
        rows = self._list_payloads("media_asset_refs", " and ".join(where_parts), tuple(params), "created_at desc, id desc")
        return [MediaAssetRef.model_validate(row) for row in rows]

    def delete_media_asset_refs(
        self,
        asset_id: str,
        ref_type: str | None = None,
        ref_id: str | None = None,
        usage: str | None = None,
    ) -> int:
        where_parts = ["asset_id = %s"]
        params: list[str] = [asset_id]
        if ref_type:
            where_parts.append("ref_type = %s")
            params.append(ref_type)
        if ref_id:
            where_parts.append("ref_id = %s")
            params.append(ref_id)
        if usage:
            where_parts.append("usage = %s")
            params.append(usage)
        with self._connection() as conn:
            result = conn.execute(
                f"delete from media_asset_refs where {' and '.join(where_parts)}",
                tuple(params),
            )
        return int(result.rowcount or 0)

    def save_sync_task(self, task: SyncTask) -> None:
        self._save_model("sync_tasks", task)

    def list_sync_tasks(self, statuses: set[str] | None = None, limit: int = 50) -> list[SyncTask]:
        if statuses:
            rows = self._list_payloads(
                "sync_tasks",
                "status = any(%s)",
                (list(statuses),),
                "created_at desc, id desc limit %s" % int(limit),
            )
        else:
            rows = self._list_payloads("sync_tasks", "true", (), "created_at desc, id desc limit %s" % int(limit))
        return [SyncTask.model_validate(row) for row in rows]

    def claim_sync_task(self, task_id: str, worker_id: str, now: str, stale_before: str) -> SyncTask | None:
        with self._connection(row_factory=dict_row) as conn:
            row = conn.execute(
                """
                update sync_tasks set
                    payload = jsonb_set(
                        jsonb_set(
                            jsonb_set(
                                jsonb_set(payload, '{status}', '"running"'::jsonb),
                                '{lockedBy}', to_jsonb(%(worker_id)s::text)
                            ),
                            '{lockedAt}', to_jsonb(%(locked_at)s::text)
                        ),
                        '{updatedAt}', to_jsonb(%(updated_at)s::text)
                    ),
                    status = 'running',
                    locked_by = %(worker_id)s,
                    locked_at = %(locked_at)s::timestamptz,
                    updated_at = %(updated_at)s::timestamptz
                where id = %(task_id)s
                  and (
                    status in ('queued', 'retrying')
                    or (status = 'running' and locked_at is not null and locked_at <= %(stale_before)s::timestamptz)
                  )
                  and (next_run_at is null or next_run_at <= %(updated_at)s::timestamptz)
                returning payload
                """,
                {
                    "task_id": task_id,
                    "worker_id": worker_id,
                    "locked_at": now,
                    "updated_at": now,
                    "stale_before": stale_before,
                },
            ).fetchone()
        return SyncTask.model_validate(row["payload"]) if row else None

    def update_sync_task(self, task: SyncTask) -> None:
        self._save_model("sync_tasks", task)

    def add_sync_task_log(self, log: SyncTaskLog) -> None:
        self._save_model("sync_task_logs", log)

    def list_sync_task_logs(self, task_id: str | None = None, limit: int = 100) -> list[SyncTaskLog]:
        if task_id:
            rows = self._list_payloads(
                "sync_task_logs",
                "task_id = %s",
                (task_id,),
                "created_at desc, id desc limit %s" % int(limit),
            )
        else:
            rows = self._list_payloads("sync_task_logs", "true", (), "created_at desc, id desc limit %s" % int(limit))
        return [SyncTaskLog.model_validate(row) for row in rows]

    def save_skill_run(self, run: SkillRun) -> None:
        self._save_model("skill_runs", run)

    def list_skill_runs(
        self,
        status: str | None = None,
        skill_id: str | None = None,
        limit: int = 100,
    ) -> list[SkillRun]:
        where_parts = ["true"]
        params: list[str] = []
        if status:
            where_parts.append("status = %s")
            params.append(status)
        if skill_id:
            where_parts.append("skill_id = %s")
            params.append(skill_id)
        rows = self._list_payloads(
            "skill_runs",
            " and ".join(where_parts),
            tuple(params),
            "started_at desc, id desc limit %s" % int(limit),
        )
        return [SkillRun.model_validate(row) for row in rows]

    def get_automation_device(self, device_id: str) -> AutomationDevice | None:
        payload = self.get_payload_by_id("automation_devices", device_id)
        return AutomationDevice.model_validate(payload) if payload else None

    def list_automation_devices(self, limit: int = 100) -> list[AutomationDevice]:
        rows = self._list_payloads(
            "automation_devices",
            "true",
            (),
            "updated_at desc, id desc limit %s" % int(limit),
        )
        return [AutomationDevice.model_validate(row) for row in rows]

    def save_automation_device(self, device: AutomationDevice) -> None:
        self._save_model("automation_devices", device)

    def get_automation_task(self, task_id: str) -> AutomationTask | None:
        payload = self.get_payload_by_id("automation_tasks", task_id)
        return AutomationTask.model_validate(payload) if payload else None

    def find_automation_task_by_idempotency_key(self, idempotency_key: str) -> AutomationTask | None:
        key = str(idempotency_key or "").strip()
        if not key:
            return None
        rows = self._list_payloads(
            "automation_tasks",
            "idempotency_key = %s",
            (key,),
            "created_at desc, id desc",
        )
        return AutomationTask.model_validate(rows[0]) if rows else None

    def save_automation_task(self, task: AutomationTask) -> None:
        self._save_model("automation_tasks", task)

    def list_automation_tasks(
        self,
        device_id: str | None = None,
        statuses: set[str] | None = None,
        limit: int = 50,
    ) -> list[AutomationTask]:
        where_parts = ["true"]
        params: list[object] = []
        if device_id:
            where_parts.append("device_id = %s")
            params.append(device_id)
        if statuses:
            where_parts.append("status = any(%s)")
            params.append(list(statuses))
        rows = self._list_payloads(
            "automation_tasks",
            " and ".join(where_parts),
            tuple(params),
            "created_at desc, id desc limit %s" % int(limit),
        )
        return [AutomationTask.model_validate(row) for row in rows]

    def claim_next_automation_task(
        self,
        device_id: str,
        active_wechat_account_id: str | None,
        now: str,
        lease_expires_at: str,
        lease_token: str,
        function_ids: set[str] | None = None,
    ) -> AutomationTask | None:
        with self._connection(row_factory=dict_row) as conn:
            with conn.transaction():
                active = conn.execute(
                    """
                    select id
                    from automation_tasks
                    where device_id = %s
                      and status = 'running'
                      and (lease_expires_at is null or lease_expires_at > %s::timestamptz)
                    limit 1
                    for update
                    """,
                    (device_id, now),
                ).fetchone()
                if active:
                    return None
                function_filter = ""
                claim_params: list[object] = [device_id]
                if function_ids:
                    function_filter = "and function_id = any(%s)"
                    claim_params.append(list(function_ids))
                claim_params.extend([now, active_wechat_account_id])
                row = conn.execute(
                    f"""
                    select payload
                    from automation_tasks
                    where device_id = %s
                      {function_filter}
                      and (
                        status = 'pending'
                        or (status = 'running' and lease_expires_at is not null and lease_expires_at <= %s::timestamptz)
                      )
                      and (
                        target_wechat_account_id is null
                        or target_wechat_account_id = %s
                        or function_id = 'wechat.switch_account'
                      )
                    order by created_at asc, id asc
                    limit 1
                    for update skip locked
                    """,
                    tuple(claim_params),
                ).fetchone()
                if not row:
                    return None
                task = AutomationTask.model_validate(row["payload"])
                updated = task.model_copy(
                    update={
                        "status": "running",
                        "attempts": task.attempts + 1,
                        "leaseToken": lease_token,
                        "leaseExpiresAt": lease_expires_at,
                        "startedAt": task.startedAt or now,
                        "updatedAt": now,
                    }
                )
                self._upsert_payload(conn, "automation_tasks", updated.model_dump(mode="json"))
                return updated

    def get_automation_group_candidate(self, candidate_id: str) -> AutomationGroupCandidate | None:
        payload = self.get_payload_by_id("automation_group_candidates", candidate_id)
        return AutomationGroupCandidate.model_validate(payload) if payload else None

    def find_automation_group_candidate_by_idempotency_key(self, idempotency_key: str) -> AutomationGroupCandidate | None:
        key = str(idempotency_key or "").strip()
        if not key:
            return None
        rows = self._list_payloads(
            "automation_group_candidates",
            "idempotency_key = %s",
            (key,),
            "saved_at desc, id desc",
        )
        return AutomationGroupCandidate.model_validate(rows[0]) if rows else None

    def save_automation_group_candidate(self, candidate: AutomationGroupCandidate) -> None:
        self._save_model("automation_group_candidates", candidate)

    def list_automation_group_candidates(
        self,
        wechat_account_id: str | None = None,
        limit: int = 100,
    ) -> list[AutomationGroupCandidate]:
        if wechat_account_id:
            rows = self._list_payloads(
                "automation_group_candidates",
                "wechat_account_id = %s",
                (wechat_account_id,),
                "saved_at desc, id desc limit %s" % int(limit),
            )
        else:
            rows = self._list_payloads(
                "automation_group_candidates",
                "true",
                (),
                "saved_at desc, id desc limit %s" % int(limit),
            )
        return [AutomationGroupCandidate.model_validate(row) for row in rows]

    def get_wecom_archive_cursor(self, corp_id: str) -> WecomArchiveCursor | None:
        rows = self._list_payloads(
            "wecom_archive_cursors",
            "corp_id = %s",
            (corp_id,),
            "last_synced_at desc, id desc",
        )
        return WecomArchiveCursor.model_validate(rows[0]) if rows else None

    def save_wecom_archive_cursor(self, cursor: WecomArchiveCursor) -> None:
        self._save_model("wecom_archive_cursors", cursor)

    def save_wecom_archive_messages(self, messages: list[WecomArchiveMessage]) -> None:
        with self._connection() as conn:
            with conn.transaction():
                for message in messages:
                    self._upsert_payload(conn, "wecom_archive_messages", message.model_dump(mode="json"))

    def existing_wecom_archive_msg_ids(self, msg_ids: set[str]) -> set[str]:
        if not msg_ids:
            return set()
        with self._connection(row_factory=dict_row) as conn:
            rows = conn.execute(
                "select msg_id from wecom_archive_messages where msg_id = any(%s)",
                (list(msg_ids),),
            ).fetchall()
        return {row["msg_id"] for row in rows if row["msg_id"]}

    def get_wecom_archive_message_by_msg_id(self, msg_id: str) -> WecomArchiveMessage | None:
        rows = self._list_payloads(
            "wecom_archive_messages",
            "msg_id = %s",
            (msg_id,),
            "seq desc, created_at desc, id desc",
        )
        return WecomArchiveMessage.model_validate(rows[0]) if rows else None

    def get_wecom_archive_message_by_generated_note_id(self, note_id: str) -> WecomArchiveMessage | None:
        rows = self._list_payloads(
            "wecom_archive_messages",
            "generated_note_id = %s",
            (note_id,),
            "seq desc, created_at desc, id desc",
        )
        return WecomArchiveMessage.model_validate(rows[0]) if rows else None

    def list_wecom_archive_messages_by_generated_note_id(self, note_id: str) -> list[WecomArchiveMessage]:
        rows = self._list_payloads(
            "wecom_archive_messages",
            "generated_note_id = %s",
            (note_id,),
            "seq asc, created_at asc, id asc",
        )
        return [WecomArchiveMessage.model_validate(row) for row in rows]

    def list_wecom_archive_messages(self, limit: int = 100) -> list[WecomArchiveMessage]:
        rows = self._list_payloads(
            "wecom_archive_messages",
            "true",
            (),
            "seq desc, created_at desc, id desc limit %s" % int(limit),
        )
        return [WecomArchiveMessage.model_validate(row) for row in rows]

    def get_resource_wallet(self, owner_user_id: str) -> ResourceWallet | None:
        rows = self._list_payloads("resource_wallets", "owner_user_id = %s", (owner_user_id,), "updated_at desc, id desc")
        return ResourceWallet.model_validate(rows[0]) if rows else None

    def save_resource_wallet(self, wallet: ResourceWallet) -> None:
        self._save_model("resource_wallets", wallet)

    def save_resource_point_ledger(self, ledger: ResourcePointLedger) -> None:
        self._save_model("resource_point_ledgers", ledger)

    def list_resource_point_ledgers(self, owner_user_id: str, limit: int = 100) -> list[ResourcePointLedger]:
        rows = self._list_payloads(
            "resource_point_ledgers",
            "owner_user_id = %s",
            (owner_user_id,),
            "created_at_source desc, id desc limit %s" % int(limit),
        )
        return [ResourcePointLedger.model_validate(row) for row in rows]

    def get_resource_free_quota(self, owner_user_id: str, quota_type: str, period_key: str) -> ResourceFreeQuota | None:
        rows = self._list_payloads(
            "resource_free_quotas",
            "owner_user_id = %s and quota_type = %s and period_key = %s",
            (owner_user_id, quota_type, period_key),
            "updated_at desc, id desc",
        )
        return ResourceFreeQuota.model_validate(rows[0]) if rows else None

    def save_resource_free_quota(self, quota: ResourceFreeQuota) -> None:
        self._save_model("resource_free_quotas", quota)

    def find_resource_unlock_record(
        self,
        owner_user_id: str,
        action_type: str,
        target_type: str,
        target_id: str,
    ) -> ResourceUnlockRecord | None:
        rows = self._list_payloads(
            "resource_unlock_records",
            "owner_user_id = %s and action_type = %s and target_type = %s and target_id = %s",
            (owner_user_id, action_type, target_type, target_id),
            "unlocked_at desc, id desc",
        )
        return ResourceUnlockRecord.model_validate(rows[0]) if rows else None

    def save_resource_unlock_record(self, record: ResourceUnlockRecord) -> None:
        self._save_model("resource_unlock_records", record)

    def list_opportunity_leads(self, statuses: set[str] | None = None, keyword: str | None = None) -> list[OpportunityLead]:
        where_parts = ["true"]
        params: list[str] = []
        if statuses:
            where_parts.append("status = any(%s)")
            params.append(list(statuses))
        clean_keyword = (keyword or "").strip()
        if clean_keyword:
            where_parts.append("(title ilike %s or payload->>'summary' ilike %s or payload->>'content' ilike %s or city ilike %s or industry ilike %s)")
            like = f"%{clean_keyword}%"
            params.extend([like, like, like, like, like])
        rows = self._list_payloads(
            "opportunity_leads",
            " and ".join(where_parts),
            tuple(params),
            "coalesce(published_at, updated_at) desc, id desc",
        )
        return [OpportunityLead.model_validate(row) for row in rows]

    def get_opportunity_lead(self, lead_id: str) -> OpportunityLead | None:
        payload = self.get_payload_by_id("opportunity_leads", lead_id)
        return OpportunityLead.model_validate(payload) if payload else None

    def save_opportunity_lead(self, lead: OpportunityLead) -> None:
        self._save_model("opportunity_leads", lead)

    def list_opportunity_lead_sources(self, lead_id: str) -> list[OpportunityLeadSource]:
        rows = self._list_payloads(
            "opportunity_lead_sources",
            "lead_id = %s",
            (lead_id,),
            "source_captured_at desc, id desc",
        )
        return [OpportunityLeadSource.model_validate(row) for row in rows]

    def save_opportunity_lead_source(self, source: OpportunityLeadSource) -> None:
        self._save_model("opportunity_lead_sources", source)

    def list_opportunity_lead_contacts(self, lead_id: str) -> list[OpportunityLeadContact]:
        rows = self._list_payloads(
            "opportunity_lead_contacts",
            "lead_id = %s",
            (lead_id,),
            "created_at desc, id desc",
        )
        return [OpportunityLeadContact.model_validate(row) for row in rows]

    def save_opportunity_lead_contact(self, contact: OpportunityLeadContact) -> None:
        self._save_model("opportunity_lead_contacts", contact)

    def get_opportunity_lead_save(self, lead_id: str, user_id: str) -> OpportunityLeadSave | None:
        rows = self._list_payloads(
            "opportunity_lead_saves",
            "lead_id = %s and user_id = %s",
            (lead_id, user_id),
            "updated_at desc, id desc",
        )
        return OpportunityLeadSave.model_validate(rows[0]) if rows else None

    def save_opportunity_lead_save(self, lead_save: OpportunityLeadSave) -> None:
        self._save_model("opportunity_lead_saves", lead_save)

    def list_opportunity_lead_saves_for_user(self, user_id: str) -> list[OpportunityLeadSave]:
        rows = self._list_payloads(
            "opportunity_lead_saves",
            "user_id = %s",
            (user_id,),
            "updated_at desc, id desc",
        )
        return [OpportunityLeadSave.model_validate(row) for row in rows]

    def save_opportunity_lead_followup(self, followup: OpportunityLeadFollowup) -> None:
        self._save_model("opportunity_lead_followups", followup)

    def list_opportunity_lead_followups(self, lead_id: str, user_id: str | None = None) -> list[OpportunityLeadFollowup]:
        where_parts = ["lead_id = %s"]
        params: list[str] = [lead_id]
        if user_id:
            where_parts.append("user_id = %s")
            params.append(user_id)
        rows = self._list_payloads(
            "opportunity_lead_followups",
            " and ".join(where_parts),
            tuple(params),
            "created_at desc, id desc",
        )
        return [OpportunityLeadFollowup.model_validate(row) for row in rows]

    def get_response_package(self, package_id: str) -> ResponsePackage | None:
        payload = self.get_payload_by_id("response_packages", package_id)
        return ResponsePackage.model_validate(payload) if payload else None

    def get_response_package_for_lead_user(self, lead_id: str, owner_user_id: str) -> ResponsePackage | None:
        rows = self._list_payloads(
            "response_packages",
            "lead_id = %s and owner_user_id = %s and status != %s",
            (lead_id, owner_user_id, "archived"),
            "updated_at desc, id desc",
        )
        return ResponsePackage.model_validate(rows[0]) if rows else None

    def save_response_package(self, package: ResponsePackage) -> None:
        self._save_model("response_packages", package)

    def list_response_package_items(self, package_id: str) -> list[ResponsePackageItem]:
        rows = self._list_payloads(
            "response_package_items",
            "response_package_id = %s",
            (package_id,),
            "sort_order asc, id asc",
        )
        return [ResponsePackageItem.model_validate(row) for row in rows]

    def save_response_package_item(self, item: ResponsePackageItem) -> None:
        self._save_model("response_package_items", item)

    def save_response_package_event(self, event: ResponsePackageEvent) -> None:
        self._save_model("response_package_events", event)

    def list_opportunity_subscriptions(self, owner_user_id: str) -> list[OpportunitySubscription]:
        rows = self._list_payloads(
            "opportunity_subscriptions",
            "owner_user_id = %s and status <> 'deleted'",
            (owner_user_id,),
            "updated_at desc, id desc",
        )
        return [OpportunitySubscription.model_validate(row) for row in rows]

    def save_opportunity_subscription(self, subscription: OpportunitySubscription) -> None:
        self._save_model("opportunity_subscriptions", subscription)

    def list_supply_demand_cards(
        self,
        owner_user_id: str | None = None,
        statuses: set[str] | None = None,
        keyword: str | None = None,
    ) -> list[SupplyDemandCard]:
        where_parts = ["true"]
        params: list[str | list[str]] = []
        if owner_user_id:
            where_parts.append("owner_user_id = %s")
            params.append(owner_user_id)
        if statuses:
            where_parts.append("status = any(%s)")
            params.append(list(statuses))
        if keyword:
            where_parts.append("(title ilike %s or payload->>'summary' ilike %s or city ilike %s or industry ilike %s)")
            params.extend([f"%{keyword}%", f"%{keyword}%", f"%{keyword}%", f"%{keyword}%"])
        rows = self._list_payloads("supply_demand_cards", " and ".join(where_parts), tuple(params), "updated_at desc, id desc")
        return [SupplyDemandCard.model_validate(row) for row in rows]

    def get_supply_demand_card(self, card_id: str) -> SupplyDemandCard | None:
        payload = self.get_payload_by_id("supply_demand_cards", card_id)
        return SupplyDemandCard.model_validate(payload) if payload else None

    def save_supply_demand_card(self, card: SupplyDemandCard) -> None:
        self._save_model("supply_demand_cards", card)

    def list_supply_demand_applications(
        self,
        card_id: str | None = None,
        applicant_user_id: str | None = None,
        owner_user_id: str | None = None,
    ) -> list[SupplyDemandApplication]:
        where_parts = ["true"]
        params: list[str] = []
        if card_id:
            where_parts.append("card_id = %s")
            params.append(card_id)
        if applicant_user_id:
            where_parts.append("applicant_user_id = %s")
            params.append(applicant_user_id)
        if owner_user_id:
            where_parts.append("owner_user_id = %s")
            params.append(owner_user_id)
        rows = self._list_payloads("supply_demand_applications", " and ".join(where_parts), tuple(params), "updated_at desc, id desc")
        return [SupplyDemandApplication.model_validate(row) for row in rows]

    def get_supply_demand_application(self, application_id: str) -> SupplyDemandApplication | None:
        payload = self.get_payload_by_id("supply_demand_applications", application_id)
        return SupplyDemandApplication.model_validate(payload) if payload else None

    def save_supply_demand_application(self, application: SupplyDemandApplication) -> None:
        self._save_model("supply_demand_applications", application)

    def list_opportunity_push_digests(self, owner_user_id: str) -> list[OpportunityPushDigest]:
        rows = self._list_payloads(
            "opportunity_push_digests",
            "owner_user_id = %s",
            (owner_user_id,),
            "created_at_index desc, id desc",
        )
        return [OpportunityPushDigest.model_validate(row) for row in rows]

    def get_opportunity_push_digest(self, digest_id: str) -> OpportunityPushDigest | None:
        payload = self.get_payload_by_id("opportunity_push_digests", digest_id)
        return OpportunityPushDigest.model_validate(payload) if payload else None

    def save_opportunity_push_digest(self, digest: OpportunityPushDigest) -> None:
        self._save_model("opportunity_push_digests", digest)

    def init_schema(self) -> None:
        with self._connection() as conn:
            with conn.transaction():
                conn.execute("select pg_advisory_xact_lock(81207008435)")
                for table_name in self.TABLES.values():
                    conn.execute(
                        f"""
                        create table if not exists {table_name} (
                            id text primary key,
                            payload jsonb not null,
                            created_at timestamptz not null default now(),
                            updated_at timestamptz not null default now()
                        )
                        """
                    )
                    conn.execute(
                        f"create index if not exists idx_{table_name}_payload_gin on {table_name} using gin (payload)"
                    )
                    for column_name, column_type, _ in self.FIELD_COLUMNS.get(table_name, []):
                        conn.execute(f"alter table {table_name} add column if not exists {column_name} {column_type}")
                    for index_name, expression in self.INDEXES.get(table_name, []):
                        conn.execute(f"create index if not exists {index_name} on {table_name} ({expression})")
                conn.execute(
                    """
                    create table if not exists ops_feature_flags (
                        key text primary key,
                        enabled boolean not null,
                        payment_required boolean not null,
                        updated_at timestamptz not null default now(),
                        updated_by text
                    )
                    """
                )
                conn.execute(
                    """
                    create unique index if not exists uq_mutual_recharge_orders_transaction
                    on mutual_recharge_orders (payment_transaction_id)
                    where payment_transaction_id is not null
                    """
                )
                conn.execute(
                    """
                    create unique index if not exists uq_mutual_activity_events_idempotency
                    on mutual_activity_events (idempotency_key)
                    """
                )
                conn.execute(
                    """
                    create unique index if not exists uq_users_openid
                    on users (openid)
                    where openid is not null
                    """
                )
                conn.execute(
                    """
                    create unique index if not exists uq_raw_messages_wecom_msg_id
                    on raw_messages (wecom_msg_id)
                    where wecom_msg_id is not null
                    """
                )
                conn.execute(
                    """
                    create unique index if not exists uq_wecom_bind_card_tokens_token_hash
                    on wecom_bind_card_tokens (token_hash)
                    where token_hash is not null
                    """
                )
                conn.execute(
                    """
                    create unique index if not exists uq_wecom_bind_card_tokens_welcome_hash
                    on wecom_bind_card_tokens (welcome_code_hash)
                    where welcome_code_hash is not null
                    """
                )
                conn.execute(
                    """
                    create unique index if not exists uq_sync_cursors_open_kfid
                    on sync_cursors (open_kfid)
                    """
                )
                conn.execute(
                    """
                    create unique index if not exists uq_lead_reminders_card_viewer
                    on lead_reminders (card_id, viewer_user_id)
                    """
                )
                conn.execute(
                    """
                    create unique index if not exists uq_customer_radar_summaries_owner_mode
                    on customer_radar_summaries (owner_user_id, mode)
                    """
                )
                conn.execute(
                    """
                    create unique index if not exists uq_wecom_archive_cursors_corp
                    on wecom_archive_cursors (corp_id)
                    """
                )
                conn.execute(
                    """
                    create unique index if not exists uq_wecom_archive_messages_msg_id
                    on wecom_archive_messages (msg_id)
                    where msg_id is not null
                    """
                )
                conn.execute(
                    """
                    create unique index if not exists uq_media_assets_original_hash
                    on media_assets (media_type, original_sha256)
                    where original_sha256 is not null and status = 'active'
                    """
                )
                conn.execute(
                    """
                    create unique index if not exists uq_media_assets_storage_hash
                    on media_assets (media_type, storage_sha256)
                    where storage_sha256 is not null and status = 'active'
                    """
                )
                conn.execute(
                    """
                    create unique index if not exists uq_resource_wallets_owner
                    on resource_wallets (owner_user_id)
                    """
                )
                conn.execute(
                    """
                    create unique index if not exists uq_resource_free_quotas_owner_period
                    on resource_free_quotas (owner_user_id, quota_type, period_key)
                    """
                )
                conn.execute(
                    """
                    create unique index if not exists uq_opportunity_lead_saves_lead_user
                    on opportunity_lead_saves (lead_id, user_id)
                    """
                )
                conn.execute(
                    """
                    create unique index if not exists uq_membership_orders_transaction
                    on membership_orders (payment_transaction_id)
                    where payment_transaction_id is not null
                    """
                )
                conn.execute(
                    """
                    create unique index if not exists uq_referral_relations_invitee
                    on referral_relations (invitee_user_id)
                    """
                )
                conn.execute(
                    """
                    create unique index if not exists uq_referral_rewards_order
                    on referral_rewards (source_order_id)
                    """
                )
                conn.execute(
                    """
                    create unique index if not exists uq_same_style_owner_key
                    on same_style_generations (owner_user_id, idempotency_key)
                    """
                )
                conn.execute(
                    """
                    create unique index if not exists uq_user_notes_owner_idempotency
                    on user_notes (owner_user_id, idempotency_key)
                    where idempotency_key is not null
                    """
                )
                conn.execute(
                    """
                    create unique index if not exists uq_showcase_pages_owner_idempotency
                    on showcase_pages (owner_user_id, idempotency_key)
                    where idempotency_key is not null
                    """
                )
                conn.execute(
                    """
                    create unique index if not exists uq_live_qr_codes_code
                    on live_qr_codes (code)
                    """
                )
                conn.execute(
                    """
                    create unique index if not exists uq_notification_preferences_user
                    on notification_preferences (user_id)
                    """
                )
                conn.execute(
                    """
                    create unique index if not exists uq_wechat_subscription_deliveries_dedupe
                    on wechat_subscription_deliveries (dedupe_key)
                    """
                )
                conn.execute(
                    """
                    create unique index if not exists uq_wechat_subscription_grants_request
                    on wechat_subscription_grants (user_id, template_id, request_id)
                    where request_id is not null and request_id <> ''
                    """
                )

    def _upsert_payload(self, conn, table_name: str, payload: dict) -> None:
        payload = strip_unicode_surrogates(payload)
        field_columns = self.FIELD_COLUMNS.get(table_name, [])
        columns = ["id", "payload", "created_at", "updated_at", *[column[0] for column in field_columns]]
        placeholders = ["%s", "%s::jsonb", "coalesce(%s::timestamptz, now())", "coalesce(%s::timestamptz, now())"]
        placeholders.extend(["%s"] * len(field_columns))
        update_columns = [column for column in columns if column != "id"]
        update_sql = ", ".join([f"{column} = excluded.{column}" for column in update_columns])
        values = [
            payload["id"],
            json.dumps(payload, ensure_ascii=False),
            payload.get("createdAt") or payload.get("sentAt"),
            payload.get("updatedAt") or payload.get("sentAt"),
            *[payload.get(payload_key) for _, _, payload_key in field_columns],
        ]
        conn.execute(
            f"""
            insert into {table_name} ({", ".join(columns)})
            values ({", ".join(placeholders)})
            on conflict (id) do update set {update_sql}
            """,
            values,
        )

    def _save_model(self, table_name: str, item) -> None:
        self._ensure_known_table(table_name)
        with self._connection() as conn:
            with conn.transaction():
                self._upsert_payload(conn, table_name, item.model_dump(mode="json"))

    def _list_payloads(
        self,
        table_name: str,
        where_sql: str,
        params: tuple,
        order_sql: str,
        limit_sql: str = "",
    ) -> list[dict]:
        self._ensure_known_table(table_name)
        with self._connection(row_factory=dict_row) as conn:
            rows = conn.execute(
                f"select payload from {table_name} where {where_sql} order by {order_sql}{limit_sql}",
                params,
            ).fetchall()
        return [row["payload"] for row in rows]

    def _ensure_known_table(self, table_name: str) -> None:
        if table_name not in self.TABLES.values():
            raise ValueError(f"Unknown repository table: {table_name}")


def build_repository(database_backend: str, database_url: str, data_file: Path) -> AppRepository:
    if database_backend == "postgres" and database_url:
        try:
            return PostgresRepository(database_url)
        except psycopg.Error:
            require_postgres = os.getenv("DATABASE_REQUIRE_POSTGRES", "").lower() in {"1", "true", "yes"}
            if require_postgres:
                raise
            return JsonRepository(data_file)
    return JsonRepository(data_file)
