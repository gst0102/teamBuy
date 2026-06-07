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
    assert isinstance(payload["success"], bool)
    assert isinstance(payload["data"]["missing"], list)


def test_real_sync_is_guarded_while_mock_enabled(client):
    response = client.post("/api/wecom/real-sync")
    assert response.status_code == 400
    assert "WECOM_USE_MOCK=true" in response.json()["detail"]


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


def test_owner_can_delete_and_follow_relay(client):
    relay_response = client.post(
        "/api/cards/card_seed_001/relay",
        json={
            "userId": "user_seed_owner",
            "nickname": "张团长",
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
