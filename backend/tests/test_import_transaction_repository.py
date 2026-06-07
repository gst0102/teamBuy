from __future__ import annotations

from app.models.domain import Card, ImportBatch, ImportNotification, RawMessage, RelayConfig
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
