create table if not exists archive_core_cursors (
    stream_key text primary key,
    next_seq bigint not null default 0,
    last_batch_count integer not null default 0,
    last_success_at timestamptz,
    last_error text,
    updated_at timestamptz not null default now()
);

create table if not exists archive_core_messages (
    event_id text primary key,
    stream_key text not null,
    seq bigint not null,
    message_id_hash text,
    room_id_hash text,
    message_type text,
    message_time bigint,
    sealed_payload text not null,
    created_at timestamptz not null default now(),
    unique (stream_key, seq)
);

create index if not exists idx_archive_core_messages_created
    on archive_core_messages (created_at);

create table if not exists archive_core_deliveries (
    event_id text not null references archive_core_messages(event_id) on delete cascade,
    project_id text not null,
    status text not null default 'pending',
    attempts integer not null default 0,
    next_attempt_at timestamptz not null default now(),
    delivered_at timestamptz,
    last_error text,
    updated_at timestamptz not null default now(),
    primary key (event_id, project_id)
);

create index if not exists idx_archive_core_deliveries_pending
    on archive_core_deliveries (status, next_attempt_at);

create table if not exists archive_core_wakes (
    id bigserial primary key,
    trigger text not null,
    created_at timestamptz not null default now(),
    consumed_at timestamptz
);
