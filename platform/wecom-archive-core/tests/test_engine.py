from __future__ import annotations

import json

from app.codec import SealedPayload
from app.config import ProjectRoute, Settings
from app.engine import normalize_message


def _settings() -> Settings:
    return Settings(
        environment="test",
        database_url="",
        corp_id="corp",
        archive_secret="secret",
        admin_token="admin",
        callback_token="token",
        encoding_aes_key="aes",
        private_key_path=__import__("pathlib").Path("/tmp/private"),
        sdk_lib_path=__import__("pathlib").Path("/tmp/sdk"),
        proxy="",
        proxy_password="",
        sdk_timeout_seconds=30,
        data_key=b"0123456789abcdef0123456789abcdef",
        media_token_key=b"abcdef0123456789abcdef0123456789",
        enabled=False,
        worker_enabled=False,
        poll_interval_seconds=60,
        batch_limit=50,
        delivery_limit=50,
        delivery_timeout_seconds=15,
        projects=(ProjectRoute("test", "http://localhost/events", "token", frozenset({"room-1"})),),
    )


def test_normalize_replaces_sdk_file_id_and_seals_original() -> None:
    settings = _settings()
    raw = {
        "seq": 7,
        "msgid": "msg-7",
        "roomid": "room-1",
        "from": "external-1",
        "msgtype": "image",
        "msgtime": 1710000000,
        "decryptedPayload": {"image": {"sdkfileid": "sdk-secret"}},
    }
    event, metadata = normalize_message(raw, "archive_stream", settings.media_token_key)
    assert event["eventId"].endswith("_7")
    assert event["message"]["decryptedPayload"]["image"]["sdkfileid"].startswith("archive_")
    assert event["message"]["mediaRefs"]
    assert metadata["rawMessage"]["decryptedPayload"]["image"]["sdkfileid"] == "sdk-secret"


def test_normalize_replaces_media_ids_inside_note_item_json_strings() -> None:
    settings = _settings()
    raw = {
        "seq": 8,
        "msgid": "msg-note-8",
        "roomid": "room-1",
        "from": "external-1",
        "msgtype": "note",
        "decryptedPayload": {
            "info": {
                "items": [
                    {
                        "msg_type": "image",
                        "content": json.dumps({"sdkfileid": "sdk-note-image", "md5sum": "image-md5"}),
                    },
                    {
                        "msg_type": "video",
                        "content": json.dumps({"sdkfileid": "sdk-note-video", "md5sum": "video-md5"}),
                    },
                ]
            }
        },
    }

    event, _ = normalize_message(raw, "archive_stream", settings.media_token_key)
    items = event["message"]["decryptedPayload"]["info"]["items"]
    image_content = json.loads(items[0]["content"])
    video_content = json.loads(items[1]["content"])

    assert image_content["sdkfileid"].startswith("archive_")
    assert video_content["sdkfileid"].startswith("archive_")
    assert len(event["message"]["mediaRefs"]) == 2
    assert event["message"]["mediaRefs"][0]["path"].endswith("content.sdkfileid")


def test_route_requires_explicit_chat_or_allow_all() -> None:
    route = ProjectRoute("p", "http://localhost", "token")
    assert not route.matches("room-1", "text")
    assert ProjectRoute("p", "http://localhost", "token", allow_all_chats=True).matches("room-1", "text")
    assert not route.matches("", "text")
    assert ProjectRoute("p", "http://localhost", "token", include_direct_messages=True).matches("", "text")
    restricted = ProjectRoute(
        "p",
        "http://localhost",
        "token",
        include_direct_messages=True,
        to_user_ids=frozenset({"sales-2"}),
    )
    assert not restricted.matches("", "text", to_user_ids=("sales-1",))
    assert restricted.matches("", "text", to_user_ids=("sales-2",))


def test_teambuy_private_and_petlove_group_routes_are_isolated() -> None:
    teambuy = ProjectRoute(
        "teamBuy",
        "http://teambuy/events",
        "team-token",
        chat_ids=frozenset({"team-group"}),
        include_direct_messages=True,
        to_user_ids=frozenset({"team-sales"}),
    )
    petlove = ProjectRoute(
        "petlove",
        "http://petlove/events",
        "pet-token",
        chat_ids=frozenset({"pet-group"}),
    )

    assert teambuy.matches("", "text", to_user_ids=("team-sales",))
    assert not teambuy.matches("", "text", to_user_ids=("other-sales",))
    assert teambuy.matches("team-group", "text")
    assert not teambuy.matches("pet-group", "text")
    assert petlove.matches("pet-group", "text")
    assert not petlove.matches("team-group", "text")
    assert not petlove.matches("", "text", to_user_ids=("team-sales",))


def test_sealed_payload_authenticates_content() -> None:
    box = SealedPayload(b"0123456789abcdef0123456789abcdef")
    sealed = box.seal({"roomId": "room-1", "content": "private"})
    assert box.open(sealed)["content"] == "private"


class _ReplayStore:
    def __init__(self) -> None:
        self.rows: list[dict] = []
        self.added: list[tuple[str, str]] = []

    def messages_after(self, stream_key: str, after_seq: int, limit: int) -> list[dict]:
        return self.rows[:limit]

    def add_delivery(self, event_id: str, project_id: str) -> bool:
        self.added.append((event_id, project_id))
        return True


def test_replay_adds_only_events_matching_the_new_project_route() -> None:
    from app.engine import ArchiveCoreEngine

    settings = _settings()
    store = _ReplayStore()
    engine = ArchiveCoreEngine(settings, store, object())
    store.rows = [
        {
            "event_id": "event-7",
            "sealed_payload": engine.sealed.seal(
                {"seq": 7, "roomid": "room-1", "msgtype": "text", "decryptedPayload": {}}
            ),
        },
        {
            "event_id": "event-8",
            "sealed_payload": engine.sealed.seal(
                {"seq": 8, "roomid": "room-other", "msgtype": "text", "decryptedPayload": {}}
            ),
        },
    ]

    result = engine.replay_project("test", after_seq=0, limit=100)

    assert result["scanned"] == 2
    assert result["deliveriesAdded"] == 1
    assert store.added == [("event-7", "test")]
