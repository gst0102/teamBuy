from __future__ import annotations

from app.services.repository import PostgresRepository


def test_postgres_repository_maps_core_query_columns():
    field_map = {
        table_name: {column_name for column_name, _, _ in columns}
        for table_name, columns in PostgresRepository.FIELD_COLUMNS.items()
    }

    assert {"external_user_id", "conversation_id", "status", "started_at"} <= field_map["import_batches"]
    assert {"import_batch_id", "msg_type", "received_at"} <= field_map["raw_messages"]
    assert {"wecom_msg_id", "wecom_token", "open_kfid"} <= field_map["raw_messages"]
    assert {"owner_user_id", "status", "title"} <= field_map["cards"]
    assert {"card_id", "viewer_user_id", "anonymous_id", "date_key"} <= field_map["view_events"]
    assert {"card_id", "user_id", "status", "follow_up_status"} <= field_map["relay_entries"]


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
    assert "idx_relay_entries_card_status" in indexes["relay_entries"]


def test_postgres_repository_rejects_unknown_table_name_without_connecting():
    repo = object.__new__(PostgresRepository)
    try:
        repo._ensure_known_table("not_a_real_table")
    except ValueError as exc:
        assert "Unknown repository table" in str(exc)
    else:
        raise AssertionError("unknown table should be rejected")
