from __future__ import annotations

from app.api.dependencies import get_app_service, get_sync_task_queue, get_wecom_client
from app.core.config import settings
from app.services.media_storage_service import MediaStorageService
from app.services.media_processing_service import MediaProcessingService
from app.services.wecom_client import DownloadedMedia
from io import BytesIO
from PIL import Image


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


def test_real_sync_records_media_retry_job_on_download_failure(client, monkeypatch):
    class FailingWecomClient:
        async def sync_msg(self, cursor=None, token=None, limit=None):
            return {
                "errcode": 0,
                "errmsg": "ok",
                "next_cursor": "cursor_media_failed",
                "has_more": 0,
                "msg_list": [
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

    assert response.status_code == 502
    retries = client.get("/api/wecom/media-retries").json()["data"]
    assert retries[-1]["mediaId"] == "media_failed_001"
    assert retries[-1]["status"] == "failed"
    assert retries[-1]["attempts"] == 1


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
    assert "导入成功" in notifications[-1]["message"]


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
    response = client.post(
        "/api/wecom/mock-sync",
        json={"externalUserId": "external_link", "conversationId": "conv_link", "fixture": "link"},
    )
    assert response.status_code == 200

    pending = client.get("/api/imports/pending").json()["data"]
    latest = pending[-1]
    card = latest["generatedCard"]
    assert latest["sourceType"] == "web_link"
    assert card["sourceUrl"] == "https://example.com/group-buy"
    assert card["coverUrl"] == "https://example.com/cover.jpg"


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
    assert card["ownerUserId"] == login["id"]

    publish = client.post(f"/api/cards/{card['id']}/publish", json={"userId": login["id"]})
    assert publish.status_code == 200
    assert publish.json()["data"]["status"] == "published"


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
