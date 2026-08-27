from __future__ import annotations

from app.api.dependencies import get_app_service
from app.models.domain import CustomerAction, LeadReminder, MessageRecord, MessageThread, ReferralReward, ShowcaseEvent, ShowcaseItem, ShowcasePage, UserNote, ViewEvent
from app.services.time_utils import now_iso
from app.core.config import settings


def login(client, openid: str, nickname: str, phone: str | None = None):
    payload = {"openid": openid, "nickname": nickname}
    if phone:
        payload["phone"] = phone
    return client.post("/api/auth/mock-login", json=payload).json()["data"]


def confirm_membership(client, user_id: str, transaction_id: str):
    order = client.post(
        "/api/scrm/membership/orders",
        json={"userId": user_id},
    ).json()["data"]["order"]
    response = client.post(
        f"/api/scrm/membership/orders/{order['id']}/test-confirm",
        json={"transactionId": transaction_id},
    )
    assert response.status_code == 200
    return order, response.json()["data"]


def test_free_customer_intelligence_masks_identity_and_member_unlocks(client):
    owner = login(client, "openid_scrm_owner", "销售A")
    visitor = login(client, "openid_scrm_visitor", "客户王", "13900001234")
    service = client.app.dependency_overrides[get_app_service]()
    now = now_iso()
    note = UserNote(
        id="note_scrm_signal",
        ownerUserId=owner["id"],
        status="active",
        title="长沙改善三房",
        summary="近地铁，精装三房",
        body="公开资料",
        visibilityConfig={"cardType": "property_listing"},
        createdAt=now,
        updatedAt=now,
    )
    service.repo.save_user_note(note)
    showcase = ShowcasePage(
        id="showcase_scrm_signal",
        ownerUserId=owner["id"],
        status="published",
        name="改善房精选",
        items=[ShowcaseItem(noteId=note.id)],
        createdAt=now,
        updatedAt=now,
    )
    service.repo.save_showcase_page(showcase)
    service.repo.add_showcase_event(
        ShowcaseEvent(
            id="showcase_event_scrm_signal",
            showcaseId=showcase.id,
            ownerUserId=owner["id"],
            eventType="view",
            viewerUserId=visitor["id"],
            viewType="logged_in",
            nickname="客户王",
            dateKey=now[:10],
            createdAt=now,
        )
    )

    free = client.get(
        "/api/scrm/customer-intelligence",
        params={"ownerUserId": owner["id"], "requesterUserId": owner["id"]},
    )
    assert free.status_code == 200
    free_data = free.json()["data"]
    assert free_data["locked"] is True
    assert free_data["summary"]["visitorCount"] == 1
    assert "dashboard" not in free_data
    assert "13900001234" not in free.text
    assert "客户王" not in free.text
    free_showcases = client.get("/api/showcases", params={"ownerUserId": owner["id"]})
    assert free_showcases.status_code == 200
    assert free_showcases.json()["data"][0]["analytics"]["locked"] is True
    assert "客户王" not in free_showcases.text
    assert client.get(
        f"/api/showcases/{showcase.id}/analytics",
        params={"ownerUserId": owner["id"]},
    ).status_code == 402
    locked_followup = client.post(
        "/api/scrm/customer-followups/ensure",
        json={
            "ownerUserId": owner["id"],
            "requesterUserId": owner["id"],
            "customerId": visitor["id"],
        },
    )
    assert locked_followup.status_code == 402

    confirm_membership(client, owner["id"], "txn_scrm_owner_1")
    paid = client.get(
        "/api/scrm/customer-intelligence",
        params={"ownerUserId": owner["id"], "requesterUserId": owner["id"]},
    )
    assert paid.status_code == 200
    assert paid.json()["data"]["locked"] is False
    assert paid.json()["data"]["dashboard"]["summary"]["visitorCount"] == 1


def test_customer_followup_action_uses_compact_radar_projection(client, monkeypatch):
    owner = login(client, "openid_compact_followup_owner", "轻量跟进店主")
    confirm_membership(client, owner["id"], "txn_compact_followup")
    service = client.app.dependency_overrides[get_app_service]()
    now = now_iso()
    note = UserNote(
        id="note_compact_followup",
        ownerUserId=owner["id"],
        status="active",
        title="轻量跟进来源资料",
        summary="雷达卡片来源",
        body="公开内容",
        visibilityConfig={"cardType": "property_listing"},
        createdAt=now,
        updatedAt=now,
    )
    service.repo.save_user_note(note)

    def fail_full_customer_detail(*args, **kwargs):
        raise AssertionError("首次跟进不应重建完整客户详情")

    monkeypatch.setattr(service, "get_customer_detail", fail_full_customer_detail)
    response = client.post(
        "/api/scrm/customer-followups/action",
        json={
            "ownerUserId": owner["id"],
            "requesterUserId": owner["id"],
            "customerId": "visitor:compact-followup",
            "action": "start",
            "mode": "property",
            "operationId": "compact-followup-operation-1",
            "visitorIdentityId": "visitor:compact-followup",
            "anonymousId": "anonymous-compact-followup",
            "sourceNoteId": note.id,
            "nickname": "匿名访客",
            "viewCount": 2,
            "lastActivityAt": now,
        },
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["persisted"] is True
    assert data["lead"]["status"] == "following"
    assert data["lead"]["cardId"] == note.id
    assert data["lead"]["visitorIdentityId"] == "visitor:compact-followup"
    assert data["followupCounts"]["following"] == 1


def test_customer_followup_action_persists_complete_draft_atomically(client, monkeypatch):
    owner = login(client, "openid_atomic_followup_owner", "原子跟进店主")
    confirm_membership(client, owner["id"], "txn_atomic_followup")
    service = client.app.dependency_overrides[get_app_service]()
    now = now_iso()
    note = UserNote(
        id="note_atomic_followup",
        ownerUserId=owner["id"],
        status="active",
        title="原子跟进资料",
        summary="跟进来源资料",
        body="公开内容",
        visibilityConfig={"cardType": "property_listing"},
        createdAt=now,
        updatedAt=now,
    )
    service.repo.save_user_note(note)

    def fail_full_customer_detail(*args, **kwargs):
        raise AssertionError("完整详情不应参与首次跟进写入")

    monkeypatch.setattr(service, "get_customer_detail", fail_full_customer_detail)
    payload = {
        "ownerUserId": owner["id"],
        "requesterUserId": owner["id"],
        "customerId": "visitor:atomic-followup",
        "action": "start",
        "mode": "property",
        "operationId": "atomic-followup-operation-1",
        "visitorIdentityId": "visitor:atomic-followup",
        "anonymousId": "anonymous-atomic-followup",
        "sourceNoteId": note.id,
        "nickname": "匿名访客",
        "viewCount": 3,
        "lastActivityAt": now,
        "followUpTags": ["已微信联系", "需求已确认"],
        "logContent": "下周发方案",
        "nextFollowUpAt": "2026-08-30",
    }
    response = client.post("/api/scrm/customer-followups/action", json=payload)
    assert response.status_code == 200
    lead = response.json()["data"]["lead"]
    assert lead["status"] == "following"
    assert lead["customerTags"] == ["已微信联系", "需求已确认"]
    assert lead["nextFollowUpAt"] == "2026-08-30"
    assert lead["followUpLogs"][0]["action"] == "start"
    assert lead["followUpLogs"][0]["actionLabel"] == "已开始跟进"
    assert lead["followUpLogs"][0]["tags"] == ["已微信联系", "需求已确认"]
    assert lead["followUpLogs"][0]["note"] == "下周发方案"
    assert lead["followUpLogs"][0]["nextFollowUpAt"] == "2026-08-30"

    retry_payload = {**payload, "followUpTags": ["待报价"], "logContent": "不应覆盖"}
    retry = client.post("/api/scrm/customer-followups/action", json=retry_payload)
    assert retry.status_code == 200
    retry_lead = retry.json()["data"]["lead"]
    assert retry.json()["data"]["idempotent"] is True
    assert retry_lead["customerTags"] == ["已微信联系", "需求已确认"]
    assert len(retry_lead["followUpLogs"]) == 1

    continued = client.post(
        "/api/scrm/customer-followups/action",
        json={
            "ownerUserId": owner["id"],
            "requesterUserId": owner["id"],
            "customerId": "",
            "leadId": lead["id"],
            "action": "continue",
            "mode": "property",
            "operationId": "atomic-followup-operation-2",
            "expectedVersion": lead["version"],
            "followUpTags": ["待报价"],
            "logContent": "已发方案",
            "nextFollowUpAt": "2026-09-02",
        },
    )
    assert continued.status_code == 200
    continued_lead = continued.json()["data"]["lead"]
    assert continued_lead["status"] == "following"
    assert continued_lead["version"] == lead["version"] + 1
    assert continued_lead["customerTags"] == ["待报价"]
    assert continued_lead["followUpLogs"][0]["action"] == "continue"
    assert continued_lead["followUpLogs"][0]["tags"] == ["待报价"]
    assert continued_lead["followUpLogs"][0]["note"] == "已发方案"
    assert continued_lead["followUpLogs"][0]["nextFollowUpAt"] == "2026-09-02"
    assert len(continued_lead["followUpLogs"]) == 2


def test_customer_intelligence_summary_does_not_build_full_dashboard(client, monkeypatch):
    owner = login(client, "openid_summary_projection_owner", "摘要店主")
    confirm_membership(client, owner["id"], "txn_summary_projection")
    service = client.app.dependency_overrides[get_app_service]()
    now = now_iso()
    note = UserNote(
        id="note_summary_projection",
        ownerUserId=owner["id"],
        status="active",
        title="摘要投影资料",
        summary="用于验证摘要状态计数",
        body="公开内容",
        visibilityConfig={"cardType": "property_listing"},
        createdAt=now,
        updatedAt=now,
    )
    service.repo.save_user_note(note)
    service.repo.save_lead_reminder(
        LeadReminder(
            id="lead_summary_following",
            ownerUserId=owner["id"],
            cardId=note.id,
            viewerUserId="summary-following",
            visitorIdentityId="user:summary-following",
            nickname="跟进客户",
            status="following",
            createdAt=now,
            updatedAt=now,
        )
    )
    service.repo.save_lead_reminder(
        LeadReminder(
            id="lead_summary_abandoned",
            ownerUserId=owner["id"],
            cardId=note.id,
            viewerUserId="summary-abandoned",
            visitorIdentityId="user:summary-abandoned",
            nickname="放弃客户",
            status="paused",
            createdAt=now,
            updatedAt=now,
        )
    )

    def fail_full_dashboard(*args, **kwargs):
        raise AssertionError("摘要接口不应构建完整客户看板")

    monkeypatch.setattr(service, "_build_business_dashboard", fail_full_dashboard)
    response = client.get(
        "/api/scrm/customer-intelligence/summary",
        params={"ownerUserId": owner["id"], "requesterUserId": owner["id"], "mode": "property"},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["locked"] is False
    assert data["source"] == "lightweight_radar_projection"
    assert data["summary"]["pending"] == 0
    assert data["summary"]["following"] == 1
    assert data["summary"]["abandoned"] == 1

    persisted = service.repo.get_customer_radar_summary(owner["id"], "property")
    assert persisted is not None
    assert persisted.isDirty is False
    assert persisted.followingCount == 1
    assert persisted.abandonedCount == 1
    assert not hasattr(persisted, "customerPhone")

    service._customer_intelligence_summary_cache.clear()
    def fail_full_lead_read(*args, **kwargs):
        raise AssertionError("命中 count-only 摘要时不应读取全部线索")

    monkeypatch.setattr(service.repo, "list_lead_reminders", fail_full_lead_read)
    cached_projection = client.get(
        "/api/scrm/customer-intelligence/summary",
        params={"ownerUserId": owner["id"], "requesterUserId": owner["id"], "mode": "property"},
    )
    assert cached_projection.status_code == 200
    assert cached_projection.json()["data"]["source"] == "customer_radar_summary"

    service._invalidate_customer_intelligence_cache(owner["id"])
    assert service.repo.get_customer_radar_summary(owner["id"], "property").isDirty is True


def test_property_customer_intelligence_includes_source_card_leads_in_status_tabs(client):
    owner = login(client, "openid_property_source_lead_owner", "房源销售")
    confirm_membership(client, owner["id"], "txn_property_source_lead")
    service = client.app.dependency_overrides[get_app_service]()
    now = now_iso()
    note = UserNote(
        id="note_property_source_lead",
        ownerUserId=owner["id"],
        sourceCardId="card_property_source_lead",
        status="active",
        title="来源卡片房源",
        summary="用于验证房源雷达状态投影",
        body="房源公开资料",
        visibilityConfig={"cardType": "property_listing"},
        createdAt=now,
        updatedAt=now,
    )
    service.repo.save_user_note(note)
    following = LeadReminder(
        id="lead_property_source_following",
        ownerUserId=owner["id"],
        cardId=note.sourceCardId,
        viewerUserId="property-source-following",
        visitorIdentityId="user:property-source-following",
        nickname="跟进客户",
        status="following",
        createdAt=now,
        updatedAt=now,
    )
    abandoned = LeadReminder(
        id="lead_property_source_abandoned",
        ownerUserId=owner["id"],
        cardId=note.sourceCardId,
        viewerUserId="property-source-abandoned",
        visitorIdentityId="user:property-source-abandoned",
        nickname="放弃客户",
        status="paused",
        conclusionReason="放弃跟进",
        closedAt=now,
        createdAt=now,
        updatedAt=now,
    )
    service.repo.save_lead_reminder(following)
    service.repo.save_lead_reminder(abandoned)

    response = client.get(
        "/api/scrm/customer-intelligence",
        params={
            "ownerUserId": owner["id"],
            "requesterUserId": owner["id"],
            "mode": "property",
        },
    )

    assert response.status_code == 200
    dashboard = response.json()["data"]["dashboard"]
    assert dashboard["opportunitySummary"]["followingFollowupCount"] == 1
    assert dashboard["opportunitySummary"]["abandonedFollowupCount"] == 1
    assert dashboard["followingProfiles"][0]["leadReminderId"] == following.id
    assert dashboard["abandonedProfiles"][0]["leadReminderId"] == abandoned.id


def test_customer_intelligence_refresh_suppresses_cross_scene_lead_and_bypasses_cache(client):
    owner = login(client, "openid_property_cross_scene_owner", "房源销售")
    confirm_membership(client, owner["id"], "txn_property_cross_scene")
    service = client.app.dependency_overrides[get_app_service]()
    now = now_iso()
    note = UserNote(
        id="note_property_cross_scene",
        ownerUserId=owner["id"],
        status="active",
        title="跨场景身份屏蔽测试房源",
        summary="验证房源雷达不会重新显示已处理访客",
        body="房源公开资料",
        visibilityConfig={"cardType": "property_listing"},
        createdAt=now,
        updatedAt=now,
    )
    service.repo.save_user_note(note)
    showcase = ShowcasePage(
        id="showcase_property_cross_scene",
        ownerUserId=owner["id"],
        status="published",
        name="跨场景身份屏蔽展示页",
        items=[ShowcaseItem(noteId=note.id)],
        createdAt=now,
        updatedAt=now,
    )
    service.repo.save_showcase_page(showcase)
    visitor_identity = "user:cross-scene-visitor"
    service.repo.add_showcase_event(
        ShowcaseEvent(
            id="showcase_event_property_cross_scene",
            showcaseId=showcase.id,
            ownerUserId=owner["id"],
            eventType="view",
            viewerUserId="cross-scene-visitor",
            visitorIdentityId=visitor_identity,
            viewType="logged_in",
            nickname="跨场景客户",
            dateKey=now[:10],
            createdAt=now,
        )
    )

    initial = client.get(
        "/api/scrm/customer-intelligence",
        params={
            "ownerUserId": owner["id"],
            "requesterUserId": owner["id"],
            "mode": "property",
        },
    )
    assert initial.status_code == 200
    initial_dashboard = initial.json()["data"]["dashboard"]
    assert any(item["visitorIdentityId"] == visitor_identity for item in initial_dashboard["radarProfiles"])

    # Simulate a follow-up action persisted by another service instance. The
    # normal response may still be the old process-local snapshot, but an
    # explicit refresh must read the durable cross-scene decision.
    service.repo.save_lead_reminder(
        LeadReminder(
            id="lead_groupbuy_cross_scene_abandoned",
            ownerUserId=owner["id"],
            cardId="note_groupbuy_cross_scene",
            viewerUserId="cross-scene-visitor",
            visitorIdentityId=visitor_identity,
            nickname="跨场景客户",
            status="paused",
            conclusionReason="放弃跟进",
            closedAt=now,
            createdAt=now,
            updatedAt=now,
        )
    )

    stale = client.get(
        "/api/scrm/customer-intelligence",
        params={
            "ownerUserId": owner["id"],
            "requesterUserId": owner["id"],
            "mode": "property",
        },
    )
    assert stale.status_code == 200
    assert any(item["visitorIdentityId"] == visitor_identity for item in stale.json()["data"]["dashboard"]["radarProfiles"])

    refreshed = client.get(
        "/api/scrm/customer-intelligence",
        params={
            "ownerUserId": owner["id"],
            "requesterUserId": owner["id"],
            "mode": "property",
            "refresh": "1",
        },
    )
    assert refreshed.status_code == 200
    refreshed_dashboard = refreshed.json()["data"]["dashboard"]
    assert all(item["visitorIdentityId"] != visitor_identity for item in refreshed_dashboard["radarProfiles"])
    assert refreshed_dashboard["summary"]["visitorCount"] == 0


def test_customer_intelligence_rejects_cross_owner(client):
    owner = login(client, "openid_scrm_acl_owner", "销售A")
    other = login(client, "openid_scrm_acl_other", "销售B")
    response = client.get(
        "/api/scrm/customer-intelligence",
        params={"ownerUserId": owner["id"], "requesterUserId": other["id"]},
    )
    assert response.status_code == 403


def test_customer_detail_is_owner_scoped_and_uses_canonical_identity(client, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", "ops-secret")
    owner = login(client, "openid_scrm_detail_owner", "详情店主")
    visitor = login(client, "openid_scrm_detail_visitor", "详情客户", "13900004567")
    other = login(client, "openid_scrm_detail_other", "其他店主")
    service = client.app.dependency_overrides[get_app_service]()
    now = now_iso()
    note = UserNote(
        id="note_scrm_detail",
        ownerUserId=owner["id"],
        status="active",
        title="详情测试资料",
        summary="详情测试",
        body="详情测试正文",
        createdAt=now,
        updatedAt=now,
    )
    service.repo.save_user_note(note)
    showcase = ShowcasePage(
        id="showcase_scrm_detail",
        ownerUserId=owner["id"],
        status="published",
        name="详情测试展示页",
        items=[ShowcaseItem(noteId=note.id)],
        createdAt=now,
        updatedAt=now,
    )
    service.repo.save_showcase_page(showcase)
    service.repo.add_showcase_event(
        ShowcaseEvent(
            id="showcase_event_scrm_detail",
            showcaseId=showcase.id,
            ownerUserId=owner["id"],
            eventType="view",
            viewerUserId=visitor["id"],
            viewType="logged_in",
            nickname="详情客户",
            dateKey=now[:10],
            createdAt=now,
        )
    )
    service.repo.add_showcase_event(
        ShowcaseEvent(
            id="showcase_event_scrm_detail_unrelated",
            showcaseId=showcase.id,
            ownerUserId=owner["id"],
            eventType="view",
            viewerUserId="unrelated_viewer",
            viewType="logged_in",
            nickname="其他访客",
            dateKey=now[:10],
            createdAt=now,
        )
    )

    locked_detail = client.get(
        "/api/scrm/customer-detail",
        params={
            "ownerUserId": owner["id"],
            "requesterUserId": owner["id"],
            "customerId": visitor["id"],
        },
    )
    assert locked_detail.status_code == 200
    assert locked_detail.json()["data"]["locked"] is True
    assert "customer" not in locked_detail.json()["data"]
    assert "详情客户" not in locked_detail.text

    free_mode = client.put(
        "/api/ops-admin/customer-info-chain",
        headers={"X-Admin-Token": "ops-secret"},
        json={"paymentRequired": False, "operatorName": "test"},
    )
    assert free_mode.status_code == 200
    detail = client.get(
        "/api/scrm/customer-detail",
        params={
            "ownerUserId": owner["id"],
            "requesterUserId": owner["id"],
            "customerId": visitor["id"],
        },
    )
    assert detail.status_code == 200
    data = detail.json()["data"]
    assert data["locked"] is False
    assert data["customer"]["viewerUserId"] == visitor["id"]
    assert data["customer"]["nickname"] == "详情客户"
    assert data["customer"]["phone"] == "13900004567"

    double_encoded = client.get(
        "/api/scrm/customer-detail",
        params={
            "ownerUserId": owner["id"],
            "requesterUserId": owner["id"],
            "customerId": f"user%3A{visitor['id']}",
        },
    )
    assert double_encoded.status_code == 200
    assert double_encoded.json()["data"]["customer"]["viewerUserId"] == visitor["id"]

    ensured = client.post(
        "/api/scrm/customer-followups/ensure",
        json={
            "ownerUserId": owner["id"],
            "requesterUserId": owner["id"],
            "customerId": visitor["id"],
        },
    )
    assert ensured.status_code == 200
    ensured_data = ensured.json()["data"]
    assert ensured_data["created"] is True
    assert ensured_data["lead"]["customerPhone"] == "13900004567"

    reused = client.post(
        "/api/scrm/customer-followups/ensure",
        json={
            "ownerUserId": owner["id"],
            "requesterUserId": owner["id"],
            "customerId": visitor["id"],
        },
    )
    assert reused.status_code == 200
    assert reused.json()["data"]["created"] is False
    assert reused.json()["data"]["lead"]["id"] == ensured_data["lead"]["id"]

    started = client.post(
        "/api/scrm/customer-followups/action",
        json={
            "ownerUserId": owner["id"],
            "requesterUserId": owner["id"],
            "customerId": visitor["id"],
            "leadId": ensured_data["lead"]["id"],
            "action": "start",
            "operationId": "test-start-operation-1",
        },
    )
    assert started.status_code == 200
    started_data = started.json()["data"]
    assert started_data["lead"]["status"] == "following"
    assert started_data["actionLabel"] == "已开始跟进"
    assert started_data["lead"]["followUpLogs"][0]["content"] == "已开始跟进"
    assert started_data["persisted"] is True
    assert started_data["lead"]["version"] == ensured_data["lead"]["version"] + 1

    started_retry = client.post(
        "/api/scrm/customer-followups/action",
        json={
            "ownerUserId": owner["id"],
            "requesterUserId": owner["id"],
            "customerId": visitor["id"],
            "leadId": ensured_data["lead"]["id"],
            "action": "start",
            "operationId": "test-start-operation-1",
        },
    )
    assert started_retry.status_code == 200
    assert started_retry.json()["data"]["idempotent"] is True
    assert started_retry.json()["data"]["lead"]["version"] == started_data["lead"]["version"]
    assert len(started_retry.json()["data"]["lead"]["followUpLogs"]) == 1

    stale_action = client.post(
        "/api/scrm/customer-followups/action",
        json={
            "ownerUserId": owner["id"],
            "requesterUserId": owner["id"],
            "customerId": visitor["id"],
            "leadId": ensured_data["lead"]["id"],
            "action": "continue",
            "expectedVersion": ensured_data["lead"]["version"],
            "operationId": "test-stale-operation-1",
        },
    )
    assert stale_action.status_code == 409

    mismatched_customer_action = client.post(
        "/api/scrm/customer-followups/action",
        json={
            "ownerUserId": owner["id"],
            "requesterUserId": owner["id"],
            "customerId": "user:not-the-lead-owner",
            "leadId": ensured_data["lead"]["id"],
            "action": "abandon",
        },
    )
    assert mismatched_customer_action.status_code == 404

    service.repo.save_message_thread(
        MessageThread(
            id="thread_scrm_detail_message",
            noteId=note.id,
            ownerUserId=owner["id"],
            buyerUserId=visitor["id"],
            participantUserIds=[owner["id"], visitor["id"]],
            title=note.title,
            lastMessage="想了解这份资料的详细信息",
            lastMessageAt=now,
            unreadByUser={owner["id"]: 1, visitor["id"]: 0},
            createdAt=now,
            updatedAt=now,
        )
    )
    service.repo.save_message_record(
        MessageRecord(
            id="message_scrm_detail_message",
            threadId="thread_scrm_detail_message",
            senderUserId=visitor["id"],
            content="想了解这份资料的详细信息",
            createdAt=now,
        )
    )
    detail_with_message = client.get(
        "/api/scrm/customer-detail",
        params={
            "ownerUserId": owner["id"],
            "requesterUserId": owner["id"],
            "customerId": visitor["id"],
            "leadId": ensured_data["lead"]["id"],
        },
    )
    assert detail_with_message.status_code == 200
    message_summary = detail_with_message.json()["data"]["messageSummary"]
    assert message_summary["hasMessages"] is True
    assert message_summary["unreadCount"] == 1
    assert message_summary["latestThreadId"] == "thread_scrm_detail_message"
    assert message_summary["latestMessage"]["content"] == "想了解这份资料的详细信息"

    continued = client.post(
        "/api/scrm/customer-followups/action",
        json={
            "ownerUserId": owner["id"],
            "requesterUserId": owner["id"],
            "customerId": visitor["id"],
            "leadId": ensured_data["lead"]["id"],
            "action": "continue",
        },
    )
    assert continued.status_code == 200
    continued_data = continued.json()["data"]
    assert continued_data["lead"]["status"] == "following"
    assert continued_data["actionLabel"] == "已继续跟进"
    assert continued_data["lead"]["followUpLogs"][0]["content"] == "已继续跟进"
    assert len(continued_data["lead"]["followUpLogs"]) == 2

    recorded = client.put(
        f"/api/lead-reminders/{ensured_data['lead']['id']}",
        json={
            "ownerUserId": owner["id"],
            "followUpTags": ["已电话沟通", "需求已确认"],
            "followUpAction": "record",
            "logContent": "客户确认预算，等待报价",
            "nextFollowUpAt": "2026-08-29",
        },
    )
    assert recorded.status_code == 200
    recorded_lead = recorded.json()["data"]
    recorded_log = recorded_lead["followUpLogs"][0]
    assert recorded_lead["nextFollowUpAt"] == "2026-08-29"
    assert recorded_log["action"] == "record"
    assert recorded_log["tags"] == ["已电话沟通", "需求已确认"]
    assert recorded_log["note"] == "客户确认预算，等待报价"
    assert recorded_log["nextFollowUpAt"] == "2026-08-29"
    assert recorded_log["createdAt"]

    tag_only = client.put(
        f"/api/lead-reminders/{ensured_data['lead']['id']}",
        json={
            "ownerUserId": owner["id"],
            "followUpTags": ["待回访"],
            "followUpAction": "record",
        },
    )
    assert tag_only.status_code == 200
    tag_only_log = tag_only.json()["data"]["followUpLogs"][0]
    assert tag_only_log["tags"] == ["待回访"]
    assert tag_only_log["note"] is None
    assert tag_only_log["nextFollowUpAt"] == "2026-08-29"

    radar_after_start = client.get(
        "/api/scrm/customer-intelligence",
        params={"ownerUserId": owner["id"], "requesterUserId": owner["id"]},
    )
    assert radar_after_start.status_code == 200
    start_dashboard = radar_after_start.json()["data"]["dashboard"]
    assert all(item.get("leadReminderId") != ensured_data["lead"]["id"] for item in start_dashboard["radarProfiles"])
    assert all(item.get("visitorIdentityId") != f"user:{visitor['id']}" for item in start_dashboard["radarProfiles"])
    assert any(item.get("leadReminderId") == ensured_data["lead"]["id"] for item in start_dashboard["followingProfiles"])
    following_profile = next(
        item for item in start_dashboard["followingProfiles"]
        if item.get("leadReminderId") == ensured_data["lead"]["id"]
    )
    assert following_profile["nextFollowUpAt"] == "2026-08-29"
    assert "followUpLogs" not in following_profile
    assert "latestFollowUp" not in following_profile

    abandoned = client.post(
        "/api/scrm/customer-followups/action",
        json={
            "ownerUserId": owner["id"],
            "requesterUserId": owner["id"],
            "customerId": visitor["id"],
            "leadId": ensured_data["lead"]["id"],
            "action": "abandon",
        },
    )
    assert abandoned.status_code == 200
    assert abandoned.json()["data"]["lead"]["status"] == "paused"
    assert abandoned.json()["data"]["lead"]["conclusionReason"] == "放弃跟进"

    radar_after_abandon = client.get(
        "/api/scrm/customer-intelligence",
        params={"ownerUserId": owner["id"], "requesterUserId": owner["id"]},
    )
    assert radar_after_abandon.status_code == 200
    radar_dashboard = radar_after_abandon.json()["data"]["dashboard"]
    abandoned_lead_id = ensured_data["lead"]["id"]
    abandoned_customer_id = f"user:{visitor['id']}"
    assert all(item.get("leadReminderId") != abandoned_lead_id for item in radar_dashboard["radarProfiles"])
    assert all(item.get("leadReminderId") != abandoned_lead_id for item in radar_dashboard["opportunityAlerts"])
    assert all(item.get("visitorIdentityId") != abandoned_customer_id for item in radar_dashboard["radarProfiles"])
    assert all(item.get("visitorIdentityId") != abandoned_customer_id for item in radar_dashboard["opportunityAlerts"])
    assert any(item.get("leadReminderId") == abandoned_lead_id for item in radar_dashboard["abandonedProfiles"])
    assert {item.get("leadReminderId") for item in radar_dashboard["abandonedProfiles"]} == {abandoned_lead_id}
    assert radar_dashboard["opportunitySummary"]["abandonedFollowupCount"] == 1

    retained_detail = client.get(
        "/api/scrm/customer-detail",
        params={
            "ownerUserId": owner["id"],
            "requesterUserId": owner["id"],
            "customerId": visitor["id"],
        },
    )
    assert retained_detail.status_code == 200
    retained_lead = retained_detail.json()["data"]["lead"]
    assert retained_lead["status"] == "paused"
    retained_record = next(
        item for item in retained_lead["followUpLogs"]
        if item.get("action") == "record"
    )
    assert retained_record["tags"] == ["待回访"]
    assert retained_record["nextFollowUpAt"] == "2026-08-29"

    forbidden = client.get(
        "/api/scrm/customer-detail",
        params={
            "ownerUserId": owner["id"],
            "requesterUserId": other["id"],
            "customerId": visitor["id"],
        },
    )
    assert forbidden.status_code == 403

    missing = client.get(
        "/api/scrm/customer-detail",
        params={
            "ownerUserId": owner["id"],
            "requesterUserId": owner["id"],
            "customerId": "user:not-a-real-customer",
        },
    )
    assert missing.status_code == 404

    restored = client.post(
        "/api/scrm/customer-followups/action",
        json={
            "ownerUserId": owner["id"],
            "requesterUserId": owner["id"],
            "customerId": visitor["id"],
            "leadId": abandoned_lead_id,
            "action": "restore",
        },
    )
    assert restored.status_code == 200
    assert restored.json()["data"]["removedFromRadar"] is False
    assert restored.json()["data"]["lead"]["status"] == "pending"

    radar_after_restore = client.get(
        "/api/scrm/customer-intelligence",
        params={"ownerUserId": owner["id"], "requesterUserId": owner["id"]},
    )
    assert any(item.get("leadReminderId") == abandoned_lead_id for item in radar_after_restore.json()["data"]["dashboard"]["radarProfiles"])

    abandoned_again = client.post(
        "/api/scrm/customer-followups/action",
        json={
            "ownerUserId": owner["id"],
            "requesterUserId": owner["id"],
            "customerId": visitor["id"],
            "leadId": abandoned_lead_id,
            "action": "abandon",
        },
    )
    assert abandoned_again.status_code == 200
    deleted = client.delete(
        f"/api/lead-reminders/{abandoned_lead_id}",
        params={"ownerUserId": owner["id"]},
    )
    assert deleted.status_code == 200
    visible_reminders = client.get(
        "/api/lead-reminders",
        params={"ownerUserId": owner["id"]},
    )
    assert visible_reminders.status_code == 200
    assert all(item["id"] != abandoned_lead_id for item in visible_reminders.json()["data"])
    radar_after_delete = client.get(
        "/api/scrm/customer-intelligence",
        params={"ownerUserId": owner["id"], "requesterUserId": owner["id"]},
    )
    deleted_dashboard = radar_after_delete.json()["data"]["dashboard"]
    assert all(item.get("leadReminderId") != abandoned_lead_id for item in deleted_dashboard["radarProfiles"])
    assert all(item.get("visitorIdentityId") != abandoned_customer_id for item in deleted_dashboard["radarProfiles"])


def test_anonymous_radar_ids_resolve_direct_detail_and_contacts(client, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", "ops-secret")
    owner = login(client, "openid_scrm_anonymous_radar_owner", "匿名雷达店主")
    service = client.app.dependency_overrides[get_app_service]()
    now = now_iso()
    note = UserNote(
        id="note_scrm_anonymous_radar",
        ownerUserId=owner["id"],
        status="active",
        title="匿名访客详情资料",
        summary="匿名访客详情回归测试",
        body="匿名访客详情回归测试正文",
        visibilityConfig={"cardType": "property_listing"},
        createdAt=now,
        updatedAt=now,
    )
    service.repo.save_user_note(note)

    anonymous_ids = ["anonymous-alpha", "anonymous-beta", "anonymous-gamma"]
    for index, anonymous_id in enumerate(anonymous_ids):
        service.repo.add_view_event(
            ViewEvent(
                id=f"view_scrm_anonymous_{index}",
                cardId=note.id,
                viewType="anonymous",
                anonymousId=anonymous_id,
                nickname="匿名客户",
                durationSeconds=120,
                focusSections=["价格/优惠"],
                viewedAt=now,
                dateKey=now[:10],
            )
        )
    service.repo.add_view_event(
        ViewEvent(
            id="view_scrm_anonymous_legacy",
            cardId=note.id,
            viewType="anonymous",
            nickname="匿名客户",
            durationSeconds=120,
            focusSections=["价格/优惠"],
            viewedAt=now,
            dateKey=now[:10],
        )
    )
    service.repo.save_customer_action(
        CustomerAction(
            id="action_scrm_anonymous_beta",
            ownerUserId=owner["id"],
            noteId=note.id,
            sourceCardId=note.id,
            anonymousId="anonymous-beta",
            actionKey="lead-contact",
            actionLabel="留下电话/微信",
            payload={"email": "beta@example.com", "remark": "详情回归"},
            createdAt=now,
            updatedAt=now,
        )
    )

    free_mode = client.put(
        "/api/ops-admin/customer-info-chain",
        headers={"X-Admin-Token": "ops-secret"},
        json={"paymentRequired": False, "operatorName": "test"},
    )
    assert free_mode.status_code == 200

    intelligence = client.get(
        "/api/scrm/customer-intelligence",
        params={"ownerUserId": owner["id"], "requesterUserId": owner["id"]},
    )
    assert intelligence.status_code == 200
    dashboard = intelligence.json()["data"]["dashboard"]
    profiles = {item["anonymousId"]: item for item in dashboard["radarProfiles"]}
    alerts = {item["anonymousId"]: item for item in dashboard["opportunityAlerts"]}
    assert set(profiles) == set(anonymous_ids) | {""}
    assert set(alerts) == set(anonymous_ids) | {""}
    assert all(item["customerId"] == item["visitorIdentityId"] for item in alerts.values())
    assert alerts["anonymous-beta"]["email"] == "beta@example.com"

    for anonymous_id in anonymous_ids:
        customer_id = alerts[anonymous_id]["customerId"]
        detail = client.get(
            "/api/scrm/customer-detail",
            params={
                "ownerUserId": owner["id"],
                "requesterUserId": owner["id"],
                "customerId": customer_id,
            },
        )
        assert detail.status_code == 200
        data = detail.json()["data"]
        assert data["locked"] is False
        assert data["customer"]["visitorIdentityId"] == customer_id
        assert data["timeline"]["customerId"] == customer_id

    anonymous_started = client.post(
        "/api/scrm/customer-followups/action",
        json={
            "ownerUserId": owner["id"],
            "requesterUserId": owner["id"],
            "customerId": alerts["anonymous-alpha"]["customerId"],
            "action": "start",
        },
    )
    assert anonymous_started.status_code == 200
    assert anonymous_started.json()["data"]["lead"]["status"] == "following"

    anonymous_abandoned = client.post(
        "/api/scrm/customer-followups/action",
        json={
            "ownerUserId": owner["id"],
            "requesterUserId": owner["id"],
            "customerId": alerts["anonymous-beta"]["customerId"],
            "action": "abandon",
        },
    )
    assert anonymous_abandoned.status_code == 200
    assert anonymous_abandoned.json()["data"]["lead"]["status"] == "paused"

    after_actions = client.get(
        "/api/scrm/customer-intelligence",
        params={"ownerUserId": owner["id"], "requesterUserId": owner["id"]},
    )
    assert after_actions.status_code == 200
    after_dashboard = after_actions.json()["data"]["dashboard"]
    assert all(item.get("anonymousId") not in {"anonymous-alpha", "anonymous-beta"} for item in after_dashboard["radarProfiles"])
    assert all(item.get("anonymousId") not in {"anonymous-alpha", "anonymous-beta"} for item in after_dashboard["opportunityAlerts"])

    beta_detail = client.get(
        "/api/scrm/customer-detail",
        params={
            "ownerUserId": owner["id"],
            "requesterUserId": owner["id"],
            "customerId": alerts["anonymous-beta"]["customerId"],
        },
    )
    assert beta_detail.json()["data"]["customer"]["email"] == "beta@example.com"
    assert beta_detail.json()["data"]["lead"]["status"] == "paused"


def test_membership_payment_is_idempotent_and_refund_revokes_only_source_entitlement(client):
    user = login(client, "openid_scrm_member", "会员用户")
    first_order, first = confirm_membership(client, user["id"], "txn_member_1")
    duplicate = client.post(
        f"/api/scrm/membership/orders/{first_order['id']}/test-confirm",
        json={"transactionId": "txn_member_1"},
    )
    assert duplicate.status_code == 200
    assert duplicate.json()["data"]["duplicate"] is True
    _, second = confirm_membership(client, user["id"], "txn_member_2")
    assert second["entitlement"]["startsAt"] == first["entitlement"]["expiresAt"]

    refunded = client.post(
        f"/api/scrm/membership/orders/{first_order['id']}/test-refund",
        json={"operatorUserId": "ops_test"},
    )
    assert refunded.status_code == 200
    status = client.get("/api/scrm/membership", params={"userId": user["id"]}).json()["data"]
    assert status["active"] is True


def test_referral_generates_only_direct_50_percent_reward_and_refund_revokes(client):
    inviter = login(client, "openid_ref_inviter", "群主")
    invitee = login(client, "openid_ref_invitee", "销售B")
    third = login(client, "openid_ref_third", "销售C")
    confirm_membership(client, inviter["id"], "txn_ref_inviter_1")

    center = client.get("/api/scrm/referrals", params={"userId": inviter["id"]}).json()["data"]
    bind = client.post(
        "/api/scrm/referrals/bind",
        json={"inviteeUserId": invitee["id"], "inviteCode": center["inviteCode"]},
    )
    assert bind.status_code == 200
    invitee_center = client.get("/api/scrm/referrals", params={"userId": invitee["id"]}).json()["data"]
    client.post(
        "/api/scrm/referrals/bind",
        json={"inviteeUserId": third["id"], "inviteCode": invitee_center["inviteCode"]},
    )

    order, _ = confirm_membership(client, invitee["id"], "txn_ref_invitee_1")
    confirm_membership(client, third["id"], "txn_ref_third_1")
    inviter_result = client.get("/api/scrm/referrals", params={"userId": inviter["id"]}).json()["data"]
    invitee_result = client.get("/api/scrm/referrals", params={"userId": invitee["id"]}).json()["data"]
    assert inviter_result["totals"]["available"] == 995
    assert invitee_result["totals"]["available"] == 995
    assert inviter_result["secondLevelRewardEnabled"] is False
    assert len(inviter_result["rewards"]) == 1

    refunded = client.post(
        f"/api/scrm/membership/orders/{order['id']}/test-refund",
        json={"operatorUserId": "ops_test"},
    )
    assert refunded.status_code == 200
    inviter_after = client.get("/api/scrm/referrals", params={"userId": inviter["id"]}).json()["data"]
    assert inviter_after["totals"]["available"] == 0
    assert inviter_after["totals"]["revoked"] == 995


def test_refund_rejects_pending_withdrawal_and_releases_unrelated_rewards(client):
    inviter = login(client, "openid_ref_withdraw_inviter", "群主")
    first = login(client, "openid_ref_withdraw_first", "销售一")
    second = login(client, "openid_ref_withdraw_second", "销售二")
    confirm_membership(client, inviter["id"], "txn_withdraw_inviter")
    code = client.get("/api/scrm/referrals", params={"userId": inviter["id"]}).json()["data"]["inviteCode"]
    for user in (first, second):
        assert client.post("/api/scrm/referrals/bind", json={"inviteeUserId": user["id"], "inviteCode": code}).status_code == 200
    first_order, _ = confirm_membership(client, first["id"], "txn_withdraw_first")
    confirm_membership(client, second["id"], "txn_withdraw_second")
    withdrawal = client.post(
        "/api/scrm/referrals/withdrawals",
        json={"userId": inviter["id"], "amountFen": 1990},
    )
    assert withdrawal.status_code == 200
    center = client.get("/api/scrm/referrals", params={"userId": inviter["id"]}).json()["data"]
    assert center["totals"]["reserved"] == 1990
    refunded = client.post(
        f"/api/scrm/membership/orders/{first_order['id']}/test-refund",
        json={"operatorUserId": "ops_test"},
    )
    assert refunded.status_code == 200
    after = client.get("/api/scrm/referrals", params={"userId": inviter["id"]}).json()["data"]
    assert after["totals"]["revoked"] == 995
    assert after["totals"]["available"] == 995
    assert after["withdrawals"][0]["status"] == "rejected"


def test_referral_withdrawal_minimum_amount_switches_by_environment(client, monkeypatch):
    user = login(client, "openid_ref_minimum", "最低提现测试")
    service = client.app.dependency_overrides[get_app_service]()
    now = now_iso()
    state = service._load()
    for index in range(2):
        state.referral_rewards.append(
            ReferralReward(
                id=f"referral_reward_minimum_{index}",
                inviterUserId=user["id"],
                inviteeUserId=f"minimum_invitee_{index}",
                sourceOrderId=f"minimum_order_{index}",
                amountFen=995,
                status="available",
                availableAt=now,
                createdAt=now,
                updatedAt=now,
            )
        )
    service._save(state)

    monkeypatch.setattr(settings, "app_env", "development")
    below_test_minimum = client.post(
        "/api/scrm/referrals/withdrawals",
        json={"userId": user["id"], "amountFen": 9},
    )
    assert below_test_minimum.status_code == 400
    assert "0.10" in below_test_minimum.json()["detail"]
    test_withdrawal = client.post(
        "/api/scrm/referrals/withdrawals",
        json={"userId": user["id"], "amountFen": 995},
    )
    assert test_withdrawal.status_code == 200
    second_same_day = client.post(
        "/api/scrm/referrals/withdrawals",
        json={"userId": user["id"], "amountFen": 995},
    )
    assert second_same_day.status_code == 400
    assert "每日最多提现" in second_same_day.json()["detail"]

    monkeypatch.setattr(settings, "app_env", "production")
    below_production_minimum = client.post(
        "/api/scrm/referrals/withdrawals",
        json={"userId": user["id"], "amountFen": 995},
        headers={"Authorization": f"Bearer {user['authToken']}"},
    )
    assert below_production_minimum.status_code == 400
    assert "10.00" in below_production_minimum.json()["detail"]


def test_referral_withdrawal_supports_partial_fixed_amount_selection(client, monkeypatch):
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(settings, "admin_token", "ops-secret")
    user = login(client, "openid_ref_partial_withdrawal", "部分提现测试")
    service = client.app.dependency_overrides[get_app_service]()
    now = now_iso()
    state = service._load()
    state.referral_rewards.append(
        ReferralReward(
            id="referral_reward_partial_withdrawal",
            inviterUserId=user["id"],
            inviteeUserId="partial_withdrawal_invitee",
            sourceOrderId="partial_withdrawal_order",
            amountFen=2000,
            status="available",
            availableAt=now,
            createdAt=now,
            updatedAt=now,
        )
    )
    service._save(state)

    withdrawal = client.post(
        "/api/scrm/referrals/withdrawals",
        json={"userId": user["id"], "amountFen": 1000},
    )
    assert withdrawal.status_code == 200, withdrawal.text
    withdrawal_data = withdrawal.json()["data"]
    assert withdrawal_data["rewardAllocations"] == {"referral_reward_partial_withdrawal": 1000}

    reserved_center = client.get("/api/scrm/referrals", params={"userId": user["id"]}).json()["data"]
    assert reserved_center["totals"]["available"] == 1000
    assert reserved_center["totals"]["reserved"] == 1000

    settled = client.post(
        f"/api/ops-admin/referral-withdrawals/{withdrawal_data['id']}/settle",
        headers={"X-Admin-Token": "ops-secret"},
    )
    assert settled.status_code == 200, settled.text
    settled_center = client.get("/api/scrm/referrals", params={"userId": user["id"]}).json()["data"]
    assert settled_center["totals"]["withdrawn"] == 1000
    assert settled_center["totals"]["available"] == 1000


def test_share_link_attribution_is_idempotent_and_requires_active_inviter(client):
    inviter = login(client, "openid_share_inviter", "分享者")
    invitee = login(client, "openid_share_invitee", "好友")
    bind = client.post(
        "/api/scrm/referrals/share-bind",
        json={"inviteeUserId": invitee["id"], "inviterUserId": inviter["id"]},
    )
    assert bind.status_code == 200
    assert bind.json()["data"]["relation"]["source"] == "share_link"
    duplicate = client.post(
        "/api/scrm/referrals/share-bind",
        json={"inviteeUserId": invitee["id"], "inviterUserId": inviter["id"]},
    )
    assert duplicate.status_code == 200
    assert duplicate.json()["data"]["duplicate"] is True
    competing_inviter = login(client, "openid_share_competing_inviter", "另一位分享者")
    locked = client.post(
        "/api/scrm/referrals/share-bind",
        json={"inviteeUserId": invitee["id"], "inviterUserId": competing_inviter["id"]},
    )
    assert locked.status_code == 200
    assert locked.json()["data"]["locked"] is True
    assert locked.json()["data"]["relation"]["inviterUserId"] == inviter["id"]

    confirm_membership(client, invitee["id"], "txn_share_invitee_free_inviter")
    center = client.get("/api/scrm/referrals", params={"userId": inviter["id"]}).json()["data"]
    assert center["totals"]["available"] == 0
    assert center["eligibleForRewards"] is False

    active_inviter = login(client, "openid_share_active_inviter", "有效分享者")
    second_invitee = login(client, "openid_share_second_invitee", "第二位好友")
    confirm_membership(client, active_inviter["id"], "txn_share_active_inviter")
    assert client.post(
        "/api/scrm/referrals/share-bind",
        json={"inviteeUserId": second_invitee["id"], "inviterUserId": active_inviter["id"]},
    ).status_code == 200
    confirm_membership(client, second_invitee["id"], "txn_share_second_invitee")
    active_center = client.get("/api/scrm/referrals", params={"userId": active_inviter["id"]}).json()["data"]
    assert active_center["totals"]["available"] == 995
    assert active_center["eligibleForRewards"] is True

    expired_inviter = login(client, "openid_share_expired_inviter", "已到期分享者")
    expired_invitee = login(client, "openid_share_expired_invitee", "到期用户的好友")
    confirm_membership(client, expired_inviter["id"], "txn_share_expired_inviter")
    service = client.app.dependency_overrides[get_app_service]()
    state = service._load()
    for entitlement in state.membership_entitlements:
        if entitlement.userId == expired_inviter["id"]:
            entitlement.expiresAt = "2000-01-01T00:00:00+00:00"
    service._save(state)
    assert client.post(
        "/api/scrm/referrals/share-bind",
        json={"inviteeUserId": expired_invitee["id"], "inviterUserId": expired_inviter["id"]},
    ).status_code == 200
    confirm_membership(client, expired_invitee["id"], "txn_share_expired_invitee")
    expired_center = client.get("/api/scrm/referrals", params={"userId": expired_inviter["id"]}).json()["data"]
    assert expired_center["totals"]["available"] == 0
    assert expired_center["eligibleForRewards"] is False


def test_referral_rejects_self_rebind_and_cycle(client):
    a = login(client, "openid_ref_a", "A")
    b = login(client, "openid_ref_b", "B")
    a_code = client.get("/api/scrm/referrals", params={"userId": a["id"]}).json()["data"]["inviteCode"]
    b_code = client.get("/api/scrm/referrals", params={"userId": b["id"]}).json()["data"]["inviteCode"]
    assert client.post("/api/scrm/referrals/bind", json={"inviteeUserId": a["id"], "inviteCode": a_code}).status_code == 400
    assert client.post("/api/scrm/referrals/bind", json={"inviteeUserId": b["id"], "inviteCode": a_code}).status_code == 200
    assert client.post("/api/scrm/referrals/bind", json={"inviteeUserId": a["id"], "inviteCode": b_code}).status_code == 400


def test_referral_rejects_long_cycle(client):
    a = login(client, "openid_ref_long_a", "A")
    b = login(client, "openid_ref_long_b", "B")
    c = login(client, "openid_ref_long_c", "C")
    code_a = client.get("/api/scrm/referrals", params={"userId": a["id"]}).json()["data"]["inviteCode"]
    code_b = client.get("/api/scrm/referrals", params={"userId": b["id"]}).json()["data"]["inviteCode"]
    code_c = client.get("/api/scrm/referrals", params={"userId": c["id"]}).json()["data"]["inviteCode"]
    assert client.post("/api/scrm/referrals/bind", json={"inviteeUserId": b["id"], "inviteCode": code_a}).status_code == 200
    assert client.post("/api/scrm/referrals/bind", json={"inviteeUserId": c["id"], "inviteCode": code_b}).status_code == 200
    assert client.post("/api/scrm/referrals/bind", json={"inviteeUserId": a["id"], "inviteCode": code_c}).status_code == 400


def test_same_style_modes_are_idempotent_and_do_not_copy_private_data(client):
    source_owner = login(client, "openid_same_source", "来源销售")
    target = login(client, "openid_same_target", "新销售", "13900008888")
    service = client.app.dependency_overrides[get_app_service]()
    now = now_iso()
    source = UserNote(
        id="note_same_public",
        ownerUserId=source_owner["id"],
        status="active",
        title="营销群精选房源",
        summary="核心信息清晰",
        body="公开正文，真实房东电话 13700000000",
        phone="13800000000",
        visibilityConfig={
            "cardType": "property_listing",
            "structuredData": {"price": "199万", "landlordPhone": "13700000000"},
            "privateData": {"upstreamContact": "真实上游"},
            "internalNotes": "绝不允许复制的内部备注",
            "analyticsData": {"customerName": "私密客户"},
        },
        createdAt=now,
        updatedAt=now,
    )
    own = source.model_copy(deep=True)
    own.id = "note_same_own"
    own.ownerUserId = target["id"]
    own.title = "我的服务资料"
    service.repo.save_user_note(source)
    service.repo.save_user_note(own)

    payload = {
        "ownerUserId": target["id"],
        "mode": "reuse_content",
        "sourceNoteId": source.id,
        "idempotencyKey": "same-key-1",
    }
    first = client.post("/api/scrm/same-style/generate", json=payload)
    second = client.post("/api/scrm/same-style/generate", json=payload)
    assert first.status_code == 200
    assert second.json()["data"]["duplicate"] is True
    generated_id = first.json()["data"]["generation"]["generatedNoteId"]
    generated = service.repo.get_user_note(generated_id)
    assert generated.ownerUserId == target["id"]
    semantic_reuse = client.post(
        "/api/scrm/same-style/generate",
        json={**payload, "idempotencyKey": "same-key-semantic-retry"},
    )
    assert semantic_reuse.status_code == 200
    assert semantic_reuse.json()["data"]["duplicate"] is True
    assert semantic_reuse.json()["data"]["reused"] is True
    assert semantic_reuse.json()["data"]["generation"]["id"] == first.json()["data"]["generation"]["id"]
    assert generated.phone is None
    assert "真实上游" not in generated.model_dump_json()
    assert "13700000000" not in generated.model_dump_json()
    assert "绝不允许复制的内部备注" not in generated.model_dump_json()
    assert "私密客户" not in generated.model_dump_json()
    listed_notes = client.get("/api/notes", params={"ownerUserId": target["id"]})
    assert listed_notes.status_code == 200
    assert listed_notes.json()["data"][0]["id"] == generated_id
    assert listed_notes.json()["data"][0]["isSameStyle"] is True
    assert listed_notes.json()["data"][0]["sameStyleLabel"] == "同款"
    publish = client.post(
        f"/api/notes/{generated.id}/publish",
        json={"ownerUserId": target["id"], "expectedRevision": generated.revision},
    )
    assert publish.status_code == 200
    public_generated = client.get(f"/api/notes/public/{generated.id}").json()["data"]
    assert public_generated["ownerProfile"]["phone"] == "13900008888"
    assert "13700000000" not in str(public_generated)
    generation = first.json()["data"]["generation"]
    assert generation["referralRelationId"]
    relation = next(item for item in service._load().referral_relations if item.id == generation["referralRelationId"])
    assert relation.inviterUserId == source_owner["id"]
    assert relation.inviteeUserId == target["id"]

    legacy_dashboard = client.get(
        "/api/dashboard/business",
        params={"ownerUserId": source_owner["id"], "requesterUserId": source_owner["id"]},
    )
    assert legacy_dashboard.status_code == 402

    own_mode = client.post(
        "/api/scrm/same-style/generate",
        json={
            "ownerUserId": target["id"],
            "mode": "use_own_content",
            "ownNoteIds": [own.id],
            "idempotencyKey": "same-key-2",
        },
    )
    assert own_mode.status_code == 200
    showcase_id = own_mode.json()["data"]["generation"]["generatedShowcaseId"]
    showcase = service.repo.get_showcase_page(showcase_id)
    assert showcase.ownerUserId == target["id"]
    assert showcase.items[0].noteId == own.id


def test_business_card_same_style_keeps_only_style_and_uses_target_profile(client):
    source_owner = login(client, "openid_card_source", "原名片")
    target = login(client, "openid_card_target", "新名片", "13911112222")
    service = client.app.dependency_overrides[get_app_service]()
    now = now_iso()
    source = UserNote(
        id="note_card_same_style",
        ownerUserId=source_owner["id"],
        status="active",
        title="原作者名片",
        summary="原作者介绍",
        body="原作者私密个人经历",
        coverUrl="https://example.test/source-avatar.jpg",
        media=[{"id": "att_qr", "type": "image", "url": "https://example.test/source-qr.jpg"}],
        visibilityConfig={
            "cardType": "business_card",
            "structuredData": {"headline": "原介绍", "serviceKeywords": ["原服务"], "bio": "原作者bio", "featuredNoteIds": ["secret_note"]},
            "displayConfig": {"styleId": "warm_gold"},
            "privateData": {"phone": "13700000000"},
        },
        createdAt=now,
        updatedAt=now,
    )
    service.repo.save_user_note(source)
    response = client.post(
        "/api/scrm/same-style/generate",
        json={"ownerUserId": target["id"], "mode": "reuse_content", "sourceNoteId": source.id, "idempotencyKey": "card-style-key"},
    )
    assert response.status_code == 200
    generated = service.repo.get_user_note(response.json()["data"]["generation"]["generatedNoteId"])
    dumped = generated.model_dump_json()
    assert generated.visibilityConfig["displayConfig"]["styleId"] == "warm_gold"
    assert generated.visibilityConfig["structuredData"] == {"headline": "", "serviceKeywords": [], "bio": "", "featuredNoteIds": []}
    assert "原作者" not in dumped
    assert "secret_note" not in dumped
    assert "source-avatar" not in dumped
    assert generated.phone is None


def test_same_style_generation_does_not_persist_the_full_app_state(client, monkeypatch):
    source_owner = login(client, "openid_same_scoped_source", "来源销售")
    target = login(client, "openid_same_scoped_target", "新销售", "13911113333")
    service = client.app.dependency_overrides[get_app_service]()
    now = now_iso()
    source = UserNote(
        id="note_same_scoped_public",
        ownerUserId=source_owner["id"],
        status="active",
        shareState="published",
        title="公开资料",
        summary="公开摘要",
        body="公开正文",
        createdAt=now,
        updatedAt=now,
    )
    service.repo.save_user_note(source)

    def fail_full_state_persistence(*args, **kwargs):
        raise AssertionError("生成同款不应读写完整 AppState")

    monkeypatch.setattr(service, "_load", fail_full_state_persistence)
    monkeypatch.setattr(service, "_save", fail_full_state_persistence)
    response = client.post(
        "/api/scrm/same-style/generate",
        json={
            "ownerUserId": target["id"],
            "mode": "reuse_content",
            "sourceNoteId": source.id,
            "idempotencyKey": "same-scoped-key",
        },
    )
    assert response.status_code == 200


def test_production_identity_token_blocks_cross_account_scrm_reads(client, monkeypatch):
    owner = login(client, "openid_prod_owner", "生产账号A")
    other = login(client, "openid_prod_other", "生产账号B")
    monkeypatch.setattr(settings, "app_env", "production")

    own = client.get(
        "/api/scrm/membership",
        params={"userId": owner["id"]},
        headers={"Authorization": f"Bearer {owner['authToken']}"},
    )
    assert own.status_code == 200

    cross_account = client.get(
        "/api/scrm/membership",
        params={"userId": other["id"]},
        headers={"Authorization": f"Bearer {owner['authToken']}"},
    )
    assert cross_account.status_code == 403

    missing_token = client.get("/api/scrm/membership", params={"userId": owner["id"]})
    assert missing_token.status_code == 401
