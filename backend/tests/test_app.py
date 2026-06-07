from __future__ import annotations


def test_wecom_callback_get_verify(client):
    response = client.get(
        "/api/wecom/callback",
        params={"token": "teamBuy-dev-token", "echostr": "hello-teamBuy"},
    )
    assert response.status_code == 200
    assert response.json() == "hello-teamBuy"


def test_wecom_config_check_reports_missing_real_fields(client):
    response = client.get("/api/wecom/config-check")
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is False
    assert "WECOM_CORP_ID" in payload["data"]["missing"]


def test_real_sync_is_guarded_while_mock_enabled(client):
    response = client.post("/api/wecom/real-sync")
    assert response.status_code == 400
    assert "WECOM_USE_MOCK=true" in response.json()["detail"]


def test_health_reports_database_configuration(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["database"]["backend"] == "postgres"
    assert "DATABASE_URL" in data["database"]["missing"]


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


def test_anonymous_and_logged_in_view_stats_are_isolated(client):
    login = client.post("/api/auth/mock-login", json={"nickname": "浏览用户"}).json()["data"]
    card_id = "card_seed_001"

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
    assert any(item["nickname"] == "浏览用户" for item in owner_stats["loggedInViewers"])
    assert all(item["nickname"] != "匿名用户" for item in owner_stats["loggedInViewers"])


def test_relay_requires_phone_when_enabled(client):
    card_id = "card_seed_001"
    response = client.post(
        f"/api/cards/{card_id}/relay",
        json={"userId": "user_seed_owner", "nickname": "张团长"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "手机号为必填项"


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
