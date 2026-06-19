from __future__ import annotations

from app.api.dependencies import get_app_service, get_sync_task_queue, get_wecom_archive_client, get_wecom_client
from app.core.config import settings
from app.services.media_storage_service import MediaStorageService
from app.services.media_processing_service import MediaProcessingService
from app.models.domain import UserNote, WecomArchiveMessage
from app.services.archive_message_parsers import ArchiveMessageParser, ArchiveMessageParserRegistry, ArchiveParseResult
from app.services.ocr_service import OcrService
from app.services.helpers import new_id
from app.services.time_utils import now_iso
from app.services.wecom_archive_worker import WecomArchiveWorker
from app.services.wecom_client import DownloadedMedia
from io import BytesIO
from PIL import Image
import asyncio


class FakeSyncTask:
    def __init__(self):
        self.id = "sync_task_test"

    def model_dump(self):
        return {
            "id": self.id,
            "name": "wecom-callback-real-sync",
            "status": "queued",
            "createdAt": "2026-06-08T10:00:00+08:00",
            "updatedAt": "2026-06-08T10:00:00+08:00",
            "result": None,
            "errorMessage": None,
        }


class FakeSyncTaskQueue:
    def __init__(self):
        self.enqueued = []

    def register(self, name, handler):
        self.handler = (name, handler)

    def enqueue(self, name, payload=None, max_attempts=3):
        self.enqueued.append((name, payload, max_attempts))
        return FakeSyncTask()

    def list_recent(self):
        return [FakeSyncTask()]

    def list_logs(self, task_id=None):
        return []


def make_test_image_bytes() -> bytes:
    image = Image.new("RGB", (80, 60), (200, 60, 60))
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def test_wechat_login_uses_openid_identity(client, monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"openid": "openid_real_user_a", "unionid": "union_a"}

    monkeypatch.setattr(settings, "wechat_miniapp_appid", "wx-test")
    monkeypatch.setattr(settings, "wechat_miniapp_secret", "secret-test")
    monkeypatch.setattr("app.services.app_service.httpx.get", lambda *args, **kwargs: FakeResponse())

    first = client.post("/api/auth/wechat-login", json={"code": "code-a", "nickname": "用户A"})
    second = client.post("/api/auth/wechat-login", json={"code": "code-b", "nickname": "用户A更新"})

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["data"]["id"] == second.json()["data"]["id"]
    assert second.json()["data"]["openid"] == "openid_real_user_a"
    assert second.json()["data"]["nickname"] == "用户A更新"


def test_create_note_demo_data_for_owner(client):
    user = client.post("/api/auth/mock-login", json={"nickname": "演示用户", "openid": "openid_demo_owner"}).json()["data"]

    response = client.post("/api/notes/demo-data", params={"ownerUserId": user["id"]})

    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data["notes"]) == 4
    assert data["leadsCreated"] == 2
    assert data["actionsCreated"] == 4
    notes = client.get("/api/notes", params={"ownerUserId": user["id"]}).json()["data"]
    assert len(notes) == 4
    assert all(item["ownerUserId"] == user["id"] for item in notes)
    assert any(item["visibilityConfig"]["cardType"] == "groupbuy_product" for item in data["notes"])
    action_note = next(item for item in data["notes"] if "测试房源A" in item["title"])
    action_rows = client.get(
        f"/api/notes/{action_note['id']}/customer-actions",
        params={"ownerUserId": user["id"]},
    ).json()["data"]
    assert action_rows["summary"]["total"] == 2
    assert action_rows["summary"]["leadContact"] == 1
    assert action_rows["summary"]["appointment"] == 1
    assert action_rows["summary"]["pending"] == 1


def test_wecom_archive_worker_run_once_pulls_then_processes():
    class FakeService:
        def __init__(self):
            self.calls = []

        def pull_wecom_archive_messages(self, archive_client, limit):
            self.calls.append(("pull", archive_client, limit))
            return {"savedCount": 1}

        def process_wecom_archive_messages(self, limit, archive_client=None):
            self.calls.append(("process", limit, archive_client))
            return {"processedCount": 1}

    fake_service = FakeService()
    fake_client = object()
    worker = WecomArchiveWorker(
        fake_service,
        fake_client,
        enabled=True,
        interval_seconds=60,
        pull_limit=20,
    )

    result = asyncio.run(worker.run_once())

    assert result == {"pull": {"savedCount": 1}, "process": {"processedCount": 1}}
    assert fake_service.calls == [("pull", fake_client, 20), ("process", 20, fake_client)]


def test_archive_parser_registry_uses_explicit_parser_metadata():
    class CustomTextParser(ArchiveMessageParser):
        name = "custom-text"
        msg_types = {"text"}

        def parse(self, message, payload, msg_type):
            return ArchiveParseResult(text_blocks=["custom text"])

    registry = ArchiveMessageParserRegistry(parsers=[CustomTextParser()])
    message = WecomArchiveMessage(
        id="archive_registry_001",
        corpId="ww_registry",
        seq=1,
        msgId="archive_registry_msg_001",
        action="send",
        fromUser="wm_customer",
        toList=["user_sales"],
        msgTime="2026-06-20T10:00:00+08:00",
        msgType="text",
        rawPayload={"msgtype": "text"},
        decryptedPayload={"msgtype": "text", "text": {"content": "hello"}},
        processed=False,
        createdAt=now_iso(),
        updatedAt=now_iso(),
    )

    result = registry.parse(message, message.decryptedPayload, "text")

    assert registry.supported_types() == ["text"]
    assert result.text_blocks == ["custom text"]
    assert result.metadata["archiveParser"] == "custom-text"
    assert result.metadata["archiveMsgType"] == "text"


def test_ocr_image_upload_creates_note_via_content_to_note(client):
    service = client.app.dependency_overrides[get_app_service]()
    service.ocr_service = OcrService(
        provider="mock",
        mock_text="小区：碧桂园城市之光\n户型：公寓一房\n面积：42平\n价格：1600元/月\n位置：万家丽地铁口",
    )
    login = client.post("/api/auth/mock-login", json={"nickname": "OCR 用户"}).json()["data"]
    image = Image.new("RGB", (200, 120), color="white")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)

    response = client.post(
        "/api/ocr/image-to-note",
        data={"ownerUserId": login["id"]},
        files={"file": ("house.png", buffer.getvalue(), "image/png")},
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    note = payload["note"]
    config = note["visibilityConfig"]
    assert payload["ocr"]["provider"] == "mock"
    assert payload["ocr"]["configured"] is True
    assert note["ownerUserId"] == login["id"]
    assert note["status"] == "active"
    assert note["coverUrl"].startswith("/media/")
    assert config["sourceType"] == "ocr"
    assert config["cardType"] == "property_listing"
    assert config["structuredData"]["ocr"]["text"].startswith("小区：碧桂园城市之光")
    assert config["structuredData"]["community"] == "碧桂园城市之光"
    assert "图片识别" in config["tags"]


def test_wecom_callback_get_verify(client):
    response = client.get(
        "/api/wecom/kf/teamBuy/callback",
        params={"token": settings.wecom_callback_token, "echostr": "hello-teamBuy"},
    )
    assert response.status_code == 200
    assert response.text == "hello-teamBuy"
    assert response.headers["content-type"].startswith("text/plain")


def test_wecom_callback_post_keeps_mock_fixture_import(client):
    response = client.post(
        "/api/wecom/kf/teamBuy/callback",
        json={"fixture": "link", "externalUserId": "external_callback", "conversationId": "conv_callback"},
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["callback"]["fixture"] == "link"
    assert len(payload["syncResult"]["importBatchIds"]) == 1


def test_wecom_callback_post_triggers_real_sync_when_mock_disabled(client, monkeypatch):
    class CallbackWecomClient:
        def __init__(self):
            self.sync_called = 0

        async def sync_msg(self, cursor=None, token=None, limit=None):
            self.sync_called += 1
            return {
                "errcode": 0,
                "errmsg": "ok",
                "next_cursor": "callback_cursor_done",
                "has_more": 0,
                "msg_list": [
                    {
                        "msgid": "callback_real_msg_001",
                        "open_kfid": "wk_callback",
                        "external_userid": "external_callback_real",
                        "send_time": 1780848000,
                        "msgtype": "text",
                        "text": {"content": "callback real sync item"},
                    }
                ],
            }

    fake_client = CallbackWecomClient()
    fake_queue = FakeSyncTaskQueue()
    monkeypatch.setattr(settings, "wecom_use_mock", False)
    monkeypatch.setattr(settings, "wecom_open_kfid", "wk_callback")
    client.app.dependency_overrides[get_wecom_client] = lambda: fake_client
    client.app.dependency_overrides[get_sync_task_queue] = lambda: fake_queue

    response = client.post("/api/wecom/kf/teamBuy/callback", json={"Event": "kf_msg_or_event"})

    assert response.status_code == 200
    payload = response.json()["data"]
    assert fake_client.sync_called == 0
    assert fake_queue.enqueued[0][0] == "wecom-callback-real-sync"
    assert fake_queue.enqueued[0][1] == {"maxPages": 10}
    assert payload["callback"]["Event"] == "kf_msg_or_event"
    assert payload["syncTask"]["status"] == "queued"


def test_wecom_sync_tasks_lists_background_queue(client):
    fake_queue = FakeSyncTaskQueue()
    client.app.dependency_overrides[get_sync_task_queue] = lambda: fake_queue

    response = client.get("/api/wecom/sync-tasks")

    assert response.status_code == 200
    assert response.json()["data"][0]["id"] == "sync_task_test"


def test_wecom_sync_task_logs_lists_background_queue_logs(client):
    fake_queue = FakeSyncTaskQueue()
    client.app.dependency_overrides[get_sync_task_queue] = lambda: fake_queue

    response = client.get("/api/wecom/sync-tasks/logs")

    assert response.status_code == 200
    assert response.json()["data"] == []


def test_wecom_config_check_reports_missing_real_fields(client, monkeypatch):
    monkeypatch.setattr(settings, "public_base_url", "https://teambuy.lifelove.top")
    response = client.get("/api/wecom/config-check")
    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload["success"], bool)
    assert isinstance(payload["data"]["missing"], list)
    assert payload["data"]["callbackUrl"].endswith("/api/wecom/kf/teamBuy/callback")


def test_wecom_archive_callback_get_verify_reuses_callback_token(client, monkeypatch):
    monkeypatch.setattr(settings, "wecom_callback_token", "shared-token")
    monkeypatch.setattr(settings, "wecom_archive_callback_token", "shared-token")

    response = client.get(
        "/api/wecom/archive/callback",
        params={"token": "shared-token", "echostr": "hello-archive"},
    )

    assert response.status_code == 200
    assert response.text == "hello-archive"
    assert response.headers["content-type"].startswith("text/plain")


def test_wecom_archive_callback_rejects_wrong_token(client, monkeypatch):
    monkeypatch.setattr(settings, "wecom_callback_token", "shared-token")
    monkeypatch.setattr(settings, "wecom_archive_callback_token", "shared-token")

    response = client.get(
        "/api/wecom/archive/callback",
        params={"token": "wrong-token", "echostr": "hello-archive"},
    )

    assert response.status_code == 403


def test_wecom_archive_callback_post_accepts_event(client):
    response = client.post("/api/wecom/archive/callback", json={"Event": "archive_event"})

    assert response.status_code == 200
    assert response.json()["data"]["callback"]["Event"] == "archive_event"


def test_wecom_archive_config_check_reports_key_status(client, monkeypatch, tmp_path):
    private_key = tmp_path / "archive_private.pem"
    public_key = tmp_path / "archive_public.pem"
    private_key.write_text("PRIVATE KEY", encoding="utf-8")
    public_key.write_text("PUBLIC KEY", encoding="utf-8")
    monkeypatch.setattr(settings, "wecom_corp_id", "ww_archive")
    monkeypatch.setattr(settings, "wecom_archive_enabled", True)
    monkeypatch.setattr(settings, "wecom_archive_secret", "archive-secret")
    monkeypatch.setattr(settings, "wecom_archive_private_key_path", private_key)
    monkeypatch.setattr(settings, "wecom_archive_public_key_path", public_key)
    monkeypatch.setattr(settings, "wecom_archive_sdk_lib_path", None)

    response = client.get("/api/wecom/archive/config-check")

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["enabled"] is True
    assert payload["data"]["privateKeyReadable"] is True
    assert payload["data"]["publicKey"] == "PUBLIC KEY"
    assert payload["data"]["callbackUrl"].endswith("/api/wecom/archive/callback")
    assert payload["data"]["callbackTokenConfigured"] is True
    assert isinstance(payload["data"]["workerEnabled"], bool)
    assert isinstance(payload["data"]["workerIntervalSeconds"], int)
    assert payload["data"]["missing"] == []


def test_wecom_archive_messages_require_admin_token(client, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", "archive-admin")

    response = client.get("/api/wecom/archive/messages")

    assert response.status_code == 403


def test_wecom_archive_mock_messages_persist_cursor_and_dedupe(client, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", "archive-admin")
    monkeypatch.setattr(settings, "wecom_corp_id", "ww_archive")
    payload = {
        "messages": [
            {
                "seq": 101,
                "msgid": "archive_msg_001",
                "action": "send",
                "from": "wm_external",
                "tolist": ["zhangsan"],
                "msgtime": "2026-06-17T17:50:00+08:00",
                "msgtype": "text",
                "decryptedPayload": {"text": {"content": "客户发来一段资料"}},
            }
        ]
    }

    first = client.post("/api/wecom/archive/mock-messages", json=payload, headers={"X-Admin-Token": "archive-admin"})
    second = client.post("/api/wecom/archive/mock-messages", json=payload, headers={"X-Admin-Token": "archive-admin"})
    messages = client.get("/api/wecom/archive/messages", headers={"X-Admin-Token": "archive-admin"})
    cursor = client.get("/api/wecom/archive/cursor", headers={"X-Admin-Token": "archive-admin"})

    assert first.status_code == 200
    assert first.json()["data"]["savedCount"] == 1
    assert second.status_code == 200
    assert second.json()["data"]["savedCount"] == 0
    assert second.json()["data"]["skippedDuplicateCount"] == 1
    assert messages.status_code == 200
    assert len(messages.json()["data"]) == 1
    assert messages.json()["data"][0]["msgId"] == "archive_msg_001"
    assert cursor.status_code == 200
    assert cursor.json()["data"]["seq"] == 101


def test_wecom_archive_pull_reports_missing_sdk_config(client, monkeypatch):
    class MissingArchiveClient:
        corp_id = "ww_archive"

        def pull_and_decrypt(self, seq, limit):
            raise RuntimeError("会话内容存档 SDK 配置不完整: WECOM_ARCHIVE_SDK_LIB_PATH")

    monkeypatch.setattr(settings, "admin_token", "archive-admin")
    client.app.dependency_overrides[get_wecom_archive_client] = lambda: MissingArchiveClient()

    response = client.post("/api/wecom/archive/pull", headers={"X-Admin-Token": "archive-admin"})

    assert response.status_code == 502
    detail = response.json()["detail"]
    assert detail["message"] == "会话内容存档拉取失败"
    assert "WECOM_ARCHIVE_SDK_LIB_PATH" in detail["error"]
    assert detail["cursor"]["status"] == "failed"


def test_wecom_archive_pull_saves_decrypted_messages(client, monkeypatch):
    class FakeArchiveClient:
        corp_id = "ww_archive"

        def pull_and_decrypt(self, seq, limit):
            assert seq == 0
            assert limit == 20
            return {
                "rawCount": 1,
                "messages": [
                    {
                        "seq": 201,
                        "msgid": "archive_pull_msg_001",
                        "action": "send",
                        "from": "wm_customer",
                        "tolist": ["user_sales"],
                        "msgtime": 1781710904435,
                        "msgtype": "text",
                        "decryptedPayload": {
                            "msgid": "archive_pull_msg_001",
                            "action": "send",
                            "from": "wm_customer",
                            "tolist": ["user_sales"],
                            "msgtime": 1781710904435,
                            "msgtype": "text",
                            "text": {"content": "客户想看三房，总价 300 万，电话 13800000000"},
                        },
                    }
                ],
            }

    monkeypatch.setattr(settings, "admin_token", "archive-admin")
    client.app.dependency_overrides[get_wecom_archive_client] = lambda: FakeArchiveClient()

    response = client.post("/api/wecom/archive/pull", params={"limit": 20}, headers={"X-Admin-Token": "archive-admin"})
    messages = client.get("/api/wecom/archive/messages", headers={"X-Admin-Token": "archive-admin"})

    assert response.status_code == 200
    assert response.json()["data"]["savedCount"] == 1
    assert response.json()["data"]["cursor"]["seq"] == 201
    assert messages.json()["data"][0]["msgId"] == "archive_pull_msg_001"
    assert messages.json()["data"][0]["msgTime"].endswith("+08:00")


def test_wecom_archive_process_creates_user_note_and_is_idempotent(client, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", "archive-admin")
    payload = {
        "corpId": "ww_archive",
        "messages": [
            {
                "seq": 301,
                "msgid": "archive_process_msg_001",
                "action": "send",
                "from": "wm_customer",
                "tolist": ["user_sales"],
                "msgtime": "2026-06-17T18:40:00+08:00",
                "msgtype": "text",
                "decryptedPayload": {
                    "msgid": "archive_process_msg_001",
                    "action": "send",
                    "from": "wm_customer",
                    "tolist": ["user_sales"],
                    "msgtime": "2026-06-17T18:40:00+08:00",
                    "msgtype": "text",
                    "text": {"content": "客户要浦东两房，预算 500 万，电话 13900000000"},
                },
            }
        ],
    }
    saved = client.post("/api/wecom/archive/mock-messages", json=payload, headers={"X-Admin-Token": "archive-admin"})
    first = client.post("/api/wecom/archive/process", headers={"X-Admin-Token": "archive-admin"})
    second = client.post("/api/wecom/archive/process", headers={"X-Admin-Token": "archive-admin"})
    messages = client.get("/api/wecom/archive/messages", headers={"X-Admin-Token": "archive-admin"}).json()["data"]
    pending = client.get("/api/imports/pending").json()["data"]

    assert saved.status_code == 200
    assert first.status_code == 200
    assert first.json()["data"]["processedCount"] == 1
    note_id = first.json()["data"]["processed"][0]["noteId"]
    assert second.status_code == 200
    assert second.json()["data"]["processedCount"] == 0
    archive_message = next(item for item in messages if item["msgId"] == "archive_process_msg_001")
    assert archive_message["generatedNoteId"] == note_id
    generated = next(item for item in pending if item["generatedNote"] and item["generatedNote"]["id"] == note_id)
    assert generated["generatedNote"] is not None


def test_wecom_archive_process_auto_assigns_bound_external_user(client, monkeypatch):
    login = client.post("/api/auth/mock-login", json={"nickname": "自动归属用户"}).json()["data"]
    client.post(
        "/api/wecom/mock-sync",
        json={"externalUserId": "wm_bound_customer", "conversationId": "conv_bound_claim", "fixture": "note"},
    )
    pending = client.get("/api/imports/pending").json()["data"]
    target = pending[-1]
    client.post(f"/api/imports/{target['id']}/claim", json={"userId": login["id"]})
    monkeypatch.setattr(settings, "admin_token", "archive-admin")
    payload = {
        "corpId": "ww_archive_bound",
        "messages": [
            {
                "seq": 303,
                "msgid": "archive_bound_msg_001",
                "action": "send",
                "from": "wm_bound_customer",
                "tolist": ["user_sales"],
                "msgtime": "2026-06-17T18:45:00+08:00",
                "msgtype": "text",
                "decryptedPayload": {
                    "msgid": "archive_bound_msg_001",
                    "action": "send",
                    "from": "wm_bound_customer",
                    "tolist": ["user_sales"],
                    "msgtime": "2026-06-17T18:45:00+08:00",
                    "msgtype": "text",
                    "text": {"content": "绑定后自动进入我的笔记"},
                },
            }
        ],
    }

    saved = client.post("/api/wecom/archive/mock-messages", json=payload, headers={"X-Admin-Token": "archive-admin"})
    processed = client.post("/api/wecom/archive/process", headers={"X-Admin-Token": "archive-admin"})
    notes = client.get("/api/notes", params={"ownerUserId": login["id"]}).json()["data"]
    pending_after = client.get("/api/imports/pending").json()["data"]

    assert saved.status_code == 200
    assert processed.status_code == 200
    result = processed.json()["data"]
    assert result["processedCount"] == 1
    note_id = result["processed"][0]["noteId"]
    assert any(item["id"] == note_id and item["ownerUserId"] == login["id"] for item in notes)
    assert not any(item["generatedNote"] and item["generatedNote"]["id"] == note_id for item in pending_after)


def test_wecom_archive_process_parses_note_items(client, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", "archive-admin")
    payload = {
        "corpId": "ww_archive",
        "messages": [
            {
                "seq": 302,
                "msgid": "archive_note_msg_001",
                "action": "send",
                "from": "wm_customer",
                "tolist": ["user_sales"],
                "msgtime": 1781725151786,
                "msgtype": "note",
                "decryptedPayload": {
                    "msgid": "archive_note_msg_001",
                    "action": "send",
                    "from": "wm_customer",
                    "tolist": ["user_sales"],
                    "msgtime": 1781725151786,
                    "msgtype": "note",
                    "info": {
                        "items": [
                            {
                                "msg_type": "text",
                                "content": "{\"content\":\"小区：碧桂园城市之光\\n户型：公寓一房\\n价格：1600\"}",
                            },
                            {
                                "msg_type": "location",
                                "content": "{\"address\":\"湖南省长沙市雨花区嘉雨路碧桂园城市之光\",\"title\":\"碧桂园城市之光1栋\"}",
                            },
                            {
                                "msg_type": "image",
                                "content": "{\"md5sum\":\"img-md5\",\"filesize\":100063,\"sdkfileid\":\"sdk-file-001\"}",
                            },
                        ]
                    },
                },
            }
        ],
    }

    saved = client.post("/api/wecom/archive/mock-messages", json=payload, headers={"X-Admin-Token": "archive-admin"})
    processed = client.post("/api/wecom/archive/process", headers={"X-Admin-Token": "archive-admin"})
    pending = client.get("/api/imports/pending").json()["data"]

    assert saved.status_code == 200
    assert processed.status_code == 200
    assert processed.json()["data"]["processedCount"] == 1
    note_id = processed.json()["data"]["processed"][0]["noteId"]
    generated = next(item for item in pending if item["generatedNote"] and item["generatedNote"]["id"] == note_id)
    note = generated["generatedNote"]
    assert "碧桂园城市之光" in note["body"]
    assert "位置：湖南省长沙市雨花区嘉雨路碧桂园城市之光" in note["body"]
    assert note["media"][0]["mediaId"] == "sdk-file-001"


def test_wecom_archive_process_parses_groupbuy_chatrecord_items(client, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", "archive-admin")
    payload = {
        "corpId": "ww_archive_chatrecord_groupbuy",
        "messages": [
            {
                "seq": 303,
                "msgid": "archive_chatrecord_groupbuy_001",
                "action": "send",
                "from": "wm_customer",
                "tolist": ["user_sales"],
                "msgtime": 1781725152786,
                "msgtype": "chatrecord",
                "decryptedPayload": {
                    "msgid": "archive_chatrecord_groupbuy_001",
                    "action": "send",
                    "from": "wm_customer",
                    "tolist": ["user_sales"],
                    "msgtime": 1781725152786,
                    "msgtype": "chatrecord",
                    "chatrecord": {
                        "title": "群聊的聊天记录",
                        "item": [
                            {
                                "type": "ChatRecordText",
                                "content": "{\"content\":\"连续一个月，鸡蛋行情都是上涨状态，活动也是给大家争取了很久，还有优惠。4斤不多，约40多个，会配小礼篮。\"}",
                                "msgtime": 1779852781,
                            },
                            {
                                "type": "ChatRecordText",
                                "content": "{\"content\":\"[图片]\"}",
                                "msgtime": 1779852783,
                            },
                            {
                                "type": "ChatRecordText",
                                "content": "{\"content\":\"挑食宝宝救星来啦！\\n我们的白凤乌鸡蛋\\n精选种鸡，白凤乌鸡\\n简单一煮，蛋香十足\"}",
                                "msgtime": 1779852800,
                            },
                        ],
                    },
                },
            }
        ],
    }

    saved = client.post("/api/wecom/archive/mock-messages", json=payload, headers={"X-Admin-Token": "archive-admin"})
    processed = client.post("/api/wecom/archive/process", headers={"X-Admin-Token": "archive-admin"})
    pending = client.get("/api/imports/pending").json()["data"]

    assert saved.status_code == 200
    assert processed.status_code == 200
    assert processed.json()["data"]["processedCount"] == 1
    note_id = processed.json()["data"]["processed"][0]["noteId"]
    generated = next(item for item in pending if item["generatedNote"] and item["generatedNote"]["id"] == note_id)
    note = generated["generatedNote"]
    config = note["visibilityConfig"]
    assert "白凤乌鸡蛋" in note["body"]
    assert "[图片]" not in note["body"]
    assert config["cardType"] == "groupbuy_product"
    assert config["systemCategory"] == "团购"
    assert config["structuredData"]["productName"] == "白凤乌鸡蛋"
    assert config["structuredData"]["spec"] == "4斤，约40多个"


def test_wecom_archive_process_handles_miniapp_card(client, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", "archive-admin")
    payload = {
        "corpId": "ww_archive",
        "messages": [
            {
                "seq": 305,
                "msgid": "archive_weapp_msg_001",
                "action": "send",
                "from": "wm_customer_weapp",
                "tolist": ["user_sales"],
                "msgtime": "2026-06-19T02:41:16+08:00",
                "msgtype": "weapp",
                "decryptedPayload": {
                    "msgid": "archive_weapp_msg_001",
                    "action": "send",
                    "from": "wm_customer_weapp",
                    "tolist": ["user_sales"],
                    "msgtime": "2026-06-19T02:41:16+08:00",
                    "msgtype": "weapp",
                    "weapp": {
                        "appid": "wxcfd8224218167d98",
                        "title": "三江尊园 全天采光 好楼层 拎包入住",
                        "pagepath": "subpackages/ershoufang/pages/esfDetail/esfDetail.html?cityId=150200&houseCode=101137825091&source=share_beikexcx",
                        "username": "gh_2dbd87cb164c@app",
                        "description": "贝壳找房丨二手房新房租房装修",
                        "displayname": "贝壳找房丨二手房新房租房装修",
                    },
                },
            }
        ],
    }

    saved = client.post("/api/wecom/archive/mock-messages", json=payload, headers={"X-Admin-Token": "archive-admin"})
    processed = client.post("/api/wecom/archive/process", headers={"X-Admin-Token": "archive-admin"})
    pending = client.get("/api/imports/pending").json()["data"]

    assert saved.status_code == 200
    assert processed.status_code == 200
    assert processed.json()["data"]["processedCount"] == 1
    note_id = processed.json()["data"]["processed"][0]["noteId"]
    generated = next(item for item in pending if item["generatedNote"] and item["generatedNote"]["id"] == note_id)
    note = generated["generatedNote"]
    config = note["visibilityConfig"]
    assert generated["sourceType"] == "miniapp_link"
    assert note["title"] == "三江尊园 全天采光 好楼层 拎包入住"
    assert "小程序来源：贝壳找房" in note["body"]
    assert "房源编码：101137825091" in note["body"]
    assert "小程序路径：" not in note["body"]
    assert note["phone"] is None
    assert config["sourceType"] == "miniapp"
    assert config["showPhone"] is False
    assert config["systemCategory"] == "小程序"
    assert "小程序" in config["tags"]
    assert "贝壳找房" in config["tags"]
    suggestion = next(item for item in config["typeSuggestions"] if item["cardType"] == "property_listing")
    assert suggestion["reason"]
    assert "score" in suggestion
    assert config["recognitionExplanation"]["level"] == "medium"
    assert config["recognitionExplanation"]["selectedType"] == "text_note"
    assert any(item["cardType"] == "property_listing" for item in config["recognitionExplanation"]["candidates"])
    assert config["structuredData"]["miniapp"]["houseCode"] == "101137825091"
    assert config["structuredData"]["miniapp"]["pagePath"].startswith("subpackages/ershoufang/pages/esfDetail")
    assert config["structuredData"]["miniapp"]["webUrl"] == "https://m.ke.com/baotou/ershoufang/101137825091.html"
    assert config["sourceUrl"] == "https://m.ke.com/baotou/ershoufang/101137825091.html"
    assert config["conversionConfig"]["enableLightScrm"] is True
    assert config["conversionConfig"]["collectLeads"] is True
    assert config["conversionConfig"]["enableAppointment"] is True
    assert config["conversionConfig"]["enablePrivateConsultation"] is True
    assert config["conversionConfig"]["showContactPhone"] is False

    login = client.post("/api/auth/mock-login", json={"nickname": "房源确认用户"}).json()["data"]
    claim = client.post(f"/api/imports/{generated['id']}/claim", json={"userId": login["id"]})
    confirmed = client.post(
        f"/api/notes/{claim.json()['data']['note']['id']}/confirm-type",
        json={"ownerUserId": login["id"], "cardType": "property_listing"},
    )

    assert confirmed.status_code == 200
    confirmed_config = confirmed.json()["data"]["visibilityConfig"]
    assert confirmed_config["cardType"] == "property_listing"
    assert confirmed_config["cardState"] == "generated"
    assert confirmed_config["typeSuggestions"] == []
    assert confirmed_config["recognitionConfidence"]["level"] == "manual"
    assert confirmed_config["recognitionExplanation"]["manualConfirmation"]["cardType"] == "property_listing"
    assert confirmed_config["structuredData"]["miniapp"]["houseCode"] == "101137825091"
    assert confirmed_config["conversionConfig"]["showContactPhone"] is False


def test_wecom_archive_process_groups_nearby_messages(client, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", "archive-admin")
    payload = {
        "corpId": "ww_archive",
        "messages": [
            {
                "seq": 401,
                "msgid": "archive_group_text_001",
                "action": "send",
                "from": "wm_customer",
                "tolist": ["user_sales"],
                "msgtime": 1781725200000,
                "msgtype": "text",
                "decryptedPayload": {
                    "msgid": "archive_group_text_001",
                    "action": "send",
                    "from": "wm_customer",
                    "tolist": ["user_sales"],
                    "msgtime": 1781725200000,
                    "msgtype": "text",
                    "text": {"content": "房源：碧桂园一房，租金1600"},
                },
            },
            {
                "seq": 402,
                "msgid": "archive_group_image_001",
                "action": "send",
                "from": "wm_customer",
                "tolist": ["user_sales"],
                "msgtime": 1781725203000,
                "msgtype": "image",
                "decryptedPayload": {
                    "msgid": "archive_group_image_001",
                    "action": "send",
                    "from": "wm_customer",
                    "tolist": ["user_sales"],
                    "msgtime": 1781725203000,
                    "msgtype": "image",
                    "image": {"sdkfileid": "image-sdk-file", "md5sum": "image-md5", "filesize": 1024},
                },
            },
        ],
    }

    saved = client.post("/api/wecom/archive/mock-messages", json=payload, headers={"X-Admin-Token": "archive-admin"})
    processed = client.post("/api/wecom/archive/process", headers={"X-Admin-Token": "archive-admin"})
    pending = client.get("/api/imports/pending").json()["data"]

    assert saved.status_code == 200
    assert processed.status_code == 200
    result = processed.json()["data"]
    assert result["processedCount"] == 1
    assert result["processed"][0]["seqs"] == [401, 402]
    note_id = result["processed"][0]["noteId"]
    generated = next(item for item in pending if item["generatedNote"] and item["generatedNote"]["id"] == note_id)
    assert len(generated["rawMessageIds"]) == 2
    assert "房源：碧桂园一房" in generated["generatedNote"]["body"]
    assert generated["generatedNote"]["media"][0]["mediaId"] == "image-sdk-file"


def test_wecom_archive_process_downloads_and_attaches_image_media(client, monkeypatch, tmp_path):
    class FakeArchiveClient:
        def __init__(self):
            self.downloaded_media_ids = []

        def download_media(self, media_id):
            self.downloaded_media_ids.append(media_id)
            return DownloadedMedia(make_test_image_bytes(), "image/png", "archive-cover.png")

    monkeypatch.setattr(settings, "admin_token", "archive-admin")
    service = client.app.dependency_overrides[get_app_service]()
    media_dir = tmp_path / "archive-media"
    service.media_storage_service = MediaStorageService("local", media_dir, "/media")
    fake_archive_client = FakeArchiveClient()
    client.app.dependency_overrides[get_wecom_archive_client] = lambda: fake_archive_client
    payload = {
        "corpId": "ww_archive_media",
        "messages": [
            {
                "seq": 501,
                "msgid": "archive_media_text_001",
                "action": "send",
                "from": "wm_customer",
                "tolist": ["user_sales"],
                "msgtime": 1781725300000,
                "msgtype": "text",
                "decryptedPayload": {
                    "msgid": "archive_media_text_001",
                    "action": "send",
                    "from": "wm_customer",
                    "tolist": ["user_sales"],
                    "msgtime": 1781725300000,
                    "msgtype": "text",
                    "text": {"content": "带图房源：碧桂园一房"},
                },
            },
            {
                "seq": 502,
                "msgid": "archive_media_image_001",
                "action": "send",
                "from": "wm_customer",
                "tolist": ["user_sales"],
                "msgtime": 1781725302000,
                "msgtype": "image",
                "decryptedPayload": {
                    "msgid": "archive_media_image_001",
                    "action": "send",
                    "from": "wm_customer",
                    "tolist": ["user_sales"],
                    "msgtime": 1781725302000,
                    "msgtype": "image",
                    "image": {"sdkfileid": "archive-image-sdk-001", "md5sum": "image-md5", "filesize": 1024},
                },
            },
        ],
    }

    saved = client.post("/api/wecom/archive/mock-messages", json=payload, headers={"X-Admin-Token": "archive-admin"})
    processed = client.post("/api/wecom/archive/process", headers={"X-Admin-Token": "archive-admin"})
    pending = client.get("/api/imports/pending").json()["data"]

    assert saved.status_code == 200
    assert processed.status_code == 200
    result = processed.json()["data"]
    assert result["processedCount"] == 1
    assert result["processed"][0]["media"]["downloadedCount"] == 1
    assert fake_archive_client.downloaded_media_ids == ["archive-image-sdk-001"]
    note_id = result["processed"][0]["noteId"]
    generated = next(item for item in pending if item["generatedNote"] and item["generatedNote"]["id"] == note_id)
    note = generated["generatedNote"]
    card = generated["generatedCard"]
    assert note["media"][0]["url"].startswith("/media/")
    assert note["media"][0]["url"].endswith(".webp")
    assert card["coverUrl"] == note["media"][0]["url"]
    assert card["media"][0]["url"] == note["media"][0]["url"]
    assert len(list(media_dir.iterdir())) == 1


def test_wecom_archive_media_download_failure_keeps_note_and_records_retry(client, monkeypatch):
    class FailingArchiveClient:
        def download_media(self, media_id):
            raise RuntimeError("temporary archive media failure")

    monkeypatch.setattr(settings, "admin_token", "archive-admin")
    client.app.dependency_overrides[get_wecom_archive_client] = lambda: FailingArchiveClient()
    payload = {
        "corpId": "ww_archive_media_failed",
        "messages": [
            {
                "seq": 511,
                "msgid": "archive_media_failed_text_001",
                "action": "send",
                "from": "wm_customer",
                "tolist": ["user_sales"],
                "msgtime": 1781725400000,
                "msgtype": "text",
                "decryptedPayload": {
                    "msgid": "archive_media_failed_text_001",
                    "action": "send",
                    "from": "wm_customer",
                    "tolist": ["user_sales"],
                    "msgtime": 1781725400000,
                    "msgtype": "text",
                    "text": {"content": "图片先失败，文字仍要入库"},
                },
            },
            {
                "seq": 512,
                "msgid": "archive_media_failed_image_001",
                "action": "send",
                "from": "wm_customer",
                "tolist": ["user_sales"],
                "msgtime": 1781725401000,
                "msgtype": "image",
                "decryptedPayload": {
                    "msgid": "archive_media_failed_image_001",
                    "action": "send",
                    "from": "wm_customer",
                    "tolist": ["user_sales"],
                    "msgtime": 1781725401000,
                    "msgtype": "image",
                    "image": {"sdkfileid": "archive-image-sdk-failed", "md5sum": "image-md5", "filesize": 1024},
                },
            },
        ],
    }

    saved = client.post("/api/wecom/archive/mock-messages", json=payload, headers={"X-Admin-Token": "archive-admin"})
    processed = client.post("/api/wecom/archive/process", headers={"X-Admin-Token": "archive-admin"})
    pending = client.get("/api/imports/pending").json()["data"]
    retries = client.get("/api/wecom/media-retries", headers={"X-Admin-Token": "archive-admin"}).json()["data"]

    assert saved.status_code == 200
    assert processed.status_code == 200
    result = processed.json()["data"]
    assert result["processedCount"] == 1
    assert result["processed"][0]["media"]["failedCount"] == 1
    note_id = result["processed"][0]["noteId"]
    generated = next(item for item in pending if item["generatedNote"] and item["generatedNote"]["id"] == note_id)
    assert "图片先失败" in generated["generatedNote"]["body"]
    assert generated["generatedNote"]["media"][0]["mediaId"] == "archive-image-sdk-failed"
    assert generated["generatedNote"]["media"][0]["url"] is None
    assert retries[-1]["mediaId"] == "archive-image-sdk-failed"
    assert retries[-1]["status"] == "failed"


def test_wecom_archive_media_backfill_updates_existing_note_and_card(client, monkeypatch, tmp_path):
    class FailingArchiveClient:
        def download_media(self, media_id):
            raise RuntimeError("temporary archive media failure")

    class SuccessfulArchiveClient:
        def __init__(self):
            self.downloaded_media_ids = []

        def download_media(self, media_id):
            self.downloaded_media_ids.append(media_id)
            return DownloadedMedia(make_test_image_bytes(), "image/png", "archive-backfill.png")

    monkeypatch.setattr(settings, "admin_token", "archive-admin")
    service = client.app.dependency_overrides[get_app_service]()
    media_dir = tmp_path / "archive-backfill-media"
    service.media_storage_service = MediaStorageService("local", media_dir, "/media")
    client.app.dependency_overrides[get_wecom_archive_client] = lambda: FailingArchiveClient()
    payload = {
        "corpId": "ww_archive_media_backfill",
        "messages": [
            {
                "seq": 521,
                "msgid": "archive_media_backfill_text_001",
                "action": "send",
                "from": "wm_customer",
                "tolist": ["user_sales"],
                "msgtime": 1781725500000,
                "msgtype": "text",
                "decryptedPayload": {
                    "msgid": "archive_media_backfill_text_001",
                    "action": "send",
                    "from": "wm_customer",
                    "tolist": ["user_sales"],
                    "msgtime": 1781725500000,
                    "msgtype": "text",
                    "text": {"content": "历史图片需要回填"},
                },
            },
            {
                "seq": 522,
                "msgid": "archive_media_backfill_image_001",
                "action": "send",
                "from": "wm_customer",
                "tolist": ["user_sales"],
                "msgtime": 1781725501000,
                "msgtype": "image",
                "decryptedPayload": {
                    "msgid": "archive_media_backfill_image_001",
                    "action": "send",
                    "from": "wm_customer",
                    "tolist": ["user_sales"],
                    "msgtime": 1781725501000,
                    "msgtype": "image",
                    "image": {"sdkfileid": "archive-image-sdk-backfill", "md5sum": "image-md5", "filesize": 1024},
                },
            },
        ],
    }

    saved = client.post("/api/wecom/archive/mock-messages", json=payload, headers={"X-Admin-Token": "archive-admin"})
    processed = client.post("/api/wecom/archive/process", headers={"X-Admin-Token": "archive-admin"})
    note_id = processed.json()["data"]["processed"][0]["noteId"]
    pending_before = client.get("/api/imports/pending").json()["data"]
    generated_before = next(item for item in pending_before if item["generatedNote"] and item["generatedNote"]["id"] == note_id)
    assert saved.status_code == 200
    assert generated_before["generatedNote"]["media"][0]["url"] is None
    assert generated_before["generatedCard"]["media"] == []

    successful_client = SuccessfulArchiveClient()
    client.app.dependency_overrides[get_wecom_archive_client] = lambda: successful_client
    backfilled = client.post(
        "/api/wecom/archive/media-backfill",
        params={"limit": 10},
        headers={"X-Admin-Token": "archive-admin"},
    )
    pending_after = client.get("/api/imports/pending").json()["data"]
    generated_after = next(item for item in pending_after if item["generatedNote"] and item["generatedNote"]["id"] == note_id)

    assert backfilled.status_code == 200
    result = backfilled.json()["data"]
    assert result["downloadedCount"] == 1
    assert result["updatedNoteCount"] == 1
    assert result["updatedCardCount"] == 1
    assert successful_client.downloaded_media_ids == ["archive-image-sdk-backfill"]
    assert generated_after["generatedNote"]["media"][0]["url"].startswith("/media/")
    assert generated_after["generatedCard"]["coverUrl"] == generated_after["generatedNote"]["media"][0]["url"]
    assert generated_after["generatedCard"]["media"][0]["url"] == generated_after["generatedNote"]["media"][0]["url"]
    assert len(list(media_dir.iterdir())) == 1


def test_real_sync_uses_mock_real_response_while_mock_enabled(client):
    response = client.post("/api/wecom/real-sync")
    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["source"] == "mock-real-sync-response"
    assert payload["pagesSynced"] == 1
    assert payload["nextCursor"] == "mock_real_cursor_002"
    assert payload["hasMore"] is False
    assert len(payload["importResult"]["importBatchIds"]) >= 1


def test_real_sync_mock_response_is_idempotent(client):
    first = client.post("/api/wecom/real-sync")
    second = client.post("/api/wecom/real-sync")

    assert first.status_code == 200
    assert second.status_code == 200
    second_payload = second.json()["data"]["importResult"]
    assert second_payload["importBatchIds"] == []
    assert second_payload["deduplicatedCount"] == 4


def test_real_sync_paginates_and_persists_cursor(client, monkeypatch):
    class FakeWecomClient:
        def __init__(self):
            self.cursors = []

        async def sync_msg(self, cursor=None, token=None, limit=None):
            self.cursors.append(cursor)
            if cursor is None:
                return {
                    "errcode": 0,
                    "errmsg": "ok",
                    "next_cursor": "cursor_page_2",
                    "has_more": 1,
                    "msg_list": [
                        {
                            "msgid": "paged_msg_001",
                            "open_kfid": "wk_page",
                            "external_userid": "external_page",
                            "send_time": 1780848000,
                            "msgtype": "text",
                            "text": {"content": "first page item"},
                        }
                    ],
                }
            return {
                "errcode": 0,
                "errmsg": "ok",
                "next_cursor": "cursor_done",
                "has_more": 0,
                "msg_list": [
                    {
                        "msgid": "paged_msg_002",
                        "open_kfid": "wk_page",
                        "external_userid": "external_page",
                        "send_time": 1780848010,
                        "msgtype": "link",
                        "link": {"title": "second page item", "url": "https://example.com/page-2"},
                    }
                ],
            }

    fake_client = FakeWecomClient()
    monkeypatch.setattr(settings, "wecom_use_mock", False)
    monkeypatch.setattr(settings, "wecom_open_kfid", "wk_page")
    client.app.dependency_overrides[get_wecom_client] = lambda: fake_client

    response = client.post("/api/wecom/real-sync")

    assert response.status_code == 200
    payload = response.json()["data"]
    assert fake_client.cursors == [None, "cursor_page_2"]
    assert payload["pagesSynced"] == 2
    assert payload["nextCursor"] == "cursor_done"
    assert payload["hasMore"] is False
    assert len(payload["importResult"]["importBatchIds"]) == 2


def test_real_sync_downloads_and_stores_image_video_media(client, monkeypatch, tmp_path):
    class FakeWecomClient:
        def __init__(self):
            self.downloaded_media_ids = []

        async def sync_msg(self, cursor=None, token=None, limit=None):
            return {
                "errcode": 0,
                "errmsg": "ok",
                "next_cursor": "cursor_media_done",
                "has_more": 0,
                "msg_list": [
                    {
                        "msgid": "media_msg_text",
                        "open_kfid": "wk_media",
                        "external_userid": "external_media",
                        "send_time": 1780848000,
                        "msgtype": "text",
                        "text": {"content": "media item with phone 13700000000"},
                    },
                    {
                        "msgid": "media_msg_image",
                        "open_kfid": "wk_media",
                        "external_userid": "external_media",
                        "send_time": 1780848001,
                        "msgtype": "image",
                        "image": {"media_id": "media_image_001", "filename": "cover.png"},
                    },
                    {
                        "msgid": "media_msg_video",
                        "open_kfid": "wk_media",
                        "external_userid": "external_media",
                        "send_time": 1780848002,
                        "msgtype": "video",
                        "video": {"media_id": "media_video_001", "filename": "room.mp4"},
                    },
                ],
            }

        async def download_media(self, media_id):
            self.downloaded_media_ids.append(media_id)
            if media_id == "media_image_001":
                return DownloadedMedia(b"image-bytes", "image/png", "cover.png")
            return DownloadedMedia(b"video-bytes", "video/mp4", "room.mp4")

    service = client.app.dependency_overrides[get_app_service]()
    media_dir = tmp_path / "media"
    service.media_storage_service = MediaStorageService(
        storage_mode="local",
        storage_dir=media_dir,
        public_url_prefix="/media",
    )
    fake_client = FakeWecomClient()
    monkeypatch.setattr(settings, "wecom_use_mock", False)
    monkeypatch.setattr(settings, "wecom_open_kfid", "wk_media")
    client.app.dependency_overrides[get_wecom_client] = lambda: fake_client

    response = client.post("/api/wecom/real-sync")

    assert response.status_code == 200
    assert set(fake_client.downloaded_media_ids) == {"media_image_001", "media_video_001"}
    pending = client.get("/api/imports/pending").json()["data"]
    card = pending[-1]["generatedCard"]
    assert card["coverUrl"].startswith("/media/")
    assert any(item["type"] == "video" and item["url"].startswith("/media/") for item in card["media"])
    assert len(list(media_dir.iterdir())) == 2


def test_real_sync_records_media_retry_job_without_blocking_import(client, monkeypatch):
    class FailingWecomClient:
        async def sync_msg(self, cursor=None, token=None, limit=None):
            return {
                "errcode": 0,
                "errmsg": "ok",
                "next_cursor": "cursor_media_failed",
                "has_more": 0,
                "msg_list": [
                    {
                        "msgid": "media_failed_text",
                        "open_kfid": "wk_media_failed",
                        "external_userid": "external_media_failed",
                        "send_time": 1780847999,
                        "msgtype": "text",
                        "text": {"content": "导入文字仍应生成草稿"},
                    },
                    {
                        "msgid": "media_failed_image",
                        "open_kfid": "wk_media_failed",
                        "external_userid": "external_media_failed",
                        "send_time": 1780848000,
                        "msgtype": "image",
                        "image": {"media_id": "media_failed_001", "filename": "cover.png"},
                    }
                ],
            }

        async def download_media(self, media_id):
            from app.services.wecom_client import WecomClientError

            raise WecomClientError("temporary media download failed")

    monkeypatch.setattr(settings, "wecom_use_mock", False)
    monkeypatch.setattr(settings, "wecom_open_kfid", "wk_media_failed")
    client.app.dependency_overrides[get_wecom_client] = lambda: FailingWecomClient()

    response = client.post("/api/wecom/real-sync")

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["importResult"]["importBatchIds"]
    retries = client.get("/api/wecom/media-retries").json()["data"]
    assert retries[-1]["mediaId"] == "media_failed_001"
    assert retries[-1]["status"] == "failed"
    assert retries[-1]["attempts"] == 1
    pending = client.get("/api/imports/pending").json()["data"]
    card = pending[-1]["generatedCard"]
    assert card["title"] == "导入文字仍应生成草稿"
    assert card["media"] == []


def test_media_retry_success_is_reused_by_next_real_sync(client, monkeypatch, tmp_path):
    class RetryWecomClient:
        def __init__(self):
            self.download_calls = 0

        async def sync_msg(self, cursor=None, token=None, limit=None):
            return {
                "errcode": 0,
                "errmsg": "ok",
                "next_cursor": "cursor_retry_done",
                "has_more": 0,
                "msg_list": [
                    {
                        "msgid": "media_retry_msg",
                        "open_kfid": "wk_retry",
                        "external_userid": "external_retry",
                        "send_time": 1780848000,
                        "msgtype": "image",
                        "image": {"media_id": "media_retry_001", "filename": "cover.png"},
                    }
                ],
            }

        async def download_media(self, media_id):
            self.download_calls += 1
            return DownloadedMedia(b"image-bytes", "image/png", "cover.png")

    service = client.app.dependency_overrides[get_app_service]()
    service.save_media_retry_failure("media_retry_001", "image", "wk_retry", "temporary failure")
    media_dir = tmp_path / "media"
    service.media_storage_service = MediaStorageService("local", media_dir, "/media")
    fake_client = RetryWecomClient()
    monkeypatch.setattr(settings, "admin_token", "test-admin-token")
    monkeypatch.setattr(settings, "wecom_use_mock", False)
    monkeypatch.setattr(settings, "wecom_open_kfid", "wk_retry")
    client.app.dependency_overrides[get_wecom_client] = lambda: fake_client

    retry_response = client.post(
        "/api/wecom/media-retries/retry",
        params={"media_id": "media_retry_001"},
        headers={"X-Admin-Token": "test-admin-token"},
    )
    sync_response = client.post("/api/wecom/real-sync")

    assert retry_response.status_code == 200
    assert retry_response.json()["data"]["retried"][0]["status"] == "success"
    assert sync_response.status_code == 200
    assert fake_client.download_calls == 1
    pending = client.get("/api/imports/pending").json()["data"]
    assert pending[-1]["generatedCard"]["coverUrl"].startswith("/media/")


def test_real_sync_returns_running_status_when_lock_exists(client):
    service = client.app.dependency_overrides[get_app_service]()
    open_kfid = settings.wecom_open_kfid or "default"
    locked = service.acquire_sync_lock(open_kfid, "mock-real-sync-response", 600)
    assert locked is not None

    response = client.post("/api/wecom/real-sync")

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is False
    assert payload["data"]["syncStatus"] == "running"
    assert payload["data"]["lockedAt"] == locked.lockedAt


def test_real_sync_unlock_releases_running_lock(client, monkeypatch):
    service = client.app.dependency_overrides[get_app_service]()
    open_kfid = settings.wecom_open_kfid or "default"
    locked = service.acquire_sync_lock(open_kfid, "mock-real-sync-response", 600)
    assert locked is not None
    monkeypatch.setattr(settings, "admin_token", "test-admin-token")

    response = client.post(
        "/api/wecom/real-sync/unlock",
        params={"reason": "admin unlock"},
        headers={"X-Admin-Token": "test-admin-token"},
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["syncStatus"] == "failed"
    assert payload["lastError"] == "admin unlock"
    assert payload["lockedAt"] is None


def test_real_sync_unlock_rejects_missing_admin_token(client, monkeypatch):
    service = client.app.dependency_overrides[get_app_service]()
    open_kfid = settings.wecom_open_kfid or "default"
    locked = service.acquire_sync_lock(open_kfid, "mock-real-sync-response", 600)
    assert locked is not None
    monkeypatch.setattr(settings, "admin_token", "test-admin-token")

    response = client.post("/api/wecom/real-sync/unlock", params={"reason": "admin unlock"})

    assert response.status_code == 403
    assert service.get_sync_cursor(open_kfid).syncStatus == "running"


def test_real_sync_takes_over_expired_lock(client, monkeypatch):
    service = client.app.dependency_overrides[get_app_service]()
    open_kfid = settings.wecom_open_kfid or "default"
    locked = service.acquire_sync_lock(open_kfid, "mock-real-sync-response", 600)
    assert locked is not None
    monkeypatch.setattr(settings, "wecom_sync_lock_timeout_seconds", 0)

    response = client.post("/api/wecom/real-sync")

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["syncStatus"] == "success"
    assert payload["pagesSynced"] == 1


def test_health_reports_database_configuration(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["database"]["backend"] == "postgres"
    assert isinstance(data["database"]["configured"], bool)
    assert isinstance(data["database"]["missing"], list)


def test_location_geocode_reports_missing_key(client, monkeypatch):
    from app.api import routes_location

    monkeypatch.setattr(routes_location.settings, "tencent_map_key", "")

    response = client.get("/api/location/geocode", params={"address": "长沙市芙蓉区万家丽"})

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["configured"] is False
    assert data["found"] is False


def test_location_geocode_normalizes_tencent_result(client, monkeypatch):
    from app.api import routes_location

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "status": 0,
                "result": {
                    "title": "万国城",
                    "address": "湖南省长沙市芙蓉区远大一路",
                    "location": {"lat": 28.21, "lng": 113.02},
                    "level": "地产小区",
                    "reliability": 8,
                },
            }

    def fake_get(url, params, timeout):
        assert "geocoder" in url
        assert params["key"] == "map-key"
        assert params["address"] == "长沙市芙蓉区万国城"
        assert timeout == 8
        return FakeResponse()

    monkeypatch.setattr(routes_location.settings, "tencent_map_key", "map-key")
    monkeypatch.setattr(routes_location.httpx, "get", fake_get)

    response = client.get("/api/location/geocode", params={"address": "长沙市芙蓉区万国城"})

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["configured"] is True
    assert data["found"] is True
    assert data["latitude"] == 28.21
    assert data["longitude"] == 113.02
    assert data["name"] == "万国城"


def test_mock_import_creates_claimable_batch(client):
    response = client.post(
        "/api/wecom/mock-sync",
        json={"externalUserId": "external_test", "conversationId": "conv_test", "fixture": "note"},
    )
    assert response.status_code == 200

    pending = client.get("/api/imports/pending").json()["data"]
    assert len(pending) >= 1
    latest = pending[-1]
    assert latest["sourceType"] == "wechat_note"
    assert latest["generatedCard"]["title"]

    notifications = client.get("/api/wecom/notifications").json()["data"]
    assert notifications[-1]["status"] == "success"
    assert "已整理完成" in notifications[-1]["message"]


def test_wecom_import_uses_content_object_to_note_pipeline(client, monkeypatch):
    service = client.app.dependency_overrides[get_app_service]()
    seen = {}
    original_run = service.skill_router_service.run_content_to_note

    def spy_run_content_to_note(owner_user_id, content):
        seen["ownerUserId"] = owner_user_id
        seen["sourceType"] = content.sourceType
        seen["rawMessageIds"] = content.rawMessageIds
        seen["textBlocks"] = content.textBlocks
        return original_run(owner_user_id, content)

    monkeypatch.setattr(service.skill_router_service, "run_content_to_note", spy_run_content_to_note)

    response = client.post(
        "/api/wecom/mock-sync",
        json={"externalUserId": "external_content_object", "conversationId": "conv_content_object", "fixture": "note"},
    )

    assert response.status_code == 200
    assert seen["ownerUserId"] == "unclaimed"
    assert seen["sourceType"] == "wecom_thread"
    assert seen["rawMessageIds"]
    assert any("联系人" in text or "看房" in text for text in seen["textBlocks"])


def test_wecom_sync_import_handles_miniapp_card(client):
    service = client.app.dependency_overrides[get_app_service]()
    result = service.trigger_sync_response_import(
        {
            "next_cursor": "cursor_weapp",
            "msg_list": [
                {
                    "msgid": "sync_weapp_msg_001",
                    "open_kfid": "wk_weapp",
                    "external_userid": "external_weapp",
                    "send_time": 1781808076,
                    "msgtype": "weapp",
                    "weapp": {
                        "appid": "wxcfd8224218167d98",
                        "title": "三江尊园 全天采光 好楼层 拎包入住",
                        "pagepath": "subpackages/ershoufang/pages/esfDetail/esfDetail.html?cityId=150200&houseCode=101137825091",
                        "username": "gh_2dbd87cb164c@app",
                        "description": "贝壳找房丨二手房新房租房装修",
                        "displayname": "贝壳找房丨二手房新房租房装修",
                    },
                }
            ],
        },
        fallback_open_kfid="wk_weapp",
    )

    assert result["importBatchIds"]
    pending = client.get("/api/imports/pending").json()["data"]
    latest = pending[-1]
    note = latest["generatedNote"]
    assert latest["sourceType"] == "miniapp_link"
    assert note["title"] == "三江尊园 全天采光 好楼层 拎包入住"
    assert note["phone"] is None
    assert note["visibilityConfig"]["sourceType"] == "miniapp"
    assert note["visibilityConfig"]["showPhone"] is False
    assert note["visibilityConfig"]["structuredData"]["miniapp"]["houseCode"] == "101137825091"
    assert note["visibilityConfig"]["structuredData"]["miniapp"]["webUrl"] == "https://m.ke.com/baotou/ershoufang/101137825091.html"
    assert note["visibilityConfig"]["conversionConfig"]["enableLightScrm"] is True
    assert note["visibilityConfig"]["conversionConfig"]["collectLeads"] is True
    assert note["visibilityConfig"]["conversionConfig"]["enableAppointment"] is True


def test_wecom_import_persists_successful_skill_run(client):
    response = client.post(
        "/api/wecom/mock-sync",
        json={"externalUserId": "external_skill_run", "conversationId": "conv_skill_run", "fixture": "note"},
    )

    assert response.status_code == 200
    runs = client.get("/api/skills/runs", params={"skillId": "content-to-note"}).json()["data"]
    latest = runs[0]
    assert latest["skillId"] == "content-to-note"
    assert latest["status"] == "success"
    assert latest["outputRef"].startswith("note_")
    assert latest["inputSnapshot"]["importBatchId"] == response.json()["data"]["importBatchIds"][0]


def test_wecom_import_failure_persists_failed_skill_run_and_notification(client, monkeypatch):
    service = client.app.dependency_overrides[get_app_service]()
    original_run = service.skill_router_service.run_content_to_note

    def fail_content_to_note(owner_user_id, content):
        raise RuntimeError("content-to-note failed for test")

    monkeypatch.setattr(service.skill_router_service, "run_content_to_note", fail_content_to_note)

    response = client.post(
        "/api/wecom/mock-sync",
        json={"externalUserId": "external_skill_fail", "conversationId": "conv_skill_fail", "fixture": "note"},
    )

    assert response.status_code == 200
    import_batch_id = response.json()["data"]["importBatchIds"][0]
    failed_runs = client.get("/api/skills/runs", params={"status": "failed"}).json()["data"]
    assert failed_runs[0]["skillId"] == "content-to-note"
    assert failed_runs[0]["outputRef"] == import_batch_id
    assert failed_runs[0]["inputSnapshot"]["importBatchId"] == import_batch_id
    assert "content-to-note failed for test" in failed_runs[0]["errorMessage"]

    failures = client.get("/api/wecom/import-failures").json()["data"]
    assert failures["skillRuns"][0]["id"] == failed_runs[0]["id"]
    assert failures["notifications"][0]["importBatchId"] == import_batch_id
    assert failures["notifications"][0]["status"] == "failed"
    assert "content-to-note failed for test" in failures["notifications"][0]["message"]

    dashboard = client.get("/api/wecom/retry-dashboard").json()["data"]
    assert dashboard["summary"]["failedSkillRunCount"] >= 1
    assert dashboard["actions"]["retryImport"] == "/api/wecom/import-failures/retry"

    monkeypatch.setattr(settings, "admin_token", "test-admin-token")
    monkeypatch.setattr(service.skill_router_service, "run_content_to_note", original_run)
    retry_response = client.post(
        "/api/wecom/import-failures/retry",
        params={"importBatchId": import_batch_id},
        headers={"X-Admin-Token": "test-admin-token"},
    )

    assert retry_response.status_code == 200
    retry_payload = retry_response.json()["data"]
    assert retry_payload["importBatch"]["status"] == "success"
    assert retry_payload["generatedCard"]["id"].startswith("card_")
    assert retry_payload["notification"]["status"] == "success"


def test_mock_import_is_idempotent_for_repeated_wecom_messages(client):
    first = client.post(
        "/api/wecom/mock-sync",
        json={"externalUserId": "external_repeat", "conversationId": "conv_repeat", "fixture": "note"},
    )
    second = client.post(
        "/api/wecom/mock-sync",
        json={"externalUserId": "external_repeat", "conversationId": "conv_repeat", "fixture": "note"},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    second_payload = second.json()["data"]
    assert second_payload["importBatchIds"] == []
    assert second_payload["deduplicatedCount"] == 5
    assert second_payload["message"] == "没有新的企业微信客服消息需要导入"


def test_link_import_uses_thumbnail_and_source_url(client):
    login = client.post("/api/auth/mock-login", json={"nickname": "收藏用户"}).json()["data"]
    response = client.post(
        "/api/wecom/mock-sync",
        json={"externalUserId": "external_link", "conversationId": "conv_link", "fixture": "link"},
    )
    assert response.status_code == 200

    pending = client.get("/api/imports/pending").json()["data"]
    latest = pending[-1]
    card = latest["generatedCard"]
    note = latest["generatedNote"]
    assert latest["sourceType"] == "web_link"
    assert card["sourceUrl"] == "https://example.com/group-buy"
    assert card["coverUrl"] == "https://example.com/cover.jpg"
    assert note["visibilityConfig"]["contentMode"] == "bookmark"
    assert {"链接", "待整理"}.issubset(set(note["visibilityConfig"]["tags"]))
    assert note["visibilityConfig"]["sourceType"] == "link"
    assert note["visibilityConfig"]["systemCategory"] == "文章"
    assert note["visibilityConfig"]["tagLevels"]["rule"] == note["visibilityConfig"]["tags"]
    assert note["visibilityConfig"]["tagStatus"] == "rule_done"
    assert note["visibilityConfig"]["category"] == "文章收藏"
    assert note["visibilityConfig"]["sourceUrl"] == "https://example.com/group-buy"
    assert note["visibilityConfig"]["sourceName"] == "example.com"
    assert note["visibilityConfig"]["sourceLabel"] == "网页链接"

    claim = client.post(f"/api/imports/{latest['id']}/claim", json={"userId": login["id"]})
    note_id = claim.json()["data"]["note"]["id"]
    updated = client.put(
        f"/api/notes/{note_id}",
        json={
            **claim.json()["data"]["note"],
            "ownerUserId": login["id"],
            "visibilityConfig": {
                **claim.json()["data"]["note"]["visibilityConfig"],
                "userTags": ["露营"],
                "tags": [*claim.json()["data"]["note"]["visibilityConfig"]["tags"], "露营"],
            },
        },
    )
    assert updated.status_code == 200
    tagged = client.get("/api/notes", params={"ownerUserId": login["id"], "tag": "露营"}).json()["data"]
    assert any(item["id"] == note_id for item in tagged)

    topic = client.post("/api/notes/topics", json={"ownerUserId": login["id"], "name": "周末亲子露营"})
    assert topic.status_code == 200
    topic_id = topic.json()["data"]["id"]
    added = client.post(f"/api/notes/{note_id}/topics/{topic_id}", json={"ownerUserId": login["id"]})
    assert added.status_code == 200
    assert topic_id in added.json()["data"]["visibilityConfig"]["topicIds"]
    topic_notes = client.get("/api/notes", params={"ownerUserId": login["id"], "topicId": topic_id}).json()["data"]
    assert [item["id"] for item in topic_notes] == [note_id]

    suggestions = client.get("/api/notes/tag-suggestions", params={"ownerUserId": login["id"], "noteId": note_id})
    assert suggestions.status_code == 200
    assert "链接" in suggestions.json()["data"]["suggestedTags"]

    organized = client.post(f"/api/notes/{note_id}/organize", params={"ownerUserId": login["id"]})

    assert organized.status_code == 200
    organized_note = organized.json()["data"]
    assert organized_note["visibilityConfig"]["contentMode"] == "deep_note"
    assert "未整理" not in organized_note["visibilityConfig"]["tags"]
    assert "已整理" in organized_note["visibilityConfig"]["tags"]


def test_explicit_link_organize_command_uses_deep_note(client):
    service = client.app.dependency_overrides[get_app_service]()
    sync_response = {
        "next_cursor": "cursor_deep_link",
        "msg_list": [
            {
                "msgid": "deep_link_text_001",
                "external_userid": "external_deep_link",
                "send_time": 1780848000,
                "msgtype": "text",
                "text": {"content": "整理链接"},
            },
            {
                "msgid": "deep_link_msg_001",
                "external_userid": "external_deep_link",
                "send_time": 1780848001,
                "msgtype": "link",
                "link": {
                    "title": "值得整理的文章",
                    "description": "需要提炼重点",
                    "url": "https://example.com/deep-link",
                    "picurl": "https://example.com/deep-cover.jpg",
                },
            },
        ]
    }

    result = service.trigger_sync_response_import(sync_response, fallback_open_kfid="wk_deep_link")
    pending = client.get("/api/imports/pending").json()["data"]
    generated = next(item for item in pending if item["id"] == result["importBatchIds"][0])

    assert generated["generatedNote"]["visibilityConfig"].get("contentMode") != "bookmark"
    assert "整理链接" in generated["generatedNote"]["body"]


def test_note_import_preserves_video_media(client):
    response = client.post(
        "/api/wecom/mock-sync",
        json={"externalUserId": "external_video", "conversationId": "conv_video", "fixture": "note"},
    )
    assert response.status_code == 200

    pending = client.get("/api/imports/pending").json()["data"]
    media = pending[-1]["generatedCard"]["media"]
    assert any(item["type"] == "video" and item["url"].endswith(".mp4") for item in media)


def test_claim_import_and_publish_flow(client):
    login = client.post("/api/auth/mock-login", json={"nickname": "李中介"}).json()["data"]
    client.post(
        "/api/wecom/mock-sync",
        json={"externalUserId": "external_claim", "conversationId": "conv_claim", "fixture": "note"},
    )
    pending = client.get("/api/imports/pending").json()["data"]
    target = pending[-1]

    claim = client.post(f"/api/imports/{target['id']}/claim", json={"userId": login["id"]})
    assert claim.status_code == 200
    card = claim.json()["data"]["card"]
    note = claim.json()["data"]["note"]
    assert card["ownerUserId"] == login["id"]
    assert note["ownerUserId"] == login["id"]
    assert note["status"] == "active"
    assert claim.json()["data"]["identityBinding"]["externalUserId"] == "external_claim"
    assert claim.json()["data"]["identityBinding"]["ownerUserId"] == login["id"]

    publish = client.post(f"/api/cards/{card['id']}/publish", json={"userId": login["id"]})
    assert publish.status_code == 200
    assert publish.json()["data"]["status"] == "published"

    client.post(
        "/api/wecom/mock-sync",
        json={"externalUserId": "external_claim", "conversationId": "conv_claim_followup", "fixture": "link"},
    )
    notes = client.get("/api/notes", params={"ownerUserId": login["id"]}).json()["data"]
    pending_after = client.get("/api/imports/pending").json()["data"]
    assert len(notes) >= 2
    assert not any(item["externalUserId"] == "external_claim" and item["status"] != "claimed" for item in pending_after)


def test_import_creates_claimable_user_note_and_note_crud(client):
    login = client.post("/api/auth/mock-login", json={"nickname": "笔记用户"}).json()["data"]
    client.post(
        "/api/wecom/mock-sync",
        json={"externalUserId": "external_note_crud", "conversationId": "conv_note_crud", "fixture": "note"},
    )
    pending = client.get("/api/imports/pending").json()["data"]
    target = pending[-1]
    assert target["generatedNote"]["ownerUserId"] == "unclaimed"
    assert target["generatedNote"]["title"]

    claim = client.post(f"/api/imports/{target['id']}/claim", json={"userId": login["id"]})
    note = claim.json()["data"]["note"]

    notes = client.get("/api/notes", params={"ownerUserId": login["id"]}).json()["data"]
    assert any(item["id"] == note["id"] for item in notes)

    detail = client.get(f"/api/notes/{note['id']}", params={"ownerUserId": login["id"]})
    assert detail.status_code == 200
    assert detail.json()["data"]["sourceCardId"] == claim.json()["data"]["card"]["id"]

    card_detail = client.get(f"/api/cards/{claim.json()['data']['card']['id']}")
    assert card_detail.status_code == 200
    assert card_detail.json()["data"]["sourceNoteId"] == note["id"]
    cards = client.get("/api/cards", params={"ownerUserId": login["id"]}).json()["data"]
    assert any(item["id"] == claim.json()["data"]["card"]["id"] and item["sourceNoteId"] == note["id"] for item in cards)

    updated = client.put(
        f"/api/notes/{note['id']}",
        json={
            "ownerUserId": login["id"],
            "title": "更新后的笔记",
            "summary": "更新摘要",
            "body": "更新正文 13800138000",
            "categoryIds": ["cat_seed_sale"],
            "phone": "13800138000",
            "visibilityConfig": {"showPhone": True},
        },
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["title"] == "更新后的笔记"
    assert updated.json()["data"]["categoryIds"] == ["cat_seed_sale"]

    structured = client.put(
        f"/api/notes/{note['id']}",
        json={
            "ownerUserId": login["id"],
            "title": "碧桂园城市之光1栋1210",
            "summary": "房源字段卡",
            "body": "小区：碧桂园城市之光1栋1210\n户型：公寓一房\n价格：1600元/月\n商圈：万家丽、高桥北",
            "categoryIds": ["cat_seed_sale"],
            "phone": "13800138000",
            "visibilityConfig": {
                "cardType": "property_listing",
                "cardState": "collected",
                "contentMode": "structured_card",
                "systemCategory": "房源",
                "tags": ["房产", "房源"],
                "structuredData": {
                    "community": "碧桂园城市之光1栋1210",
                    "layout": "公寓一房",
                    "price": "1600元/月",
                    "businessArea": "万家丽、高桥北",
                },
                "conversionConfig": {
                    "showContactPhone": True,
                    "enableLightScrm": True,
                    "collectLeads": True,
                    "enableAppointment": True,
                    "enablePrivateConsultation": False,
                    "enableSharePoster": True,
                    "enableGroupRelay": False,
                    "enablePaymentPlaceholder": False,
                },
            },
        },
    )
    assert structured.status_code == 200
    assert structured.json()["data"]["visibilityConfig"]["structuredData"]["businessArea"] == "万家丽、高桥北"

    filtered = client.get(
        "/api/notes",
        params={"ownerUserId": login["id"], "keyword": "万家丽", "categoryId": "cat_seed_sale"},
    ).json()["data"]
    assert [item["id"] for item in filtered] == [note["id"]]

    created_date = structured.json()["data"]["createdAt"].split("T", 1)[0]
    _, month, day = created_date.split("-")
    compact_month_day = f"{int(month)}{int(day)}"
    for keyword in [created_date, f"{int(month)}月", compact_month_day]:
        fuzzy_filtered = client.get(
            "/api/notes",
            params={"ownerUserId": login["id"], "keyword": keyword},
        ).json()["data"]
        assert note["id"] in [item["id"] for item in fuzzy_filtered]

    organized = client.post(f"/api/notes/{note['id']}/organize", params={"ownerUserId": login["id"]})
    assert organized.status_code == 200
    organized_config = organized.json()["data"]["visibilityConfig"]
    assert organized_config["cardState"] == "organized"
    assert organized_config["structuredData"]["organizeResult"]["generationOptions"] == ["房源推广图", "微信群文案", "客户话术", "对比表"]
    assert "轻 SCRM 跟进" in organized_config["structuredData"]["organizeResult"]["enabledFeatures"]
    assert "私聊咨询" not in organized_config["structuredData"]["organizeResult"]["enabledFeatures"]

    generated = client.post(f"/api/notes/{note['id']}/generate", params={"ownerUserId": login["id"]})
    assert generated.status_code == 200
    generated_config = generated.json()["data"]["visibilityConfig"]
    assert generated_config["cardState"] == "generated"
    assert generated_config["structuredData"]["generatedResult"]["pageType"] == "property_promo_page"
    assert "预约看房" in generated_config["structuredData"]["generatedResult"]["enabledActions"]
    assert "私聊咨询" not in generated_config["structuredData"]["generatedResult"]["enabledActions"]

    viewer = client.post("/api/auth/mock-login", json={"nickname": "看房客户"}).json()["data"]
    action_config = client.get(
        f"/api/notes/{note['id']}/customer-actions/config",
        params={"viewerUserId": viewer["id"]},
    )
    assert action_config.status_code == 200
    action_keys = {item["key"] for item in action_config.json()["data"]["actions"]}
    assert {"lead-contact", "appointment"}.issubset(action_keys)

    lead_action = client.post(
        f"/api/notes/{note['id']}/customer-actions/lead-contact",
        json={
            "viewerUserId": viewer["id"],
            "nickname": viewer["nickname"],
            "avatarUrl": viewer["avatarUrl"],
            "payload": {
                "name": "王客户",
                "phone": "13900001111",
                "wechat": "wx_house_001",
                "remark": "周末方便看房",
            },
        },
    )
    assert lead_action.status_code == 200
    lead_projection = lead_action.json()["data"]["projection"]
    assert lead_projection["leadReminderId"].startswith("lead_")

    appointment_action = client.post(
        f"/api/notes/{note['id']}/customer-actions/appointment",
        json={
            "viewerUserId": viewer["id"],
            "nickname": viewer["nickname"],
            "avatarUrl": viewer["avatarUrl"],
            "payload": {
                "date": "2026-06-20",
                "time": "14:30",
                "remark": "两个人看房",
            },
        },
    )
    assert appointment_action.status_code == 200
    assert appointment_action.json()["data"]["projection"]["leadReminderId"] == lead_projection["leadReminderId"]

    lead_rows = client.get("/api/lead-reminders", params={"ownerUserId": login["id"]}).json()["data"]
    customer_lead = next(item for item in lead_rows if item["id"] == lead_projection["leadReminderId"])
    assert customer_lead["cardId"] == claim.json()["data"]["card"]["id"]
    assert customer_lead["sourceNoteId"] == note["id"]
    assert customer_lead["customerPhone"] == "13900001111"
    assert customer_lead["customerWechat"] == "wx_house_001"
    assert customer_lead["nextFollowUpAt"] == "2026-06-20T14:30:00+08:00"
    assert any("客户预约：2026-06-20 14:30" in item["content"] for item in customer_lead["followUpLogs"])

    submitted_config = client.get(
        f"/api/notes/{note['id']}/customer-actions/config",
        params={"viewerUserId": viewer["id"]},
    ).json()["data"]
    submitted = {item["key"]: item for item in submitted_config["actions"]}
    assert submitted["lead-contact"]["submitted"] is True
    assert submitted["appointment"]["submitted"] is True

    note_actions = client.get(
        f"/api/notes/{note['id']}/customer-actions",
        params={"ownerUserId": login["id"]},
    )
    assert note_actions.status_code == 200
    note_action_data = note_actions.json()["data"]
    assert note_action_data["summary"]["total"] == 2
    assert note_action_data["summary"]["leadContact"] == 1
    assert note_action_data["summary"]["appointment"] == 1
    assert note_action_data["summary"]["pending"] == 1
    assert note_action_data["summary"]["hasUnread"] is True
    assert {item["actionKey"] for item in note_action_data["actions"]} == {"lead-contact", "appointment"}
    assert note_action_data["actions"][0]["leadReminderId"] == lead_projection["leadReminderId"]
    assert note_action_data["leads"][0]["id"] == lead_projection["leadReminderId"]

    forbidden_actions = client.get(
        f"/api/notes/{note['id']}/customer-actions",
        params={"ownerUserId": viewer["id"]},
    )
    assert forbidden_actions.status_code == 403

    deleted = client.delete(f"/api/notes/{note['id']}", params={"ownerUserId": login["id"]})
    assert deleted.status_code == 200
    assert client.get("/api/notes", params={"ownerUserId": login["id"]}).json()["data"] == []
    deleted_visible = client.get(
        "/api/notes",
        params={"ownerUserId": login["id"], "includeDeleted": True},
    ).json()["data"]
    assert deleted_visible[0]["status"] == "deleted"


def test_groupbuy_product_relay_intent_uses_customer_actions_without_leads(client):
    service = client.app.dependency_overrides[get_app_service]()
    owner = client.post("/api/auth/mock-login", json={"nickname": "团长"}).json()["data"]
    now = now_iso()
    note = UserNote(
        id=new_id("note"),
        ownerUserId=owner["id"],
        status="active",
        title="丹东草莓团购",
        summary="丹东草莓，按规格接龙。",
        body="丹东草莓 3斤装 39.9元，小区自提。",
        phone="13800008888",
        locationText="小区门口",
        visibilityConfig={
            "cardType": "groupbuy_product",
            "cardState": "generated",
            "contentMode": "generated_card",
            "systemCategory": "团购",
            "structuredData": {
                "productName": "丹东草莓",
                "price": "39.9元",
                "spec": "3斤装",
                "pickupMethod": "小区自提",
                "pickupLocation": "小区门口",
                "contact": "13800008888",
                "skuConfig": {
                    "attributeGroups": [
                        {
                            "id": "taste",
                            "name": "口味",
                            "options": [
                                {"id": "sweet", "label": "甜口"},
                                {"id": "sour", "label": "酸甜"},
                            ],
                        },
                        {
                            "id": "size",
                            "name": "规格",
                            "options": [
                                {"id": "3jin", "label": "3斤装"},
                            ],
                        },
                    ],
                    "skus": [
                        {"id": "sku_1", "key": "sweet|3jin", "name": "甜口 / 3斤装", "price": "39.9元", "soldOut": False},
                        {"id": "sku_2", "key": "sour|3jin", "name": "酸甜 / 3斤装", "price": "42.9元", "soldOut": True},
                    ],
                },
            },
            "conversionConfig": {
                "showContactPhone": True,
                "enableLightScrm": False,
                "collectLeads": False,
                "enableAppointment": False,
                "enablePrivateConsultation": False,
                "enableSharePoster": True,
                "enableGroupRelay": True,
                "enablePaymentPlaceholder": False,
            },
        },
        createdAt=now,
        updatedAt=now,
    )
    service.repo.save_user_note(note)
    viewer = client.post("/api/auth/mock-login", json={"nickname": "买家"}).json()["data"]

    action_config = client.get(f"/api/notes/{note.id}/customer-actions/config", params={"viewerUserId": viewer["id"]})
    assert action_config.status_code == 200
    actions = {item["key"]: item for item in action_config.json()["data"]["actions"]}
    assert set(actions) == {"relay-intent"}
    assert actions["relay-intent"]["skuConfig"]["skus"][1]["soldOut"] is True

    sold_out = client.post(
        f"/api/notes/{note.id}/customer-actions/relay-intent",
        json={
            "viewerUserId": viewer["id"],
            "nickname": viewer["nickname"],
            "avatarUrl": viewer["avatarUrl"],
            "payload": {"skuKey": "sour|3jin", "quantity": 1, "phone": "13900003333", "address": "小区门口"},
        },
    )
    assert sold_out.status_code == 400

    submitted = client.post(
        f"/api/notes/{note.id}/customer-actions/relay-intent",
        json={
            "viewerUserId": viewer["id"],
            "nickname": viewer["nickname"],
            "avatarUrl": viewer["avatarUrl"],
            "payload": {"skuKey": "sweet|3jin", "quantity": 2, "phone": "13900003333", "address": "小区门口", "wechat": "wx_buyer", "remark": "下午自提"},
        },
    )
    assert submitted.status_code == 200
    assert submitted.json()["data"]["projection"] == {}
    assert submitted.json()["data"]["action"]["payload"]["skuName"] == "甜口 / 3斤装"
    assert submitted.json()["data"]["action"]["payload"]["name"] == "买家"
    assert submitted.json()["data"]["action"]["payload"]["avatarUrl"] == viewer["avatarUrl"]
    resubmitted_config = client.get(f"/api/notes/{note.id}/customer-actions/config", params={"viewerUserId": viewer["id"]})
    resubmitted_action = resubmitted_config.json()["data"]["actions"][0]
    assert resubmitted_action["submitted"] is True
    assert resubmitted_action["submittedPayload"]["skuKey"] == "sweet|3jin"
    assert resubmitted_action["submittedPayload"]["quantity"] == 2
    assert resubmitted_action["submittedPayload"]["phone"] == "13900003333"
    assert resubmitted_action["submittedPayload"]["address"] == "小区门口"

    duplicate = client.post(
        f"/api/notes/{note.id}/customer-actions/relay-intent",
        json={"viewerUserId": viewer["id"], "payload": {"skuKey": "sweet|3jin", "quantity": 1, "phone": "13900003333", "address": "小区门口"}},
    )
    assert duplicate.status_code == 409
    assert client.get("/api/lead-reminders", params={"ownerUserId": owner["id"]}).json()["data"] == []

    owner_actions = client.get(f"/api/notes/{note.id}/customer-actions", params={"ownerUserId": owner["id"]})
    assert owner_actions.status_code == 200
    data = owner_actions.json()["data"]
    assert data["cardType"] == "groupbuy_product"
    assert data["summary"]["orderIntent"] == 1
    assert data["summary"]["relayIntent"] == 1
    assert data["summary"]["leads"] == 0
    assert data["actions"][0]["customerName"] == "买家"
    assert data["actions"][0]["customerAvatarUrl"] == viewer["avatarUrl"]
    assert data["actions"][0]["displayRows"][0] == {"label": "规格", "value": "甜口 / 3斤装"}
    assert {"label": "地址", "value": "小区门口"} in data["actions"][0]["displayRows"]

    disabled_note = note.model_copy(deep=True)
    disabled_note.id = new_id("note")
    disabled_note.visibilityConfig["conversionConfig"]["enableGroupRelay"] = False
    service.repo.save_user_note(disabled_note)
    disabled = client.post(
        f"/api/notes/{disabled_note.id}/customer-actions/relay-intent",
        json={"viewerUserId": viewer["id"], "payload": {"skuKey": "sweet|3jin", "quantity": 1, "phone": "13900003333", "address": "小区门口"}},
    )
    assert disabled.status_code == 400

    disabled_config = client.get(f"/api/notes/{disabled_note.id}/customer-actions/config", params={"viewerUserId": viewer["id"]})
    disabled_actions = {item["key"]: item for item in disabled_config.json()["data"]["actions"]}
    assert set(disabled_actions) == {"order-intent"}
    order = client.post(
        f"/api/notes/{disabled_note.id}/customer-actions/order-intent",
        json={
            "viewerUserId": viewer["id"],
            "nickname": viewer["nickname"],
            "avatarUrl": viewer["avatarUrl"],
            "payload": {"skuKey": "sweet|3jin", "quantity": 3, "phone": "13900003333", "address": "小区门口", "remark": "放门卫"},
        },
    )
    assert order.status_code == 200
    assert order.json()["data"]["projection"] == {}
    assert order.json()["data"]["statusText"] == "已下单 甜口 / 3斤装 x 3"
    order_id = order.json()["data"]["action"]["id"]
    disabled_owner_actions = client.get(f"/api/notes/{disabled_note.id}/customer-actions", params={"ownerUserId": owner["id"]})
    disabled_data = disabled_owner_actions.json()["data"]
    assert disabled_data["summary"]["orderIntent"] == 1
    assert disabled_data["summary"]["relayIntent"] == 0
    assert disabled_data["summary"]["leads"] == 0
    assert disabled_data["actions"][0]["actionKey"] == "order-intent"
    assert {"label": "地址", "value": "小区门口"} in disabled_data["actions"][0]["displayRows"]
    assert {"label": "备注", "value": "放门卫"} in disabled_data["actions"][0]["displayRows"]

    buyer_orders = client.get("/api/orders", params={"userId": viewer["id"], "role": "buyer"})
    assert buyer_orders.status_code == 200
    buyer_order_ids = {item["id"] for item in buyer_orders.json()["data"]["orders"]}
    assert order_id in buyer_order_ids

    seller_orders = client.get("/api/orders", params={"userId": owner["id"], "role": "seller"})
    assert seller_orders.status_code == 200
    seller_order = next(item for item in seller_orders.json()["data"]["orders"] if item["id"] == order_id)
    assert seller_order["address"] == "小区门口"
    assert seller_order["phone"] == "13900003333"
    assert seller_order["remark"] == "放门卫"

    outsider = client.post("/api/auth/mock-login", json={"nickname": "路人"}).json()["data"]
    forbidden_order = client.get(f"/api/orders/{order_id}", params={"userId": outsider["id"]})
    assert forbidden_order.status_code == 403

    updated_status = client.patch(
        f"/api/orders/{order_id}/status",
        json={"userId": owner["id"], "status": "contacted"},
    )
    assert updated_status.status_code == 200
    assert updated_status.json()["data"]["status"] == "contacted"
    buyer_status_update = client.patch(
        f"/api/orders/{order_id}/status",
        json={"userId": viewer["id"], "status": "completed"},
    )
    assert buyer_status_update.status_code == 403

    thread = client.post(
        "/api/messages/threads",
        json={
            "userId": viewer["id"],
            "noteId": disabled_note.id,
            "orderActionId": order_id,
            "content": "老板，下午可以自提吗？",
        },
    )
    assert thread.status_code == 200
    thread_id = thread.json()["data"]["id"]
    thread_data = thread.json()["data"]
    assert thread_data["participants"][owner["id"]]["role"] == "owner"
    assert thread_data["participants"][viewer["id"]]["role"] == "buyer"
    assert thread_data["participants"][viewer["id"]]["nickname"] == viewer["nickname"]
    owner_threads = client.get("/api/messages/threads", params={"userId": owner["id"]})
    assert owner_threads.json()["data"]["unreadTotal"] == 1
    messages = client.get(f"/api/messages/threads/{thread_id}/messages", params={"userId": owner["id"]})
    assert messages.status_code == 200
    assert messages.json()["data"]["messages"][0]["content"] == "老板，下午可以自提吗？"
    assert messages.json()["data"]["thread"]["participants"][viewer["id"]]["avatarUrl"] == viewer["avatarUrl"]
    read = client.post(f"/api/messages/threads/{thread_id}/read", json={"userId": owner["id"]})
    assert read.status_code == 200
    assert read.json()["data"]["unreadCount"] == 0
    reply = client.post(
        f"/api/messages/threads/{thread_id}/messages",
        json={"userId": owner["id"], "content": "可以，到了发消息。"},
    )
    assert reply.status_code == 200
    outsider_messages = client.get(f"/api/messages/threads/{thread_id}/messages", params={"userId": outsider["id"]})
    assert outsider_messages.status_code == 403


def test_demo_data_includes_product_relay_mock_for_current_user(client):
    owner = client.post("/api/auth/mock-login", json={"nickname": "演示团长"}).json()["data"]
    created = client.post("/api/notes/demo-data", params={"ownerUserId": owner["id"]})
    assert created.status_code == 200
    notes = created.json()["data"]["notes"]
    product = next(item for item in notes if item["visibilityConfig"]["cardType"] == "groupbuy_product")
    assert product["ownerUserId"] == owner["id"]
    assert product["visibilityConfig"]["conversionConfig"]["enableGroupRelay"] is True

    listed = client.get("/api/notes", params={"ownerUserId": owner["id"]}).json()["data"]
    assert any(item["id"] == product["id"] for item in listed)

    owner_actions = client.get(f"/api/notes/{product['id']}/customer-actions", params={"ownerUserId": owner["id"]})
    assert owner_actions.status_code == 200
    action_data = owner_actions.json()["data"]
    assert action_data["summary"]["orderIntent"] == 1
    assert action_data["summary"]["relayIntent"] == 1
    assert action_data["summary"]["leads"] == 0
    assert action_data["actions"][0]["payload"]["skuName"] == "甜口 / 3斤装"


def test_manual_create_card_flow(client):
    login = client.post("/api/auth/mock-login", json={"nickname": "手动发布者"}).json()["data"]
    response = client.post(
        "/api/cards",
        json={
            "ownerUserId": login["id"],
            "title": "手动添加资源",
            "detailText": "这是一条手动添加的资源详情",
            "projectName": "悦享测试",
            "locationText": "上海",
            "phone": "13900000000",
            "relayConfig": {"enabled": True, "requirePhone": True, "requireAddress": False},
        },
    )

    assert response.status_code == 200
    card = response.json()["data"]
    assert card["ownerUserId"] == login["id"]
    assert card["status"] == "draft"
    assert card["title"] == "手动添加资源"

    cards = client.get("/api/cards", params={"ownerUserId": login["id"]}).json()["data"]
    assert any(item["id"] == card["id"] for item in cards)


def test_manual_create_card_persists_media_payload(client):
    login = client.post("/api/auth/mock-login", json={"nickname": "素材资源用户"}).json()["data"]
    response = client.post(
        "/api/cards",
        json={
            "ownerUserId": login["id"],
            "title": "带素材资源",
            "detailText": "包含详情素材",
            "coverUrl": "http://127.0.0.1:8000/media/cover.png",
            "media": [
                {"type": "image", "url": "http://127.0.0.1:8000/media/cover.png", "sortOrder": 1},
                {"type": "image", "url": "http://127.0.0.1:8000/media/detail-1.png", "sortOrder": 2},
                {"type": "video", "url": "http://127.0.0.1:8000/media/detail-2.mp4", "sortOrder": 3},
            ],
        },
    )

    assert response.status_code == 200
    card = response.json()["data"]
    assert len(card["media"]) == 3
    assert card["media"][1]["url"].endswith("detail-1.png")
    assert card["media"][2]["type"] == "video"


def test_update_card_flow_accepts_relay_config_payload(client):
    login = client.post("/api/auth/mock-login", json={"nickname": "编辑资源用户"}).json()["data"]
    created = client.post(
        "/api/cards",
        json={
            "ownerUserId": login["id"],
            "title": "待编辑资源",
            "detailText": "初始内容",
            "projectName": "初始项目",
            "relayConfig": {"enabled": True, "requirePhone": False, "requireAddress": False},
        },
    )
    assert created.status_code == 200
    card = created.json()["data"]

    updated = client.put(
        f"/api/cards/{card['id']}",
        json={
            "ownerUserId": login["id"],
            "title": "已编辑资源",
            "detailText": "编辑后内容",
            "projectName": "编辑后项目",
            "locationText": "上海",
            "phone": "13900000000",
            "relayNotice": "请联系我",
            "sourceUrl": None,
            "enabledFields": [],
            "categoryIds": [],
            "media": [
                {"type": "image", "url": "http://127.0.0.1:8000/media/edit-cover.png", "sortOrder": 1},
                {"type": "video", "url": "http://127.0.0.1:8000/media/edit-video.mp4", "sortOrder": 2},
            ],
            "relayConfig": {"enabled": True, "requirePhone": True, "requireAddress": False},
        },
    )

    assert updated.status_code == 200
    payload = updated.json()["data"]
    assert payload["title"] == "已编辑资源"
    assert payload["relayConfig"]["requirePhone"] is True
    assert len(payload["media"]) == 2


def test_delete_card_flow_removes_card(client):
    login = client.post("/api/auth/mock-login", json={"nickname": "删除资源用户"}).json()["data"]
    created = client.post(
        "/api/cards",
        json={
            "ownerUserId": login["id"],
            "title": "待删除资源",
            "detailText": "删除前内容",
        },
    )
    assert created.status_code == 200
    card_id = created.json()["data"]["id"]

    deleted = client.delete(f"/api/cards/{card_id}", params={"ownerUserId": login["id"]})
    assert deleted.status_code == 200
    assert deleted.json()["data"]["deletedCardId"] == card_id

    missing = client.get(f"/api/cards/{card_id}")
    assert missing.status_code == 404


def test_manual_asset_upload_returns_media_url(client):
    login = client.post("/api/auth/mock-login", json={"nickname": "上传用户"}).json()["data"]

    response = client.post(
        "/api/uploads/asset",
        data={"ownerUserId": login["id"], "mediaType": "image"},
        files={"file": ("cover.png", b"image-bytes", "image/png")},
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["mediaType"] == "image"
    assert payload["name"] == "cover.png"
    assert payload["url"]


def test_manual_image_upload_compresses_before_storage(client, tmp_path):
    service = client.app.dependency_overrides[get_app_service]()
    media_dir = tmp_path / "media"
    service.media_storage_service = MediaStorageService("local", media_dir, "/media")
    service.media_processing_service = MediaProcessingService(image_max_edge=640, image_quality=80)
    login = client.post("/api/auth/mock-login", json={"nickname": "压缩上传用户"}).json()["data"]
    image = Image.new("RGB", (1800, 1200), (200, 60, 60))
    output = BytesIO()
    image.save(output, format="PNG")

    response = client.post(
        "/api/uploads/asset",
        data={"ownerUserId": login["id"], "mediaType": "image"},
        files={"file": ("large.png", output.getvalue(), "image/png")},
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["mediaType"] == "image"
    assert payload["contentType"] == "image/webp"
    assert payload["compressed"] is True
    assert payload["storedSize"] < payload["originalSize"]
    stored_files = list(media_dir.iterdir())
    assert len(stored_files) == 1
    with Image.open(stored_files[0]) as stored:
        assert stored.format == "WEBP"
        assert max(stored.size) <= 640


def test_lead_reminder_flow_persists_status_note_and_filters(client):
    owner = client.post("/api/auth/mock-login", json={"nickname": "线索团长"}).json()["data"]
    other = client.post("/api/auth/mock-login", json={"nickname": "其他用户"}).json()["data"]
    card = client.post(
        "/api/cards",
        json={
            "ownerUserId": owner["id"],
            "title": "高意向资源",
            "detailText": "线索持久化测试",
        },
    ).json()["data"]

    created = client.post(
        "/api/lead-reminders",
        json={
            "ownerUserId": owner["id"],
            "cardId": card["id"],
            "viewerUserId": "viewer-high",
            "nickname": "高意向访客",
            "avatarUrl": "",
            "status": "pending",
            "note": "先问预算",
            "viewCount": 3,
            "lastViewedAt": "2026-06-09T15:00:00+08:00",
        },
    )
    assert created.status_code == 200
    reminder = created.json()["data"]
    assert reminder["status"] == "pending"
    assert reminder["note"] == "先问预算"

    listed = client.get("/api/lead-reminders", params={"ownerUserId": owner["id"]}).json()["data"]
    assert len(listed) == 1
    assert listed[0]["cardTitle"] == "高意向资源"

    detail = client.get(
        f"/api/lead-reminders/{reminder['id']}",
        params={"ownerUserId": owner["id"]},
    )
    assert detail.status_code == 200
    assert detail.json()["data"]["cardTitle"] == "高意向资源"

    profile_update = client.put(
        f"/api/lead-reminders/{reminder['id']}",
        json={
            "ownerUserId": owner["id"],
            "customerPhone": "13800000000",
            "customerWechat": "wx_high_intent",
            "budgetText": "300 万内",
            "intentLevel": "高意向",
            "customerTags": ["改善", "老客户"],
        },
    )
    assert profile_update.status_code == 200
    profile_payload = profile_update.json()["data"]
    assert profile_payload["customerPhone"] == "13800000000"
    assert profile_payload["customerWechat"] == "wx_high_intent"
    assert profile_payload["budgetText"] == "300 万内"
    assert profile_payload["intentLevel"] == "高意向"
    assert profile_payload["customerTags"] == ["改善", "老客户"]

    forbidden_detail = client.get(
        f"/api/lead-reminders/{reminder['id']}",
        params={"ownerUserId": other["id"]},
    )
    assert forbidden_detail.status_code == 403

    forbidden = client.put(
        f"/api/lead-reminders/{reminder['id']}",
        json={"ownerUserId": other["id"], "status": "contacted"},
    )
    assert forbidden.status_code == 403

    contacted = client.put(
        f"/api/lead-reminders/{reminder['id']}",
        json={
            "ownerUserId": owner["id"],
            "status": "contacted",
            "note": "已电话联系",
            "nextFollowUpAt": "2026-06-12",
            "logContent": "电话沟通过，想再看一次详情",
        },
    )
    assert contacted.status_code == 200
    contacted_payload = contacted.json()["data"]
    assert contacted_payload["status"] == "contacted"
    assert contacted_payload["note"] == "已电话联系"
    assert contacted_payload["contactedAt"]
    assert contacted_payload["nextFollowUpAt"] == "2026-06-12"
    assert contacted_payload["followUpLogs"][0]["content"] == "电话沟通过，想再看一次详情"

    archived = client.put(
        f"/api/lead-reminders/{reminder['id']}",
        json={"ownerUserId": owner["id"], "status": "invalid", "conclusionReason": "客户明确不需要"},
    )
    assert archived.status_code == 200
    archived_payload = archived.json()["data"]
    assert archived_payload["status"] == "invalid"
    assert archived_payload["conclusionReason"] == "客户明确不需要"
    assert archived_payload["closedAt"]

    invalid_rows = client.get(
        "/api/lead-reminders",
        params={"ownerUserId": owner["id"], "status": "invalid"},
    ).json()["data"]
    assert len(invalid_rows) == 1

    restored = client.put(
        f"/api/lead-reminders/{reminder['id']}",
        json={"ownerUserId": owner["id"], "status": "pending"},
    )
    assert restored.status_code == 200
    restored_payload = restored.json()["data"]
    assert restored_payload["status"] == "pending"
    assert restored_payload["conclusionReason"] is None
    assert restored_payload["closedAt"] is None

    pending = client.get(
        "/api/lead-reminders",
        params={"ownerUserId": owner["id"], "status": "pending"},
    ).json()["data"]
    assert len(pending) == 1
    contacted_rows = client.get(
        "/api/lead-reminders",
        params={"ownerUserId": owner["id"], "status": "contacted"},
    ).json()["data"]
    assert contacted_rows == []

    deleted = client.delete(
        f"/api/lead-reminders/{reminder['id']}",
        params={"ownerUserId": owner["id"]},
    )
    assert deleted.status_code == 200
    assert client.get("/api/lead-reminders", params={"ownerUserId": owner["id"]}).json()["data"] == []


def test_category_management_and_filtering(client):
    login = client.post("/api/auth/mock-login", json={"nickname": "标签用户"}).json()["data"]
    created = client.post(
        "/api/categories",
        json={"ownerUserId": login["id"], "name": "学区房"},
    )
    assert created.status_code == 200
    category = created.json()["data"]

    card_response = client.post(
        "/api/cards",
        json={
            "ownerUserId": login["id"],
            "title": "带标签资源",
            "detailText": "标签筛选测试",
            "categoryIds": [category["id"]],
        },
    )
    assert card_response.status_code == 200

    filtered = client.get(
        "/api/cards",
        params={"ownerUserId": login["id"], "categoryId": category["id"]},
    ).json()["data"]
    assert len(filtered) == 1
    assert filtered[0]["title"] == "带标签资源"

    delete = client.delete(
        f"/api/categories/{category['id']}",
        params={"ownerUserId": login["id"]},
    )
    assert delete.status_code == 200

    categories = client.get("/api/categories", params={"ownerUserId": login["id"]}).json()["data"]
    assert categories == []
    card = client.get(f"/api/cards/{card_response.json()['data']['id']}").json()["data"]
    assert card["categoryIds"] == []


def test_anonymous_and_logged_in_view_stats_are_isolated(client):
    login = client.post("/api/auth/mock-login", json={"nickname": "浏览用户"}).json()["data"]
    card_id = "card_seed_001"

    client.post(
        f"/api/cards/{card_id}/view",
        json={"viewerUserId": login["id"], "nickname": login["nickname"], "avatarUrl": login["avatarUrl"]},
    )
    client.post(
        f"/api/cards/{card_id}/view",
        json={"viewerUserId": login["id"], "nickname": login["nickname"], "avatarUrl": login["avatarUrl"]},
    )
    client.post(f"/api/cards/{card_id}/view", json={"anonymousId": "anon_1"})

    public_stats = client.get(f"/api/cards/{card_id}/stats").json()["data"]
    owner_stats = client.get(
        f"/api/cards/{card_id}/stats",
        params={"requesterUserId": "user_seed_owner"},
    ).json()["data"]

    assert public_stats["anonymousPv"] >= 1
    browser_viewer = next(item for item in owner_stats["loggedInViewers"] if item["nickname"] == "浏览用户")
    assert browser_viewer["viewCount"] == 2
    assert all(item["nickname"] != "匿名用户" for item in owner_stats["loggedInViewers"])


def test_relay_requires_phone_when_enabled(client):
    card_id = "card_seed_001"
    response = client.post(
        f"/api/cards/{card_id}/relay",
        json={"userId": "user_seed_owner", "nickname": "张团长"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "手机号为必填项"


def test_non_owner_stats_masks_relay_private_fields(client):
    card_id = "card_seed_001"
    relay_response = client.post(
        f"/api/cards/{card_id}/relay",
        json={
            "userId": "user_customer_alpha",
            "nickname": "Alice",
            "phone": "13900000000",
            "address": "North Garden 1",
        },
    )
    assert relay_response.status_code == 200

    public_stats = client.get(
        f"/api/cards/{card_id}/stats",
        params={"requesterUserId": "user_customer_beta"},
    ).json()["data"]
    owner_stats = client.get(
        f"/api/cards/{card_id}/stats",
        params={"requesterUserId": "user_seed_owner"},
    ).json()["data"]

    public_entry = next(item for item in public_stats["relayEntries"] if item["userId"] == "user_customer_alpha")
    owner_entry = next(item for item in owner_stats["relayEntries"] if item["userId"] == "user_customer_alpha")

    assert public_entry["nickname"] != "Alice"
    assert public_entry["phone"] is None
    assert public_entry["address"] is None
    assert owner_entry["nickname"] == "Alice"
    assert owner_entry["phone"] == "13900000000"
    assert owner_entry["address"] == "North Garden 1"


def test_customer_relay_submission_is_single_active_entry(client):
    card_id = "card_seed_001"
    payload = {
        "userId": "user_customer_repeat",
        "nickname": "Repeat User",
        "phone": "13900000000",
        "address": "North Garden 2",
    }

    first = client.post(f"/api/cards/{card_id}/relay", json=payload)
    assert first.status_code == 200
    relay_id = first.json()["data"]["id"]

    stats = client.get(
        f"/api/cards/{card_id}/stats",
        params={"requesterUserId": "user_customer_repeat"},
    ).json()["data"]
    assert stats["currentUserRelay"]["userId"] == "user_customer_repeat"
    assert stats["currentUserRelay"]["followUpStatus"] == "pending"

    follow = client.post(
        f"/api/relays/{relay_id}/follow-up",
        json={"operatorUserId": "user_seed_owner"},
    )
    assert follow.status_code == 200

    followed_stats = client.get(
        f"/api/cards/{card_id}/stats",
        params={"requesterUserId": "user_customer_repeat"},
    ).json()["data"]
    assert followed_stats["currentUserRelay"]["followUpStatus"] == "followed"

    second = client.post(f"/api/cards/{card_id}/relay", json=payload)
    assert second.status_code == 409
    assert second.json()["detail"] == "你已经提交过接龙"


def test_duplicate_card_keeps_stats_isolated(client):
    response = client.post(
        "/api/cards/card_seed_001/duplicate",
        json={"userId": "user_seed_owner"},
    )
    assert response.status_code == 200
    duplicated = response.json()["data"]

    stats = client.get(
        f"/api/cards/{duplicated['id']}/stats",
        params={"requesterUserId": "user_seed_owner"},
    ).json()["data"]
    assert stats["pv"] == 0
    assert stats["relayCount"] == 0


def test_owner_can_delete_and_follow_relay(client):
    relay_response = client.post(
        "/api/cards/card_seed_001/relay",
        json={
            "userId": "user_customer_follow",
            "nickname": "Follow User",
            "phone": "13900000000",
            "address": "城南新区 1 号",
        },
    )
    assert relay_response.status_code == 200
    relay_id = relay_response.json()["data"]["id"]

    follow = client.post(
        f"/api/relays/{relay_id}/follow-up",
        json={"operatorUserId": "user_seed_owner"},
    )
    assert follow.status_code == 200
    assert follow.json()["data"]["followUpStatus"] == "followed"

    delete = client.delete(
        f"/api/relays/{relay_id}",
        params={"operatorUserId": "user_seed_owner"},
    )
    assert delete.status_code == 200
    assert delete.json()["data"]["status"] == "deleted"
