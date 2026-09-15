from __future__ import annotations

from backend.tests.test_group_tools import group_payload, login
from app.core.config import settings


def test_group_resource_review_queue_requires_admin_and_uses_real_user_submissions(client, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", "ops-secret")
    owner = login(client, "审核发布者")
    created = client.post("/api/group-resources", json=group_payload(owner["id"], "真实用户群"))
    resource_id = created.json()["data"]["id"]

    assert client.get("/api/ops-admin/group-resource-review").status_code == 403
    listing = client.get("/api/ops-admin/group-resource-review", headers={"X-Admin-Token": "ops-secret"})
    assert listing.status_code == 200
    data = listing.json()["data"]
    assert data["total"] == 1
    assert data["items"][0]["id"] == resource_id
    assert data["items"][0]["effectiveStatus"] == "reviewing"
    assert data["summary"]["reviewing"] == 1

    detail = client.get(f"/api/ops-admin/group-resource-review/{resource_id}", headers={"X-Admin-Token": "ops-secret"})
    assert detail.status_code == 200
    assert detail.json()["data"]["qrImageUrl"] == "/media/group-test.png"
    assert detail.json()["data"]["owner"]["nickname"] == "审核发布者"


def test_group_resource_review_approve_is_idempotent_and_credits_reward_ledger(client, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", "ops-secret")
    owner = login(client, "奖励审核者")
    created = client.post("/api/group-resources", json=group_payload(owner["id"], "待审核群"))
    resource_id = created.json()["data"]["id"]
    headers = {"X-Admin-Token": "ops-secret"}

    first = client.post(
        f"/api/ops-admin/group-resource-review/{resource_id}/approve",
        headers=headers,
        json={"operatorName": "管理员A", "reason": "二维码和群信息已核验"},
    )
    second = client.post(
        f"/api/ops-admin/group-resource-review/{resource_id}/approve",
        headers=headers,
        json={"operatorName": "管理员A", "reason": "重复点击"},
    )
    assert first.status_code == 200
    assert second.status_code == 200
    detail = second.json()["data"]["detail"]
    assert detail["reviewStatus"] == "approved"
    assert detail["rewardState"] == "paid"
    rewards = [item for item in detail["pointTransactions"] if item["ledgerType"] == "group_resource_publish_reward"]
    assert len(rewards) == 1
    assert rewards[0]["pointsDelta"] == 10
    assert rewards[0]["pointType"] == "base"
    assert detail["owner"]["groupResourcePenaltyDebt"] == 0


def test_two_paid_distinct_complaints_pause_resource_and_refund_each_viewer_once(client):
    owner = login(client, "投诉资源发布者")
    viewer_a = login(client, "投诉用户A")
    viewer_b = login(client, "投诉用户B")
    resource = client.post("/api/group-resources", json=group_payload(owner["id"], "待保护群")).json()["data"]
    resource_id = resource["id"]

    assert client.post(f"/api/group-resources/{resource_id}/view", json={"userId": viewer_a["id"]}).status_code == 200
    assert client.post(f"/api/group-resources/{resource_id}/view", json={"userId": viewer_b["id"]}).status_code == 200
    first = client.post(
        f"/api/group-resources/{resource_id}/complaints",
        json={"userId": viewer_a["id"], "reason": "二维码无法入群"},
    )
    duplicate = client.post(
        f"/api/group-resources/{resource_id}/complaints",
        json={"userId": viewer_a["id"], "reason": "重复投诉"},
    )
    second = client.post(
        f"/api/group-resources/{resource_id}/complaints",
        json={"userId": viewer_b["id"], "reason": "群信息不符"},
    )
    assert first.status_code == 200
    assert duplicate.status_code == 200
    assert duplicate.json()["data"]["duplicate"] is True
    assert second.status_code == 200
    assert second.json()["data"]["protected"] is True
    assert client.get("/api/group-resources").json()["data"] == []
    assert client.post(f"/api/group-resources/{resource_id}/view", json={"userId": login(client, '投诉用户C')["id"]}).status_code == 410

    for viewer in (viewer_a, viewer_b):
        points = client.get(f"/api/scrm/mutual-help?userId={viewer['id']}").json()["data"]["points"]
        assert points["base"] == 100


def test_invalidate_can_revoke_reward_and_record_penalty_debt_without_negative_balance(client, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", "ops-secret")
    owner = login(client, "处罚对象")
    resource = client.post("/api/group-resources", json=group_payload(owner["id"], "需处罚群")).json()["data"]
    headers = {"X-Admin-Token": "ops-secret"}
    assert client.post(f"/api/ops-admin/group-resource-review/{resource['id']}/approve", headers=headers, json={}).status_code == 200
    invalidated = client.post(
        f"/api/ops-admin/group-resource-review/{resource['id']}/invalidate",
        headers=headers,
        json={"operatorName": "管理员B", "reason": "确认二维码无效", "extraPenalty": 500, "pausePublisher": True, "refundViewers": True},
    )
    assert invalidated.status_code == 200
    detail = invalidated.json()["data"]["detail"]
    assert detail["reviewStatus"] == "rejected"
    assert detail["owner"]["groupResourcePublishingPaused"] is True
    assert detail["owner"]["groupResourcePenaltyDebt"] > 0
    assert detail["owner"]["groupResourcePenaltyDebt"] == detail["penaltyDebt"]

    blocked = client.post("/api/group-resources", json=group_payload(owner["id"], "处罚后再发"))
    assert blocked.status_code == 403


def test_complaint_requires_paid_view_and_invalidate_is_idempotent(client, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", "ops-secret")
    owner = login(client, "幂等发布者")
    viewer = login(client, "未付费投诉者")
    resource = client.post("/api/group-resources", json=group_payload(owner["id"], "幂等群")).json()["data"]
    resource_id = resource["id"]

    unpaid = client.post(
        f"/api/group-resources/{resource_id}/complaints",
        json={"userId": viewer["id"], "reason": "没有付费也试投诉"},
    )
    assert unpaid.status_code == 403

    headers = {"X-Admin-Token": "ops-secret"}
    assert client.post(f"/api/ops-admin/group-resource-review/{resource_id}/approve", headers=headers, json={}).status_code == 200
    first = client.post(
        f"/api/ops-admin/group-resource-review/{resource_id}/invalidate",
        headers=headers,
        json={"reason": "确认无效", "extraPenalty": 10, "pausePublisher": False},
    )
    second = client.post(
        f"/api/ops-admin/group-resource-review/{resource_id}/invalidate",
        headers=headers,
        json={"reason": "重复点击", "extraPenalty": 10, "pausePublisher": False},
    )
    assert first.status_code == 200
    assert second.status_code == 200
    detail = second.json()["data"]["detail"]
    assert second.json()["data"]["result"]["idempotent"] is True
    penalties = [item for item in detail["pointTransactions"] if item["ledgerType"] == "group_resource_penalty"]
    assert len(penalties) == 1
    assert sum(item["pointsDelta"] for item in penalties) == -20
    assert {item["pointType"] for item in penalties} == {"base"}
    assert sum(abs(item["pointsDelta"]) for item in penalties) == 20
    owner_points = client.get(f"/api/scrm/mutual-help?userId={owner['id']}").json()["data"]["points"]
    assert owner_points == {"total": 90, "base": 90, "reward": 0}

    removed = client.post(
        f"/api/ops-admin/group-resource-review/{resource_id}/remove",
        headers=headers,
        json={"reason": "永久下架"},
    )
    blocked = client.post(
        f"/api/ops-admin/group-resource-review/{resource_id}/penalty",
        headers=headers,
        json={"reason": "下架后重复处罚", "extraPenalty": 10},
    )
    assert removed.status_code == 200
    assert blocked.status_code == 409


def test_production_catalogue_is_public_but_group_actions_require_login(client, monkeypatch):
    monkeypatch.setattr(settings, "app_env", "production")
    assert client.get("/api/group-resources").status_code == 200
    assert client.post("/api/group-resources", json={}).status_code == 401
    assert client.post("/api/group-resources/unknown/view", json={"userId": "someone"}).status_code == 401
    assert client.post("/api/group-resources/unknown/complaints", json={"userId": "someone", "reason": "test"}).status_code == 401
