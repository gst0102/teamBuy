from __future__ import annotations

import json

from app.api.dependencies import get_app_service
from app.core.config import settings
from app.services.ops_console_store import OpsConsoleStore


def login(client, openid: str, nickname: str):
    return client.post(
        "/api/auth/mock-login",
        json={"openid": openid, "nickname": nickname},
    ).json()["data"]


def test_customer_info_chain_switch_is_server_authoritative(client, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", "ops-secret")
    owner = login(client, "openid_feature_owner", "开关测试用户")
    service = client.app.dependency_overrides[get_app_service]()
    headers = {"X-Admin-Token": "ops-secret"}

    closed = client.put(
        "/api/ops-admin/customer-info-chain",
        headers=headers,
        json={"enabled": False, "operatorName": "reviewer"},
    )
    assert closed.status_code == 200
    assert closed.json()["data"] == {
        "enabled": False,
        "paymentRequired": True,
        "updatedBy": "reviewer",
        "updatedAt": closed.json()["data"]["updatedAt"],
    }

    membership = client.get("/api/scrm/membership", params={"userId": owner["id"]})
    assert membership.status_code == 200
    assert membership.json()["data"]["featureEnabled"] is False
    assert membership.json()["data"]["status"] == "disabled"

    intelligence = client.get(
        "/api/scrm/customer-intelligence",
        params={"ownerUserId": owner["id"], "requesterUserId": owner["id"]},
    )
    assert intelligence.status_code == 200
    assert intelligence.json()["data"]["featureEnabled"] is False
    assert "dashboard" not in intelligence.json()["data"]

    order = client.post("/api/scrm/membership/orders", json={"userId": owner["id"]})
    assert order.status_code == 403
    assert service.customer_info_chain_enabled() is False

    reopened = client.put(
        "/api/ops-admin/customer-info-chain",
        headers=headers,
        json={"enabled": True, "operatorName": "reviewer"},
    )
    assert reopened.status_code == 200
    assert reopened.json()["data"]["enabled"] is True
    assert service.customer_info_chain_enabled() is True
    assert client.post("/api/scrm/membership/orders", json={"userId": owner["id"]}).status_code == 200

    free_mode = client.put(
        "/api/ops-admin/customer-info-chain",
        headers=headers,
        json={"paymentRequired": False, "operatorName": "reviewer"},
    )
    assert free_mode.status_code == 200
    assert free_mode.json()["data"]["enabled"] is True
    assert free_mode.json()["data"]["paymentRequired"] is False

    free_membership = client.get("/api/scrm/membership", params={"userId": owner["id"]})
    assert free_membership.status_code == 200
    assert free_membership.json()["data"]["paymentRequired"] is False
    free_intelligence = client.get(
        "/api/scrm/customer-intelligence",
        params={"ownerUserId": owner["id"], "requesterUserId": owner["id"]},
    )
    assert free_intelligence.status_code == 200
    assert free_intelligence.json()["data"]["locked"] is False
    assert free_intelligence.json()["data"]["paymentRequired"] is False
    assert client.post("/api/scrm/membership/orders", json={"userId": owner["id"]}).status_code == 409

    paid_mode = client.put(
        "/api/ops-admin/customer-info-chain",
        headers=headers,
        json={"paymentRequired": True, "operatorName": "reviewer"},
    )
    assert paid_mode.status_code == 200
    assert paid_mode.json()["data"]["paymentRequired"] is True


def test_customer_operations_panel_has_real_metrics_and_masks_contacts(client, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", "ops-secret")
    operations = client.get(
        "/api/ops-admin/customer-operations",
        headers={"X-Admin-Token": "ops-secret"},
    )
    assert operations.status_code == 200
    data = operations.json()["data"]
    assert data["payment"]["channel"] == "wechat_pay"
    assert "customerPhone" not in operations.text
    assert "customerWechat" not in operations.text
    assert set(data["today"]) >= {"views", "uniqueVisitors", "customerActions", "pendingFollowUps"}
    assert set(data["period"]) >= {
        "key",
        "days",
        "label",
        "views",
        "uniqueVisitors",
        "anonymousUniqueVisitors",
        "customerActions",
        "highIntentActions",
    }
    assert set(data["queues"]) >= {"subscriptionFailed", "archiveUnprocessed", "mediaAssetCount"}

    period_30d = client.get(
        "/api/ops-admin/customer-operations?period=30d",
        headers={"X-Admin-Token": "ops-secret"},
    )
    assert period_30d.status_code == 200
    assert period_30d.json()["data"]["period"]["key"] == "30d"


def test_customer_info_chain_database_failure_fails_closed_and_is_visible(tmp_path, monkeypatch):
    store = OpsConsoleStore(tmp_path / "ops-console-state.json", database_url="postgresql://unreachable.invalid/db")

    def fail_read():
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(store, "_get_postgres_customer_info_chain_config", fail_read)

    assert store.get_customer_info_chain_config() == {
        "enabled": False,
        "paymentRequired": True,
        "updatedAt": None,
        "updatedBy": None,
        "available": False,
    }


def test_legacy_customer_info_chain_flags_use_strict_boolean_coercion(tmp_path):
    path = tmp_path / "ops-console-state.json"
    path.write_text(
        json.dumps({
            "customerInfoChainEnabled": "false",
            "customerInfoChainPaymentRequired": "true",
        }),
        encoding="utf-8",
    )
    store = OpsConsoleStore(path)

    assert store._read_legacy_customer_info_chain_config()["enabled"] is False
    assert store._read_legacy_customer_info_chain_config()["paymentRequired"] is True
