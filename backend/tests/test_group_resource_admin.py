from __future__ import annotations

import base64

from app.core.config import settings
from backend.tests.test_group_tools import group_payload, login, qr_bytes


def admin_group_payload(name: str = "运营房产群") -> dict:
    return {
        "name": name,
        "cityMode": "city",
        "cityLabel": "长沙市",
        "industry": "房产",
        "purpose": "找同行",
        "memberRange": "100-300",
        "activeLevel": "中",
        "remark": "管理员维护的公开群",
        "qrImageUrl": "/media/admin-group.png",
        "expiresInDays": 7,
    }


def test_mobile_group_admin_requires_server_role_and_bypasses_daily_quota(client, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", "ops-secret")
    operator = login(client, "手机群管理员")

    denied = client.post(
        f"/api/group-resources/admin?userId={operator['id']}",
        json=admin_group_payload(),
    )
    assert denied.status_code == 403
    assert client.get(f"/api/group-resources/admin-status?userId={operator['id']}").json()["data"]["enabled"] is False

    enabled = client.put(
        f"/api/ops-admin/group-resource-admins/{operator['id']}",
        headers={"X-Admin-Token": "ops-secret"},
        json={"enabled": True, "operatorName": "PC管理员"},
    )
    assert enabled.status_code == 200
    assert enabled.json()["data"]["enabled"] is True
    assert client.get(f"/api/group-resources/admin-status?userId={operator['id']}").json()["data"]["enabled"] is True

    # A normal publication still consumes the ordinary user's daily slot.
    regular = client.post("/api/group-resources", json=group_payload(operator["id"], "普通发布群"))
    assert regular.status_code == 200
    blocked_regular = client.post("/api/group-resources", json=group_payload(operator["id"], "普通发布群2"))
    assert blocked_regular.status_code == 409

    # The authenticated admin route has its own audited path and does not use
    # the ordinary quota or create a personal publish reward.
    first = client.post(f"/api/group-resources/admin?userId={operator['id']}", json=admin_group_payload("管理员群1"))
    second = client.post(f"/api/group-resources/admin?userId={operator['id']}", json=admin_group_payload("管理员群2"))
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["data"]["rewardAmount"] == 0
    assert first.json()["data"]["rewardStatusText"] == "无需发放"
    assert first.json()["data"]["reviewStatus"] == "approved"
    assert first.json()["data"].get("sourceType") is None

    review = client.get(
        "/api/ops-admin/group-resource-review",
        headers={"X-Admin-Token": "ops-secret"},
    ).json()["data"]
    admin_rows = [item for item in review["items"] if item["name"] == "管理员群1"]
    assert len(admin_rows) == 1
    assert admin_rows[0]["sourceType"] == "mobile_admin"

    disabled = client.put(
        f"/api/ops-admin/group-resource-admins/{operator['id']}",
        headers={"X-Admin-Token": "ops-secret"},
        json={"enabled": False, "operatorName": "PC管理员"},
    )
    assert disabled.status_code == 200
    assert disabled.json()["data"]["enabled"] is False
    assert client.get(f"/api/group-resources/admin-status?userId={operator['id']}").json()["data"]["enabled"] is False
    revoked = client.post(
        f"/api/group-resources/admin?userId={operator['id']}",
        json=admin_group_payload("撤销后不应创建"),
    )
    assert revoked.status_code == 403


def test_pc_catalog_group_uses_canonical_resource_and_no_personal_reward(client, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", "ops-secret")
    headers = {"X-Admin-Token": "ops-secret"}
    image_data = "data:image/png;base64," + base64.b64encode(qr_bytes("https://example.com/admin-group")).decode("ascii")

    created = client.post(
        "/api/ops-admin/group-resource-catalog",
        headers=headers,
        json={**admin_group_payload("PC正式群"), "qrImageUrl": None, "qrImageData": image_data},
    )
    assert created.status_code == 200
    resource = created.json()["data"]
    assert resource["ownerUserId"] == "platform_admin"
    assert resource["rewardAmount"] == 0
    assert resource["rewardStatusText"] == "无需发放"
    assert resource["reviewStatus"] == "approved"
    assert resource["qrImageUrl"]

    public = client.get("/api/group-resources").json()["data"]
    public_row = next(item for item in public if item["id"] == resource["id"])
    assert public_row["qrImageUrl"] == ""
    assert public_row.get("sourceType") is None

    approved = client.post(
        f"/api/ops-admin/group-resource-review/{resource['id']}/approve",
        headers=headers,
        json={"operatorName": "PC管理员", "reason": "已核验二维码"},
    )
    assert approved.status_code == 200
    detail = approved.json()["data"]["detail"]
    assert detail["sourceType"] == "platform_admin"
    assert detail["reviewStatus"] == "approved"
    assert detail["rewardState"] == "capped"
    assert detail["pointTransactions"] == []


def test_group_resource_admin_configuration_is_admin_token_only(client, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", "ops-secret")
    user = login(client, "待开通用户")
    assert client.get("/api/ops-admin/group-resource-admins").status_code == 403
    assert client.put(
        f"/api/ops-admin/group-resource-admins/{user['id']}",
        json={"enabled": True},
    ).status_code == 403
    missing = client.put(
        "/api/ops-admin/group-resource-admins/missing-user",
        headers={"X-Admin-Token": "ops-secret"},
        json={"enabled": True},
    )
    assert missing.status_code == 404
