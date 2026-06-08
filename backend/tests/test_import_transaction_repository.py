from __future__ import annotations

from app.models.domain import Card, ImportBatch, ImportNotification, RawMessage, RelayConfig, SyncCursor
from app.services.repository import JsonRepository


def test_json_repository_saves_import_artifacts_together(tmp_path):
    repo = JsonRepository(tmp_path / "state.json")
    batch = ImportBatch(
        id="import_tx_001",
        externalUserId="external_tx",
        conversationId="conv_tx",
        status="success",
        titleCandidate="事务测试素材",
        sourceType="wechat_note",
        rawMessageIds=["msg_tx_001"],
        generatedCardId="card_tx_001",
        startedAt="2026-06-08T10:00:00+08:00",
        endedAt="2026-06-08T10:00:10+08:00",
        createdAt="2026-06-08T10:00:00+08:00",
        updatedAt="2026-06-08T10:00:10+08:00",
    )
    raw_message = RawMessage(
        id="msg_tx_001",
        importBatchId="import_tx_001",
        wecomMsgId="wecom_tx_msg_001",
        wecomToken="mock_cursor_tx",
        openKfid="wk_mock_tx",
        externalUserId="external_tx",
        conversationId="conv_tx",
        msgType="text",
        content={"text": "事务测试素材"},
        receivedAt="2026-06-08T10:00:00+08:00",
        createdAt="2026-06-08T10:00:00+08:00",
    )
    card = Card(
        id="card_tx_001",
        ownerUserId="unclaimed",
        importBatchId="import_tx_001",
        status="draft",
        title="事务测试素材",
        detailText="事务测试素材",
        enabledFields=[],
        categoryIds=[],
        media=[],
        relayConfig=RelayConfig(),
        createdAt="2026-06-08T10:00:10+08:00",
        updatedAt="2026-06-08T10:00:10+08:00",
    )
    notification = ImportNotification(
        id="notice_tx_001",
        importBatchId="import_tx_001",
        externalUserId="external_tx",
        conversationId="conv_tx",
        status="success",
        title="事务测试素材",
        message="《事务测试素材》导入成功，请打开小程序认领编辑。",
        channel="mock",
        sentAt="2026-06-08T10:00:11+08:00",
    )

    repo.save_import_artifacts(batch, [raw_message], card, notification)
    state = repo.load()

    assert state.import_batches[0].id == "import_tx_001"
    assert state.raw_messages[0].importBatchId == "import_tx_001"
    assert repo.existing_wecom_msg_ids({"wecom_tx_msg_001", "missing_msg"}) == {"wecom_tx_msg_001"}
    assert state.cards[0].importBatchId == "import_tx_001"
    assert state.import_notifications[0].importBatchId == "import_tx_001"


def test_json_repository_persists_sync_cursor(tmp_path):
    repo = JsonRepository(tmp_path / "state.json")
    cursor = SyncCursor(
        id="sync_cursor_wk_test",
        openKfid="wk_test",
        cursor="cursor_next",
        hasMore=True,
        lastSource="wecom-sync-msg",
        lastPayload={"next_cursor": "cursor_next", "has_more": 1},
        lastSyncedAt="2026-06-08T10:00:00+08:00",
        createdAt="2026-06-08T10:00:00+08:00",
        updatedAt="2026-06-08T10:00:00+08:00",
    )

    repo.save_sync_cursor(cursor)

    loaded = repo.get_sync_cursor("wk_test")
    assert loaded is not None
    assert loaded.cursor == "cursor_next"
    assert loaded.hasMore is True


def test_json_repository_sync_lock_blocks_duplicate_runs(tmp_path):
    repo = JsonRepository(tmp_path / "state.json")

    first = repo.acquire_sync_lock(
        open_kfid="wk_lock",
        source="wecom-sync-msg",
        lock_token="lock_1",
        now="2026-06-08T10:00:00+08:00",
        stale_before="2026-06-08T09:50:00+08:00",
    )
    second = repo.acquire_sync_lock(
        open_kfid="wk_lock",
        source="wecom-sync-msg",
        lock_token="lock_2",
        now="2026-06-08T10:00:01+08:00",
        stale_before="2026-06-08T09:50:01+08:00",
    )

    assert first is not None
    assert first.syncStatus == "running"
    assert first.lockToken == "lock_1"
    assert second is None

    released = repo.release_sync_lock(
        open_kfid="wk_lock",
        lock_token="lock_1",
        status="success",
        error_message=None,
        now="2026-06-08T10:00:02+08:00",
    )
    third = repo.acquire_sync_lock(
        open_kfid="wk_lock",
        source="wecom-sync-msg",
        lock_token="lock_3",
        now="2026-06-08T10:00:03+08:00",
        stale_before="2026-06-08T09:50:03+08:00",
    )

    assert released is not None
    assert released.syncStatus == "success"
    assert released.lockToken is None
    assert third is not None
    assert third.lockToken == "lock_3"


def test_json_repository_sync_lock_can_take_over_stale_run(tmp_path):
    repo = JsonRepository(tmp_path / "state.json")

    first = repo.acquire_sync_lock(
        open_kfid="wk_stale",
        source="wecom-sync-msg",
        lock_token="old_lock",
        now="2026-06-08T10:00:00+08:00",
        stale_before="2026-06-08T09:50:00+08:00",
    )
    takeover = repo.acquire_sync_lock(
        open_kfid="wk_stale",
        source="wecom-sync-msg",
        lock_token="new_lock",
        now="2026-06-08T10:11:00+08:00",
        stale_before="2026-06-08T10:01:00+08:00",
    )

    assert first is not None
    assert takeover is not None
    assert takeover.lockToken == "new_lock"
    assert takeover.lockedAt == "2026-06-08T10:11:00+08:00"


def test_json_repository_force_releases_sync_lock(tmp_path):
    repo = JsonRepository(tmp_path / "state.json")
    repo.acquire_sync_lock(
        open_kfid="wk_force",
        source="wecom-sync-msg",
        lock_token="force_lock",
        now="2026-06-08T10:00:00+08:00",
        stale_before="2026-06-08T09:50:00+08:00",
    )

    released = repo.force_release_sync_lock(
        open_kfid="wk_force",
        reason="manual unlock",
        now="2026-06-08T10:05:00+08:00",
    )

    assert released is not None
    assert released.syncStatus == "failed"
    assert released.lockToken is None
    assert released.lockedAt is None
    assert released.lastError == "manual unlock"
