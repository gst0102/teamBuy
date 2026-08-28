from __future__ import annotations

import asyncio

from app.api.dependencies import get_app_service, get_sync_task_queue
from app.core.config import settings
from app.models.domain import UserNote, WechatSubscriptionGrant
from app.schemas.cards import RecordViewRequest
from app.services.time_utils import now_iso
from app.services.wechat_miniapp_client import WechatMiniappClientError


def login(client, openid: str, nickname: str):
    return client.post("/api/auth/mock-login", json={"openid": openid, "nickname": nickname}).json()["data"]


def test_subscription_grant_is_consumed_by_note_view_notification(client):
    owner = login(client, "openid_subscription_owner", "资料发布人")
    visitor = login(client, "openid_subscription_visitor", "客户甲")
    service = client.app.dependency_overrides[get_app_service]()
    now = now_iso()
    note = UserNote(
        id="note_subscription_view",
        ownerUserId=owner["id"],
        status="active",
        shareState="published",
        title="重点资料",
        summary="客户查看提醒测试",
        body="公开内容",
        createdAt=now,
        updatedAt=now,
    )
    service.repo.save_user_note(note)

    config = client.get("/api/scrm/notification-config", params={"userId": owner["id"]})
    assert config.status_code == 200
    assert config.json()["data"]["preferences"]["ordinaryAnonymousViewEnabled"] is True

    accepted = client.post(
        "/api/scrm/notification-subscriptions",
        json={
            "userId": owner["id"],
            "templateId": config.json()["data"]["templateId"],
            "status": "accept",
            "requestId": "request_subscription_1",
        },
    )
    assert accepted.status_code == 200
    assert accepted.json()["data"]["accepted"] is True

    viewed = client.post(
        f"/api/notes/{note.id}/view",
        json={"viewerUserId": visitor["id"], "sessionId": "session_subscription_1"},
    )
    assert viewed.status_code == 200
    notification = viewed.json()["data"]["notification"]
    assert notification["queued"] is True
    delivery = service.repo.get_wechat_subscription_delivery(notification["deliveryId"])
    assert delivery and delivery.viewerType == "ordinary"
    grant = service.repo.get_wechat_subscription_grant(delivery.grantId)
    assert grant and grant.status == "reserved"

    class FakeWechatClient:
        def is_configured(self):
            return True

        async def send_subscribe_message(self, **kwargs):
            assert kwargs["openid"] == owner["openid"]
            assert "thing13" in kwargs["data"]
            return {"errcode": 0}

    service.wechat_miniapp_client = FakeWechatClient()
    result = asyncio.run(service.send_wechat_subscription_task({"deliveryId": delivery.id}))
    assert result["syncStatus"] == "success"
    assert service.repo.get_wechat_subscription_delivery(delivery.id).status == "sent"
    assert service.repo.get_wechat_subscription_grant(delivery.grantId).status == "consumed"


def test_subscription_preference_and_grant_request_are_idempotent(client):
    owner = login(client, "openid_subscription_preference", "偏好设置用户")
    service = client.app.dependency_overrides[get_app_service]()
    template_id = service.get_notification_config(owner["id"])["templateId"]
    payload = {"userId": owner["id"], "templateId": template_id, "status": "accept", "requestId": "request_same"}
    first = client.post("/api/scrm/notification-subscriptions", json=payload)
    second = client.post("/api/scrm/notification-subscriptions", json=payload)
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["data"]["duplicate"] is True
    assert len(service.repo.list_wechat_subscription_grants(owner["id"], template_id)) == 1

    updated = client.put(
        "/api/scrm/notification-preferences",
        json={
            "userId": owner["id"],
            "importantCustomerViewEnabled": True,
            "ordinaryAnonymousViewEnabled": False,
        },
    )
    assert updated.status_code == 200
    config = client.get("/api/scrm/notification-config", params={"userId": owner["id"]}).json()["data"]
    assert config["preferences"]["ordinaryAnonymousViewEnabled"] is False


def test_production_public_view_ignores_spoofed_viewer_identity_and_queues_anonymous_notification(client, monkeypatch):
    monkeypatch.setattr(settings, "app_env", "production")
    owner = login(client, "openid_subscription_secure_owner", "资料发布人")
    visitor = login(client, "openid_subscription_secure_visitor", "真实客户")
    service = client.app.dependency_overrides[get_app_service]()
    now = now_iso()
    note = UserNote(
        id="note_subscription_identity_boundary",
        ownerUserId=owner["id"],
        status="active",
        shareState="published",
        title="身份边界测试",
        summary="不能伪造客户身份",
        body="公开内容",
        createdAt=now,
        updatedAt=now,
    )
    service.repo.save_user_note(note)

    authenticated = client.post(
        f"/api/notes/{note.id}/view",
        headers={"Authorization": f"Bearer {visitor['authToken']}"},
        json={"viewerUserId": owner["id"], "nickname": "伪造的发布人", "sessionId": "secure-session-1"},
    )
    assert authenticated.status_code == 200
    assert authenticated.json()["data"]["viewerUserId"] == visitor["id"]
    assert authenticated.json()["data"]["nickname"] == visitor["nickname"]

    assert service._notification_preference_payload(None, True)["ordinaryAnonymousViewEnabled"] is True
    service.repo.save_wechat_subscription_grant(
        WechatSubscriptionGrant(
            id="anonymous-view-grant",
            userId=owner["id"],
            templateId=settings.wechat_miniapp_subscribe_template_id,
            requestId="anonymous-view-request",
            status="available",
            source="test",
            authorizedAt=now,
            createdAt=now,
            updatedAt=now,
        )
    )

    anonymous = client.post(
        f"/api/notes/{note.id}/view",
        json={"anonymousId": "rotating-attacker-id", "sessionId": "secure-session-2"},
    )
    assert anonymous.status_code == 200
    assert anonymous.json()["data"]["viewerUserId"] is None
    assert anonymous.json()["data"]["notification"]["queued"] is True
    delivery = service.repo.get_wechat_subscription_delivery(anonymous.json()["data"]["notification"]["deliveryId"])
    assert delivery and delivery.viewerType == "anonymous"
    assert delivery.viewerLabel == "匿名访客"

    duplicate = client.post(
        f"/api/notes/{note.id}/view",
        json={"anonymousId": "a-different-rotating-id", "sessionId": "secure-session-3"},
    )
    assert duplicate.status_code == 200
    assert duplicate.json()["data"]["notification"] == {"queued": False, "reason": "duplicate"}


def test_subscription_retry_exhaustion_releases_reserved_grant(client):
    owner = login(client, "openid_subscription_retry_owner", "重试发布人")
    visitor = login(client, "openid_subscription_retry_visitor", "重试客户")
    service = client.app.dependency_overrides[get_app_service]()
    now = now_iso()
    note = UserNote(
        id="note_subscription_retry_exhaustion",
        ownerUserId=owner["id"],
        status="active",
        shareState="published",
        title="重试耗尽测试",
        summary="重试耗尽后释放额度",
        body="公开内容",
        createdAt=now,
        updatedAt=now,
    )
    service.repo.save_user_note(note)
    template_id = service.get_notification_config(owner["id"])["templateId"]
    service.record_notification_subscription(owner["id"], template_id, "accept", "test", "retry-request")
    event = service.record_note_view(
        note.id,
        RecordViewRequest(viewerUserId=visitor["id"], sessionId="retry-session"),
    )
    queue = client.app.dependency_overrides[get_sync_task_queue]()
    notification = service.queue_note_view_notification(note.id, event, queue)
    delivery = service.repo.get_wechat_subscription_delivery(notification["deliveryId"])
    assert delivery and delivery.status == "queued"
    grant_id = delivery.grantId

    class AlwaysFailWechatClient:
        def is_configured(self):
            return True

        async def send_subscribe_message(self, **kwargs):
            raise WechatMiniappClientError("temporary微信故障", errcode=45009, retryable=True)

    service.wechat_miniapp_client = AlwaysFailWechatClient()
    for attempt in range(3):
        if attempt < 2:
            try:
                asyncio.run(service.send_wechat_subscription_task({"deliveryId": delivery.id}))
            except WechatMiniappClientError:
                pass
        else:
            result = asyncio.run(service.send_wechat_subscription_task({"deliveryId": delivery.id}))
            assert result["reason"] == "retry_exhausted"
    assert service.repo.get_wechat_subscription_delivery(delivery.id).status == "failed"
    assert service.repo.get_wechat_subscription_grant(grant_id).status == "available"


def test_subscription_queue_failure_marks_delivery_failed_and_can_retry(client):
    owner = login(client, "openid_subscription_queue_owner", "队列发布人")
    visitor = login(client, "openid_subscription_queue_visitor", "队列客户")
    service = client.app.dependency_overrides[get_app_service]()
    queue = client.app.dependency_overrides[get_sync_task_queue]()
    now = now_iso()
    note = UserNote(
        id="note_subscription_queue_failure",
        ownerUserId=owner["id"],
        status="active",
        shareState="published",
        title="队列失败测试",
        summary="保存成功但入列失败",
        body="公开内容",
        createdAt=now,
        updatedAt=now,
    )
    service.repo.save_user_note(note)
    template_id = service.get_notification_config(owner["id"])["templateId"]
    service.record_notification_subscription(owner["id"], template_id, "accept", "test", "queue-request")
    event = service.record_note_view(
        note.id,
        RecordViewRequest(viewerUserId=visitor["id"], sessionId="queue-session"),
    )

    class FailingQueue:
        def enqueue(self, *args, **kwargs):
            raise RuntimeError("queue unavailable")

    failed = service.queue_note_view_notification(note.id, event, FailingQueue())
    assert failed == {"queued": False, "reason": "queue_unavailable"}
    delivery = service.repo.find_wechat_subscription_delivery_by_dedupe_key(
        next(item.dedupeKey for item in service.repo.load().wechat_subscription_deliveries)
    )
    assert delivery and delivery.status == "failed"
    assert delivery.lastError == "queue_unavailable"
    assert service.repo.get_wechat_subscription_grant(delivery.grantId).status == "available"

    retried = service.queue_note_view_notification(note.id, event, queue)
    assert retried["queued"] is True
    assert service.repo.get_wechat_subscription_delivery(delivery.id).status == "queued"


def test_stale_reserved_subscription_grant_is_released(client):
    owner = login(client, "openid_subscription_stale_owner", "过期额度用户")
    service = client.app.dependency_overrides[get_app_service]()
    template_id = service.get_notification_config(owner["id"])["templateId"]
    service.record_notification_subscription(owner["id"], template_id, "accept", "test", "stale-request")
    grant = service.repo.list_wechat_subscription_grants(owner["id"], template_id)[0]
    grant.status = "reserved"
    grant.reservedAt = "2020-01-01T00:00:00+00:00"
    service.repo.save_wechat_subscription_grant(grant)

    assert service.recover_stale_subscription_grants() == 1
    assert service.repo.get_wechat_subscription_grant(grant.id).status == "available"


def test_customer_message_queues_existing_template_and_deep_links_to_thread(client):
    owner = login(client, "openid_message_subscription_owner", "资料发布人")
    buyer = login(client, "openid_message_subscription_buyer", "高意向客户")
    outsider = login(client, "openid_message_subscription_outsider", "无关用户")
    service = client.app.dependency_overrides[get_app_service]()
    now = now_iso()
    note = UserNote(
        id="note_message_subscription",
        ownerUserId=owner["id"],
        status="active",
        shareState="published",
        title="客户留言资料",
        summary="客户留言订阅测试",
        body="公开内容",
        createdAt=now,
        updatedAt=now,
    )
    service.repo.save_user_note(note)
    template_id = service.get_notification_config(owner["id"])["templateId"]
    service.record_notification_subscription(owner["id"], template_id, "accept", "test", "message-request")

    created = client.post(
        "/api/messages/threads",
        json={
            "userId": buyer["id"],
            "noteId": note.id,
            "content": "请联系我 13800138000，微信：buyer_contact",
        },
    )
    assert created.status_code == 200
    data = created.json()["data"]
    notification = data["notification"]
    assert notification["queued"] is True
    assert notification["notificationType"] == "message"
    assert notification["threadId"] == data["id"]

    deliveries = service.repo.list_wechat_subscription_deliveries(owner["id"])
    message_delivery = next(item for item in deliveries if item.notificationType == "message")
    assert message_delivery.threadId == data["id"]
    assert message_delivery.messageId == data["message"]["id"]
    assert message_delivery.page == f"/pages/message-thread/index?id={data['id']}&source=subscription&autoHome=1"
    assert message_delivery.viewerType == "important"
    assert message_delivery.data["thing3"]["value"].startswith("客户留言")
    assert "13800138000" not in message_delivery.data["thing3"]["value"]
    assert "buyer_contact" not in message_delivery.data["thing3"]["value"]

    forbidden = client.get(
        f"/api/messages/threads/{data['id']}/messages",
        params={"userId": outsider["id"]},
    )
    assert forbidden.status_code == 403

    owner_reply = client.post(
        f"/api/messages/threads/{data['id']}/messages",
        json={"userId": owner["id"], "content": "收到，我来跟进"},
    )
    assert owner_reply.status_code == 200
    assert "notification" not in owner_reply.json()["data"]
    assert len([item for item in service.repo.list_wechat_subscription_deliveries(owner["id"]) if item.notificationType == "message"]) == 1


def test_customer_message_supersedes_queued_view_notification(client):
    owner = login(client, "openid_message_priority_owner", "优先级发布人")
    buyer = login(client, "openid_message_priority_buyer", "高置信客户")
    service = client.app.dependency_overrides[get_app_service]()
    queue = client.app.dependency_overrides[get_sync_task_queue]()
    now = now_iso()
    note = UserNote(
        id="note_message_priority",
        ownerUserId=owner["id"],
        status="active",
        shareState="published",
        title="优先级测试资料",
        summary="留言应优先于普通浏览",
        body="公开内容",
        createdAt=now,
        updatedAt=now,
    )
    service.repo.save_user_note(note)
    template_id = service.get_notification_config(owner["id"])["templateId"]
    service.record_notification_subscription(owner["id"], template_id, "accept", "test", "priority-request")
    view_event = service.record_note_view(
        note.id,
        RecordViewRequest(viewerUserId=buyer["id"], sessionId="priority-view-session"),
    )
    view_notification = service.queue_note_view_notification(note.id, view_event, queue)
    view_delivery = service.repo.get_wechat_subscription_delivery(view_notification["deliveryId"])
    assert view_delivery and view_delivery.notificationType == "view" and view_delivery.status == "queued"

    created = client.post(
        "/api/messages/threads",
        json={"userId": buyer["id"], "noteId": note.id, "content": "我想进一步了解"},
    )
    assert created.status_code == 200
    assert created.json()["data"]["notification"]["queued"] is True
    assert service.repo.get_wechat_subscription_delivery(view_delivery.id).status == "skipped"
    assert service.repo.get_wechat_subscription_delivery(view_delivery.id).lastError == "superseded_by_customer_message"
    message_deliveries = [
        item for item in service.repo.list_wechat_subscription_deliveries(owner["id"])
        if item.notificationType == "message"
    ]
    assert len(message_deliveries) == 1
    assert message_deliveries[0].grantId == view_delivery.grantId
    assert service.repo.get_wechat_subscription_grant(message_deliveries[0].grantId).status == "reserved"


def test_customer_message_notification_is_deduplicated_within_time_bucket(client):
    owner = login(client, "openid_message_dedupe_owner", "去重发布人")
    buyer = login(client, "openid_message_dedupe_buyer", "重复留言客户")
    service = client.app.dependency_overrides[get_app_service]()
    now = now_iso()
    note = UserNote(
        id="note_message_dedupe",
        ownerUserId=owner["id"],
        status="active",
        shareState="published",
        title="重复留言资料",
        summary="同一时间窗只通知一次",
        body="公开内容",
        createdAt=now,
        updatedAt=now,
    )
    service.repo.save_user_note(note)
    template_id = service.get_notification_config(owner["id"])["templateId"]
    service.record_notification_subscription(owner["id"], template_id, "accept", "test", "dedupe-request")

    first = client.post(
        "/api/messages/threads",
        json={"userId": buyer["id"], "noteId": note.id, "content": "第一次留言"},
    )
    assert first.status_code == 200
    thread_id = first.json()["data"]["id"]
    second = client.post(
        f"/api/messages/threads/{thread_id}/messages",
        json={"userId": buyer["id"], "content": "补充留言"},
    )
    assert second.status_code == 200
    assert "notification" not in second.json()["data"]
    message_deliveries = [
        item for item in service.repo.list_wechat_subscription_deliveries(owner["id"])
        if item.notificationType == "message"
    ]
    assert len(message_deliveries) == 1


def test_customer_message_queue_failure_restores_superseded_view_notification(client):
    owner = login(client, "openid_message_queue_restore_owner", "回滚发布人")
    buyer = login(client, "openid_message_queue_restore_buyer", "回滚客户")
    service = client.app.dependency_overrides[get_app_service]()
    queue = client.app.dependency_overrides[get_sync_task_queue]()
    now = now_iso()
    note = UserNote(
        id="note_message_queue_restore",
        ownerUserId=owner["id"],
        status="active",
        shareState="published",
        title="留言入队回滚资料",
        summary="留言队列失败时恢复浏览通知",
        body="公开内容",
        createdAt=now,
        updatedAt=now,
    )
    service.repo.save_user_note(note)
    template_id = service.get_notification_config(owner["id"])["templateId"]
    service.record_notification_subscription(owner["id"], template_id, "accept", "test", "restore-request")
    view_event = service.record_note_view(
        note.id,
        RecordViewRequest(viewerUserId=buyer["id"], sessionId="restore-view-session"),
    )
    view_notification = service.queue_note_view_notification(note.id, view_event, queue)
    view_delivery = service.repo.get_wechat_subscription_delivery(view_notification["deliveryId"])
    assert view_delivery and view_delivery.status == "queued"

    class FailingQueue:
        def enqueue(self, *args, **kwargs):
            raise RuntimeError("queue unavailable")

    created = service.create_message_thread(
        {"userId": buyer["id"], "noteId": note.id, "content": "留言入队失败回滚"},
    )
    result = service.queue_message_notification(created["id"], created["message"]["id"], FailingQueue())
    assert result == {"queued": False, "reason": "queue_unavailable"}
    restored = service.repo.get_wechat_subscription_delivery(view_delivery.id)
    assert restored and restored.status == "queued" and restored.lastError is None
    assert service.repo.get_wechat_subscription_grant(restored.grantId).status == "reserved"
