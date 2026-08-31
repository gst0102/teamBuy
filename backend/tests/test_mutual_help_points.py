from __future__ import annotations

from app.core.config import settings


def login(client, openid: str):
    return client.post(
        "/api/auth/mock-login",
        json={"openid": openid, "nickname": "互助积分测试用户"},
    ).json()["data"]


def test_mutual_help_initial_points_recharge_and_admin_switches(client, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", "mutual-ops-secret")
    user = login(client, "openid_mutual_points_user")

    initial = client.get(f"/api/scrm/mutual-help?userId={user['id']}")
    assert initial.status_code == 200
    assert initial.json()["data"]["account"]["balance"] == 100
    assert initial.json()["data"]["config"]["rechargeEnabled"] is True
    assert initial.json()["data"]["config"]["withdrawalEnabled"] is False

    order = client.post(
        "/api/scrm/mutual-help/recharge/orders",
        json={"userId": user["id"], "points": 100},
    )
    assert order.status_code == 200
    assert order.json()["data"]["testMode"] is True

    confirmed = client.post(
        f"/api/scrm/mutual-help/recharge/orders/{order.json()['data']['order']['id']}/test-confirm",
        json={"transactionId": "mutual-test-transaction-1"},
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["data"]["account"]["balance"] == 200

    duplicate = client.post(
        f"/api/scrm/mutual-help/recharge/orders/{order.json()['data']['order']['id']}/test-confirm",
        json={"transactionId": "mutual-test-transaction-1"},
    )
    assert duplicate.status_code == 200
    assert duplicate.json()["data"]["duplicate"] is True

    assert client.post(
        "/api/scrm/mutual-help/activity",
        json={"userId": user["id"], "eventType": "published", "taskId": "task-1"},
    ).status_code == 200
    assert client.post(
        "/api/scrm/mutual-help/activity",
        json={"userId": user["id"], "eventType": "completed", "taskId": "task-2"},
    ).status_code == 200

    headers = {"X-Admin-Token": "mutual-ops-secret"}
    operations = client.get("/api/ops-admin/mutual-help", headers=headers)
    assert operations.status_code == 200
    periods = operations.json()["data"]["periods"]
    assert periods["today"]["publishedTasks"] == 1
    assert periods["today"]["completedTasks"] == 1
    assert periods["today"]["rechargeOrders"] == 1
    assert periods["today"]["rechargePoints"] == 100

    updated = client.put(
        "/api/ops-admin/mutual-help",
        headers=headers,
        json={"rechargeVisible": False, "withdrawalVisible": True},
    )
    assert updated.status_code == 200
    config = updated.json()["data"]
    assert config["rechargeVisible"] is False
    assert config["withdrawalVisible"] is True

    public_after_update = client.get(f"/api/scrm/mutual-help?userId={user['id']}")
    assert public_after_update.json()["data"]["config"]["rechargeVisible"] is False
    assert public_after_update.json()["data"]["config"]["withdrawalVisible"] is True


def test_mutual_help_recharge_can_be_closed_at_backend(client, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", "mutual-ops-secret")
    user = login(client, "openid_mutual_points_closed_user")
    headers = {"X-Admin-Token": "mutual-ops-secret"}

    response = client.put(
        "/api/ops-admin/mutual-help",
        headers=headers,
        json={"rechargeEnabled": False},
    )
    assert response.status_code == 200

    blocked = client.post(
        "/api/scrm/mutual-help/recharge/orders",
        json={"userId": user["id"], "points": 100},
    )
    assert blocked.status_code == 403
