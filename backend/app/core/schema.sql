create table if not exists users (
    id text primary key,
    payload jsonb not null,
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

create table if not exists view_events (
    id text primary key,
    payload jsonb not null,
    card_id text,
    viewer_user_id text,
    view_type text,
    anonymous_id text,
    date_key date,
    viewed_at timestamptz,
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

create table if not exists categories (
    id text primary key,
    payload jsonb not null,
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

create index if not exists idx_import_batches_status on import_batches (status);
create index if not exists idx_import_batches_conversation on import_batches (external_user_id, conversation_id, started_at);
create index if not exists idx_import_batches_claimed_by on import_batches (claimed_by_user_id);
create index if not exists idx_raw_messages_batch on raw_messages (import_batch_id);
create index if not exists idx_raw_messages_conversation_time on raw_messages (external_user_id, conversation_id, received_at);
create index if not exists idx_raw_messages_type on raw_messages (msg_type);
create index if not exists idx_cards_owner_status on cards (owner_user_id, status, updated_at);
create index if not exists idx_cards_import_batch on cards (import_batch_id);
create index if not exists idx_cards_source_card on cards (source_card_id);
create index if not exists idx_view_events_card_time on view_events (card_id, viewed_at);
create index if not exists idx_view_events_card_date on view_events (card_id, date_key);
create index if not exists idx_view_events_logged_viewer on view_events (card_id, viewer_user_id);
create index if not exists idx_view_events_anonymous on view_events (card_id, anonymous_id);
create index if not exists idx_relay_entries_card_status on relay_entries (card_id, status, created_at);
create index if not exists idx_relay_entries_card_follow_up on relay_entries (card_id, follow_up_status);
create index if not exists idx_relay_entries_user on relay_entries (user_id);
