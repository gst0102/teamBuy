create table if not exists users (
    id text primary key,
    payload jsonb not null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists wecom_identity_bindings (
    id text primary key,
    payload jsonb not null,
    source_type text,
    external_user_id text,
    owner_user_id text,
    bind_source text,
    first_import_batch_id text,
    last_import_batch_id text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists wecom_bind_card_tokens (
    id text primary key,
    payload jsonb not null,
    token_hash text,
    welcome_code_hash text,
    external_user_id text,
    status text,
    delivery_status text,
    expires_at timestamptz,
    used_at timestamptz,
    owner_user_id text,
    owner_openid text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists wecom_bind_card_assets (
    id text primary key,
    payload jsonb not null,
    source_sha256 text,
    media_id text,
    media_id_expires_at timestamptz,
    status text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists import_batches (
    id text primary key,
    payload jsonb not null,
    external_user_id text,
    conversation_id text,
    claimed_by_user_id text,
    status text,
    title_candidate text,
    source_type text,
    generated_card_id text,
    started_at timestamptz,
    ended_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists raw_messages (
    id text primary key,
    payload jsonb not null,
    import_batch_id text,
    wecom_msg_id text,
    wecom_token text,
    open_kfid text,
    external_user_id text,
    conversation_id text,
    msg_type text,
    media_id text,
    received_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists cards (
    id text primary key,
    payload jsonb not null,
    owner_user_id text,
    import_batch_id text,
    source_card_id text,
    status text,
    title text,
    published_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

-- User notes are persisted through the repository's dynamic JSONB table in
-- PostgreSQL. These columns are added by repository.init_schema() so existing
-- databases receive the lifecycle/idempotency indexes without a destructive
-- migration.

create table if not exists view_events (
    id text primary key,
    payload jsonb not null,
    card_id text,
    viewer_user_id text,
    view_type text,
    anonymous_id text,
    visitor_identity_id text,
    share_id text,
    share_from_user_id text,
    scene text,
    referrer text,
    date_key date,
    viewed_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists showcase_events (
    id text primary key,
    payload jsonb not null,
    showcase_id text,
    owner_user_id text,
    event_type text,
    note_id text,
    share_id text,
    share_from_user_id text,
    scene text,
    referrer text,
    viewer_user_id text,
    view_type text,
    anonymous_id text,
    date_key date,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists relay_entries (
    id text primary key,
    payload jsonb not null,
    card_id text,
    user_id text,
    nickname text,
    status text,
    follow_up_status text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists customer_actions (
    id text primary key,
    payload jsonb not null,
    owner_user_id text,
    note_id text,
    source_card_id text,
    viewer_user_id text,
    anonymous_id text,
    visitor_identity_id text,
    action_key text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

-- Rebuildable radar first-screen projection.  It stores counts only; no
-- customer identity, contact details, lead history, or event payloads.
create table if not exists customer_radar_summaries (
    id text primary key,
    payload jsonb not null,
    owner_user_id text not null,
    mode text not null default '',
    pending_count integer not null default 0,
    visitor_count integer not null default 0,
    following_count integer not null default 0,
    abandoned_count integer not null default 0,
    high_intent_count integer not null default 0,
    interaction_count integer not null default 0,
    revival_count integer not null default 0,
    filtered_count integer not null default 0,
    is_dirty boolean not null default true,
    refreshed_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create unique index if not exists uq_customer_radar_summaries_owner_mode
    on customer_radar_summaries (owner_user_id, mode);
create index if not exists idx_customer_radar_summaries_owner_dirty
    on customer_radar_summaries (owner_user_id, is_dirty, updated_at);

create table if not exists message_threads (
    id text primary key,
    payload jsonb not null,
    note_id text,
    order_action_id text,
    owner_user_id text,
    buyer_user_id text,
    last_message_at timestamptz,
    status text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists message_records (
    id text primary key,
    payload jsonb not null,
    thread_id text,
    sender_user_id text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists categories (
    id text primary key,
    payload jsonb not null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists topics (
    id text primary key,
    payload jsonb not null,
    owner_user_id text,
    name text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists import_notifications (
    id text primary key,
    payload jsonb not null,
    import_batch_id text,
    external_user_id text,
    conversation_id text,
    status text,
    channel text,
    sent_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists sync_cursors (
    id text primary key,
    payload jsonb not null,
    open_kfid text,
    cursor_value text,
    has_more boolean,
    last_source text,
    last_synced_at timestamptz,
    sync_status text,
    lock_token text,
    locked_at timestamptz,
    last_error text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists media_retry_jobs (
    id text primary key,
    payload jsonb not null,
    media_id text,
    media_type text,
    open_kfid text,
    status text,
    attempts integer,
    last_attempt_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists media_assets (
    id text primary key,
    payload jsonb not null,
    media_type text,
    original_sha256 text,
    storage_sha256 text,
    url text,
    status text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists media_asset_refs (
    id text primary key,
    payload jsonb not null,
    asset_id text,
    owner_user_id text,
    ref_type text,
    ref_id text,
    usage text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists sync_tasks (
    id text primary key,
    payload jsonb not null,
    name text,
    status text,
    attempts integer,
    max_attempts integer,
    next_run_at timestamptz,
    locked_by text,
    locked_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists sync_task_logs (
    id text primary key,
    payload jsonb not null,
    task_id text,
    event text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists skill_runs (
    id text primary key,
    payload jsonb not null,
    skill_id text,
    status text,
    output_ref text,
    model_provider text,
    started_at timestamptz,
    ended_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists automation_devices (
    id text primary key,
    payload jsonb not null,
    name text,
    platform text,
    hid_device_id text,
    status text,
    active_wechat_account_id text,
    last_heartbeat_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists automation_tasks (
    id text primary key,
    payload jsonb not null,
    function_id text,
    device_id text,
    target_wechat_account_id text,
    status text,
    attempts integer,
    lease_token text,
    lease_expires_at timestamptz,
    idempotency_key text,
    started_at timestamptz,
    finished_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists automation_group_candidates (
    id text primary key,
    payload jsonb not null,
    device_id text,
    wechat_account_id text,
    group_qr_code text,
    group_name text,
    saved_at timestamptz,
    join_status text,
    can_send boolean,
    idempotency_key text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists wecom_archive_cursors (
    id text primary key,
    payload jsonb not null,
    corp_id text,
    seq bigint,
    status text,
    last_synced_at timestamptz,
    lock_token text,
    locked_at timestamptz,
    last_error text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists wecom_archive_messages (
    id text primary key,
    payload jsonb not null,
    corp_id text,
    seq bigint,
    msg_id text,
    action text,
    from_user text,
    room_id text,
    msg_time timestamptz,
    msg_type text,
    generated_note_id text,
    processed_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists membership_orders (
    id text primary key,
    payload jsonb not null,
    user_id text,
    status text,
    payment_transaction_id text,
    paid_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists membership_entitlements (
    id text primary key,
    payload jsonb not null,
    user_id text,
    entitlement_key text,
    status text,
    expires_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

-- Mutual-help points are a separate ledger from resource-tool points and
-- membership/referral money.  The balance is only a projection; every
-- recharge must also have a ledger row.
create table if not exists mutual_point_accounts (
    id text primary key,
    payload jsonb not null,
    user_id text not null,
    balance integer not null default 0,
    updated_at_source timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists mutual_point_ledgers (
    id text primary key,
    payload jsonb not null,
    user_id text not null,
    ledger_type text not null,
    points_delta integer not null,
    related_order_id text,
    created_at_source timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists mutual_recharge_orders (
    id text primary key,
    payload jsonb not null,
    user_id text not null,
    points integer not null,
    amount_fen integer not null,
    status text not null,
    payment_channel text not null,
    payment_transaction_id text,
    paid_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists mutual_activity_events (
    id text primary key,
    payload jsonb not null,
    event_type text not null,
    user_id text not null,
    task_id text not null,
    task_kind text not null,
    idempotency_key text not null,
    created_at_source timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists notification_preferences (
    id text primary key,
    payload jsonb not null,
    user_id text,
    important_customer_view_enabled boolean,
    ordinary_anonymous_view_enabled boolean,
    updated_at_source timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists wechat_subscription_grants (
    id text primary key,
    payload jsonb not null,
    user_id text,
    template_id text,
    request_id text,
    status text,
    source text,
    authorized_at timestamptz,
    reserved_at timestamptz,
    consumed_at timestamptz,
    invalid_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists wechat_subscription_deliveries (
    id text primary key,
    payload jsonb not null,
    owner_user_id text,
    grant_id text,
    template_id text,
    resource_type text,
    resource_id text,
    viewer_type text,
    dedupe_key text,
    status text,
    sent_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists referral_relations (
    id text primary key,
    payload jsonb not null,
    inviter_user_id text,
    invitee_user_id text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists referral_rewards (
    id text primary key,
    payload jsonb not null,
    inviter_user_id text,
    invitee_user_id text,
    source_order_id text,
    status text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists referral_withdrawals (
    id text primary key,
    payload jsonb not null,
    user_id text,
    status text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists same_style_generations (
    id text primary key,
    payload jsonb not null,
    owner_user_id text,
    idempotency_key text,
    source_note_id text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists live_qr_codes (
    id text primary key,
    payload jsonb not null,
    code text,
    status text,
    scan_count integer not null default 0,
    last_scanned_at timestamptz,
    target_expires_at timestamptz,
    target_updated_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists idx_import_batches_status on import_batches (status);
create index if not exists idx_wecom_identity_bindings_source_external on wecom_identity_bindings (source_type, external_user_id);
create index if not exists idx_wecom_identity_bindings_owner on wecom_identity_bindings (owner_user_id, updated_at);
create unique index if not exists uq_users_openid on users (openid) where openid is not null;
create unique index if not exists uq_wecom_identity_bindings_source_external on wecom_identity_bindings (source_type, external_user_id);
create index if not exists idx_import_batches_conversation on import_batches (external_user_id, conversation_id, started_at);
create index if not exists idx_import_batches_claimed_by on import_batches (claimed_by_user_id);
create index if not exists idx_raw_messages_batch on raw_messages (import_batch_id);
create index if not exists idx_raw_messages_wecom_msg_id on raw_messages (wecom_msg_id);
create index if not exists idx_raw_messages_open_kfid_token on raw_messages (open_kfid, wecom_token);
create index if not exists idx_raw_messages_conversation_time on raw_messages (external_user_id, conversation_id, received_at);
create index if not exists idx_raw_messages_type on raw_messages (msg_type);
create unique index if not exists uq_raw_messages_wecom_msg_id on raw_messages (wecom_msg_id) where wecom_msg_id is not null;
create index if not exists idx_cards_owner_status on cards (owner_user_id, status, updated_at);
create index if not exists idx_cards_import_batch on cards (import_batch_id);
create index if not exists idx_cards_source_card on cards (source_card_id);
create index if not exists idx_view_events_card_time on view_events (card_id, viewed_at);
create index if not exists idx_view_events_card_date on view_events (card_id, date_key);
create index if not exists idx_view_events_logged_viewer on view_events (card_id, viewer_user_id);
create index if not exists idx_view_events_anonymous on view_events (card_id, anonymous_id);
create index if not exists idx_view_events_visitor_identity on view_events (card_id, visitor_identity_id);
create index if not exists idx_view_events_share on view_events (card_id, share_id, viewed_at);
create index if not exists idx_showcase_events_showcase_time on showcase_events (showcase_id, created_at);
create index if not exists idx_showcase_events_owner_time on showcase_events (owner_user_id, created_at);
create index if not exists idx_showcase_events_type on showcase_events (showcase_id, event_type, created_at);
create index if not exists idx_showcase_events_viewer on showcase_events (showcase_id, viewer_user_id);
create index if not exists idx_showcase_events_anonymous on showcase_events (showcase_id, anonymous_id);
create index if not exists idx_showcase_events_share on showcase_events (showcase_id, share_id, created_at);
create unique index if not exists uq_notification_preferences_user on notification_preferences (user_id);
create index if not exists idx_wechat_subscription_grants_user_status on wechat_subscription_grants (user_id, template_id, status, authorized_at);
create unique index if not exists uq_wechat_subscription_deliveries_dedupe on wechat_subscription_deliveries (dedupe_key);
create unique index if not exists uq_wechat_subscription_grants_request on wechat_subscription_grants (user_id, template_id, request_id) where request_id is not null and request_id <> '';
create index if not exists idx_wechat_subscription_deliveries_owner_time on wechat_subscription_deliveries (owner_user_id, created_at);
create index if not exists idx_relay_entries_card_status on relay_entries (card_id, status, created_at);
create index if not exists idx_relay_entries_card_follow_up on relay_entries (card_id, follow_up_status);
create index if not exists idx_relay_entries_user on relay_entries (user_id);
create index if not exists idx_customer_actions_note_time on customer_actions (note_id, created_at);
create index if not exists idx_customer_actions_owner_time on customer_actions (owner_user_id, created_at);
create index if not exists idx_customer_actions_note_viewer on customer_actions (note_id, viewer_user_id, action_key);
create index if not exists idx_customer_actions_note_anonymous on customer_actions (note_id, anonymous_id, action_key);

-- Operational feature flags are deliberately kept outside the content
-- tables.  The customer-information chain is read from this table in
-- PostgreSQL; the legacy JSON fields are used only for the one-time seed.
create table if not exists ops_feature_flags (
    key text primary key,
    enabled boolean not null,
    payment_required boolean not null,
    updated_at timestamptz not null default now(),
    updated_by text
);

create index if not exists idx_message_threads_owner_time on message_threads (owner_user_id, last_message_at);
create index if not exists idx_message_threads_buyer_time on message_threads (buyer_user_id, last_message_at);
create index if not exists idx_message_threads_note on message_threads (note_id);
create index if not exists idx_message_threads_order on message_threads (order_action_id);
create index if not exists idx_message_records_thread_time on message_records (thread_id, created_at);
create index if not exists idx_sync_cursors_open_kfid on sync_cursors (open_kfid);
create index if not exists idx_sync_cursors_last_synced on sync_cursors (last_synced_at);
create unique index if not exists uq_sync_cursors_open_kfid on sync_cursors (open_kfid);
create index if not exists idx_media_retry_jobs_status on media_retry_jobs (status, updated_at);
create index if not exists idx_media_retry_jobs_media_id on media_retry_jobs (media_id);
create index if not exists idx_media_assets_original_hash on media_assets (media_type, original_sha256);
create index if not exists idx_media_assets_storage_hash on media_assets (media_type, storage_sha256);
create index if not exists idx_media_assets_url on media_assets (url);
create unique index if not exists uq_media_assets_original_hash on media_assets (media_type, original_sha256) where original_sha256 is not null and status = 'active';
create unique index if not exists uq_media_assets_storage_hash on media_assets (media_type, storage_sha256) where storage_sha256 is not null and status = 'active';
create index if not exists idx_media_asset_refs_asset on media_asset_refs (asset_id, created_at);
create index if not exists idx_media_asset_refs_ref on media_asset_refs (ref_type, ref_id);
create index if not exists idx_media_asset_refs_owner on media_asset_refs (owner_user_id, created_at);
create index if not exists idx_sync_tasks_ready on sync_tasks (status, next_run_at, created_at);
create index if not exists idx_sync_tasks_name_status on sync_tasks (name, status, updated_at);
create index if not exists idx_sync_tasks_locked on sync_tasks (locked_by, locked_at);
create index if not exists idx_sync_task_logs_task_time on sync_task_logs (task_id, created_at);
create index if not exists idx_skill_runs_status_time on skill_runs (status, started_at);
create index if not exists idx_skill_runs_skill_time on skill_runs (skill_id, started_at);
create index if not exists idx_skill_runs_output_ref on skill_runs (output_ref);
create index if not exists idx_wecom_archive_cursors_corp on wecom_archive_cursors (corp_id);
create index if not exists idx_wecom_archive_cursors_status on wecom_archive_cursors (status, updated_at);
create unique index if not exists uq_wecom_archive_cursors_corp on wecom_archive_cursors (corp_id);
create index if not exists idx_wecom_archive_messages_corp_seq on wecom_archive_messages (corp_id, seq);
create index if not exists idx_wecom_archive_messages_msg_id on wecom_archive_messages (msg_id);
create index if not exists idx_wecom_archive_messages_type_time on wecom_archive_messages (msg_type, msg_time);
create index if not exists idx_wecom_archive_messages_generated_note on wecom_archive_messages (generated_note_id);
create unique index if not exists uq_wecom_archive_messages_msg_id on wecom_archive_messages (msg_id) where msg_id is not null;
create index if not exists idx_membership_orders_user_status on membership_orders (user_id, status, updated_at);
create unique index if not exists uq_membership_orders_transaction on membership_orders (payment_transaction_id) where payment_transaction_id is not null;
create index if not exists idx_membership_entitlements_user_expiry on membership_entitlements (user_id, status, expires_at);
create index if not exists idx_mutual_point_accounts_user on mutual_point_accounts (user_id);
create index if not exists idx_mutual_point_ledgers_user_time on mutual_point_ledgers (user_id, created_at_source);
create index if not exists idx_mutual_point_ledgers_order on mutual_point_ledgers (related_order_id);
create index if not exists idx_mutual_recharge_orders_user_status on mutual_recharge_orders (user_id, status, created_at);
create index if not exists idx_mutual_recharge_orders_transaction on mutual_recharge_orders (payment_transaction_id);
create index if not exists idx_mutual_activity_events_type_time on mutual_activity_events (event_type, created_at_source);
create index if not exists idx_mutual_activity_events_user_time on mutual_activity_events (user_id, created_at_source);
create unique index if not exists uq_mutual_activity_events_idempotency on mutual_activity_events (idempotency_key);
create index if not exists idx_referral_relations_inviter on referral_relations (inviter_user_id, created_at);
create unique index if not exists uq_referral_relations_invitee on referral_relations (invitee_user_id);
create index if not exists idx_referral_rewards_inviter_status on referral_rewards (inviter_user_id, status, updated_at);
create unique index if not exists uq_referral_rewards_order on referral_rewards (source_order_id);
create index if not exists idx_referral_withdrawals_user_status on referral_withdrawals (user_id, status, updated_at);
create index if not exists idx_same_style_owner_time on same_style_generations (owner_user_id, created_at);
create unique index if not exists uq_same_style_owner_key on same_style_generations (owner_user_id, idempotency_key);
create index if not exists idx_live_qr_codes_code on live_qr_codes (code);
create index if not exists idx_live_qr_codes_status_updated on live_qr_codes (status, updated_at);
create unique index if not exists uq_live_qr_codes_code on live_qr_codes (code);
