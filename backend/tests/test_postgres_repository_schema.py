from __future__ import annotations

from contextlib import contextmanager

from psycopg.rows import dict_row, tuple_row

from app.services.ops_console_store import OpsConsoleStore
from app.services.repository import PostgresRepository


class _FakeConnection:
    def __init__(self):
        self.row_factory = None


class _FakePool:
    def __init__(self):
        self.connection_instance = _FakeConnection()

    @contextmanager
    def connection(self):
        yield self.connection_instance


def test_postgres_pooled_connections_preserve_default_row_factory():
    pool = _FakePool()
    repo = object.__new__(PostgresRepository)
    repo._pool = pool

    with repo._connection():
        assert pool.connection_instance.row_factory is tuple_row
    assert pool.connection_instance.row_factory is tuple_row

    with repo._connection(row_factory=dict_row):
        assert pool.connection_instance.row_factory is dict_row
    assert pool.connection_instance.row_factory is tuple_row

    store = object.__new__(OpsConsoleStore)
    store._get_postgres_pool = lambda: pool
    with store._postgres_connection():
        assert pool.connection_instance.row_factory is dict_row
    assert pool.connection_instance.row_factory is tuple_row


def test_postgres_repository_maps_core_query_columns():
    field_map = {
        table_name: {column_name for column_name, _, _ in columns}
        for table_name, columns in PostgresRepository.FIELD_COLUMNS.items()
    }

    assert {"external_user_id", "conversation_id", "status", "started_at"} <= field_map["import_batches"]
    assert {"import_batch_id", "msg_type", "received_at"} <= field_map["raw_messages"]
    assert {"wecom_msg_id", "wecom_token", "open_kfid"} <= field_map["raw_messages"]
    assert {"owner_user_id", "status", "title"} <= field_map["cards"]
    assert {
        "card_id",
        "viewer_user_id",
        "anonymous_id",
        "visitor_identity_id",
        "share_id",
        "share_from_user_id",
        "scene",
        "referrer",
        "date_key",
    } <= field_map["view_events"]
    assert {
        "showcase_id",
        "owner_user_id",
        "event_type",
        "viewer_user_id",
        "anonymous_id",
        "share_id",
        "share_from_user_id",
        "scene",
    } <= field_map["showcase_events"]
    assert {"card_id", "user_id", "status", "follow_up_status"} <= field_map["relay_entries"]
    assert {"card_id", "viewer_user_id", "visitor_identity_id", "status", "version"} <= field_map["lead_reminders"]
    assert {
        "owner_user_id",
        "mode",
        "pending_count",
        "visitor_count",
        "following_count",
        "abandoned_count",
        "high_intent_count",
        "interaction_count",
        "revival_count",
        "filtered_count",
        "is_dirty",
        "refreshed_at",
    } <= field_map["customer_radar_summaries"]
    assert {
        "note_id",
        "source_card_id",
        "viewer_user_id",
        "anonymous_id",
        "visitor_identity_id",
        "action_key",
    } <= field_map["customer_actions"]
    assert {"open_kfid", "cursor_value", "has_more", "last_synced_at"} <= field_map["sync_cursors"]
    assert {"sync_status", "lock_token", "locked_at", "last_error"} <= field_map["sync_cursors"]
    assert {"media_id", "media_type", "status", "attempts"} <= field_map["media_retry_jobs"]
    assert {"name", "status", "attempts", "next_run_at", "locked_by", "locked_at"} <= field_map["sync_tasks"]
    assert {"task_id", "event"} <= field_map["sync_task_logs"]


def test_postgres_repository_defines_hot_path_indexes():
    indexes = {
        table_name: {index_name for index_name, _ in index_specs}
        for table_name, index_specs in PostgresRepository.INDEXES.items()
    }

    assert "idx_import_batches_conversation" in indexes["import_batches"]
    assert "idx_raw_messages_conversation_time" in indexes["raw_messages"]
    assert "idx_raw_messages_wecom_msg_id" in indexes["raw_messages"]
    assert "idx_raw_messages_open_kfid_token" in indexes["raw_messages"]
    assert "idx_cards_owner_status" in indexes["cards"]
    assert "idx_view_events_card_date" in indexes["view_events"]
    assert "idx_view_events_visitor_identity" in indexes["view_events"]
    assert "idx_view_events_share" in indexes["view_events"]
    assert "idx_showcase_events_showcase_time" in indexes["showcase_events"]
    assert "idx_showcase_events_share" in indexes["showcase_events"]
    assert "idx_relay_entries_card_status" in indexes["relay_entries"]
    assert "idx_customer_radar_summaries_owner_dirty" in indexes["customer_radar_summaries"]
    assert "idx_sync_cursors_open_kfid" in indexes["sync_cursors"]
    assert "idx_media_retry_jobs_status" in indexes["media_retry_jobs"]
    assert "idx_sync_tasks_ready" in indexes["sync_tasks"]
    assert "idx_sync_tasks_locked" in indexes["sync_tasks"]
    assert "idx_sync_task_logs_task_time" in indexes["sync_task_logs"]


def test_postgres_repository_rejects_unknown_table_name_without_connecting():
    repo = object.__new__(PostgresRepository)
    try:
        repo._ensure_known_table("not_a_real_table")
    except ValueError as exc:
        assert "Unknown repository table" in str(exc)
    else:
        raise AssertionError("unknown table should be rejected")
