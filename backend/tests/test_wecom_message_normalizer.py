from __future__ import annotations

from app.services.wecom_message_normalizer import WecomMessageNormalizer


def test_normalizer_maps_real_text_message_shape():
    normalizer = WecomMessageNormalizer()

    message = normalizer.normalize_message(
        {
            "msgid": "msg_real_text_001",
            "open_kfid": "wk_real_001",
            "external_userid": "external_real_001",
            "send_time": 1780848000,
            "msgtype": "text",
            "text": {"content": "真实文本内容"},
        },
        fallback_conversation_id="conv_fallback",
    )

    assert message["wecomMsgId"] == "msg_real_text_001"
    assert message["openKfid"] == "wk_real_001"
    assert message["externalUserId"] == "external_real_001"
    assert message["conversationId"] == "conv_fallback"
    assert message["msgType"] == "text"
    assert message["content"] == {"text": "真实文本内容"}
    assert message["receivedAt"].startswith("2026-06-08")


def test_normalizer_maps_media_and_link_shapes():
    normalizer = WecomMessageNormalizer()
    messages = normalizer.normalize_messages(
        [
            {
                "msgid": "msg_img",
                "token": "cursor_1",
                "msgtype": "image",
                "image": {"media_id": "media_img", "filename": "cover.jpg"},
                "send_time": 1780848001000,
            },
            {
                "msgid": "msg_video",
                "token": "cursor_1",
                "msgtype": "video",
                "video": {"media_id": "media_video", "filename": "room.mp4"},
                "send_time": 1780848002,
            },
            {
                "msgid": "msg_link",
                "token": "cursor_1",
                "msgtype": "link",
                "link": {
                    "title": "链接标题",
                    "desc": "链接描述",
                    "url": "https://example.com/item",
                    "picurl": "https://example.com/pic.jpg",
                },
                "send_time": 1780848003,
            },
            {
                "msgid": "msg_location",
                "token": "cursor_1",
                "msgtype": "location",
                "location": {"name": "项目地址", "latitude": 30.1, "longitude": 120.2},
                "send_time": 1780848004,
            },
        ],
        fallback_external_user_id="external_media",
    )

    assert messages[0]["mediaId"] == "media_img"
    assert messages[0]["content"]["caption"] == "cover.jpg"
    assert messages[1]["mediaId"] == "media_video"
    assert messages[2]["content"]["description"] == "链接描述"
    assert messages[2]["content"]["thumbUrl"] == "https://example.com/pic.jpg"
    assert messages[3]["content"]["label"] == "项目地址"
    assert {item["conversationId"] for item in messages} == {"cursor_1"}


def test_normalizer_preserves_existing_mock_shape():
    normalizer = WecomMessageNormalizer()
    message = normalizer.normalize_message(
        {
            "wecomMsgId": "mock_msg",
            "wecomToken": "mock_cursor",
            "openKfid": "wk_mock",
            "externalUserId": "external_mock",
            "conversationId": "conv_mock",
            "msgType": "link",
            "receivedAt": "2026-06-08T11:10:00+08:00",
            "content": {
                "title": "标题",
                "description": "描述",
                "url": "https://example.com",
                "thumbUrl": "https://example.com/cover.jpg",
            },
        }
    )

    assert message["msgType"] == "link"
    assert message["content"]["title"] == "标题"
    assert message["conversationId"] == "conv_mock"


def test_normalizer_maps_sync_response_message_list():
    normalizer = WecomMessageNormalizer()
    messages = normalizer.normalize_sync_response(
        {
            "next_cursor": "cursor_next",
            "msg_list": [
                {
                    "msgid": "msg_real_001",
                    "open_kfid": "wk_real",
                    "external_userid": "external_real",
                    "send_time": 1780848000,
                    "msgtype": "text",
                    "text": {"content": "鐪熷疄杩斿洖鏂囨湰"},
                }
            ],
        }
    )

    assert messages[0]["wecomMsgId"] == "msg_real_001"
    assert messages[0]["wecomToken"] == "cursor_next"
    assert messages[0]["openKfid"] == "wk_real"
    assert messages[0]["externalUserId"] == "external_real"
