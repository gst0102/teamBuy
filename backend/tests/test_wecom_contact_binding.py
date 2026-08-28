from __future__ import annotations

from urllib.parse import parse_qs, urlparse

from app.api.dependencies import get_app_service, get_wecom_client
from app.core.config import settings


def login(client, openid: str, nickname: str):
    return client.post("/api/auth/mock-login", json={"openid": openid, "nickname": nickname}).json()["data"]


class FakeWecomContactClient:
    def __init__(self):
        self.sent = []

    async def send_contact_welcome_mini_program(self, **kwargs):
        self.sent.append(kwargs)
        return {"errcode": 0, "errmsg": "ok"}


class FailingWecomContactClient(FakeWecomContactClient):
    async def send_contact_welcome_mini_program(self, **kwargs):
        self.sent.append(kwargs)
        raise RuntimeError("temporary welcome send failure")


def test_contact_add_event_sends_one_time_card_and_card_click_binds_user(client, monkeypatch):
    monkeypatch.setattr(settings, "wecom_use_mock", False)
    monkeypatch.setattr(settings, "wechat_miniapp_appid", "wx-test-miniapp")
    monkeypatch.setattr(settings, "wecom_bind_card_pic_media_id", "MEDIA_BIND_CARD")
    fake_client = FakeWecomContactClient()
    client.app.dependency_overrides[get_wecom_client] = lambda: fake_client

    owner = login(client, "openid_contact_binding_owner", "资料助手用户")
    event = {
        "Event": "change_external_contact",
        "ChangeType": "add_external_contact",
        "ExternalUserID": "wo_external_contact_001",
        "WelcomeCode": "welcome-code-001",
    }
    response = client.post("/api/wecom/kf/teamBuy/callback", json=event)

    assert response.status_code == 200
    assert response.json()["data"]["contact"]["status"] == "sent"
    assert len(fake_client.sent) == 1
    assert "资料整理助手" in fake_client.sent[0]["text_content"]
    assert "开启我的资料库" in fake_client.sent[0]["text_content"]
    card_page = fake_client.sent[0]["page"]
    token = parse_qs(urlparse(card_page).query)["token"][0]

    bound = client.post(
        "/api/auth/wecom-bind-card",
        headers={"Authorization": f"Bearer {owner['authToken']}"},
        json={"token": token, "userId": owner["id"]},
    )
    assert bound.status_code == 200
    assert bound.json()["data"]["status"] == "bound"

    repeated = client.post(
        "/api/auth/wecom-bind-card",
        headers={"Authorization": f"Bearer {owner['authToken']}"},
        json={"token": token, "userId": owner["id"]},
    )
    assert repeated.status_code == 200
    assert repeated.json()["data"]["status"] == "already_bound"

    service = client.app.dependency_overrides[get_app_service]()
    binding = service.repo.get_wecom_identity_binding("wecom_external_user", "wo_external_contact_001")
    assert binding is not None
    assert binding.ownerUserId == owner["id"]


def test_contact_callback_duplicate_welcome_code_does_not_send_a_second_card(client, monkeypatch):
    monkeypatch.setattr(settings, "wecom_use_mock", False)
    monkeypatch.setattr(settings, "wechat_miniapp_appid", "wx-test-miniapp")
    monkeypatch.setattr(settings, "wecom_bind_card_pic_media_id", "MEDIA_BIND_CARD")
    fake_client = FakeWecomContactClient()
    client.app.dependency_overrides[get_wecom_client] = lambda: fake_client
    event = {
        "Event": "change_external_contact",
        "ChangeType": "add_external_contact",
        "ExternalUserID": "wo_external_contact_duplicate",
        "WelcomeCode": "welcome-code-duplicate",
    }

    first = client.post("/api/wecom/kf/teamBuy/callback", json=event)
    second = client.post("/api/wecom/kf/teamBuy/callback", json=event)

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["data"]["contact"]["status"] == "already_issued"
    assert len(fake_client.sent) == 1


def test_failed_welcome_code_callback_is_not_retried_or_reissued(client, monkeypatch):
    monkeypatch.setattr(settings, "wecom_use_mock", False)
    monkeypatch.setattr(settings, "wechat_miniapp_appid", "wx-test-miniapp")
    monkeypatch.setattr(settings, "wecom_bind_card_pic_media_id", "MEDIA_BIND_CARD")
    fake_client = FailingWecomContactClient()
    client.app.dependency_overrides[get_wecom_client] = lambda: fake_client
    event = {
        "Event": "change_external_contact",
        "ChangeType": "add_external_contact",
        "ExternalUserID": "wo_external_contact_failed_once",
        "WelcomeCode": "welcome-code-failed-once",
    }

    first = client.post("/api/wecom/kf/teamBuy/callback", json=event)
    second = client.post("/api/wecom/kf/teamBuy/callback", json=event)

    assert first.status_code == 200
    assert first.json()["data"]["contact"]["status"] == "send_failed"
    assert second.status_code == 200
    assert second.json()["data"]["contact"]["status"] == "already_issued"
    assert len(fake_client.sent) == 1


def test_contact_card_cannot_be_used_by_a_second_user(client, monkeypatch):
    monkeypatch.setattr(settings, "wecom_use_mock", False)
    monkeypatch.setattr(settings, "wechat_miniapp_appid", "wx-test-miniapp")
    monkeypatch.setattr(settings, "wecom_bind_card_pic_media_id", "MEDIA_BIND_CARD")
    fake_client = FakeWecomContactClient()
    client.app.dependency_overrides[get_wecom_client] = lambda: fake_client
    first = login(client, "openid_contact_first", "第一个用户")
    second = login(client, "openid_contact_second", "第二个用户")
    event = {
        "Event": "change_external_contact",
        "ChangeType": "add_external_contact",
        "ExternalUserID": "wo_external_contact_single_use",
        "WelcomeCode": "welcome-code-single-use",
    }
    client.post("/api/wecom/kf/teamBuy/callback", json=event)
    token = parse_qs(urlparse(fake_client.sent[0]["page"]).query)["token"][0]

    accepted = client.post(
        "/api/auth/wecom-bind-card",
        headers={"Authorization": f"Bearer {first['authToken']}"},
        json={"token": token, "userId": first["id"]},
    )
    rejected = client.post(
        "/api/auth/wecom-bind-card",
        headers={"Authorization": f"Bearer {second['authToken']}"},
        json={"token": token, "userId": second["id"]},
    )

    assert accepted.status_code == 200
    assert rejected.status_code == 409


def test_production_never_uses_old_pending_intent_as_implicit_binding(client, monkeypatch):
    monkeypatch.setattr(settings, "app_env", "production")
    service = client.app.dependency_overrides[get_app_service]()
    user = login(client, "openid_contact_production_guard", "生产安全测试")
    service.create_wecom_bind_intent(user["id"])

    assert service._resolve_owner_user_id_for_external("wo_external_implicit_guard") == "unclaimed"
