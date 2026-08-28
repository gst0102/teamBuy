from __future__ import annotations

from app.models.domain import RawMessage
from app.services.message_aggregator import MessageAggregator


def make_message(
    message_id: str,
    external_user_id: str,
    conversation_id: str,
    received_at: str,
    msg_type: str = "text",
    content: dict | None = None,
) -> RawMessage:
    return RawMessage(
        id=message_id,
        externalUserId=external_user_id,
        conversationId=conversation_id,
        msgType=msg_type,
        content=content or {"text": f"message {message_id}"},
        receivedAt=received_at,
        createdAt=received_at,
    )


def test_aggregator_splits_messages_after_60_seconds():
    messages = [
        make_message("msg_1", "external_1", "conv_1", "2026-06-08T10:00:00+08:00"),
        make_message("msg_2", "external_1", "conv_1", "2026-06-08T10:01:01+08:00"),
    ]

    batches = MessageAggregator().aggregate(messages)

    assert len(batches) == 2
    assert batches[0].rawMessageIds == ["msg_1"]
    assert batches[1].rawMessageIds == ["msg_2"]


def test_aggregator_does_not_merge_different_users():
    messages = [
        make_message("msg_1", "external_1", "conv_1", "2026-06-08T10:00:00+08:00"),
        make_message("msg_2", "external_2", "conv_1", "2026-06-08T10:00:20+08:00"),
    ]

    batches = MessageAggregator().aggregate(messages)

    assert len(batches) == 2
    assert {batch.externalUserId for batch in batches} == {"external_1", "external_2"}


def test_aggregator_merges_messages_at_exactly_60_seconds():
    messages = [
        make_message("msg_1", "external_1", "conv_1", "2026-06-08T10:00:00+08:00"),
        make_message("msg_2", "external_1", "conv_1", "2026-06-08T10:01:00+08:00"),
    ]

    batches = MessageAggregator().aggregate(messages)

    assert len(batches) == 1
    assert batches[0].rawMessageIds == ["msg_1", "msg_2"]


def test_aggregator_uses_first_message_as_window_origin_not_rolling_window():
    messages = [
        make_message("msg_1", "external_1", "conv_1", "2026-06-08T10:00:00+08:00"),
        make_message("msg_2", "external_1", "conv_1", "2026-06-08T10:00:59+08:00"),
        make_message("msg_3", "external_1", "conv_1", "2026-06-08T10:01:58+08:00"),
    ]

    batches = MessageAggregator().aggregate(messages)

    assert [batch.rawMessageIds for batch in batches] == [["msg_1", "msg_2"], ["msg_3"]]


def test_aggregator_keeps_image_and_caption_in_one_batch():
    messages = [
        make_message(
            "msg_image",
            "external_1",
            "conv_1",
            "2026-06-08T10:00:00+08:00",
            msg_type="image",
            content={"filename": "sticker.png"},
        ),
        make_message(
            "msg_caption",
            "external_1",
            "conv_1",
            "2026-06-08T10:00:30+08:00",
            content={"text": "表情包"},
        ),
    ]

    batches = MessageAggregator().aggregate(messages)

    assert len(batches) == 1
    assert batches[0].rawMessageIds == ["msg_image", "msg_caption"]
