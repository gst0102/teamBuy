from __future__ import annotations

from app.core.config import settings


def test_notes_pagination_keeps_legacy_and_page_shapes(client):
    owner = client.post(
        "/api/auth/mock-login",
        json={"nickname": "分页资料用户", "openid": "openid_core_list_pagination"},
    ).json()["data"]
    created = client.post("/api/notes/demo-data", params={"ownerUserId": owner["id"]})
    assert created.status_code == 200

    legacy = client.get("/api/notes", params={"ownerUserId": owner["id"]})
    page = client.get("/api/notes", params={"ownerUserId": owner["id"], "limit": 1, "offset": 0})

    assert legacy.status_code == 200
    assert isinstance(legacy.json()["data"], list)
    assert page.status_code == 200
    payload = page.json()["data"]
    assert isinstance(payload, dict)
    assert len(payload["items"]) <= 1
    assert payload["total"] >= len(payload["items"])
    assert payload["offset"] == 0


def test_paginated_opportunity_supply_and_order_endpoints_return_bounded_envelopes(client):
    user = client.post(
        "/api/auth/mock-login",
        json={"nickname": "分页列表用户", "openid": "openid_core_list_shapes"},
    ).json()["data"]

    opportunity = client.get("/api/opportunity-leads", params={"limit": 5, "cursor": "0"})
    saved = client.get("/api/opportunity-leads/saved", params={"userId": user["id"], "limit": 5, "cursor": "0"})
    supply = client.get("/api/supply-demand/cards", params={"limit": 5, "cursor": "0"})
    summary = client.get("/api/orders", params={"userId": user["id"], "role": "seller", "summaryOnly": True})

    assert opportunity.status_code == 200
    assert isinstance(opportunity.json()["data"], dict)
    assert saved.status_code == 200
    assert isinstance(saved.json()["data"], dict)
    assert supply.status_code == 200
    assert isinstance(supply.json()["data"], dict)
    assert summary.status_code == 200
    summary_payload = summary.json()["data"]
    assert summary_payload["orders"] == []
    assert summary_payload["summary"]["total"] == 0


def test_supply_demand_catalogue_is_public_in_production(client, monkeypatch):
    monkeypatch.setattr(settings, "app_env", "production")

    response = client.get("/api/supply-demand/cards", params={"limit": 5, "cursor": "0"})

    assert response.status_code == 200
    assert isinstance(response.json()["data"], dict)
