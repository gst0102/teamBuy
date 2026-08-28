from __future__ import annotations


def make_note(client, owner_id: str, card_type: str, raw_text: str):
    response = client.post(
        "/api/notes/manual-draft",
        json={
            "ownerUserId": owner_id,
            "cardType": card_type,
            "inputMode": "paste_text",
            "rawText": raw_text,
        },
    )
    assert response.status_code == 200
    return response.json()["data"]


def test_showcase_template_mapping_is_server_authoritative(client):
    owner = client.post("/api/auth/mock-login", json={"nickname": "场景映射用户"}).json()["data"]
    note = make_note(client, owner["id"], "property_listing", "小区：滨江花园\n租金：2800元/月\n户型：两房")
    created = client.post(
        "/api/showcases",
        json={
            "ownerUserId": owner["id"],
            "name": "房源合集",
            "sceneType": "property",
            "templateId": "brand_card",
            "items": [{"noteId": note["id"]}],
        },
    )
    assert created.status_code == 200
    payload = created.json()["data"]
    assert payload["sceneType"] == "property"
    assert payload["templateId"] == "featured_window"
    listed = client.get("/api/showcases", params={"ownerUserId": owner["id"]}).json()["data"][0]
    assert "brand_card" not in listed["allowedTemplateIds"]


def test_showcase_rejects_scene_mismatched_note(client):
    owner = client.post("/api/auth/mock-login", json={"nickname": "类型约束用户"}).json()["data"]
    note = make_note(client, owner["id"], "groupbuy_product", "商品：夏季风扇\n价格：99")
    response = client.post(
        "/api/showcases",
        json={
            "ownerUserId": owner["id"],
            "name": "错误类型合集",
            "sceneType": "property",
            "items": [{"noteId": note["id"]}],
        },
    )
    assert response.status_code == 400
    assert "类型不匹配" in response.json()["detail"]


def test_note_share_can_be_revoked_and_republished(client):
    owner = client.post("/api/auth/mock-login", json={"nickname": "分享状态用户"}).json()["data"]
    note = make_note(client, owner["id"], "text_note", "一份可以公开分享的资料")
    published = client.post(f"/api/notes/{note['id']}/publish", json={"ownerUserId": owner["id"]})
    assert published.status_code == 200
    revoked = client.post(f"/api/notes/{note['id']}/revoke", json={"ownerUserId": owner["id"]})
    assert revoked.status_code == 200
    assert revoked.json()["data"]["shareState"] == "revoked"
    assert client.get(f"/api/notes/public/{note['id']}").status_code == 404
    republished = client.post(f"/api/notes/{note['id']}/publish", json={"ownerUserId": owner["id"]})
    assert republished.status_code == 200
    assert republished.json()["data"]["shareState"] == "published"


def test_revoking_note_invalidates_published_showcase_snapshot(client):
    owner = client.post("/api/auth/mock-login", json={"nickname": "快照撤回用户"}).json()["data"]
    note = make_note(client, owner["id"], "text_note", "用于合集快照撤回")
    showcase = client.post(
        "/api/showcases",
        json={"ownerUserId": owner["id"], "name": "快照合集", "items": [{"noteId": note["id"]}]},
    ).json()["data"]
    assert client.post(f"/api/showcases/{showcase['id']}/publish", json={"ownerUserId": owner["id"]}).status_code == 200
    assert client.get(f"/api/showcases/public/{showcase['id']}").json()["data"]["items"]
    assert client.post(f"/api/notes/{note['id']}/revoke", json={"ownerUserId": owner["id"]}).status_code == 200
    assert client.get(f"/api/showcases/public/{showcase['id']}").json()["data"]["items"] == []
