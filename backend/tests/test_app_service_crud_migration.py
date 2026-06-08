from __future__ import annotations

import inspect

from app.services.app_service import AppService


def test_hot_paths_do_not_call_full_state_load_or_save():
    method_names = [
        "list_pending_imports",
        "trigger_mock_import",
        "trigger_sync_response_import",
        "import_synced_messages",
        "get_sync_cursor",
        "acquire_sync_lock",
        "release_sync_lock",
        "advance_sync_cursor",
        "claim_import",
        "list_cards",
        "get_card",
        "update_card",
        "publish_card",
        "duplicate_card",
        "record_view",
        "get_card_stats",
        "create_relay",
        "list_relays",
        "delete_relay",
        "mark_followed",
    ]

    for method_name in method_names:
        source = inspect.getsource(getattr(AppService, method_name))
        assert "self._load()" not in source, method_name
        assert "self._save(" not in source, method_name


def test_import_flow_uses_single_import_artifact_transaction():
    source = inspect.getsource(AppService.import_synced_messages)
    assert "save_import_artifacts" in source
    assert "save_raw_messages" not in source
    assert "save_import_batch" not in source
    assert "save_import_notification" not in source
