from __future__ import annotations


def test_api_and_health_responses_are_not_shared_by_http_caches(client):
    health = client.get("/health")
    assert health.headers["cache-control"] == "no-store, max-age=0"
    assert health.headers["pragma"] == "no-cache"

    response = client.post("/api/skills/route", json={"text": "整理笔记"})
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store, max-age=0"
    assert response.headers["pragma"] == "no-cache"
    assert "authorization" in response.headers["vary"].lower()


def test_publish_card_invalidates_the_server_card_list_cache(client):
    payload = {
        "ownerUserId": "user_seed_owner",
        "title": "缓存失效回归卡",
        "detailText": "用于验证发布后列表立即刷新。",
        "relayConfig": {"enabled": True, "requirePhone": False, "requireAddress": False},
    }
    created = client.post("/api/cards", json=payload)
    assert created.status_code == 200
    card_id = created.json()["data"]["id"]

    before = client.get("/api/cards", params={"ownerUserId": "user_seed_owner"})
    assert before.status_code == 200
    assert next(item for item in before.json()["data"] if item["id"] == card_id)["status"] == "draft"

    published = client.post(f"/api/cards/{card_id}/publish", json={"userId": "user_seed_owner"})
    assert published.status_code == 200

    after = client.get("/api/cards", params={"ownerUserId": "user_seed_owner"})
    assert after.status_code == 200
    assert next(item for item in after.json()["data"] if item["id"] == card_id)["status"] == "published"
