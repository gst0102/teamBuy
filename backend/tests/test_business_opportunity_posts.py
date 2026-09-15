from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.api.dependencies import get_app_service


def login(client, *, nickname: str, openid: str, phone: str | None = None, wechat: str | None = None):
    return client.post(
        "/api/auth/mock-login",
        json={
            "nickname": nickname,
            "openid": openid,
            "phone": phone,
            "wechat": wechat,
        },
    ).json()["data"]


def test_business_opportunity_post_supports_manual_contact_and_one_point_unlock(client):
    owner = login(client, nickname="合作机会发布者", openid="openid_business_post_owner")
    viewer = login(client, nickname="合作机会查看者", openid="openid_business_post_viewer")

    created = client.post(
        "/api/supply-demand/cards",
        json={
            "userId": owner["id"],
            "cardType": "supply",
            "title": "招渠道合作｜云服务与 AI 技术支持",
            "summary": "提供云服务器、大模型和 AI 技术支持，欢迎渠道合作。",
            "contactSource": "manual",
            "contactType": "wechat",
            "contactValue": "cloud_support_wx",
            "expiresAt": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
            "status": "pending_review",
        },
    )
    assert created.status_code == 200
    card = created.json()["data"]
    assert card["status"] == "pending_review"
    assert "contactValueEncrypted" not in card
    assert card["contactLocked"] is True
    assert card["contactList"][0]["contactMasked"] == "cl***wx"

    service = client.app.dependency_overrides[get_app_service]()
    service.review_supply_demand_card(card["id"], "published", "通过")

    public = client.get(
        "/api/supply-demand/cards",
        params={"cardType": "supply", "limit": 10},
    )
    assert public.status_code == 200
    public_card = next(item for item in public.json()["data"]["items"] if item["id"] == card["id"])
    assert public_card["sourceLabel"] == "用户发布"
    assert public_card["contacts"] == []
    assert public_card["contactLocked"] is True

    detail = client.get(
        f"/api/supply-demand/cards/{card['id']}",
        params={"userId": viewer["id"]},
    )
    assert detail.status_code == 200
    assert detail.json()["data"]["contacts"] == []

    unlocked = client.post(
        f"/api/supply-demand/cards/{card['id']}/unlock-contact",
        json={"userId": viewer["id"]},
    )
    assert unlocked.status_code == 200
    assert unlocked.json()["data"]["charged"] is True
    assert unlocked.json()["data"]["card"]["contacts"][0]["contactValue"] == "cloud_support_wx"

    duplicate = client.post(
        f"/api/supply-demand/cards/{card['id']}/unlock-contact",
        json={"userId": viewer["id"]},
    )
    assert duplicate.status_code == 200
    assert duplicate.json()["data"]["duplicate"] is True
    assert duplicate.json()["data"]["wallet"]["balance"] == 99


def test_business_opportunity_post_uses_profile_contact_or_requires_manual_contact(client):
    profile_owner = login(
        client,
        nickname="名片联系方式用户",
        openid="openid_business_post_profile",
        phone="13800138000",
        wechat="profile_wx",
    )
    business_card = client.post(
        "/api/notes/manual-draft",
        json={"ownerUserId": profile_owner["id"], "cardType": "business_card", "inputMode": "blank"},
    )
    assert business_card.status_code == 200
    profile_card = client.post(
        "/api/supply-demand/cards",
        json={
            "userId": profile_owner["id"],
            "cardType": "demand",
            "title": "寻找技术合作伙伴",
            "summary": "正在寻找可以长期合作的技术团队。",
            "contactSource": "business_card",
            "status": "draft",
        },
    )
    assert profile_card.status_code == 200
    assert profile_card.json()["data"]["contactSource"] == "business_card"
    assert profile_card.json()["data"]["contactLocked"] is True
    assert profile_card.json()["data"]["contacts"] == []

    no_contact_owner = login(client, nickname="无联系方式用户", openid="openid_business_post_no_contact")
    rejected = client.post(
        "/api/supply-demand/cards",
        json={
            "userId": no_contact_owner["id"],
            "cardType": "supply",
            "title": "没有联系方式不能发布",
            "summary": "这条内容应该要求补充电话或微信。",
            "contactSource": "business_card",
            "status": "draft",
        },
    )
    assert rejected.status_code == 400
    assert rejected.json()["detail"] == "合作名片还没有电话或微信，请手动填写"


def test_business_opportunity_post_can_clear_existing_expiry_for_long_term(client):
    owner = login(client, nickname="长期合作用户", openid="openid_business_post_expiry")
    future = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
    created = client.post(
        "/api/supply-demand/cards",
        json={
            "userId": owner["id"],
            "cardType": "supply",
            "title": "长期合作机会",
            "summary": "长期有效的合作介绍。",
            "contactSource": "manual",
            "contactType": "wechat",
            "contactValue": "long_term_wx",
            "expiresAt": future,
            "status": "draft",
        },
    )
    assert created.status_code == 200
    card_id = created.json()["data"]["id"]

    updated = client.put(
        f"/api/supply-demand/cards/{card_id}",
        json={
            "userId": owner["id"],
            "cardType": "supply",
            "title": "长期合作机会",
            "summary": "长期有效的合作介绍。",
            "contactSource": "manual",
            "contactType": "wechat",
            "contactValue": "long_term_wx",
            "expiresAt": "",
            "status": "draft",
        },
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["expiresAt"] is None
