from __future__ import annotations

from app.api.dependencies import get_app_service, get_sync_task_queue, get_wecom_archive_client, get_wecom_client
from app.core.config import settings
from app.services.media_storage_service import MediaStorageService
from app.services.media_processing_service import MediaProcessingService
from app.models.domain import CustomerAction, LeadReminder, ShowcaseEvent, ShowcaseItem, ShowcasePage, UserNote, ViewEvent, WecomArchiveMessage, WecomIdentityBinding
from app.services.archive_message_parsers import ArchiveMessageParser, ArchiveMessageParserRegistry, ArchiveParseResult
from app.services.ocr_service import OcrResult, OcrService
from app.services.helpers import new_id
from app.services.time_utils import now_iso
from app.services.wecom_archive_worker import WecomArchiveWorker
from app.services.wecom_client import DownloadedMedia
from io import BytesIO
from PIL import Image
import asyncio
import json
from zipfile import ZipFile, ZIP_DEFLATED


class FakeSyncTask:
    def __init__(self):
        self.id = "sync_task_test"

    def model_dump(self):
        return {
            "id": self.id,
            "name": "wecom-callback-real-sync",
            "status": "queued",
            "createdAt": "2026-06-08T10:00:00+08:00",
            "updatedAt": "2026-06-08T10:00:00+08:00",
            "result": None,
            "errorMessage": None,
        }


class FakeSyncTaskQueue:
    def __init__(self):
        self.enqueued = []

    def register(self, name, handler):
        self.handler = (name, handler)

    def enqueue(self, name, payload=None, max_attempts=3):
        self.enqueued.append((name, payload, max_attempts))
        return FakeSyncTask()

    def list_recent(self):
        return [FakeSyncTask()]

    def list_logs(self, task_id=None):
        return []


def make_test_image_bytes() -> bytes:
    image = Image.new("RGB", (80, 60), (200, 60, 60))
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def run_test_background_queue(client, delay: float = 0.05) -> None:
    queue = client.app.dependency_overrides[get_sync_task_queue]()

    async def run():
        queue.start_pending()
        await asyncio.sleep(delay)

    asyncio.run(run())


def test_wechat_login_uses_openid_identity(client, monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"openid": "openid_real_user_a", "unionid": "union_a"}

    monkeypatch.setattr(settings, "wechat_miniapp_appid", "wx-test")
    monkeypatch.setattr(settings, "wechat_miniapp_secret", "secret-test")
    monkeypatch.setattr("app.services.app_service.httpx.get", lambda *args, **kwargs: FakeResponse())

    first = client.post("/api/auth/wechat-login", json={"code": "code-a", "nickname": "用户A"})
    second = client.post("/api/auth/wechat-login", json={"code": "code-b", "nickname": "用户A更新"})

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["data"]["id"] == second.json()["data"]["id"]
    assert second.json()["data"]["openid"] == "openid_real_user_a"
    assert second.json()["data"]["nickname"] == "用户A更新"


def test_mock_login_can_be_disabled(client, monkeypatch):
    monkeypatch.setattr(settings, "allow_mock_login", False)

    response = client.post("/api/auth/mock-login", json={"nickname": "演示用户", "openid": "openid_mock_disabled"})

    assert response.status_code == 403
    assert response.json()["detail"] == "测试登录已关闭"


def test_update_user_profile(client):
    user = client.post(
        "/api/auth/mock-login",
        json={
            "nickname": "旧昵称",
            "openid": "openid_profile_update",
            "avatarUrl": "https://example.com/avatar-default.png",
        },
    ).json()["data"]

    response = client.patch(
        f"/api/auth/users/{user['id']}/profile",
        json={
            "nickname": "新昵称🔥",
            "avatarUrl": "https://cdn.example.test/avatar.png",
            "phone": "15100001111",
        },
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["id"] == user["id"]
    assert data["nickname"] == "新昵称🔥"
    assert data["avatarUrl"] == "https://cdn.example.test/avatar.png"
    assert data["phone"] == "15100001111"


def test_update_user_profile_not_found(client):
    response = client.patch(
        "/api/auth/users/user_missing/profile",
        json={"nickname": "不存在"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "用户不存在"


def test_ops_admin_overview_requires_admin_token(client, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", "ops-secret")

    response = client.get("/api/ops-admin/overview")

    assert response.status_code == 403
    assert response.json()["detail"] == "admin token verification failed"


def test_resource_wallet_initializes_and_persists_by_user(client):
    user = client.post("/api/auth/mock-login", json={"nickname": "商机用户", "openid": "openid_wallet_owner"}).json()["data"]

    first = client.get("/api/resource-wallet/me", params={"ownerUserId": user["id"]})
    second = client.get("/api/resource-wallet/me", params={"ownerUserId": user["id"]})

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["data"]["wallet"]["balance"] == 100
    assert second.json()["data"]["wallet"]["balance"] == 100
    assert len(second.json()["data"]["recentLedgers"]) == 1
    assert second.json()["data"]["recentLedgers"][0]["ledgerType"] == "grant"


def test_ops_can_adjust_resource_wallet(client, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", "ops-secret")
    user = client.post("/api/auth/mock-login", json={"nickname": "调整用户", "openid": "openid_wallet_adjust"}).json()["data"]

    response = client.post(
        "/api/ops/resource-wallet/adjust",
        headers={"X-Admin-Token": "ops-secret"},
        json={"userId": user["id"], "pointsDelta": 30, "reason": "人工补发测试积分", "operatorId": "ops-a"},
    )

    assert response.status_code == 200
    assert response.json()["data"]["wallet"]["balance"] == 130
    ledger = response.json()["data"]["ledger"]
    assert ledger["ledgerType"] == "adjust"
    assert ledger["pointsDelta"] == 30


def test_resource_wallet_consume_is_idempotent_for_same_target(client):
    user = client.post("/api/auth/mock-login", json={"nickname": "扣费用户", "openid": "openid_wallet_consume"}).json()["data"]
    payload = {
        "ownerUserId": user["id"],
        "actionType": "contact_unlock",
        "targetType": "opportunity_lead",
        "targetId": "lead-a",
        "pointsCost": 20,
        "reason": "查看联系方式",
    }

    first = client.post("/api/resource-wallet/consume", json=payload)
    second = client.post("/api/resource-wallet/consume", json=payload)
    ledger = client.get("/api/resource-wallet/ledger", params={"ownerUserId": user["id"]}).json()["data"]

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["data"]["wallet"]["balance"] == 80
    assert first.json()["data"]["charged"] is True
    assert second.json()["data"]["wallet"]["balance"] == 80
    assert second.json()["data"]["duplicate"] is True
    assert [item["ledgerType"] for item in ledger].count("consume") == 1


def test_resource_wallet_uses_free_quota_before_points(client):
    user = client.post("/api/auth/mock-login", json={"nickname": "免费额度用户", "openid": "openid_wallet_quota"}).json()["data"]

    first = client.post(
        "/api/resource-wallet/consume",
        json={
            "ownerUserId": user["id"],
            "actionType": "response_package_generate",
            "targetType": "opportunity_lead",
            "targetId": "lead-free-1",
            "pointsCost": 15,
            "freeQuotaType": "response_package_daily",
            "freeQuotaLimit": 1,
            "periodKey": "2026-07-01",
        },
    )
    second = client.post(
        "/api/resource-wallet/consume",
        json={
            "ownerUserId": user["id"],
            "actionType": "response_package_generate",
            "targetType": "opportunity_lead",
            "targetId": "lead-free-2",
            "pointsCost": 15,
            "freeQuotaType": "response_package_daily",
            "freeQuotaLimit": 1,
            "periodKey": "2026-07-01",
        },
    )

    assert first.status_code == 200
    assert first.json()["data"]["usedFreeQuota"] is True
    assert first.json()["data"]["wallet"]["balance"] == 100
    assert second.status_code == 200
    assert second.json()["data"]["usedFreeQuota"] is False
    assert second.json()["data"]["wallet"]["balance"] == 85


def test_resource_wallet_isolated_between_users(client):
    user_a = client.post("/api/auth/mock-login", json={"nickname": "钱包A", "openid": "openid_wallet_a"}).json()["data"]
    user_b = client.post("/api/auth/mock-login", json={"nickname": "钱包B", "openid": "openid_wallet_b"}).json()["data"]

    client.post(
        "/api/resource-wallet/consume",
        json={
            "ownerUserId": user_a["id"],
            "actionType": "contact_unlock",
            "targetType": "opportunity_lead",
            "targetId": "lead-user-a",
            "pointsCost": 40,
        },
    )
    wallet_a = client.get("/api/resource-wallet/me", params={"ownerUserId": user_a["id"]}).json()["data"]["wallet"]
    wallet_b = client.get("/api/resource-wallet/me", params={"ownerUserId": user_b["id"]}).json()["data"]["wallet"]

    assert wallet_a["balance"] == 60
    assert wallet_b["balance"] == 100


def test_ops_can_create_and_publish_opportunity_lead(client, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", "ops-secret")

    response = client.post(
        "/api/ops/opportunity-leads",
        headers={"X-Admin-Token": "ops-secret"},
        json={
            "title": "长沙新店找开业地推合作",
            "summary": "餐饮新店需要本地推广渠道，预算明确。",
            "city": "长沙",
            "district": "开福区",
            "industry": "本地生活",
            "demandType": "找渠道",
            "content": "需要 7 天内启动，优先有社区群和地推队伍。",
            "tags": ["长沙", "地推", "餐饮"],
            "contactStatus": "available",
            "trustStatus": "verified",
            "status": "published",
            "source": {
                "sourcePlatform": "小红书",
                "sourceUrl": "https://example.com/source",
                "sourceAuthor": "测试博主",
                "rawText": "原始公开线索文本",
            },
            "contacts": [
                {"contactType": "phone", "contactValue": "13611747285", "verifyStatus": "verified"}
            ],
        },
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["title"] == "长沙新店找开业地推合作"
    assert data["status"] == "published"
    assert data["sources"][0]["sourcePlatform"] == "小红书"
    assert data["contacts"][0]["contactMasked"] == "136****7285"


def test_public_opportunity_leads_hide_source_and_contact_value(client, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", "ops-secret")
    created = client.post(
        "/api/ops/opportunity-leads",
        headers={"X-Admin-Token": "ops-secret"},
        json={
            "title": "上海房产渠道找合作",
            "summary": "需要能提供租房客源的合作方。",
            "city": "上海",
            "industry": "房产",
            "status": "published",
            "source": {"sourcePlatform": "微博", "rawText": "不要在前台展示具体来源"},
            "contacts": [{"contactType": "wechat", "contactValue": "agent_abc_123"}],
        },
    ).json()["data"]

    listing = client.get("/api/opportunity-leads")
    detail = client.get(f"/api/opportunity-leads/{created['id']}")

    assert listing.status_code == 200
    assert detail.status_code == 200
    public_text = json.dumps(detail.json()["data"], ensure_ascii=False)
    assert "微博" not in public_text
    assert "agent_abc_123" not in public_text
    assert "官方收录" in public_text
    assert listing.json()["data"][0]["sourceLabel"] == "官方收录"
    assert listing.json()["data"][0]["hasContact"] is True


def test_opportunity_lead_save_and_followup(client, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", "ops-secret")
    user = client.post("/api/auth/mock-login", json={"nickname": "商机跟进用户", "openid": "openid_opp_lead_user"}).json()["data"]
    lead = client.post(
        "/api/ops/opportunity-leads",
        headers={"X-Admin-Token": "ops-secret"},
        json={"title": "需要装修案例合作", "summary": "业主找装修方案", "city": "长沙", "industry": "装修", "status": "published"},
    ).json()["data"]

    saved = client.post(
        f"/api/opportunity-leads/{lead['id']}/save",
        json={"userId": user["id"], "status": "saved", "note": "适合发服务方案"},
    )
    followed = client.post(
        f"/api/opportunity-leads/{lead['id']}/followups",
        json={"userId": user["id"], "actionType": "contacted", "note": "已电话沟通"},
    )
    saved_list = client.get("/api/opportunity-leads/saved", params={"userId": user["id"]})

    assert saved.status_code == 200
    assert saved.json()["data"]["save"]["status"] == "saved"
    assert followed.status_code == 200
    assert followed.json()["data"]["save"]["status"] == "contacted"
    assert saved_list.status_code == 200
    assert saved_list.json()["data"][0]["save"]["status"] == "contacted"


def test_response_package_preview_and_create_uses_free_quota(client, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", "ops-secret")
    user = client.post("/api/auth/mock-login", json={"nickname": "回应包用户", "openid": "openid_resp_pkg_user"}).json()["data"]
    service = client.app.dependency_overrides[get_app_service]()
    now = now_iso()
    service.repo.save_user_note(
        UserNote(
            id="note_response_asset",
            ownerUserId=user["id"],
            status="active",
            title="长沙本地生活推广案例",
            summary="包含开业地推、社区群和商圈推广案例。",
            body="长沙本地生活商家开业推广服务介绍。",
            visibilityConfig={"cardType": "service_offer", "tags": ["长沙", "本地生活", "推广渠道"]},
            createdAt=now,
            updatedAt=now,
        )
    )
    lead = client.post(
        "/api/ops/opportunity-leads",
        headers={"X-Admin-Token": "ops-secret"},
        json={
            "title": "长沙新店找推广渠道",
            "summary": "开业前需要本地推广合作方。",
            "city": "长沙",
            "industry": "本地生活",
            "demandType": "找渠道",
            "tags": ["推广渠道"],
            "status": "published",
            "contacts": [{"contactType": "phone", "contactValue": "13611747285"}],
        },
    ).json()["data"]

    preview = client.post(
        f"/api/opportunity-leads/{lead['id']}/response-packages/preview",
        json={"userId": user["id"]},
    )
    created = client.post(
        f"/api/opportunity-leads/{lead['id']}/response-packages",
        json={"userId": user["id"]},
    )
    wallet = client.get("/api/resource-wallet/me", params={"ownerUserId": user["id"]})
    saved_list = client.get("/api/opportunity-leads/saved", params={"userId": user["id"]})

    assert preview.status_code == 200
    assert preview.json()["data"]["existingPackageId"] is None
    assert preview.json()["data"]["recommendedAssets"][0]["assetId"] == "note_response_asset"
    assert preview.json()["data"]["trackingUrl"] is None
    assert created.status_code == 200
    package = created.json()["data"]
    assert package["usedFreeQuota"] is True
    assert package["costPoints"] == 0
    assert package["items"][0]["assetTitle"] == "长沙本地生活推广案例"
    assert package["trackingUrl"].startswith("/pages/response-package/index?id=")
    assert wallet.json()["data"]["wallet"]["balance"] == 100
    assert saved_list.json()["data"][0]["save"]["status"] == "following"


def test_response_package_create_is_idempotent_and_private(client, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", "ops-secret")
    user = client.post("/api/auth/mock-login", json={"nickname": "回应包拥有者", "openid": "openid_resp_pkg_owner"}).json()["data"]
    other = client.post("/api/auth/mock-login", json={"nickname": "其他用户", "openid": "openid_resp_pkg_other"}).json()["data"]
    lead = client.post(
        "/api/ops/opportunity-leads",
        headers={"X-Admin-Token": "ops-secret"},
        json={"title": "上海品牌找渠道", "summary": "需要合作方", "city": "上海", "industry": "品牌", "status": "published"},
    ).json()["data"]

    first = client.post(f"/api/opportunity-leads/{lead['id']}/response-packages", json={"userId": user["id"]})
    second = client.post(f"/api/opportunity-leads/{lead['id']}/response-packages", json={"userId": user["id"]})
    package_id = first.json()["data"]["id"]
    denied = client.get(f"/api/response-packages/{package_id}", params={"ownerUserId": other["id"]})
    ledger = client.get("/api/resource-wallet/ledger", params={"ownerUserId": user["id"]}).json()["data"]

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["data"]["id"] == package_id
    assert denied.status_code == 403
    assert [item["actionType"] for item in ledger].count("response_package_generate") == 1


def test_response_package_event_updates_last_viewed(client, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", "ops-secret")
    user = client.post("/api/auth/mock-login", json={"nickname": "回应包事件用户", "openid": "openid_resp_pkg_event"}).json()["data"]
    lead = client.post(
        "/api/ops/opportunity-leads",
        headers={"X-Admin-Token": "ops-secret"},
        json={"title": "深圳客户找服务商", "summary": "需要服务商", "city": "深圳", "industry": "企业服务", "status": "published"},
    ).json()["data"]
    package = client.post(f"/api/opportunity-leads/{lead['id']}/response-packages", json={"userId": user["id"]}).json()["data"]

    event = client.post(
        f"/api/response-packages/{package['id']}/events",
        json={"eventType": "view", "viewerId": user["id"], "metadata": {"scene": "miniapp"}},
    )
    fetched = client.get(f"/api/response-packages/{package['id']}", params={"ownerUserId": user["id"]})

    assert event.status_code == 200
    assert event.json()["data"]["event"]["eventType"] == "view"
    assert event.json()["data"]["event"]["metadata"]["scene"] == "miniapp"
    assert fetched.json()["data"]["lastViewedAt"]


def test_ops_opportunity_dashboard_wallets_packages_and_offline(client, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", "ops-secret")
    user = client.post("/api/auth/mock-login", json={"nickname": "PC后台用户", "openid": "openid_ops_pc_user"}).json()["data"]
    lead = client.post(
        "/api/ops/opportunity-leads",
        headers={"X-Admin-Token": "ops-secret"},
        json={"title": "长沙商家找渠道", "summary": "需要推广渠道", "city": "长沙", "industry": "本地生活", "status": "published"},
    ).json()["data"]
    package = client.post(f"/api/opportunity-leads/{lead['id']}/response-packages", json={"userId": user["id"]}).json()["data"]

    dashboard = client.get("/api/ops/opportunity-dashboard", headers={"X-Admin-Token": "ops-secret"})
    wallets = client.get("/api/ops/resource-wallet/users", headers={"X-Admin-Token": "ops-secret"})
    packages = client.get("/api/ops/response-packages", headers={"X-Admin-Token": "ops-secret"})
    adjusted = client.post(
        f"/api/ops/resource-wallet/users/{user['id']}/adjust",
        headers={"X-Admin-Token": "ops-secret"},
        json={"userId": user["id"], "pointsDelta": 10, "reason": "PC 后台补发", "operatorId": "ops-pc"},
    )
    offlined = client.post(f"/api/ops/opportunity-leads/{lead['id']}/offline", headers={"X-Admin-Token": "ops-secret"})
    public_detail = client.get(f"/api/opportunity-leads/{lead['id']}")

    assert dashboard.status_code == 200
    assert dashboard.json()["data"]["summary"]["publishedLeads"] >= 1
    assert dashboard.json()["data"]["summary"]["todayResponsePackages"] >= 1
    assert wallets.status_code == 200
    assert any(item["userId"] == user["id"] for item in wallets.json()["data"]["items"])
    assert packages.status_code == 200
    assert packages.json()["data"]["items"][0]["id"] == package["id"]
    assert packages.json()["data"]["items"][0]["leadTitle"] == "长沙商家找渠道"
    assert adjusted.status_code == 200
    assert adjusted.json()["data"]["ledger"]["operatorId"] == "ops-pc"
    assert offlined.status_code == 200
    assert offlined.json()["data"]["status"] == "archived"
    assert public_detail.status_code == 404


def test_p1_subscription_unlock_supply_and_response_radar(client, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", "ops-secret")
    user = client.post("/api/auth/mock-login", json={"nickname": "P1用户", "openid": "openid_p1_user"}).json()["data"]
    service = client.app.dependency_overrides[get_app_service]()
    now = now_iso()
    service.repo.save_user_note(
        UserNote(
            id="note_p1_service_asset",
            ownerUserId=user["id"],
            status="active",
            title="长沙本地生活服务介绍",
            summary="推广渠道和案例介绍",
            body="长沙餐饮推广 本地生活 商圈渠道",
            visibilityConfig={"cardType": "service_offer", "tags": ["长沙", "推广渠道"]},
            createdAt=now,
            updatedAt=now,
        )
    )
    service.repo.save_user_note(
        UserNote(
            id="note_p1_case_asset",
            ownerUserId=user["id"],
            status="active",
            title="开业推广成功案例",
            summary="餐饮新店开业案例",
            body="餐饮 推广 案例",
            visibilityConfig={"cardType": "business_card", "tags": ["餐饮"]},
            createdAt=now,
            updatedAt=now,
        )
    )
    lead = client.post(
        "/api/ops/opportunity-leads",
        headers={"X-Admin-Token": "ops-secret"},
        json={
            "title": "长沙餐饮新店找推广渠道",
            "summary": "需要长沙本地生活渠道",
            "city": "长沙",
            "industry": "本地生活",
            "demandType": "找渠道",
            "status": "published",
            "contacts": [{"contactType": "phone", "contactValue": "13611747285", "verifyStatus": "verified"}],
        },
    ).json()["data"]

    sub = client.post(
        "/api/opportunity-subscriptions",
        json={
            "userId": user["id"],
            "direction": "两边都看",
            "lookingFor": "渠道",
            "providing": "本地服务",
            "city": "长沙",
            "contactRequirement": "有电话",
            "keywords": "餐饮 推广",
            "reminderCadence": "每天早上",
        },
    )
    matched = client.get("/api/opportunity-leads", params={"userId": user["id"], "city": "长沙", "contactStatus": "有联系方式"})
    unmatched = client.get("/api/opportunity-leads", params={"userId": user["id"], "city": "深圳"})
    unlock_first = client.post(f"/api/opportunity-leads/{lead['id']}/unlock-contact", json={"userId": user["id"]})
    unlock_second = client.post(f"/api/opportunity-leads/{lead['id']}/unlock-contact", json={"userId": user["id"]})
    saved_update = client.post(
        f"/api/opportunity-leads/{lead['id']}/save",
        json={"userId": user["id"], "status": "following", "note": "已约明天跟进", "reminderAt": "2026-07-02T10:00:00+08:00"},
    )
    saved_list = client.get(
        "/api/opportunity-leads/saved",
        params={"userId": user["id"], "status": "following", "packageStatus": "not_generated"},
    )
    preview = client.post(
        f"/api/opportunity-leads/{lead['id']}/response-packages/preview",
        json={"userId": user["id"], "selectedAssetIds": ["note_p1_case_asset"]},
    )
    package = client.post(
        f"/api/opportunity-leads/{lead['id']}/response-packages",
        json={"userId": user["id"], "selectedAssetIds": ["note_p1_case_asset"]},
    ).json()["data"]
    saved_after_package = client.get(
        "/api/opportunity-leads/saved",
        params={"userId": user["id"], "packageStatus": "generated"},
    )
    client.post(f"/api/response-packages/{package['id']}/events", json={"eventType": "view", "viewerId": user["id"]})
    radar = client.get(f"/api/response-packages/{package['id']}/radar", params={"ownerUserId": user["id"]})

    draft = client.post(
        "/api/supply-demand/cards",
        json={
            "userId": user["id"],
            "cardType": "supply",
            "title": "长沙地推团队可接开业推广",
            "summary": "社区和商圈地推资源",
            "city": "长沙",
            "industry": "本地生活",
            "demandType": "推广渠道",
            "status": "draft",
        },
    )
    submitted = client.post(f"/api/supply-demand/cards/{draft.json()['data']['id']}/submit", json={"userId": user["id"]})
    before_review = client.get("/api/supply-demand/cards")
    reviewed = client.post(
        f"/api/ops/supply-demand/cards/{draft.json()['data']['id']}/review",
        headers={"X-Admin-Token": "ops-secret"},
        json={"status": "published", "reviewNote": "通过"},
    )
    applicant = client.post("/api/auth/mock-login", json={"nickname": "申请人", "openid": "openid_p1_applicant", "phone": "13900000001"}).json()["data"]
    detail = client.get(f"/api/supply-demand/cards/{draft.json()['data']['id']}", params={"userId": applicant["id"]})
    application = client.post(
        f"/api/supply-demand/cards/{draft.json()['data']['id']}/applications",
        json={"userId": applicant["id"], "message": "我可以提供社区团长资源"},
    )
    owner_apps = client.get("/api/supply-demand/cards/applications", params={"userId": user["id"], "role": "owner"})
    applicant_apps = client.get("/api/supply-demand/cards/applications", params={"userId": applicant["id"], "role": "applicant"})
    app_review = client.post(
        f"/api/supply-demand/cards/applications/{application.json()['data']['application']['id']}/review",
        json={"userId": user["id"], "status": "accepted"},
    )
    edit_draft = client.post(
        "/api/supply-demand/cards",
        json={
            "userId": user["id"],
            "cardType": "demand",
            "title": "需要长沙社区团长资源",
            "summary": "用于编辑回填测试",
            "city": "长沙",
            "industry": "本地生活",
            "demandType": "找渠道",
            "status": "draft",
        },
    )
    edit_detail = client.get(f"/api/supply-demand/cards/{edit_draft.json()['data']['id']}", params={"userId": user["id"]})
    edit_saved = client.put(
        f"/api/supply-demand/cards/{edit_draft.json()['data']['id']}",
        json={
            "userId": user["id"],
            "cardType": "demand",
            "title": "需要长沙社区团长资源-已编辑",
            "summary": "编辑后内容",
            "city": "长沙",
            "industry": "本地生活",
            "demandType": "找渠道",
            "status": "draft",
        },
    )
    digest = client.post("/api/opportunity-push-digests/generate", json={"userId": user["id"]})
    ops_digest = client.post("/api/ops/opportunity-push-digests/generate", headers={"X-Admin-Token": "ops-secret"})
    digests = client.get("/api/opportunity-push-digests", params={"userId": user["id"]})
    digest_read = client.post(f"/api/opportunity-push-digests/{digest.json()['data']['id']}/read", json={"userId": user["id"]})
    after_review = client.get("/api/supply-demand/cards", params={"city": "长沙", "industry": "本地生活", "cardType": "supply"})
    filtered_out = client.get("/api/supply-demand/cards", params={"city": "深圳"})
    mine = client.get("/api/supply-demand/cards/me", params={"userId": user["id"]})

    assert sub.status_code == 200
    assert matched.status_code == 200
    assert matched.json()["data"]["subscription"]["city"] == "长沙"
    assert matched.json()["data"]["recommendationTitle"] == "今日推荐机会"
    assert matched.json()["data"]["items"][0]["id"] == lead["id"]
    assert unmatched.json()["data"]["items"] == []
    assert unlock_first.status_code == 200
    assert unlock_first.json()["data"]["contacts"][0]["contactValue"] == "13611747285"
    assert unlock_first.json()["data"]["charged"] is True
    assert unlock_second.json()["data"]["duplicate"] is True
    assert saved_update.json()["data"]["save"]["status"] == "following"
    assert saved_list.json()["data"][0]["save"]["reminderAt"] == "2026-07-02T10:00:00+08:00"
    assert saved_list.json()["data"][0]["packageStatus"] == "not_generated"
    assert preview.json()["data"]["selectedAssetIds"] == ["note_p1_case_asset"]
    assert preview.json()["data"]["recommendedAssets"][0]["assetId"] == "note_p1_case_asset"
    assert package["items"][0]["assetId"] == "note_p1_case_asset"
    assert saved_after_package.json()["data"][0]["packageStatus"] == "generated"
    assert radar.status_code == 200
    assert radar.json()["data"]["opened"] is True
    assert draft.status_code == 200
    assert submitted.json()["data"]["status"] == "pending_review"
    assert before_review.json()["data"] == []
    assert reviewed.json()["data"]["status"] == "published"
    assert detail.json()["data"]["id"] == draft.json()["data"]["id"]
    assert application.json()["data"]["application"]["status"] == "pending"
    assert owner_apps.json()["data"][0]["application"]["message"] == "我可以提供社区团长资源"
    assert applicant_apps.json()["data"][0]["card"]["title"] == "长沙地推团队可接开业推广"
    assert app_review.json()["data"]["application"]["status"] == "accepted"
    assert edit_detail.json()["data"]["isMine"] is True
    assert edit_detail.json()["data"]["title"] == "需要长沙社区团长资源"
    assert edit_saved.json()["data"]["title"] == "需要长沙社区团长资源-已编辑"
    assert digest.json()["data"]["title"] == "今日推荐机会"
    assert ops_digest.json()["data"]["total"] >= 1
    assert digest.json()["data"]["totalCount"] >= 1
    assert digest.json()["data"]["id"] in {item["id"] for item in digests.json()["data"]}
    assert digest_read.json()["data"]["status"] == "read"
    assert after_review.json()["data"][0]["title"] == "长沙地推团队可接开业推广"
    assert filtered_out.json()["data"] == []
    published_mine = next(item for item in mine.json()["data"] if item["id"] == draft.json()["data"]["id"])
    assert published_mine["status"] == "published"
    assert published_mine["applicationCount"] == 1


def test_ops_admin_overview_and_leaderboards(client, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", "ops-secret")
    owner = client.post("/api/auth/mock-login", json={"nickname": "运营用户", "openid": "openid_ops_owner"}).json()["data"]
    service = client.app.dependency_overrides[get_app_service]()
    now = now_iso()
    note = UserNote(
        id="note_ops_dashboard",
        ownerUserId=owner["id"],
        status="active",
        title="运营资料",
        summary="今日资料",
        body="资料正文",
        createdAt=now,
        updatedAt=now,
    )
    showcase = ShowcasePage(
        id="showcase_ops_dashboard",
        ownerUserId=owner["id"],
        status="published",
        name="运营合集",
        items=[ShowcaseItem(noteId=note.id, sortOrder=1)],
        publishedAt=now,
        createdAt=now,
        updatedAt=now,
    )
    action = CustomerAction(
        id="action_ops_dashboard",
        ownerUserId=owner["id"],
        noteId=note.id,
        actionKey="consult-click",
        actionLabel="咨询动作",
        createdAt=now,
        updatedAt=now,
    )
    showcase_event = ShowcaseEvent(
        id="showcase_event_ops_dashboard",
        showcaseId=showcase.id,
        ownerUserId=owner["id"],
        eventType="view",
        noteId=note.id,
        viewType="share",
        createdAt=now,
        dateKey=now[:10],
    )
    service.repo.save_user_note(note)
    service.repo.save_showcase_page(showcase)
    service.repo.save_customer_action(action)
    service.repo.add_showcase_event(showcase_event)

    headers = {"X-Admin-Token": "ops-secret"}
    overview = client.get("/api/ops-admin/overview", headers=headers)
    users = client.get("/api/ops-admin/user-leaderboard", headers=headers)
    content = client.get("/api/ops-admin/content-leaderboard", headers=headers)

    assert overview.status_code == 200
    overview_data = overview.json()["data"]
    assert overview_data["summary"]["todayNewUsers"] >= 1
    assert overview_data["summary"]["todayNewNotes"] >= 1
    assert overview_data["summary"]["todayNewShowcases"] >= 1
    assert overview_data["summary"]["todayCustomerActions"] >= 1
    assert overview_data["summary"]["todayShowcaseViews"] >= 1
    assert len(overview_data["trend7d"]) == 7

    assert users.status_code == 200
    user_rows = users.json()["data"]["items"]
    assert any(item["userId"] == owner["id"] and item["showcaseCount"] >= 1 for item in user_rows)

    assert content.status_code == 200
    content_data = content.json()["data"]
    assert any(item["showcaseId"] == showcase.id and item["openCount"] >= 1 for item in content_data["showcases"])
    assert any(item["noteId"] == note.id and item["actionCount"] >= 1 for item in content_data["notes"])


def test_ops_admin_group_upload_preview_and_save_batch(client, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", "ops-secret")
    headers = {"X-Admin-Token": "ops-secret"}
    raw_text = "\n".join(
        [
            "长沙租房群|长沙|岳麓区|房源|长租,中介|https://example.com/qr-1.png|2026-07-03|新增渠道",
            "字段不完整|长沙",
        ]
    )

    preview = client.post("/api/ops-admin/group-upload/preview", headers=headers, json={"rawText": raw_text})
    saved = client.post(
        "/api/ops-admin/group-upload/batches",
        headers=headers,
        json={"rawText": raw_text, "batchName": "首批群码", "operatorName": "运营A"},
    )
    listing = client.get("/api/ops-admin/group-upload/batches", headers=headers)

    assert preview.status_code == 200
    preview_data = preview.json()["data"]
    assert preview_data["summary"]["totalCount"] == 2
    assert preview_data["summary"]["successCount"] == 1
    assert preview_data["summary"]["failedCount"] == 1

    assert saved.status_code == 200
    saved_data = saved.json()["data"]
    assert saved_data["batchName"] == "首批群码"
    assert saved_data["successCount"] == 1

    assert listing.status_code == 200
    assert listing.json()["data"][0]["batchName"] == "首批群码"


def build_test_xlsx(rows):
    shared_strings = []
    shared_index = {}

    def sst_index(value):
        text = str(value)
        if text not in shared_index:
            shared_index[text] = len(shared_strings)
            shared_strings.append(text)
        return shared_index[text]

    def col_name(index):
        result = ""
        idx = index
        while idx > 0:
            idx, rem = divmod(idx - 1, 26)
            result = chr(65 + rem) + result
        return result

    sheet_rows = []
    for row_idx, row in enumerate(rows, start=1):
        cells = []
        for col_idx, value in enumerate(row, start=1):
            if value in (None, ""):
                continue
            cells.append(f'<c r="{col_name(col_idx)}{row_idx}" t="s"><v>{sst_index(value)}</v></c>')
        sheet_rows.append(f'<row r="{row_idx}">{"".join(cells)}</row>')

    shared_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="{len(shared_strings)}" uniqueCount="{len(shared_strings)}">'
        + "".join(f"<si><t>{value}</t></si>" for value in shared_strings)
        + "</sst>"
    )
    sheet_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
        + "".join(sheet_rows)
        + "</sheetData></worksheet>"
    )
    workbook_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets></workbook>'
    )
    workbook_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
        '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" Target="sharedStrings.xml"/>'
        '</Relationships>'
    )
    root_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        '</Relationships>'
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        '<Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>'
        '</Types>'
    )

    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", root_rels)
        zf.writestr("xl/workbook.xml", workbook_xml)
        zf.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        zf.writestr("xl/worksheets/sheet1.xml", sheet_xml)
        zf.writestr("xl/sharedStrings.xml", shared_xml)
    return output.getvalue()


def test_ops_admin_group_upload_preview_and_save_batch_by_xlsx(client, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", "ops-secret")
    headers = {"X-Admin-Token": "ops-secret"}
    content = build_test_xlsx([
        ["群名称", "城市", "区域", "类型", "标签", "二维码链接", "有效期", "备注"],
        ["长沙租房群", "长沙", "岳麓区", "房源", "长租,中介", "https://example.com/qr-1.png", "2026-07-03", "新增渠道"],
        ["字段不完整", "长沙", "", "房源", "", "", "", ""],
    ])

    preview = client.post(
        "/api/ops-admin/group-upload/preview-file",
        headers=headers,
        files={"file": ("groups.xlsx", content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    saved = client.post(
        "/api/ops-admin/group-upload/batches-file",
        headers=headers,
        data={"batchName": "Excel首批群码", "operatorName": "运营A"},
        files={"file": ("groups.xlsx", content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )

    assert preview.status_code == 200
    preview_data = preview.json()["data"]
    assert preview_data["summary"]["totalCount"] == 2
    assert preview_data["summary"]["successCount"] == 1
    assert preview_data["summary"]["failedCount"] == 1

    assert saved.status_code == 200
    assert saved.json()["data"]["batchName"] == "Excel首批群码"


def test_ops_admin_group_upload_template_downloads(client, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", "ops-secret")
    headers = {"X-Admin-Token": "ops-secret"}

    csv_response = client.get("/api/ops-admin/group-upload/template.csv", headers=headers)
    xlsx_response = client.get("/api/ops-admin/group-upload/template.xlsx", headers=headers)

    assert csv_response.status_code == 200
    assert "群名称" in csv_response.content.decode("utf-8-sig")
    assert csv_response.headers["content-type"].startswith("text/csv")

    assert xlsx_response.status_code == 200
    assert xlsx_response.headers["content-type"].startswith("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    assert len(xlsx_response.content) > 100


def test_ops_admin_single_group_resource_flow(client, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", "ops-secret")
    headers = {"X-Admin-Token": "ops-secret"}
    created = client.post(
        "/api/ops-admin/group-resources",
        headers=headers,
        json={
            "name": "长沙租房群",
            "cityMode": "city",
            "cityLabel": "长沙市 岳麓区",
            "region": [],
            "groupType": "房源",
            "purposes": ["找同行", "找客户"],
            "memberRange": "100-300",
            "activeLevel": "高",
            "expiresInDays": 5,
            "remark": "需验证名片",
            "customTags": ["金融", "爱好者"],
            "qrImageData": "data:image/png;base64,abc123",
            "operatorName": "运营A",
        },
    )
    listing = client.get("/api/ops-admin/group-resources", headers=headers)

    assert created.status_code == 200
    created_data = created.json()["data"]
    assert created_data["name"] == "长沙租房群"
    assert created_data["groupType"] == "房源"
    assert created_data["qrStatus"] == "uploaded"
    assert created_data["purposes"] == ["找同行", "找客户"]

    assert listing.status_code == 200
    assert listing.json()["data"][0]["name"] == "长沙租房群"


def test_ops_admin_wecom_group_join_way_requires_admin_token(client, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", "ops-secret")

    response = client.get("/api/ops-admin/wecom-group-join-ways")

    assert response.status_code == 403
    assert response.json()["detail"] == "admin token verification failed"


def test_ops_admin_wecom_group_join_way_dry_run(client, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", "ops-secret")

    response = client.post(
        "/api/ops-admin/wecom-group-join-ways",
        headers={"X-Admin-Token": "ops-secret"},
        json={
            "remark": "资料助手资源测试群",
            "chatIdList": ["wr_chat_001"],
            "roomBaseName": "资料助手资源测试群",
            "roomBaseId": 1,
            "state": "teambuy_resource_test",
            "dryRun": True,
        },
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["dryRun"] is True
    assert data["request"]["scene"] == 2
    assert data["request"]["chatIdList"] == ["wr_chat_001"]


def test_ops_admin_wecom_customer_groups_normalizes_list(client, monkeypatch):
    class FakeWecomClient:
        async def list_customer_groups(self, **kwargs):
            assert kwargs["status_filter"] == 0
            assert kwargs["limit"] == 100
            return {
                "errcode": 0,
                "errmsg": "ok",
                "group_chat_list": [
                    {
                        "chat_id": "wr_chat_001",
                        "name": "资料助手资源测试群",
                        "owner": "zhangsan",
                        "status": 0,
                        "create_time": 1710000000,
                    }
                ],
                "next_cursor": "",
            }

    monkeypatch.setattr(settings, "admin_token", "ops-secret")
    client.app.dependency_overrides[get_wecom_client] = lambda: FakeWecomClient()

    response = client.get("/api/ops-admin/wecom-customer-groups", headers={"X-Admin-Token": "ops-secret"})

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["items"] == [{
        "chatId": "wr_chat_001",
        "name": "资料助手资源测试群",
        "owner": "zhangsan",
        "status": 0,
        "createTime": 1710000000,
    }]
    assert data["nextCursor"] == ""


def test_ops_admin_wecom_group_join_way_create_saves_config(client, monkeypatch):
    class FakeWecomClient:
        def __init__(self):
            self.calls = []

        async def create_group_join_way(self, **kwargs):
            self.calls.append(kwargs)
            return {"errcode": 0, "errmsg": "ok", "config_id": "config_join_way_001"}

    fake_client = FakeWecomClient()
    monkeypatch.setattr(settings, "admin_token", "ops-secret")
    client.app.dependency_overrides[get_wecom_client] = lambda: fake_client

    response = client.post(
        "/api/ops-admin/wecom-group-join-ways",
        headers={"X-Admin-Token": "ops-secret"},
        json={
            "remark": "资料助手资源测试群",
            "chatIdList": ["wr_chat_001", "wr_chat_002"],
            "roomBaseName": "资料助手资源测试群",
            "roomBaseId": 3,
            "autoCreateRoom": 1,
            "state": "teambuy_resource_test",
            "operatorName": "依依",
            "dryRun": False,
        },
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["configId"] == "config_join_way_001"
    assert data["chatIdList"] == ["wr_chat_001", "wr_chat_002"]
    assert fake_client.calls[0]["scene"] == 2
    assert fake_client.calls[0]["room_base_id"] == 3

    listing = client.get("/api/ops-admin/wecom-group-join-ways", headers={"X-Admin-Token": "ops-secret"})
    assert listing.status_code == 200
    assert listing.json()["data"][0]["configId"] == "config_join_way_001"


def test_ops_admin_feedback_ticket_flow(client, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", "ops-secret")
    headers = {"X-Admin-Token": "ops-secret"}

    created = client.post(
        "/api/ops-admin/feedback",
        headers=headers,
        json={
            "type": "suggestion",
            "userId": "user_feedback_a",
            "userNickname": "建议用户",
            "contact": "wechat_abc",
            "content": "建议增加日报导出",
        },
    )
    ticket_id = created.json()["data"]["id"]
    updated = client.patch(
        f"/api/ops-admin/feedback/{ticket_id}",
        headers=headers,
        json={
            "status": "accepted",
            "replyText": "已记录进排期",
            "rewardNote": "采纳奖励 +300",
            "operatorName": "运营B",
        },
    )
    listing = client.get("/api/ops-admin/feedback", headers=headers)

    assert created.status_code == 200
    assert updated.status_code == 200
    updated_data = updated.json()["data"]
    assert updated_data["status"] == "accepted"
    assert updated_data["replyText"] == "已记录进排期"
    assert updated_data["rewardNote"] == "采纳奖励 +300"

    assert listing.status_code == 200
    assert listing.json()["data"][0]["id"] == ticket_id


def test_process_and_store_media_reuses_same_image_asset(client):
    service = client.app.dependency_overrides[get_app_service]()
    content = make_test_image_bytes()

    first_url = service.process_and_store_media(
        media_id="media_same_a",
        media_type="image",
        content=content,
        content_type="image/png",
        filename="room.png",
        owner_user_id="user-a",
        ref_type="note",
        ref_id="note-a",
    )
    second_url = service.process_and_store_media(
        media_id="media_same_b",
        media_type="image",
        content=content,
        content_type="image/png",
        filename="room-copy.png",
        owner_user_id="user-b",
        ref_type="note",
        ref_id="note-b",
    )

    state = service.repo.load()
    assert second_url == first_url
    assert len(state.media_assets) == 1
    assert state.media_assets[0].mediaType == "image"
    assert state.media_assets[0].contentType == "image/webp"
    assert len(state.media_asset_refs) == 2


def test_property_same_clone_note_creates_b_owned_note_with_replaced_contact(client):
    source_owner = client.post("/api/auth/mock-login", json={"nickname": "A中介", "openid": "openid_clone_source"}).json()["data"]
    target_owner = client.post(
        "/api/auth/mock-login",
        json={"nickname": "B中介", "openid": "openid_clone_target", "phone": "13900001111"},
    ).json()["data"]
    service = client.app.dependency_overrides[get_app_service]()
    now = now_iso()
    source_note = UserNote(
        id="note_public_source_clone",
        ownerUserId=source_owner["id"],
        status="active",
        title="龙悦和府 两房",
        summary="近地铁，可带看",
        body="龙悦和府 88平 两房，家电齐全。",
        coverUrl="/media/source-room.webp",
        media=[{"type": "image", "url": "/media/source-room.webp", "title": "客厅"}],
        phone="13800000000",
        locationText="龙悦和府",
        visibilityConfig={
            "cardType": "property_listing",
            "cardState": "editing",
            "structuredData": {
                "community": "龙悦和府",
                "layout": "两房",
                "price": "88万",
                "phone": "13800000000",
                "contactWechat": "agent-a",
                "landlordPhone": "13700000000",
            },
            "privateData": {"upstreamContact": "真实房东13700000000"},
        },
        createdAt=now,
        updatedAt=now,
    )
    service.repo.save_user_note(source_note)

    response = client.post(
        "/api/notes/property-same/clone",
        json={
            "ownerUserId": target_owner["id"],
            "sourceType": "note",
            "sourceId": source_note.id,
            "phone": "13900002222",
            "wechat": "agent-b",
        },
    )

    assert response.status_code == 200
    data = response.json()["data"]
    cloned = data["note"]
    structured = cloned["visibilityConfig"]["structuredData"]
    private_data = cloned["visibilityConfig"]["privateData"]
    assert data["type"] == "note"
    assert cloned["ownerUserId"] == target_owner["id"]
    assert cloned["id"] != source_note.id
    assert cloned["phone"] == "13900002222"
    assert structured["community"] == "龙悦和府"
    assert structured["phone"] == "13900002222"
    assert structured["wechat"] == "agent-b"
    assert "landlordPhone" not in structured
    assert private_data["upstreamContact"] in {"13800000000", "agent-a", "A中介"}
    assert private_data["upstreamContact"] != "真实房东13700000000"
    assert cloned["media"][0]["url"] == "/media/source-room.webp"
    source_actions = client.get(
        f"/api/notes/{source_note.id}/customer-actions",
        params={"ownerUserId": source_owner["id"]},
    ).json()["data"]
    assert source_actions["summary"]["leads"] == 0
    clone_action = next(item for item in source_actions["actions"] if item["actionLabel"] == "生成同款")
    assert clone_action["visitorIdentityType"] == "peer_agent"
    assert clone_action["visitorIdentityLabel"] == "疑似中介"
    dashboard = client.get(
        "/api/dashboard/business",
        params={"ownerUserId": source_owner["id"], "requesterUserId": source_owner["id"], "mode": "property"},
    ).json()["data"]
    peer_profile = next(item for item in dashboard["visitorProfiles"] if item.get("viewerUserId") == target_owner["id"])
    assert peer_profile["visitorIdentityType"] == "peer_agent"
    assert dashboard["summary"]["pendingLeadCount"] == 0


def test_property_same_clone_showcase_creates_b_owned_showcase_and_notes(client):
    source_owner = client.post("/api/auth/mock-login", json={"nickname": "A合集", "openid": "openid_showcase_source"}).json()["data"]
    target_owner = client.post("/api/auth/mock-login", json={"nickname": "B合集", "openid": "openid_showcase_target"}).json()["data"]
    service = client.app.dependency_overrides[get_app_service]()
    now = now_iso()
    source_note = UserNote(
        id="note_showcase_source_clone",
        ownerUserId=source_owner["id"],
        status="active",
        title="毛坯一房",
        summary="低总价",
        body="毛坯一房，方便带看。",
        coverUrl="/media/showcase-room.webp",
        media=[{"type": "image", "url": "/media/showcase-room.webp"}],
        phone="13800003333",
        locationText="加州郡府",
        visibilityConfig={
            "cardType": "property_listing",
            "structuredData": {"community": "加州郡府", "layout": "一房", "price": "88万", "wechat": "agent-a"},
        },
        createdAt=now,
        updatedAt=now,
    )
    service.repo.save_user_note(source_note)
    source_showcase = ShowcasePage(
        id="showcase_public_source_clone",
        ownerUserId=source_owner["id"],
        status="published",
        name="本周精选房源",
        description="适合同行对盘",
        bannerUrl="/media/banner.webp",
        templateId="featured_window",
        shareTitle="本周精选房源",
        contactConfig={"phone": "13800003333", "wechat": "agent-a"},
        displayConfig={"layoutMode": "grid", "filters": ["全部", "一房"]},
        items=[ShowcaseItem(noteId=source_note.id, sortOrder=0, displayTitle="毛坯一房")],
        publicSnapshot={},
        snapshotVersion=0,
        snapshotCreatedAt=None,
        publishedAt=now,
        createdAt=now,
        updatedAt=now,
    )
    service.repo.save_showcase_page(source_showcase)

    response = client.post(
        "/api/notes/property-same/clone",
        json={
            "ownerUserId": target_owner["id"],
            "sourceType": "showcase",
            "sourceId": source_showcase.id,
            "phone": "13900004444",
            "wechat": "agent-b",
        },
    )

    assert response.status_code == 200
    data = response.json()["data"]
    showcase = data["showcase"]
    assert data["type"] == "showcase"
    assert showcase["ownerUserId"] == target_owner["id"]
    assert showcase["id"] != source_showcase.id
    assert showcase["status"] == "draft"
    assert showcase["contactConfig"]["phone"] == "13900004444"
    assert showcase["contactConfig"]["wechat"] == "agent-b"
    assert showcase["displayConfig"]["layoutMode"] == "grid"
    assert showcase["items"][0]["noteId"] != source_note.id
    cloned_note = service.repo.get_user_note(showcase["items"][0]["noteId"])
    assert cloned_note is not None
    assert cloned_note.ownerUserId == target_owner["id"]
    assert cloned_note.phone == "13900004444"


def test_update_user_profile_rejects_temporary_avatar_path(client):
    user = client.post(
        "/api/auth/mock-login",
        json={"nickname": "头像用户", "openid": "openid_profile_temp_avatar"},
    ).json()["data"]

    response = client.patch(
        f"/api/auth/users/{user['id']}/profile",
        json={"avatarUrl": "wxfile://tmp_avatar.jpg"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "头像地址必须是可访问的 HTTPS 地址"


def test_update_user_profile_rejects_http_avatar_url(client):
    user = client.post(
        "/api/auth/mock-login",
        json={"nickname": "头像用户B", "openid": "openid_profile_http_avatar"},
    ).json()["data"]

    response = client.patch(
        f"/api/auth/users/{user['id']}/profile",
        json={"avatarUrl": "http://cdn.example.test/avatar.png"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "头像地址必须是可访问的 HTTPS 地址"


def test_create_note_demo_data_for_owner(client):
    user = client.post("/api/auth/mock-login", json={"nickname": "演示用户", "openid": "openid_demo_owner"}).json()["data"]

    response = client.post("/api/notes/demo-data", params={"ownerUserId": user["id"]})

    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data["notes"]) == 4
    assert data["leadsCreated"] == 2
    assert data["actionsCreated"] == 4
    assert data["showcasesCreated"] == 1
    assert data["showcaseEventsCreated"] == 5
    notes = client.get("/api/notes", params={"ownerUserId": user["id"]}).json()["data"]
    assert len(notes) == 4
    assert all(item["ownerUserId"] == user["id"] for item in notes)
    assert any(item["visibilityConfig"]["cardType"] == "groupbuy_product" for item in data["notes"])
    action_note = next(item for item in data["notes"] if "测试房源A" in item["title"])
    action_rows = client.get(
        f"/api/notes/{action_note['id']}/customer-actions",
        params={"ownerUserId": user["id"]},
    ).json()["data"]
    assert action_rows["summary"]["total"] == 2
    assert action_rows["summary"]["leadContact"] == 1
    assert action_rows["summary"]["appointment"] == 1
    assert action_rows["summary"]["pending"] == 1
    dashboard = client.get(
        "/api/dashboard/business",
        params={"ownerUserId": user["id"], "requesterUserId": user["id"]},
    )
    assert dashboard.status_code == 200
    dashboard_data = dashboard.json()["data"]
    assert dashboard_data["summary"]["showcaseOpenCount"] == 2
    assert dashboard_data["summary"]["noteClickCount"] == 1
    assert dashboard_data["summary"]["consultCount"] == 2
    assert dashboard_data["topNotes"][0]["noteId"] == action_note["id"]
    assert any(action_note["id"] in item.get("noteIds", []) for item in dashboard_data["visitorProfiles"])

    service = client.app.dependency_overrides[get_app_service]()
    now = now_iso()
    real_note = UserNote(
        id=new_id("note"),
        ownerUserId=user["id"],
        status="active",
        title="真实客户资料",
        summary="不带演示标记，清理测试数据时必须保留",
        body="这是一条真实资料。",
        visibilityConfig={"cardType": "text_note", "tags": ["真实资料"]},
        createdAt=now,
        updatedAt=now,
    )
    service.repo.save_user_note(real_note)
    real_showcase = ShowcasePage(
        id=new_id("showcase"),
        ownerUserId=user["id"],
        status="published",
        name="真实展示页",
        description="不带演示标记，清理测试数据时必须保留",
        items=[ShowcaseItem(noteId=real_note.id)],
        publishedAt=now,
        createdAt=now,
        updatedAt=now,
    )
    service.repo.save_showcase_page(real_showcase)

    cleanup = client.post("/api/notes/demo-data/cleanup", params={"ownerUserId": user["id"]})
    assert cleanup.status_code == 200
    deleted = cleanup.json()["data"]["deleted"]
    assert deleted["notes"] == 4
    assert deleted["showcases"] == 1
    assert deleted["showcaseEvents"] == 5
    assert deleted["leads"] == 2
    assert deleted["actions"] == 4
    cleaned_dashboard = client.get(
        "/api/dashboard/business",
        params={"ownerUserId": user["id"], "requesterUserId": user["id"]},
    ).json()["data"]
    assert cleaned_dashboard["summary"]["showcaseOpenCount"] == 0
    assert cleaned_dashboard["summary"]["noteClickCount"] == 0
    assert cleaned_dashboard["summary"]["consultCount"] == 0
    remaining_notes = client.get("/api/notes", params={"ownerUserId": user["id"]}).json()["data"]
    remaining_showcases = client.get("/api/showcases", params={"ownerUserId": user["id"]}).json()["data"]
    assert [item["id"] for item in remaining_notes] == [real_note.id]
    assert [item["id"] for item in remaining_showcases] == [real_showcase.id]


def test_manual_note_draft_creates_property_from_pasted_text(client):
    owner = client.post("/api/auth/mock-login", json={"nickname": "手动房源用户", "openid": "openid_manual_property"}).json()["data"]
    raw_text = "\n".join(
        [
            "小区：滨江花园",
            "户型：两房一厅",
            "面积：89平",
            "租金：5800元/月",
            "地址：浦东新区花木路",
            "电话：13800138000",
        ]
    )

    response = client.post(
        "/api/notes/manual-draft",
        json={
            "ownerUserId": owner["id"],
            "cardType": "property_listing",
            "inputMode": "paste_text",
            "rawText": raw_text,
        },
    )

    assert response.status_code == 200
    note = response.json()["data"]
    config = note["visibilityConfig"]
    structured = config["structuredData"]
    assert config["cardType"] == "property_listing"
    assert config["sourceType"] == "manual_text"
    assert "房源" in config["tags"]
    assert config["conversionConfig"]["enableAppointment"] is True
    assert structured["community"] == "滨江花园"
    assert structured["rawText"] == raw_text

    cards = client.get("/api/cards", params={"ownerUserId": owner["id"]}).json()["data"]
    property_card = next(item for item in cards if item.get("sourceNoteId") == note["id"])
    assert property_card["id"] == f"note_card_{note['id']}"
    assert property_card["cardType"] == "property_listing"
    assert property_card["categoryName"] == "房源"


def test_property_batch_parse_and_create_keeps_upstream_private(client):
    owner = client.post("/api/auth/mock-login", json={"nickname": "批量房源用户", "openid": "openid_property_batch"}).json()["data"]
    raw_text = "\n".join(
        [
            "挂牌: 中介费50%，全部密码锁，看房给我打电话",
            "1，樟盛苑16号201新装一室户燃气洗澡做饭，卫生间带窗户，干湿分离，",
            "主卧独卫B室 4280，",
            "北一房D室 3480，",
            "☎️ 18501775740 ☎️ 15900904520",
            "2，樟盛苑15号1601新装一室户燃气洗澡做饭，",
            "C北一房4180",
            "⚠️带小孩，孕妇，老人，不租，🈲️养宠物",
            "🉑️办居住证🉑️落户🉑️办停车位🉑️开发票",
            "微信➕18501775740朋友圈里都有照片和视频 中介费%50租高有红包",
            "🎉🎉玉兰四期6号602北次阁楼1500已空",
            "看房电话☎️13818539676➕微信有视频 13916193590v",
        ]
    )

    parsed_res = client.post(
        "/api/notes/property-batch/parse",
        json={"ownerUserId": owner["id"], "rawText": raw_text},
    )

    assert parsed_res.status_code == 200
    parsed = parsed_res.json()["data"]
    assert parsed["detectedCount"] == 4
    titles = [item["title"] for item in parsed["candidates"]]
    assert "樟盛苑16号201 · 主卧独卫B室" in titles
    assert "樟盛苑16号201 · 北一房D室" in titles
    assert "樟盛苑15号1601 · C北一房" in titles
    assert "玉兰四期6号602 · 北次阁楼" in titles
    first = parsed["candidates"][0]
    assert "禁宠" in first["publicTags"]
    assert "可办居住证" in first["publicTags"]
    assert any("上游电话" in item for item in first["privateTags"])
    assert "中介费50%" in first["privateTags"]
    assert first["privateData"]["upstreamPhones"] == ["18501775740", "15900904520", "13818539676", "13916193590"]

    create_res = client.post(
        "/api/notes/property-batch/create",
        json={"ownerUserId": owner["id"], "rawText": raw_text, "candidates": parsed["candidates"]},
    )

    assert create_res.status_code == 200
    created = create_res.json()["data"]
    assert created["createdCount"] == 4
    assert created["showcaseId"]
    showcase = client.get(
        f"/api/showcases/{created['showcaseId']}",
        params={"ownerUserId": owner["id"]},
    ).json()["data"]
    assert showcase["templateId"] == "property_batch_collection"
    assert showcase["name"].endswith("房源合集 4套")
    assert len(showcase["items"]) == 4
    assert {item["noteId"] for item in showcase["items"]} == set(created["noteIds"])
    filters = showcase["displayConfig"]["propertyFilters"]
    assert {item["key"] for item in filters} >= {"area", "layout", "price"}
    price_filter = next(item for item in filters if item["key"] == "price")
    assert any(option["value"] == "3000以上" for option in price_filter["options"])
    note = created["notes"][0]
    config = note["visibilityConfig"]
    structured = config["structuredData"]
    assert config["cardType"] == "property_listing"
    assert config["sourceType"] == "property_batch_text"
    assert "禁宠" in config["tags"]
    assert "contactPhone" not in structured
    assert "wechat" not in structured
    assert config["privateData"]["commission"] == "中介费50%"
    assert "18501775740" in config["privateData"]["upstreamPhones"]
    assert note["phone"] is None


def test_property_batch_parse_numbered_rental_list_with_contacts(client):
    owner = client.post("/api/auth/mock-login", json={"nickname": "挂牌清单用户", "openid": "openid_property_batch_numbered"}).json()["data"]
    raw_text = "\n".join(
        [
            "挂牌",
            "1）松涛路200弄朝南次卧3000",
            "2）松涛路200弄50号301次卧3100",
            "3）汤臣四期次卧一室户3100",
            "4)玉兰4期122号1401次卧2500",
            "5)万科500号410一室户3500",
            "6）申源苑4号701主卧3380",
            "汤臣四期大厅一室户3700",
            "电话15201882219。",
        ]
    )

    parsed_res = client.post(
        "/api/notes/property-batch/parse",
        json={"ownerUserId": owner["id"], "rawText": raw_text},
    )

    assert parsed_res.status_code == 200
    parsed = parsed_res.json()["data"]
    assert parsed["detectedCount"] == 7
    titles = [item["title"] for item in parsed["candidates"]]
    assert "松涛路200弄 · 朝南次卧" in titles
    assert "松涛路200弄50号301 · 次卧" in titles
    assert "汤臣四期 · 次卧" in titles
    assert "玉兰4期122号1401 · 次卧" in titles
    assert "万科500号410 · 一室户" in titles
    assert "申源苑4号701 · 主卧" in titles
    assert "汤臣四期 · 大厅一室户" in titles
    assert parsed["privacySummary"]["upstreamPhones"] == ["15201882219"]


def test_property_batch_parse_table_style_apartment_list_with_keycap_digits(client):
    owner = client.post("/api/auth/mock-login", json={"nickname": "表格式房源用户", "openid": "openid_property_batch_table"}).json()["data"]
    raw_text = "\n".join(
        [
            "湘聚公寓最新房源表🉐🉐所有房源降价直租",
            "㊗️㊗️㊗️还价就租",
            "佣金原价年签80%，还价佣金70%",
            "",
            "新时代广场，富兴时代地铁6号线，湘雅附一，华创国际，开福寺地铁口",
            "1925南栋",
            "2号房一1️⃣2️⃣5️⃣0️⃣",
            "2015北栋",
            "9号房一1️⃣1️⃣5️⃣0️⃣（特价）",
            "",
            "在水一方，碧沙湖地铁，蓝弯国际，保利国际，南湖医院，书院路",
            "1811",
            "9号房一1️⃣1️⃣0️⃣0️⃣（特价）",
            "",
            "建鸿达现代公寓，华创国际，开福寺",
            "414南栋",
            "3号房一1️⃣3️⃣5️⃣0️⃣",
            "",
            "标志大厦，华创国际，开福寺",
            "606",
            "6号房一8️⃣5️⃣0️⃣（内窗）",
            "",
            "1508",
            "1号房一1️⃣0️⃣5️⃣0️⃣",
            "8号房一9️⃣0️⃣0️⃣",
            "5号房一1️⃣6️⃣0️⃣0️⃣",
            "",
            "1. 水费物业费网络费每月30元",
            "2. 电费：1元一度，所有房子都独立厨卫",
            "",
            "电话☎️13268058758微信同号",
            "各位中介朋友大力推荐，多多联系",
            "温馨提示：🈲止养宠物",
        ]
    )

    service = client.app.dependency_overrides[get_app_service]()
    assert service._looks_like_property_batch_text(raw_text) is True

    parsed_res = client.post(
        "/api/notes/property-batch/parse",
        json={"ownerUserId": owner["id"], "rawText": raw_text},
    )

    assert parsed_res.status_code == 200
    parsed = parsed_res.json()["data"]
    assert parsed["detectedCount"] == 8
    titles = [item["title"] for item in parsed["candidates"]]
    assert "新时代广场 · 1925南栋 · 2号房" in titles
    assert "新时代广场 · 2015北栋 · 9号房" in titles
    assert "在水一方 · 1811 · 9号房" in titles
    assert "建鸿达现代公寓 · 414南栋 · 3号房" in titles
    assert "标志大厦 · 606 · 6号房" in titles
    assert "标志大厦 · 1508 · 1号房" in titles
    assert "标志大厦 · 1508 · 8号房" in titles
    assert "标志大厦 · 1508 · 5号房" in titles
    assert [item["price"] for item in parsed["candidates"]] == [
        "1250元/月",
        "1150元/月",
        "1100元/月",
        "1350元/月",
        "850元/月",
        "1050元/月",
        "900元/月",
        "1600元/月",
    ]
    assert parsed["privacySummary"]["upstreamPhones"] == ["13268058758"]
    assert parsed["privacySummary"]["upstreamWechat"] == "13268058758"
    assert "佣金" in parsed["privacySummary"]["commission"]
    assert "禁宠" in parsed["candidates"][0]["publicTags"]
    assert any("上游电话" in item for item in parsed["candidates"][0]["privateTags"])


def test_property_batch_docx_text_samples_keep_expected_split_counts(client):
    owner = client.post("/api/auth/mock-login", json={"nickname": "房源样本文档用户", "openid": "openid_property_batch_docx_samples"}).json()["data"]
    samples = [
        (
            13,
            "\n".join(
                [
                    "觅租好房！ 可短租、月付",
                    "🏠一房",
                    "1.红星安置小区404房，家电齐全，带天然气，1550元/月包物业，钥匙在门口消防栓",
                    "2.东塘瑞府1710，1600元/月包物业，钥匙在门口消防栓",
                    "4.剑桥名门4栋903，1550元/月包物业，钥匙在门口窗户上",
                    "6.华景苑1714，1550元/月包物业，密码看房",
                    "11.Bobo天下城4栋804，1600元/月包物业，钥匙在楼梯间消防栓",
                    "建发中央公园9栋206，1700元/月包物业，密码看房",
                    "东塘瑞府1345房，1450元/月包物业，钥匙在门口消防栓",
                    "东塘瑞府2507房，1450元/月，钥匙在门口消防栓",
                    "芒果雅苑1栋1103，1000元/月包物业，密码看房",
                    "中江佳境天城8栋1906，1150元/月包物业，密码看房",
                    "新力铂园18栋1929房，1450元/月包物业，密码看房",
                    "🏠两房",
                    "1.阳光锦城1209房，1700元/月包物业，密码看房",
                    "3.东方新世界3栋5039，2000元/月不包物业，钥匙在门口消防栓",
                    "电话☎️ 15973197572",
                ]
            ),
        ),
        (
            12,
            "\n".join(
                [
                    "密码看房，佣金秒结，看房热线：15773132602（微信同号）",
                    "小区：森和大厦",
                    "户型：公寓一房  民水民电",
                    "价格：1500",
                    "万润时光里 公寓一房 边户 有WiFi",
                    "1650（使用WiFi需+50每月）",
                    "小区：明城国际中心 正规一室一厅 民水民电",
                    "价格：2380特价",
                    "小区：米兰春天G2-217",
                    "户型：复式一房 loft一房",
                    "价格：1300特价",
                    "小区：碧桂园城市之光",
                    "价格：1600",
                    "小区：乐尚城 公寓一房 余5间",
                    "价格：1200-1500",
                    "小区：新世界广场 公寓一房",
                    "价格：1350",
                    "小区：江南华府",
                    "户型：公寓一房 民水商电民燃气",
                    "价格：1400",
                    "小区：保利中环广场 户型：公寓一房",
                    "价格：1400",
                    "小区：世茂璀璨天城 loft两房 带门带衣帽间",
                    "价格：2000特价不支持谈价",
                    "平安街 有网络| 余11间",
                    "580-1350",
                    "梦华公寓 有网络| 余2间",
                    "1280-1300",
                ]
            ),
        ),
        (
            6,
            "\n".join(
                [
                    "密码锁看房",
                    "1 上城星座2188房 一室一厅 2380/月 独立卫厨",
                    "2 上城星座1305房 一室一厅2280/月 独立卫厨",
                    "1 上海城19栋 2606房 一室一厅 1780/月 独立厨卫",
                    "2 上海城19栋 2615房 一室一厅 1780/月 独立厨卫",
                    "3 上海城19栋 2616房 一室一厅 1780/月 独立厨卫",
                    "4 上海城19栋 2609房(左) 一室1180。独立厨卫",
                    "发财热线 15273611231 15675889264",
                ]
            ),
        ),
        (
            4,
            "\n".join(
                [
                    "新房源，随时看房，中介费50",
                    "1，合庆镇，向东村，邬家宅7号205一室户1280元",
                    "合庆镇前哨村马家宅51号超大1室户可做员工宿舍，住6~7个人¥2850",
                    "锦川佳苑3号204一2房1厅已空。5080元",
                    "4川虹新苑20号601大厅一室户天然气做饭。2280元",
                    "养宠物不租13127982873 电话13795267856",
                ]
            ),
        ),
        (
            5,
            "\n".join(
                [
                    "地铁14号线地铁50米金葵新城强烈推荐50%中介费+红包",
                    "945弄24号1101大南厅2680",
                    "地铁2号线零距离700米妙境路160号213朝南大平层一室一厅2500",
                    "妙境路107号205朝南一室1680空",
                    "妙境路107号312朝南一室户1780空",
                    "妙境路107号307一室户空1780",
                    "徐小姐17701877537微信同 19921370138李姐",
                ]
            ),
        ),
        (
            8,
            "\n".join(
                [
                    "所有房源看中房子给价就租，可办居住证",
                    "季桥村蔡圈717号",
                    "203室980",
                    "205室1080小复式一厅",
                    "季桥村蔡圈726号",
                    "109室880",
                    "201室1180朝阳一室户",
                    "利民村416号",
                    "102室1380朝阳大一室户",
                    "西新村草镇239号",
                    "105室1580朝阳一室户转租",
                    "下沙新村257号",
                    "1280",
                    "鹤鹤小区49号",
                    "306室1260",
                    "看房电话微信:13816149161",
                ]
            ),
        ),
    ]
    service = client.app.dependency_overrides[get_app_service]()
    for expected_count, raw_text in samples:
        assert service._looks_like_property_batch_text(raw_text) is True
        parsed_res = client.post(
            "/api/notes/property-batch/parse",
            json={"ownerUserId": owner["id"], "rawText": raw_text},
        )
        assert parsed_res.status_code == 200
        assert parsed_res.json()["data"]["detectedCount"] == expected_count


def test_property_batch_parse_short_listing_by_whole_text_elements(client):
    owner = client.post("/api/auth/mock-login", json={"nickname": "短挂牌用户", "openid": "openid_property_batch_short_listing"}).json()["data"]
    raw_text = "\n".join(
        [
            "挂牌：",
            "",
            "2，玉兰286弄10号601室南次一室户2500元，以空，",
            "",
            "3，玉兰四期73号202室北一室一厅3800元（实体墙）租客7月11号搬空，看房提前打电话，朋友圈有视频",
            "",
            "",
            "欢迎各位中介朋友带看，中介费%50",
            "电话☎️13611747285",
            "13671648195。",
        ]
    )

    parsed_res = client.post(
        "/api/notes/property-batch/parse",
        json={"ownerUserId": owner["id"], "rawText": raw_text},
    )

    assert parsed_res.status_code == 200
    parsed = parsed_res.json()["data"]
    assert parsed["detectedCount"] == 2
    titles = [item["title"] for item in parsed["candidates"]]
    assert "玉兰286弄10号601室 · 南次一室户" in titles
    assert "玉兰四期73号202室 · 北一室一厅" in titles
    assert parsed["privacySummary"]["upstreamPhones"] == ["13611747285", "13671648195"]
    assert parsed["privacySummary"]["commission"] == "中介费%50"

    create_res = client.post(
        "/api/notes/property-batch/create",
        json={"ownerUserId": owner["id"], "rawText": raw_text, "candidates": parsed["candidates"]},
    )

    assert create_res.status_code == 200
    created = create_res.json()["data"]
    assert created["createdCount"] == 2
    showcase = client.get(
        f"/api/showcases/{created['showcaseId']}",
        params={"ownerUserId": owner["id"]},
    ).json()["data"]
    assert showcase["templateId"] == "property_batch_collection"
    assert len(showcase["items"]) == 2
    assert all(item["phone"] is None for item in created["notes"])
    assert all(item["visibilityConfig"]["privateData"]["commission"] == "中介费%50" for item in created["notes"])


def test_note_preview_view_updates_note_list_stats(client):
    owner = client.post("/api/auth/mock-login", json={"nickname": "资料发布者", "openid": "openid_note_view_owner"}).json()["data"]
    viewer = client.post("/api/auth/mock-login", json={"nickname": "客户访客", "openid": "openid_note_view_customer"}).json()["data"]
    created = client.post(
        "/api/notes/manual-draft",
        json={
            "ownerUserId": owner["id"],
            "cardType": "property_listing",
            "inputMode": "paste_text",
            "rawText": "小区：城市之光\n租金：1600元/月\n电话：13800138000",
        },
    ).json()["data"]

    before = client.get("/api/notes", params={"ownerUserId": owner["id"]}).json()["data"]
    target_before = next(item for item in before if item["id"] == created["id"])
    assert target_before["stats"]["pv"] == 0

    share_id = "share_note_view_test_001"
    share_response = client.post(
        f"/api/notes/{created['id']}/view",
        json={
            "eventType": "share",
            "viewerUserId": owner["id"],
            "shareId": share_id,
            "shareFromUserId": owner["id"],
            "scene": "library_send_customer",
            "referrer": "library",
        },
    )
    assert share_response.status_code == 200
    shared = client.get("/api/notes", params={"ownerUserId": owner["id"]}).json()["data"]
    target_shared = next(item for item in shared if item["id"] == created["id"])
    assert target_shared["stats"]["pv"] == 0
    assert target_shared["stats"]["uv"] == 0
    assert target_shared["stats"]["shareCount"] == 1
    assert target_shared["stats"]["topShareId"] == share_id

    owner_view = client.post(
        f"/api/notes/{created['id']}/view",
        json={"viewerUserId": owner["id"], "nickname": owner["nickname"], "shareId": share_id, "shareFromUserId": owner["id"]},
    )
    assert owner_view.status_code == 200
    after_owner_view = client.get("/api/notes", params={"ownerUserId": owner["id"]}).json()["data"]
    target_after_owner = next(item for item in after_owner_view if item["id"] == created["id"])
    assert target_after_owner["stats"]["pv"] == 0
    assert target_after_owner["stats"]["uv"] == 0

    response = client.post(
        f"/api/notes/{created['id']}/view",
        json={
            "viewerUserId": viewer["id"],
            "nickname": viewer["nickname"],
            "avatarUrl": viewer["avatarUrl"],
            "shareId": share_id,
            "shareFromUserId": owner["id"],
            "scene": "library_send_customer",
        },
    )
    assert response.status_code == 200

    after = client.get("/api/notes", params={"ownerUserId": owner["id"]}).json()["data"]
    target_after = next(item for item in after if item["id"] == created["id"])
    assert target_after["stats"]["pv"] == 1
    assert target_after["stats"]["uv"] == 1
    assert target_after["stats"]["loggedInViewers"][0]["nickname"] == "客户访客"


def test_opportunity_radar_uses_public_view_behavior_without_duplicate_pv(client):
    owner = client.post("/api/auth/mock-login", json={"nickname": "成交助手用户", "openid": "openid_opp_owner"}).json()["data"]
    viewer = client.post("/api/auth/mock-login", json={"nickname": "王女士", "openid": "openid_opp_viewer"}).json()["data"]
    note = client.post(
        "/api/notes/manual-draft",
        json={
            "ownerUserId": owner["id"],
            "cardType": "service_offer",
            "inputMode": "paste_text",
            "rawText": "暑期英语班介绍\n课程内容：自然拼读\n价格优惠：早鸟价 1999 元\n联系方式：添加老师微信咨询",
        },
    ).json()["data"]

    payload = {
        "viewerUserId": viewer["id"],
        "nickname": viewer["nickname"],
        "avatarUrl": viewer["avatarUrl"],
        "sessionId": "session_opp_view_001",
        "durationSeconds": 1,
        "maxScrollPercent": 10,
        "focusSections": ["课程内容"],
    }
    first = client.post(f"/api/notes/{note['id']}/view", json=payload)
    assert first.status_code == 200
    second = client.post(
        f"/api/notes/{note['id']}/view",
        json={**payload, "durationSeconds": 138, "maxScrollPercent": 90, "focusSections": ["价格/优惠", "联系方式"]},
    )
    assert second.status_code == 200

    notes = client.get("/api/notes", params={"ownerUserId": owner["id"]}).json()["data"]
    target = next(item for item in notes if item["id"] == note["id"])
    assert target["stats"]["pv"] == 1

    dashboard = client.get(
        "/api/dashboard/business",
        params={"ownerUserId": owner["id"], "requesterUserId": owner["id"]},
    )
    assert dashboard.status_code == 200
    data = dashboard.json()["data"]
    assert data["opportunitySummary"]["highIntentCount"] >= 1
    assert data["opportunityAlerts"][0]["intentLevel"] == "高"
    assert "价格" in data["opportunityAlerts"][0]["message"]
    assert data["radarProfiles"][0]["durationSeconds"] == 138
    assert "followupScript" in data["opportunityAlerts"][0]


def test_public_note_hides_private_and_opportunity_data(client):
    owner = client.post("/api/auth/mock-login", json={"nickname": "隐私发布者", "openid": "openid_public_privacy_owner"}).json()["data"]
    note = client.post(
        "/api/notes/property-batch/create",
        json={
            "ownerUserId": owner["id"],
            "rawText": "城市之光一房 1600 禁宠 中介费50% 密码锁1234 电话18501775740",
            "candidates": [
                {
                    "candidateId": "property_privacy_1",
                    "title": "城市之光一房",
                    "layout": "一房",
                    "price": "1600",
                    "publicTags": ["禁宠"],
                    "privateTags": ["中介费"],
                    "privateData": {"upstreamPhones": ["18501775740"], "lockPassword": "1234"},
                    "selected": True,
                }
            ],
        },
    ).json()["data"]["notes"][0]
    public_note = client.get(f"/api/notes/public/{note['id']}").json()["data"]
    config = public_note["visibilityConfig"]
    assert "privateData" not in config
    assert "privateTags" not in config
    assert "18501775740" not in json.dumps(config, ensure_ascii=False)
    assert "1234" not in json.dumps(config, ensure_ascii=False)


def test_manual_note_draft_creates_groupbuy_from_pasted_text(client):
    owner = client.post("/api/auth/mock-login", json={"nickname": "手动团购用户", "openid": "openid_manual_groupbuy"}).json()["data"]
    raw_text = "\n".join(
        [
            "商品：烟台红富士",
            "团购价：39.9元/箱",
            "规格：5斤装",
            "截止：今晚22点",
            "取货地点：小区门口",
        ]
    )

    response = client.post(
        "/api/notes/manual-draft",
        json={
            "ownerUserId": owner["id"],
            "cardType": "groupbuy_product",
            "inputMode": "paste_text",
            "rawText": raw_text,
        },
    )

    assert response.status_code == 200
    note = response.json()["data"]
    config = note["visibilityConfig"]
    structured = config["structuredData"]
    assert config["cardType"] == "groupbuy_product"
    assert "团购" in config["tags"]
    assert "商品" in config["tags"]
    assert config["conversionConfig"]["enableGroupRelay"] is True
    assert "skuConfig" in structured
    assert structured["rawText"] == raw_text

    cards = client.get("/api/cards", params={"ownerUserId": owner["id"]}).json()["data"]
    product_card = next(item for item in cards if item.get("sourceNoteId") == note["id"])
    assert product_card["id"] == f"note_card_{note['id']}"
    assert product_card["cardType"] == "groupbuy_product"
    assert product_card["categoryName"] == "团购"


def test_manual_note_draft_creates_blank_structured_notes(client):
    owner = client.post("/api/auth/mock-login", json={"nickname": "空白资料用户", "openid": "openid_manual_blank"}).json()["data"]

    property_response = client.post(
        "/api/notes/manual-draft",
        json={"ownerUserId": owner["id"], "cardType": "property_listing", "inputMode": "blank"},
    )
    groupbuy_response = client.post(
        "/api/notes/manual-draft",
        json={"ownerUserId": owner["id"], "cardType": "groupbuy_product", "inputMode": "blank"},
    )

    assert property_response.status_code == 200
    property_note = property_response.json()["data"]
    assert property_note["title"] == "未命名房源"
    assert property_note["visibilityConfig"]["cardType"] == "property_listing"
    assert property_note["visibilityConfig"]["conversionConfig"]["enableAppointment"] is True
    assert property_note["visibilityConfig"]["structuredData"]["community"] == "未命名房源"
    assert groupbuy_response.status_code == 200
    groupbuy_note = groupbuy_response.json()["data"]
    assert groupbuy_note["title"] == "未命名商品"
    assert groupbuy_note["visibilityConfig"]["cardType"] == "groupbuy_product"
    assert groupbuy_note["visibilityConfig"]["conversionConfig"]["enableGroupRelay"] is True
    assert "skuConfig" in groupbuy_note["visibilityConfig"]["structuredData"]


def test_manual_note_draft_creates_business_card_from_profile(client):
    owner = client.post(
        "/api/auth/mock-login",
        json={
            "nickname": "林顾问",
            "openid": "openid_manual_business_card",
            "phone": "13800138000",
            "avatarUrl": "https://cdn.example.test/avatar.png",
        },
    ).json()["data"]

    response = client.post(
        "/api/notes/manual-draft",
        json={"ownerUserId": owner["id"], "cardType": "business_card", "inputMode": "blank"},
    )

    assert response.status_code == 200
    note = response.json()["data"]
    config = note["visibilityConfig"]
    structured = config["structuredData"]
    assert config["cardType"] == "business_card"
    assert config["systemCategory"] == "名片"
    assert "名片" in config["tags"]
    assert config["conversionConfig"]["collectLeads"] is True
    assert config["conversionConfig"]["enableAppointment"] is True
    assert structured["name"] == "林顾问"
    assert structured["phone"] == "13800138000"
    assert structured["avatarUrl"] == "https://cdn.example.test/avatar.png"


def test_service_offer_customer_actions_project_to_leads(client):
    owner = client.post("/api/auth/mock-login", json={"nickname": "服务顾问", "openid": "openid_service_owner"}).json()["data"]
    created = client.post(
        "/api/notes/manual-draft",
        json={"ownerUserId": owner["id"], "cardType": "service_offer", "inputMode": "blank"},
    )
    assert created.status_code == 200
    note = created.json()["data"]

    public_response = client.get(f"/api/notes/public/{note['id']}")
    action_config = client.get(f"/api/notes/{note['id']}/customer-actions/config", params={"anonymousId": "anon_service_1"})
    lead_response = client.post(
        f"/api/notes/{note['id']}/customer-actions/lead-contact",
        json={
            "anonymousId": "anon_service_1",
            "nickname": "服务客户",
            "payload": {"name": "服务客户", "phone": "13900139000", "wechat": "wx_service", "remark": "想咨询方案"},
        },
    )
    appointment_response = client.post(
        f"/api/notes/{note['id']}/customer-actions/appointment",
        json={
            "anonymousId": "anon_service_2",
            "nickname": "预约客户",
            "payload": {"date": "2026-06-23", "time": "10:30", "remark": "上午沟通"},
        },
    )
    owner_actions = client.get(f"/api/notes/{note['id']}/customer-actions", params={"ownerUserId": owner["id"]})

    assert public_response.status_code == 200
    assert public_response.json()["data"]["visibilityConfig"]["cardType"] == "service_offer"
    assert action_config.status_code == 200
    action_keys = {item["key"] for item in action_config.json()["data"]["actions"]}
    assert {"lead-contact", "appointment"}.issubset(action_keys)
    assert "order-intent" not in action_keys
    assert "relay-intent" not in action_keys
    assert lead_response.status_code == 200
    assert appointment_response.status_code == 200
    summary = owner_actions.json()["data"]["summary"]
    assert summary["leadContact"] == 1
    assert summary["appointment"] == 1
    assert summary["leads"] == 2
    assert summary["orderIntent"] == 0


def test_manual_note_draft_rejects_invalid_payloads(client):
    owner = client.post("/api/auth/mock-login", json={"nickname": "非法资料用户", "openid": "openid_manual_invalid"}).json()["data"]

    invalid_type = client.post(
        "/api/notes/manual-draft",
        json={"ownerUserId": owner["id"], "cardType": "video", "inputMode": "blank"},
    )
    invalid_mode = client.post(
        "/api/notes/manual-draft",
        json={"ownerUserId": owner["id"], "cardType": "text_note", "inputMode": "file"},
    )
    missing_user = client.post(
        "/api/notes/manual-draft",
        json={"ownerUserId": "user_missing", "cardType": "text_note", "inputMode": "blank"},
    )

    assert invalid_type.status_code == 400
    assert invalid_mode.status_code == 400
    assert missing_user.status_code == 404


def test_quick_capture_saves_plain_text_note(client):
    owner = client.post("/api/auth/mock-login", json={"nickname": "随手记用户", "openid": "openid_quick_plain"}).json()["data"]

    response = client.post(
        "/api/notes/quick-capture",
        json={"ownerUserId": owner["id"], "rawText": "今天买菜 32 元，客户说下周再看。"},
    )

    assert response.status_code == 200
    note = response.json()["data"]
    config = note["visibilityConfig"]
    assert note["ownerUserId"] == owner["id"]
    assert config["cardType"] == "text_note"
    assert config["sourceType"] == "manual_text"
    assert config["structuredData"]["rawText"] == "今天买菜 32 元，客户说下周再看。"

    cards = client.get("/api/cards", params={"ownerUserId": owner["id"]}).json()["data"]
    note_card = next(item for item in cards if item.get("sourceNoteId") == note["id"])
    assert note_card["id"] == f"note_card_{note['id']}"
    assert note_card["cardType"] == "text_note"
    assert note_card["categoryName"] == "普通笔记"
    assert note_card["title"] == note["title"]


def test_quick_capture_short_plain_note_visible_as_library_card(client):
    owner = client.post("/api/auth/mock-login", json={"nickname": "短笔记用户", "openid": "openid_quick_short_plain"}).json()["data"]

    response = client.post(
        "/api/notes/quick-capture",
        json={"ownerUserId": owner["id"], "rawText": "a da g g"},
    )

    assert response.status_code == 200
    note = response.json()["data"]
    assert note["visibilityConfig"]["cardType"] == "text_note"

    cards = client.get("/api/cards", params={"ownerUserId": owner["id"]})
    assert cards.status_code == 200
    rows = cards.json()["data"]
    note_card = next(item for item in rows if item.get("sourceNoteId") == note["id"])
    assert note_card["id"] == f"note_card_{note['id']}"
    assert note_card["cardType"] == "text_note"
    assert note_card["categoryName"] == "普通笔记"


def test_quick_capture_strips_invalid_unicode_surrogates(client):
    owner = client.post("/api/auth/mock-login", json={"nickname": "半截表情用户", "openid": "openid_quick_surrogate"}).json()["data"]
    raw_text = "客户晚上来看房\ud83d，先记一下预算 88 万"

    response = client.post(
        "/api/notes/quick-capture",
        content=json.dumps({"ownerUserId": owner["id"], "rawText": raw_text, "title": "客户\ud83d需求"}),
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 200
    note = response.json()["data"]
    config = note["visibilityConfig"]
    assert "\ud83d" not in note["title"]
    assert "\ud83d" not in config["structuredData"]["rawText"]
    assert config["structuredData"]["rawText"] == "客户晚上来看房，先记一下预算 88 万"


def test_quick_capture_keeps_valid_emoji(client):
    owner = client.post("/api/auth/mock-login", json={"nickname": "正常表情用户", "openid": "openid_quick_valid_emoji"}).json()["data"]
    raw_text = "🔥加州郡府 毛坯 小高层 三居室 126平米 88万 ☎️15147262725"

    response = client.post(
        "/api/notes/quick-capture",
        json={"ownerUserId": owner["id"], "rawText": raw_text, "title": "🔥房源"},
    )

    assert response.status_code == 200
    note = response.json()["data"]
    config = note["visibilityConfig"]
    assert "🔥" in note["title"]
    assert config["structuredData"]["rawText"] == raw_text
    assert config["cardType"] == "property_listing"


def test_public_note_preview_does_not_require_owner(client):
    owner = client.post("/api/auth/mock-login", json={"nickname": "分享资料用户", "openid": "openid_public_note_owner"}).json()["data"]
    viewer = client.post("/api/auth/mock-login", json={"nickname": "另一个手机", "openid": "openid_public_note_viewer"}).json()["data"]
    created = client.post(
        "/api/notes/quick-capture",
        json={"ownerUserId": owner["id"], "rawText": "🔥加州郡府 毛坯 小高层 三居室 126平米 88万 ☎️15147262725"},
    )
    note = created.json()["data"]

    forbidden_private = client.get(f"/api/notes/{note['id']}", params={"ownerUserId": viewer["id"]})
    public_response = client.get(f"/api/notes/public/{note['id']}")

    assert forbidden_private.status_code == 403
    assert public_response.status_code == 200
    assert public_response.json()["data"]["id"] == note["id"]
    assert public_response.json()["data"]["ownerUserId"] == owner["id"]


def test_quick_capture_routes_high_confidence_property(client):
    owner = client.post("/api/auth/mock-login", json={"nickname": "随手房源用户", "openid": "openid_quick_property"}).json()["data"]
    raw_text = "\n".join(
        [
            "小区：滨江花园",
            "户型：两房一厅",
            "面积：89平",
            "租金：5800元/月",
            "地址：浦东新区花木路",
        ]
    )

    response = client.post(
        "/api/notes/quick-capture",
        json={"ownerUserId": owner["id"], "rawText": raw_text},
    )

    assert response.status_code == 200
    note = response.json()["data"]
    config = note["visibilityConfig"]
    assert config["cardType"] == "property_listing"
    assert config["recognitionConfidence"]["level"] == "high"
    assert config["conversionConfig"]["enableAppointment"] is True
    assert config["structuredData"]["community"] == "滨江花园"


def test_property_note_uses_owner_contact_publicly_and_keeps_upstream_private(client):
    owner = client.post(
        "/api/auth/mock-login",
        json={
            "nickname": "房源发布者",
            "openid": "openid_property_owner_contact",
            "phone": "13900001111",
            "wechat": "agent-yiyi",
        },
    ).json()["data"]
    raw_text = "\n".join(
        [
            "开福区天健一期H栋1205",
            "独门独户，底价1500押一付三",
            "民水民电，密码锁",
            "上游电话：18501775740",
        ]
    )

    response = client.post(
        "/api/notes/quick-capture",
        json={"ownerUserId": owner["id"], "rawText": raw_text},
    )

    assert response.status_code == 200
    note = response.json()["data"]
    config = note["visibilityConfig"]
    structured = config["structuredData"]
    assert config["cardType"] == "property_listing"
    assert note["phone"] == "13900001111"
    assert structured["phone"] == "13900001111"
    assert structured["contact"] == "13900001111"
    assert structured["contactPhone"] == "13900001111"
    assert structured["wechat"] == "agent-yiyi"
    assert structured["contactWechat"] == "agent-yiyi"
    assert config["privateData"]["upstreamPhones"] == ["18501775740"]
    assert "18501775740" not in structured.get("contact", "")

    public_note = client.get(f"/api/notes/public/{note['id']}").json()["data"]
    public_config = public_note["visibilityConfig"]
    public_structured = public_config["structuredData"]
    assert "privateData" not in public_config
    assert public_note["phone"] == "13900001111"
    assert public_structured["contactPhone"] == "13900001111"
    assert public_structured["contactWechat"] == "agent-yiyi"
    assert "18501775740" not in json.dumps(public_note, ensure_ascii=False)


def test_quick_capture_routes_informal_property_posts_as_high_confidence(client):
    owner = client.post("/api/auth/mock-login", json={"nickname": "朋友圈房源用户", "openid": "openid_quick_property_informal"}).json()["data"]
    samples = [
        "🔥加州郡府 毛坯 小高层 双阳夹厅三居室 赠送有阳台 阴台 👉126平米 88万 详情咨询：15147262725。",
        "龙悦和府\n钢四小，乌兰小学，二十九中，\n网签即可入学\n最小78平，最大140，105独梯独户，78平也是南北通透(加三万送装修）有想了解的随时问我☎️13474976910",
    ]

    for index, raw_text in enumerate(samples):
        response = client.post(
            "/api/notes/quick-capture",
            json={"ownerUserId": owner["id"], "rawText": raw_text, "title": f"朋友圈房源{index}"},
        )

        assert response.status_code == 200
        config = response.json()["data"]["visibilityConfig"]
        assert config["cardType"] == "property_listing"
        assert config["recognitionConfidence"]["level"] == "high"
        assert config["conversionConfig"]["enableAppointment"] is True
        assert config["structuredData"]["rawText"] == raw_text


def test_confirm_plain_rental_note_reextracts_property_fields(client):
    owner = client.post("/api/auth/mock-login", json={"nickname": "旧普通房源用户", "openid": "openid_confirm_plain_rental"}).json()["data"]
    raw_text = "\n".join(
        [
            "开福区天健一期H栋1205",
            "独门独户，底价1500押一付三",
            "押一付三民水民电",
            "要求租客不养宠物 爱干净",
            "密码锁",
        ]
    )
    created = client.post(
        "/api/notes/manual-draft",
        json={
            "ownerUserId": owner["id"],
            "cardType": "text_note",
            "inputMode": "paste_text",
            "rawText": raw_text,
            "title": "开福区天健一期H栋1205 独门独户，底价1500押一付三 押一付三民水民电",
        },
    )

    assert created.status_code == 200
    note = created.json()["data"]
    assert note["visibilityConfig"]["cardType"] == "text_note"

    confirmed = client.post(
        f"/api/notes/{note['id']}/confirm-type",
        json={"ownerUserId": owner["id"], "cardType": "property_listing"},
    )

    assert confirmed.status_code == 200
    config = confirmed.json()["data"]["visibilityConfig"]
    structured = config["structuredData"]
    assert config["cardType"] == "property_listing"
    assert structured["price"] == "1500"
    assert structured["paymentMethod"] == "押一付三"
    assert structured["utilities"] == "民水民电"
    assert "不养宠物" in structured["remark"]


def test_quick_capture_routes_high_confidence_groupbuy(client):
    owner = client.post("/api/auth/mock-login", json={"nickname": "随手团购用户", "openid": "openid_quick_groupbuy"}).json()["data"]
    raw_text = "\n".join(
        [
            "商品：烟台红富士",
            "团购价：39.9元/箱",
            "规格：5斤装",
            "截止：今晚22点",
            "取货地点：小区门口",
        ]
    )

    response = client.post(
        "/api/notes/quick-capture",
        json={"ownerUserId": owner["id"], "rawText": raw_text},
    )

    assert response.status_code == 200
    note = response.json()["data"]
    config = note["visibilityConfig"]
    assert config["cardType"] == "groupbuy_product"
    assert config["recognitionConfidence"]["level"] == "high"
    assert config["conversionConfig"]["enableGroupRelay"] is True
    assert "skuConfig" in config["structuredData"]


def test_quick_capture_rejects_empty_or_missing_user(client):
    owner = client.post("/api/auth/mock-login", json={"nickname": "随手非法用户", "openid": "openid_quick_invalid"}).json()["data"]

    empty = client.post("/api/notes/quick-capture", json={"ownerUserId": owner["id"], "rawText": "   "})
    missing_user = client.post("/api/notes/quick-capture", json={"ownerUserId": "user_missing", "rawText": "普通记录"})

    assert empty.status_code == 400
    assert missing_user.status_code == 404


def test_showcase_builder_create_publish_public_and_archive(client):
    owner = client.post("/api/auth/mock-login", json={"nickname": "展示页店主", "openid": "openid_showcase_owner"}).json()["data"]
    notes = client.post("/api/notes/demo-data", params={"ownerUserId": owner["id"]}).json()["data"]["notes"]
    note_ids = [item["id"] for item in notes[:2]]

    draft = client.post(
        "/api/showcases",
        json={
            "ownerUserId": owner["id"],
            "name": "依依好房精选",
            "description": "近期主推房源和商品",
            "shareTitle": "本周精选资料",
            "contactConfig": {"phone": "13800138000", "wechat": "wx-yiyi"},
            "displayConfig": {"groupBy": "tag", "showTags": True, "activeCategory": "房产", "layoutMode": "grid"},
            "items": [
                {"noteId": note_ids[0], "sortOrder": 2, "sectionTitle": "房源"},
                {"noteId": note_ids[1], "sortOrder": 1, "sectionTitle": "房源"},
                {"noteId": notes[2]["id"], "sortOrder": 3, "visible": False},
            ],
        },
    )
    assert draft.status_code == 200
    showcase = draft.json()["data"]
    assert showcase["status"] == "draft"
    assert len(showcase["items"]) == 3

    private_list = client.get("/api/showcases", params={"ownerUserId": owner["id"]})
    assert private_list.status_code == 200
    assert private_list.json()["data"][0]["itemCount"] == 2

    public_before_publish = client.get(f"/api/showcases/public/{showcase['id']}")
    assert public_before_publish.status_code == 404
    draft_event = client.post(
        f"/api/showcases/{showcase['id']}/events",
        json={"eventType": "view", "anonymousId": "anon_draft_showcase"},
    )
    assert draft_event.status_code == 404
    assert draft_event.json()["detail"] == "展示页不存在或未发布"

    published = client.post(f"/api/showcases/{showcase['id']}/publish", json={"ownerUserId": owner["id"]})
    assert published.status_code == 200
    assert published.json()["data"]["status"] == "published"
    assert published.json()["data"]["snapshotVersion"] == 1
    assert published.json()["data"]["snapshotCreatedAt"]

    public = client.get(f"/api/showcases/public/{showcase['id']}")
    assert public.status_code == 200
    public_data = public.json()["data"]
    assert public_data["name"] == "依依好房精选"
    assert public_data["shareTitle"] == "本周精选资料"
    assert public_data["displayConfig"]["groupBy"] == "tag"
    assert public_data["displayConfig"]["activeCategory"] == "房产"
    assert public_data["displayConfig"]["layoutMode"] == "grid"
    assert public_data["snapshotVersion"] == 1
    assert public_data["snapshotSource"] == "published_snapshot"
    assert [item["noteId"] for item in public_data["items"]] == [note_ids[1], note_ids[0]]
    assert public_data["items"][0]["cardType"]
    assert public_data["items"][0]["badge"]
    assert "primaryText" in public_data["items"][0]
    assert "ownerUserId" not in public_data["items"][0]
    assert notes[2]["id"] not in [item["noteId"] for item in public_data["items"]]

    viewer = client.post("/api/auth/mock-login", json={"nickname": "展示页访客", "openid": "openid_showcase_viewer"}).json()["data"]
    share_id = "share_showcase_test_001"
    assert client.post(
        f"/api/showcases/{showcase['id']}/events",
        json={
            "eventType": "share",
            "shareId": share_id,
            "shareFromUserId": owner["id"],
            "scene": "showcase_list_share",
            "referrer": "showcases",
        },
    ).status_code == 200
    owner_showcase_view = client.post(
        f"/api/showcases/{showcase['id']}/events",
        json={
            "eventType": "view",
            "viewerUserId": owner["id"],
            "nickname": owner["nickname"],
            "shareId": share_id,
            "shareFromUserId": owner["id"],
        },
    )
    assert owner_showcase_view.status_code == 200
    assert owner_showcase_view.json()["data"]["recorded"] is False
    assert client.post(
        f"/api/showcases/{showcase['id']}/events",
        json={
            "eventType": "view",
            "viewerUserId": viewer["id"],
            "nickname": viewer["nickname"],
            "avatarUrl": viewer["avatarUrl"],
            "shareId": share_id,
            "shareFromUserId": owner["id"],
            "scene": "showcase_list_share",
        },
    ).status_code == 200
    assert client.post(
        f"/api/showcases/{showcase['id']}/events",
        json={
            "eventType": "note_click",
            "viewerUserId": viewer["id"],
            "noteId": note_ids[1],
            "shareId": share_id,
            "shareFromUserId": owner["id"],
            "scene": "showcase_list_share",
        },
    ).status_code == 200
    assert client.post(
        f"/api/showcases/{showcase['id']}/events",
        json={
            "eventType": "wechat_copy",
            "anonymousId": "anon_showcase_a",
            "shareId": share_id,
            "shareFromUserId": owner["id"],
            "scene": "showcase_list_share",
        },
    ).status_code == 200
    analytics = client.get(f"/api/showcases/{showcase['id']}/analytics", params={"ownerUserId": owner["id"]})
    assert analytics.status_code == 200
    analytics_data = analytics.json()["data"]
    assert analytics_data["summary"]["pv"] == 1
    assert analytics_data["summary"]["uv"] == 1
    assert analytics_data["summary"]["wechatCopyCount"] == 1
    assert analytics_data["summary"]["consultClickCount"] == 1
    assert analytics_data["summary"]["shareCount"] == 1
    assert analytics_data["summary"]["shareSourceCount"] == 1
    assert analytics_data["topShares"][0]["shareId"] == share_id
    assert analytics_data["topShares"][0]["openCount"] == 1
    assert analytics_data["topShares"][0]["noteClickCount"] == 1
    assert analytics_data["topShares"][0]["consultCount"] == 1
    assert analytics_data["recentEvents"][0]["shareId"] == share_id
    assert analytics_data["topNotes"][0]["noteId"] == note_ids[1]
    forbidden_analytics = client.get(f"/api/showcases/{showcase['id']}/analytics", params={"ownerUserId": viewer["id"]})
    assert forbidden_analytics.status_code == 403

    private_with_analytics = client.get("/api/showcases", params={"ownerUserId": owner["id"]}).json()["data"][0]
    assert private_with_analytics["analytics"]["summary"]["pv"] == 1

    deleted = client.delete(f"/api/notes/{note_ids[1]}", params={"ownerUserId": owner["id"]})
    assert deleted.status_code == 200
    public_after_delete = client.get(f"/api/showcases/public/{showcase['id']}")
    public_after_delete_data = public_after_delete.json()["data"]
    assert public_after_delete_data["snapshotVersion"] == 2
    assert [item["noteId"] for item in public_after_delete_data["items"]] == [note_ids[0]]

    archived = client.post(f"/api/showcases/{showcase['id']}/archive", json={"ownerUserId": owner["id"]})
    assert archived.status_code == 200
    assert archived.json()["data"]["status"] == "archived"
    assert client.get(f"/api/showcases/public/{showcase['id']}").status_code == 404
    archived_event = client.post(
        f"/api/showcases/{showcase['id']}/events",
        json={"eventType": "view", "anonymousId": "anon_archived_showcase"},
    )
    assert archived_event.status_code == 404
    assert archived_event.json()["detail"] == "展示页不存在或未发布"

    removed = client.post(f"/api/showcases/{showcase['id']}/delete", json={"ownerUserId": owner["id"]})
    assert removed.status_code == 200
    assert removed.json()["data"]["deletedShowcaseId"] == showcase["id"]
    private_after_delete = client.get("/api/showcases", params={"ownerUserId": owner["id"]})
    assert showcase["id"] not in [item["id"] for item in private_after_delete.json()["data"]]


def test_showcase_rejects_other_users_notes_and_empty_publish(client):
    owner = client.post("/api/auth/mock-login", json={"nickname": "展示页店主B", "openid": "openid_showcase_owner_b"}).json()["data"]
    other = client.post("/api/auth/mock-login", json={"nickname": "其他人", "openid": "openid_showcase_other"}).json()["data"]
    other_note = client.post("/api/notes/demo-data", params={"ownerUserId": other["id"]}).json()["data"]["notes"][0]

    forbidden = client.post(
        "/api/showcases",
        json={
            "ownerUserId": owner["id"],
            "name": "越权展示页",
            "items": [{"noteId": other_note["id"]}],
        },
    )
    assert forbidden.status_code == 403

    empty = client.post(
        "/api/showcases",
        json={
            "ownerUserId": owner["id"],
            "name": "空展示页",
            "items": [],
        },
    ).json()["data"]
    publish_empty = client.post(f"/api/showcases/{empty['id']}/publish", json={"ownerUserId": owner["id"]})
    assert publish_empty.status_code == 400
    assert "至少选择一条有效资料" in publish_empty.json()["detail"]


def test_showcase_public_uses_publish_snapshot_until_republish(client):
    owner = client.post("/api/auth/mock-login", json={"nickname": "展示页店主C", "openid": "openid_showcase_owner_c"}).json()["data"]
    note = client.post("/api/notes/demo-data", params={"ownerUserId": owner["id"]}).json()["data"]["notes"][0]
    showcase = client.post(
        "/api/showcases",
        json={
            "ownerUserId": owner["id"],
            "name": "实时资料展示页",
            "items": [{"noteId": note["id"]}],
        },
    ).json()["data"]
    client.post(f"/api/showcases/{showcase['id']}/publish", json={"ownerUserId": owner["id"]})
    public_before_update = client.get(f"/api/showcases/public/{showcase['id']}").json()["data"]

    updated = dict(note)
    updated["title"] = "更新后的房源标题"
    updated["summary"] = "更新后的摘要"
    updated["body"] = note["body"]
    update_response = client.put(f"/api/notes/{note['id']}", json=updated)
    assert update_response.status_code == 200

    public = client.get(f"/api/showcases/public/{showcase['id']}")
    assert public.status_code == 200
    item = public.json()["data"]["items"][0]
    assert item["title"] == public_before_update["items"][0]["title"]
    assert item["summary"] == public_before_update["items"][0]["summary"]

    republished = client.post(f"/api/showcases/{showcase['id']}/publish", json={"ownerUserId": owner["id"]})
    assert republished.status_code == 200
    refreshed_public = client.get(f"/api/showcases/public/{showcase['id']}")
    assert refreshed_public.status_code == 200
    refreshed_data = refreshed_public.json()["data"]
    assert refreshed_data["snapshotVersion"] == 2
    assert refreshed_data["items"][0]["title"] == "更新后的房源标题"
    assert refreshed_data["items"][0]["summary"] == "更新后的摘要"


def test_business_dashboard_aggregates_real_customer_data(client):
    owner = client.post("/api/auth/mock-login", json={"nickname": "看板用户", "openid": "openid_dashboard_owner"}).json()["data"]
    other = client.post("/api/auth/mock-login", json={"nickname": "其他看板用户", "openid": "openid_dashboard_other"}).json()["data"]
    notes = client.post("/api/notes/demo-data", params={"ownerUserId": owner["id"]}).json()["data"]["notes"]
    other_notes = client.post("/api/notes/demo-data", params={"ownerUserId": other["id"]}).json()["data"]["notes"]
    showcase = client.post(
        "/api/showcases",
        json={
            "ownerUserId": owner["id"],
            "name": "看板测试展示页",
            "items": [{"noteId": notes[0]["id"]}, {"noteId": notes[1]["id"]}],
        },
    ).json()["data"]
    other_showcase = client.post(
        "/api/showcases",
        json={
            "ownerUserId": other["id"],
            "name": "其他人的展示页",
            "items": [{"noteId": other_notes[0]["id"]}],
        },
    ).json()["data"]
    client.post(f"/api/showcases/{showcase['id']}/publish", json={"ownerUserId": owner["id"]})
    client.post(f"/api/showcases/{other_showcase['id']}/publish", json={"ownerUserId": other["id"]})
    viewer = client.post("/api/auth/mock-login", json={"nickname": "看板访客", "openid": "openid_dashboard_viewer"}).json()["data"]
    share_id = "share_dashboard_owner_001"

    assert client.post(
        f"/api/showcases/{showcase['id']}/events",
        json={"eventType": "share", "shareId": share_id, "shareFromUserId": owner["id"], "scene": "showcase_list_share"},
    ).status_code == 200
    assert client.post(
        f"/api/showcases/{showcase['id']}/events",
        json={"eventType": "view", "viewerUserId": viewer["id"], "nickname": viewer["nickname"], "shareId": share_id, "shareFromUserId": owner["id"]},
    ).status_code == 200
    assert client.post(
        f"/api/showcases/{showcase['id']}/events",
        json={"eventType": "view", "anonymousId": "anon_dashboard", "shareId": share_id, "shareFromUserId": owner["id"]},
    ).status_code == 200
    assert client.post(
        f"/api/showcases/{showcase['id']}/events",
        json={"eventType": "note_click", "viewerUserId": viewer["id"], "noteId": notes[1]["id"], "shareId": share_id, "shareFromUserId": owner["id"]},
    ).status_code == 200
    assert client.post(
        f"/api/showcases/{showcase['id']}/events",
        json={"eventType": "phone_click", "viewerUserId": viewer["id"], "shareId": share_id, "shareFromUserId": owner["id"]},
    ).status_code == 200
    assert client.post(
        f"/api/showcases/{other_showcase['id']}/events",
        json={"eventType": "view", "anonymousId": "anon_other_dashboard"},
    ).status_code == 200
    service = client.app.dependency_overrides[get_app_service]()
    action_avatar = "https://cdn.example.test/dashboard-customer.png"
    service.repo.save_customer_action(
        CustomerAction(
            id=new_id("action"),
            ownerUserId=owner["id"],
            noteId=notes[0]["id"],
            viewerUserId=viewer["id"],
            actionKey="consult-click",
            actionLabel="微信咨询",
            payload={
                "name": "看板访客",
                "avatarUrl": action_avatar,
                "phone": "13900009999",
                "wechat": "wx_dashboard",
            },
            createdAt=now_iso(),
            updatedAt=now_iso(),
        )
    )

    response = client.get(
        "/api/dashboard/business",
        params={"ownerUserId": owner["id"], "requesterUserId": owner["id"]},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["summary"]["showcaseOpenCount"] == 4
    assert data["summary"]["visitorCount"] == 4
    assert data["summary"]["loggedInVisitorCount"] == 2
    assert data["summary"]["anonymousVisitorCount"] == 2
    assert data["summary"]["noteClickCount"] == 2
    assert data["summary"]["consultCount"] == 3
    assert data["summary"]["shareCount"] == 1
    assert data["summary"]["shareSourceCount"] == 1
    assert data["summary"]["pendingLeadCount"] == 1
    assert data["summary"]["customerCount"] == 2
    assert data["summary"]["orderCount"] == 1
    assert data["summary"]["pendingOrderCount"] == 1
    assert {item["target"] for item in data["entries"]} == {"showcases", "visitors", "notes", "customers"}
    assert data["topShares"][0]["shareId"] == share_id
    assert data["topShares"][0]["openCount"] == 2
    assert data["topShares"][0]["noteClickCount"] == 1
    assert data["topShares"][0]["consultCount"] == 1
    assert data["topShares"][0]["visitorNames"]
    showcase_row = next(item for item in data["showcaseBreakdown"] if item["showcaseId"] == showcase["id"])
    assert showcase_row["openCount"] >= 2
    assert showcase_row["visitorCount"] >= 2
    assert any(item["phone"] and item["leadReminderId"] for item in data["visitorProfiles"])
    assert any(item["orderActionId"] for item in data["visitorProfiles"])
    assert any(notes[1]["id"] in item.get("noteIds", []) for item in data["visitorProfiles"])
    assert any(item["avatarUrl"] == action_avatar for item in data["visitorProfiles"])
    assert any(item["anonymous"] and item["nickname"] == "匿名客户" for item in data["recentVisitors"])
    assert {item["noteId"] for item in data["topNotes"]} >= {notes[0]["id"], notes[1]["id"]}

    owner_showcase_analytics = client.get(
        f"/api/showcases/{showcase['id']}/analytics",
        params={"ownerUserId": owner["id"]},
    )
    assert owner_showcase_analytics.status_code == 200
    forbidden_showcase_analytics = client.get(
        f"/api/showcases/{showcase['id']}/analytics",
        params={"ownerUserId": other["id"]},
    )
    assert forbidden_showcase_analytics.status_code == 403
    anonymous_showcase_analytics = client.get(f"/api/showcases/{showcase['id']}/analytics")
    assert anonymous_showcase_analytics.status_code == 422

    owner_note_actions = client.get(
        f"/api/notes/{notes[0]['id']}/customer-actions",
        params={"ownerUserId": owner["id"]},
    )
    assert owner_note_actions.status_code == 200
    forbidden_note_actions = client.get(
        f"/api/notes/{notes[0]['id']}/customer-actions",
        params={"ownerUserId": other["id"]},
    )
    assert forbidden_note_actions.status_code == 403
    anonymous_note_actions = client.get(f"/api/notes/{notes[0]['id']}/customer-actions")
    assert anonymous_note_actions.status_code == 422

    forbidden = client.get(
        "/api/dashboard/business",
        params={"ownerUserId": owner["id"], "requesterUserId": other["id"]},
    )
    assert forbidden.status_code == 403
    assert forbidden.json()["detail"] == "仅工作台拥有者可查看"

    anonymous = client.get("/api/dashboard/business", params={"ownerUserId": owner["id"]})
    assert anonymous.status_code == 401
    assert anonymous.json()["detail"] == "请先登录后查看工作台"
    assert any(item["avatarUrl"] == action_avatar for item in data["latestActions"])
    assert any(
        item["actionKey"] == "relay-intent" and item["targetType"] == "order" and item["orderActionId"]
        for item in data["latestActions"]
    )
    assert any(
        item["actionKey"] == "lead-contact" and item["targetType"] == "lead" and item["leadReminderId"]
        for item in data["latestActions"]
    )
    assert data["latestActions"][0]["priority"] >= data["latestActions"][-1]["priority"]


def test_property_business_dashboard_only_counts_property_customer_data(client):
    owner = client.post("/api/auth/mock-login", json={"nickname": "房源看板用户", "openid": "openid_property_dashboard_owner"}).json()["data"]
    viewer = client.post("/api/auth/mock-login", json={"nickname": "看房客户", "openid": "openid_property_dashboard_viewer"}).json()["data"]
    property_note = client.post(
        "/api/notes/manual-draft",
        json={
            "ownerUserId": owner["id"],
            "cardType": "property_listing",
            "inputMode": "paste_text",
            "rawText": "小区：碧桂园城市之光\n租金：1600元/月\n电话：13800138000",
        },
    ).json()["data"]
    service_note = client.post(
        "/api/notes/manual-draft",
        json={"ownerUserId": owner["id"], "cardType": "service_offer", "inputMode": "blank"},
    ).json()["data"]

    client.post(
        f"/api/notes/{property_note['id']}/view",
        json={"viewerUserId": viewer["id"], "nickname": viewer["nickname"], "avatarUrl": viewer["avatarUrl"]},
    )
    service = client.app.dependency_overrides[get_app_service]()
    service.repo.add_view_event(
        ViewEvent(
            id=new_id("view"),
            cardId=property_note["id"],
            viewerUserId=None,
            viewType="anonymous",
            anonymousId="anon_old_property_view",
            nickname="历史访客",
            avatarUrl=None,
            viewedAt="2026-01-01T10:00:00+08:00",
            dateKey="2026-01-01",
        )
    )
    orphan_lead = LeadReminder(
        id=new_id("lead"),
        ownerUserId=owner["id"],
        cardId=property_note["id"],
        viewerUserId="legacy_viewer_property",
        nickname="历史线索客户",
        avatarUrl=None,
        status="pending",
        note="旧访问详情投影出的待跟进线索",
        customerPhone="13100001111",
        customerWechat="wx_legacy_property",
        createdAt=now_iso(),
        updatedAt=now_iso(),
    )
    service.repo.save_lead_reminder(orphan_lead)
    property_action = client.post(
        f"/api/notes/{property_note['id']}/customer-actions/appointment",
        json={
            "viewerUserId": viewer["id"],
            "nickname": viewer["nickname"],
            "payload": {"date": "2026-06-24", "time": "10:30", "remark": "想看城市之光"},
        },
    )
    service_action = client.post(
        f"/api/notes/{service_note['id']}/customer-actions/appointment",
        json={
            "anonymousId": "anon_service_dashboard",
            "nickname": "服务咨询客户",
            "payload": {"date": "2026-06-25", "time": "15:00", "remark": "咨询服务"},
        },
    )
    assert property_action.status_code == 200
    assert service_action.status_code == 200

    showcase = client.post(
        "/api/showcases",
        json={
            "ownerUserId": owner["id"],
            "name": "张先生房源推荐包",
            "items": [{"noteId": property_note["id"]}, {"noteId": service_note["id"]}],
        },
    ).json()["data"]
    client.post(f"/api/showcases/{showcase['id']}/publish", json={"ownerUserId": owner["id"]})
    share_id = "share_property_dashboard_001"
    assert client.post(
        f"/api/showcases/{showcase['id']}/events",
        json={"eventType": "view", "viewerUserId": viewer["id"], "nickname": viewer["nickname"], "shareId": share_id},
    ).status_code == 200
    assert client.post(
        f"/api/showcases/{showcase['id']}/events",
        json={"eventType": "note_click", "viewerUserId": viewer["id"], "noteId": property_note["id"], "shareId": share_id},
    ).status_code == 200
    assert client.post(
        f"/api/showcases/{showcase['id']}/events",
        json={"eventType": "note_click", "viewerUserId": viewer["id"], "noteId": service_note["id"], "shareId": share_id},
    ).status_code == 200

    response = client.get(
        "/api/dashboard/business",
        params={"ownerUserId": owner["id"], "requesterUserId": owner["id"], "mode": "property"},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["summary"]["propertyCount"] == 1
    assert data["summary"]["showcaseOpenCount"] == 1
    assert data["summary"]["visitorCount"] == 2
    assert data["summary"]["loggedInVisitorCount"] == 1
    assert data["summary"]["pendingLeadCount"] == 2
    assert data["summary"]["customerCount"] == 2
    assert data["summary"]["noteClickCount"] == 3
    assert data["todaySummary"]["propertyCount"] == 1
    assert data["todaySummary"]["showcaseOpenCount"] == 1
    assert data["todaySummary"]["visitorCount"] == 1
    assert data["todaySummary"]["loggedInVisitorCount"] == 1
    assert data["todaySummary"]["pendingLeadCount"] == 2
    assert data["todaySummary"]["noteClickCount"] == 2
    assert [item["noteId"] for item in data["topNotes"]] == [property_note["id"]]
    assert data["topNotes"][0]["followupCount"] == 2
    assert data["topNotes"][0]["visitorCount"] == 2
    assert data["topNotes"][0]["todayVisitorCount"] == 1
    assert data["topShares"][0]["noteClickCount"] == 1
    assert all(item["noteId"] == property_note["id"] for item in data["latestActions"])
    assert all(item["isToday"] for item in data["latestActions"])
    assert any(item["leadReminderId"] == orphan_lead.id and item["actionKey"] == "lead-followup" for item in data["latestActions"])
    assert any(item["isToday"] for item in data["visitorProfiles"])
    assert all(service_note["id"] not in item.get("noteIds", []) for item in data["visitorProfiles"])


def test_service_business_dashboard_only_counts_service_customer_data(client):
    owner = client.post("/api/auth/mock-login", json={"nickname": "服务看板用户", "openid": "openid_service_dashboard_owner"}).json()["data"]
    viewer = client.post("/api/auth/mock-login", json={"nickname": "咨询客户", "openid": "openid_service_dashboard_viewer"}).json()["data"]
    service_note = client.post(
        "/api/notes/manual-draft",
        json={"ownerUserId": owner["id"], "cardType": "service_offer", "inputMode": "blank"},
    ).json()["data"]
    card_note = client.post(
        "/api/notes/manual-draft",
        json={"ownerUserId": owner["id"], "cardType": "business_card", "inputMode": "blank"},
    ).json()["data"]
    groupbuy_note = client.post(
        "/api/notes/manual-draft",
        json={
            "ownerUserId": owner["id"],
            "cardType": "groupbuy_product",
            "inputMode": "paste_text",
            "rawText": "团购 白凤乌鸡蛋 4斤，约40多个，今天接龙",
        },
    ).json()["data"]

    service_action = client.post(
        f"/api/notes/{service_note['id']}/customer-actions/appointment",
        json={
            "viewerUserId": viewer["id"],
            "nickname": viewer["nickname"],
            "payload": {"date": "2026-06-24", "time": "15:00", "remark": "想咨询服务"},
        },
    )
    card_action = client.post(
        f"/api/notes/{card_note['id']}/customer-actions/lead-contact",
        json={
            "anonymousId": "anon_business_card_lead",
            "nickname": "名片客户",
            "payload": {"phone": "13900001111", "wechat": "wx_card", "remark": "看了名片"},
        },
    )
    groupbuy_action = client.post(
        f"/api/notes/{groupbuy_note['id']}/customer-actions/relay-intent",
        json={
            "anonymousId": "anon_groupbuy_order",
            "nickname": "团购买家",
            "payload": {"skuKey": "default", "phone": "13800000000", "address": "小区门口", "quantity": 1},
        },
    )
    assert service_action.status_code == 200
    assert card_action.status_code == 200
    assert groupbuy_action.status_code == 200

    showcase = client.post(
        "/api/showcases",
        json={
            "ownerUserId": owner["id"],
            "name": "服务案例合集",
            "items": [{"noteId": service_note["id"]}, {"noteId": card_note["id"]}, {"noteId": groupbuy_note["id"]}],
        },
    ).json()["data"]
    client.post(f"/api/showcases/{showcase['id']}/publish", json={"ownerUserId": owner["id"]})
    assert client.post(
        f"/api/showcases/{showcase['id']}/events",
        json={"eventType": "view", "viewerUserId": viewer["id"], "nickname": viewer["nickname"], "shareId": "share_service_dashboard_001"},
    ).status_code == 200
    assert client.post(
        f"/api/showcases/{showcase['id']}/events",
        json={"eventType": "note_click", "viewerUserId": viewer["id"], "noteId": service_note["id"], "shareId": "share_service_dashboard_001"},
    ).status_code == 200
    assert client.post(
        f"/api/showcases/{showcase['id']}/events",
        json={"eventType": "note_click", "viewerUserId": viewer["id"], "noteId": groupbuy_note["id"], "shareId": "share_service_dashboard_001"},
    ).status_code == 200

    response = client.get(
        "/api/dashboard/business",
        params={"ownerUserId": owner["id"], "requesterUserId": owner["id"], "mode": "service"},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["summary"]["pendingLeadCount"] == 2
    assert data["summary"]["orderCount"] == 0
    assert {item["noteId"] for item in data["topNotes"]} == {service_note["id"]}
    assert all(item["noteId"] in {service_note["id"], card_note["id"]} for item in data["latestActions"])
    assert all(groupbuy_note["id"] not in item.get("noteIds", []) for item in data["visitorProfiles"])


def test_wecom_archive_worker_run_once_pulls_then_processes():
    class FakeService:
        def __init__(self):
            self.calls = []

        def pull_wecom_archive_messages(self, archive_client, limit):
            self.calls.append(("pull", archive_client, limit))
            return {"savedCount": 1}

        def process_wecom_archive_messages(self, limit, archive_client=None):
            self.calls.append(("process", limit, archive_client))
            return {"processedCount": 1}

    fake_service = FakeService()
    fake_client = object()
    worker = WecomArchiveWorker(
        fake_service,
        fake_client,
        enabled=True,
        interval_seconds=60,
        pull_limit=20,
    )

    result = asyncio.run(worker.run_once())

    assert result == {"pull": {"savedCount": 1}, "process": {"processedCount": 1}}
    assert fake_service.calls == [("pull", fake_client, 20), ("process", 20, fake_client)]


def test_archive_parser_registry_uses_explicit_parser_metadata():
    class CustomTextParser(ArchiveMessageParser):
        name = "custom-text"
        msg_types = {"text"}

        def parse(self, message, payload, msg_type):
            return ArchiveParseResult(text_blocks=["custom text"])

    registry = ArchiveMessageParserRegistry(parsers=[CustomTextParser()])
    message = WecomArchiveMessage(
        id="archive_registry_001",
        corpId="ww_registry",
        seq=1,
        msgId="archive_registry_msg_001",
        action="send",
        fromUser="wm_customer",
        toList=["user_sales"],
        msgTime="2026-06-20T10:00:00+08:00",
        msgType="text",
        rawPayload={"msgtype": "text"},
        decryptedPayload={"msgtype": "text", "text": {"content": "hello"}},
        processed=False,
        createdAt=now_iso(),
        updatedAt=now_iso(),
    )

    result = registry.parse(message, message.decryptedPayload, "text")

    assert registry.supported_types() == ["text"]
    assert result.text_blocks == ["custom text"]
    assert result.metadata["archiveParser"] == "custom-text"
    assert result.metadata["archiveMsgType"] == "text"


def test_ocr_image_save_then_recognize_via_content_to_note(client):
    service = client.app.dependency_overrides[get_app_service]()
    login = client.post("/api/auth/mock-login", json={"nickname": "OCR 用户"}).json()["data"]
    image = Image.new("RGB", (200, 120), color="white")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)

    save_response = client.post(
        "/api/ocr/images",
        data={"ownerUserId": login["id"]},
        files={"file": ("house.png", buffer.getvalue(), "image/png")},
    )

    assert save_response.status_code == 200
    saved_payload = save_response.json()["data"]
    saved_note = saved_payload["note"]
    saved_config = saved_note["visibilityConfig"]
    assert saved_note["ownerUserId"] == login["id"]
    assert saved_note["status"] == "active"
    assert saved_note["coverUrl"].startswith("/media/")
    assert saved_config["sourceType"] == "ocr"
    assert saved_config["cardType"] == "image_ocr"
    assert saved_config["structuredData"]["ocr"]["status"] == "queued"
    assert saved_payload["syncTask"]["name"] == "ocr-recognize-note"

    service.ocr_service = OcrService(
        provider="mock",
        mock_text="小区：碧桂园城市之光\n户型：公寓一房\n面积：42平\n价格：1600元/月\n位置：万家丽地铁口",
    )
    run_test_background_queue(client)

    note = client.get(f"/api/notes/{saved_note['id']}", params={"ownerUserId": login["id"]}).json()["data"]
    config = note["visibilityConfig"]
    assert note["id"] == saved_note["id"]
    assert note["ownerUserId"] == login["id"]
    assert note["status"] == "active"
    assert note["coverUrl"].startswith("/media/")
    assert config["sourceType"] == "ocr"
    assert config["cardType"] == "property_listing"
    assert config["structuredData"]["ocr"]["status"] == "done"
    assert config["structuredData"]["ocr"]["text"].startswith("小区：碧桂园城市之光")
    assert config["structuredData"]["community"] == "碧桂园城市之光"
    assert "图片识别" in config["tags"]


def test_ocr_recognized_property_batch_creates_notes_and_showcase(client):
    service = client.app.dependency_overrides[get_app_service]()
    login = client.post("/api/auth/mock-login", json={"nickname": "OCR 批量房源用户"}).json()["data"]
    image = Image.new("RGB", (220, 140), color="white")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)
    save_response = client.post(
        "/api/ocr/images",
        data={"ownerUserId": login["id"]},
        files={"file": ("property-batch.png", buffer.getvalue(), "image/png")},
    )
    saved_payload = save_response.json()["data"]
    saved_note = saved_payload["note"]
    assert saved_payload["ocr"]["status"] == "queued"
    service.ocr_service = OcrService(
        provider="mock",
        mock_text="\n".join(
            [
                "挂牌",
                "1）松涛路200弄朝南次卧3000",
                "2）松涛路200弄50号301次卧3100",
                "3）汤臣四期大厅一室户3700",
                "电话15201882219。",
            ]
        ),
    )

    run_test_background_queue(client)

    notes = client.get("/api/notes", params={"ownerUserId": login["id"]}).json()["data"]
    property_notes = [
        item for item in notes
        if (item.get("visibilityConfig") or {}).get("sourceType") == "ocr_property_batch"
    ]
    assert len(property_notes) == 3
    source_note = client.get(f"/api/notes/{saved_note['id']}", params={"ownerUserId": login["id"]}).json()["data"]
    assert source_note["visibilityConfig"]["structuredData"]["ocr"]["status"] == "done"
    showcases = client.get("/api/showcases", params={"ownerUserId": login["id"]}).json()["data"]
    showcase_id = next(item["id"] for item in showcases if item["templateId"] == "property_batch_collection")
    showcase = client.get(
        f"/api/showcases/{showcase_id}",
        params={"ownerUserId": login["id"]},
    ).json()["data"]
    assert showcase["templateId"] == "property_batch_collection"
    assert len(showcase["items"]) == 3
    assert any(item["key"] == "price" for item in showcase["displayConfig"]["propertyFilters"])
    created_note = property_notes[0]
    assert created_note["coverUrl"].startswith("/media/")
    assert created_note["visibilityConfig"]["sourceType"] == "ocr_property_batch"
    assert created_note["visibilityConfig"]["ocrSourceNoteId"] == saved_note["id"]
    assert "图片识别" in created_note["visibilityConfig"]["tags"]


def test_ocr_table_like_low_yield_property_batch_waits_for_manual_review(client):
    service = client.app.dependency_overrides[get_app_service]()
    login = client.post("/api/auth/mock-login", json={"nickname": "OCR 表格低质用户"}).json()["data"]
    image = Image.new("RGB", (220, 140), color="white")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)
    save_response = client.post(
        "/api/ocr/images",
        data={"ownerUserId": login["id"]},
        files={"file": ("property-table.png", buffer.getvalue(), "image/png")},
    )
    saved_note = save_response.json()["data"]["note"]

    def fake_extract_text(content, filename=None):
        return OcrResult(
            text="\n".join(
                [
                    "君华爱房·房屋管家",
                    "2026.6.30房源更新",
                    "以下房源佣金最高可达50%",
                    "人民东路",
                    "府A2号号1031",
                    "3室1厅1卫",
                    "6号2508",
                    "室1厅1卫",
                    "君合天玺1号03",
                    "云集大厦1号1110",
                    "室1斤1卫",
                    "侯利美锦图3号181",
                    "室1厅1卫",
                    "联系电话：18073154517",
                ]
            ),
            provider="paddle",
            configured=True,
            confidence=0.81,
            details={"lineCount": 14},
        )

    service.ocr_service = OcrService(provider="paddle")
    service.ocr_service.extract_text = fake_extract_text

    run_test_background_queue(client)

    notes = client.get("/api/notes", params={"ownerUserId": login["id"]}).json()["data"]
    assert not [
        item for item in notes
        if (item.get("visibilityConfig") or {}).get("sourceType") == "ocr_property_batch"
    ]


def test_property_table_ocr_worker_creates_property_batch_notes(client):
    service = client.app.dependency_overrides[get_app_service]()
    login = client.post("/api/auth/mock-login", json={"nickname": "007 表格用户", "openid": "openid_property_table_ocr"}).json()["data"]
    image = Image.new("RGB", (260, 180), color="white")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)

    class FakePropertyTableOcr:
        def looks_like_property_table_image(self, content):
            return True

        def extract_text(self, content, filename=None):
            rows = [
                "芙蓉区 人民东路 碧桂园城市之光5号1016 1室1厅1卫 1,400.00",
                "雨花区 高桥 正荣悦玺1号2207B 1室1厅1卫 1,100.00",
                "天心区 金盆岭 云集大厦1号1110 1室1厅1卫 1,500.00",
                "开福区 开福寺 建鸿达现代公寓414南栋3号房 1室1厅1卫 1,350.00",
                "芙蓉区 五一广场 标志大厦606 1室1厅1卫 850.00",
                "芙蓉区 五一广场 标志大厦1508-1号房 1室1厅1卫 1,050.00",
                "芙蓉区 五一广场 标志大厦1508-8号房 1室1厅1卫 900.00",
                "芙蓉区 五一广场 标志大厦1508-5号房 1室1厅1卫 1,600.00",
            ]
            return OcrResult(
                text="\n".join(rows),
                provider="paddle-table",
                configured=True,
                confidence=0.91,
                details={"mode": "property-table-row-ocr", "lineCount": len(rows), "rowCount": len(rows)},
            )

    service.property_table_ocr_service = FakePropertyTableOcr()
    save_response = client.post(
        "/api/ocr/images",
        data={"ownerUserId": login["id"]},
        files={"file": ("007-table.png", buffer.getvalue(), "image/png")},
    )
    assert save_response.status_code == 200
    saved_payload = save_response.json()["data"]
    assert saved_payload["ocr"]["status"] == "queued"

    run_test_background_queue(client, delay=0.1)

    notes = client.get("/api/notes", params={"ownerUserId": login["id"]}).json()["data"]
    property_notes = [
        item for item in notes
        if (item.get("visibilityConfig") or {}).get("sourceType") == "ocr_property_table"
    ]
    assert len(property_notes) == 8
    assert any((item.get("visibilityConfig") or {}).get("structuredData", {}).get("price") == "1400元/月" for item in property_notes)
    source_note = client.get(f"/api/notes/{saved_payload['note']['id']}", params={"ownerUserId": login["id"]}).json()["data"]
    ocr_data = source_note["visibilityConfig"]["structuredData"]["ocr"]
    assert ocr_data["status"] == "done"
    assert ocr_data["provider"] == "paddle-table"
    showcases = client.get("/api/showcases", params={"ownerUserId": login["id"]}).json()["data"]
    assert any(item["templateId"] == "property_batch_collection" for item in showcases)


def test_note_image_capture_saves_image_without_recognition(client):
    login = client.post("/api/auth/mock-login", json={"nickname": "图片保存用户"}).json()["data"]
    image = Image.new("RGB", (180, 100), color="white")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)

    response = client.post(
        "/api/notes/image-capture",
        data={"ownerUserId": login["id"]},
        files={"file": ("plain-image.png", buffer.getvalue(), "image/png")},
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    note = payload["note"]
    config = note["visibilityConfig"]
    assert note["title"] == "图片资料"
    assert note["coverUrl"].startswith("/media/")
    assert config["cardType"] == "image_ocr"
    assert config["sourceType"] == "ocr"
    assert config["structuredData"]["ocr"]["status"] == "queued"
    assert payload["ocr"]["status"] == "queued"
    assert payload["syncTask"]["name"] == "ocr-recognize-note"


def test_ocr_unconfigured_keeps_saved_image_note(client):
    service = client.app.dependency_overrides[get_app_service]()
    service.ocr_service = OcrService(provider="none")
    login = client.post("/api/auth/mock-login", json={"nickname": "OCR 未配置用户"}).json()["data"]
    image = Image.new("RGB", (160, 90), color="white")
    buffer = BytesIO()
    image.save(buffer, format="PNG")

    save_response = client.post(
        "/api/ocr/images",
        data={"ownerUserId": login["id"]},
        files={"file": ("image.png", buffer.getvalue(), "image/png")},
    )
    note = save_response.json()["data"]["note"]

    run_test_background_queue(client)

    updated_note = client.get(f"/api/notes/{note['id']}", params={"ownerUserId": login["id"]}).json()["data"]
    config = updated_note["visibilityConfig"]
    assert updated_note["id"] == note["id"]
    assert updated_note["coverUrl"].startswith("/media/")
    assert config["cardType"] == "image_ocr"
    assert config["structuredData"]["ocr"]["status"] == "not_configured"
    assert config["structuredData"]["ocr"]["text"] == ""


def test_wecom_callback_get_verify(client):
    response = client.get(
        "/api/wecom/kf/teamBuy/callback",
        params={"token": settings.wecom_callback_token, "echostr": "hello-teamBuy"},
    )
    assert response.status_code == 200
    assert response.text == "hello-teamBuy"
    assert response.headers["content-type"].startswith("text/plain")


def test_wecom_callback_post_keeps_mock_fixture_import(client):
    response = client.post(
        "/api/wecom/kf/teamBuy/callback",
        json={"fixture": "link", "externalUserId": "external_callback", "conversationId": "conv_callback"},
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["callback"]["fixture"] == "link"
    assert len(payload["syncResult"]["importBatchIds"]) == 1


def test_wecom_callback_post_triggers_real_sync_when_mock_disabled(client, monkeypatch):
    class CallbackWecomClient:
        def __init__(self):
            self.sync_called = 0

        async def sync_msg(self, cursor=None, token=None, limit=None):
            self.sync_called += 1
            return {
                "errcode": 0,
                "errmsg": "ok",
                "next_cursor": "callback_cursor_done",
                "has_more": 0,
                "msg_list": [
                    {
                        "msgid": "callback_real_msg_001",
                        "open_kfid": "wk_callback",
                        "external_userid": "external_callback_real",
                        "send_time": 1780848000,
                        "msgtype": "text",
                        "text": {"content": "callback real sync item"},
                    }
                ],
            }

    fake_client = CallbackWecomClient()
    fake_queue = FakeSyncTaskQueue()
    monkeypatch.setattr(settings, "wecom_use_mock", False)
    monkeypatch.setattr(settings, "wecom_open_kfid", "wk_callback")
    client.app.dependency_overrides[get_wecom_client] = lambda: fake_client
    client.app.dependency_overrides[get_sync_task_queue] = lambda: fake_queue

    response = client.post("/api/wecom/kf/teamBuy/callback", json={"Event": "kf_msg_or_event"})

    assert response.status_code == 200
    payload = response.json()["data"]
    assert fake_client.sync_called == 0
    assert fake_queue.enqueued[0][0] == "wecom-callback-real-sync"
    assert fake_queue.enqueued[0][1] == {"maxPages": 10}
    assert payload["callback"]["Event"] == "kf_msg_or_event"
    assert payload["syncTask"]["status"] == "queued"


def test_wecom_sync_tasks_lists_background_queue(client):
    fake_queue = FakeSyncTaskQueue()
    client.app.dependency_overrides[get_sync_task_queue] = lambda: fake_queue

    response = client.get("/api/wecom/sync-tasks")

    assert response.status_code == 200
    assert response.json()["data"][0]["id"] == "sync_task_test"


def test_wecom_sync_task_logs_lists_background_queue_logs(client):
    fake_queue = FakeSyncTaskQueue()
    client.app.dependency_overrides[get_sync_task_queue] = lambda: fake_queue

    response = client.get("/api/wecom/sync-tasks/logs")

    assert response.status_code == 200
    assert response.json()["data"] == []


def test_wecom_config_check_reports_missing_real_fields(client, monkeypatch):
    monkeypatch.setattr(settings, "public_base_url", "https://teambuy.lifelove.top")
    response = client.get("/api/wecom/config-check")
    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload["success"], bool)
    assert isinstance(payload["data"]["missing"], list)
    assert payload["data"]["callbackUrl"].endswith("/api/wecom/kf/teamBuy/callback")


def test_wecom_customer_service_config_uses_existing_kf_env(client, monkeypatch):
    monkeypatch.setattr(settings, "wecom_corp_id", "ww_test_corp")
    monkeypatch.setattr(settings, "wecom_open_kfid", "wk_test_kf")
    response = client.get("/api/wecom/customer-service-config")
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["corpId"] == "ww_test_corp"
    assert payload["data"]["openKfid"] == "wk_test_kf"
    assert payload["data"]["extInfoUrl"] == "https://work.weixin.qq.com/kfid/wk_test_kf"
    assert payload["data"]["configured"] is True


def test_wecom_archive_callback_get_verify_reuses_callback_token(client, monkeypatch):
    monkeypatch.setattr(settings, "wecom_callback_token", "shared-token")
    monkeypatch.setattr(settings, "wecom_archive_callback_token", "shared-token")

    response = client.get(
        "/api/wecom/archive/callback",
        params={"token": "shared-token", "echostr": "hello-archive"},
    )

    assert response.status_code == 200
    assert response.text == "hello-archive"
    assert response.headers["content-type"].startswith("text/plain")


def test_wecom_archive_callback_rejects_wrong_token(client, monkeypatch):
    monkeypatch.setattr(settings, "wecom_callback_token", "shared-token")
    monkeypatch.setattr(settings, "wecom_archive_callback_token", "shared-token")

    response = client.get(
        "/api/wecom/archive/callback",
        params={"token": "wrong-token", "echostr": "hello-archive"},
    )

    assert response.status_code == 403


def test_wecom_archive_callback_post_accepts_event(client):
    response = client.post("/api/wecom/archive/callback", json={"Event": "archive_event"})

    assert response.status_code == 200
    assert response.json()["data"]["callback"]["Event"] == "archive_event"


def test_wecom_archive_config_check_reports_key_status(client, monkeypatch, tmp_path):
    private_key = tmp_path / "archive_private.pem"
    public_key = tmp_path / "archive_public.pem"
    private_key.write_text("PRIVATE KEY", encoding="utf-8")
    public_key.write_text("PUBLIC KEY", encoding="utf-8")
    monkeypatch.setattr(settings, "wecom_corp_id", "ww_archive")
    monkeypatch.setattr(settings, "wecom_archive_enabled", True)
    monkeypatch.setattr(settings, "wecom_archive_secret", "archive-secret")
    monkeypatch.setattr(settings, "wecom_archive_private_key_path", private_key)
    monkeypatch.setattr(settings, "wecom_archive_public_key_path", public_key)
    monkeypatch.setattr(settings, "wecom_archive_sdk_lib_path", None)

    response = client.get("/api/wecom/archive/config-check")

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["enabled"] is True
    assert payload["data"]["privateKeyReadable"] is True
    assert payload["data"]["publicKey"] == "PUBLIC KEY"
    assert payload["data"]["callbackUrl"].endswith("/api/wecom/archive/callback")
    assert payload["data"]["callbackTokenConfigured"] is True
    assert isinstance(payload["data"]["workerEnabled"], bool)
    assert isinstance(payload["data"]["workerIntervalSeconds"], int)
    assert payload["data"]["missing"] == []


def test_wecom_archive_messages_require_admin_token(client, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", "archive-admin")

    response = client.get("/api/wecom/archive/messages")

    assert response.status_code == 403


def test_wecom_archive_mock_messages_persist_cursor_and_dedupe(client, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", "archive-admin")
    monkeypatch.setattr(settings, "wecom_corp_id", "ww_archive")
    payload = {
        "messages": [
            {
                "seq": 101,
                "msgid": "archive_msg_001",
                "action": "send",
                "from": "wm_external",
                "tolist": ["zhangsan"],
                "msgtime": "2026-06-17T17:50:00+08:00",
                "msgtype": "text",
                "decryptedPayload": {"text": {"content": "客户发来一段资料"}},
            }
        ]
    }

    first = client.post("/api/wecom/archive/mock-messages", json=payload, headers={"X-Admin-Token": "archive-admin"})
    second = client.post("/api/wecom/archive/mock-messages", json=payload, headers={"X-Admin-Token": "archive-admin"})
    messages = client.get("/api/wecom/archive/messages", headers={"X-Admin-Token": "archive-admin"})
    cursor = client.get("/api/wecom/archive/cursor", headers={"X-Admin-Token": "archive-admin"})

    assert first.status_code == 200
    assert first.json()["data"]["savedCount"] == 1
    assert second.status_code == 200
    assert second.json()["data"]["savedCount"] == 0
    assert second.json()["data"]["skippedDuplicateCount"] == 1
    assert messages.status_code == 200
    assert len(messages.json()["data"]) == 1
    assert messages.json()["data"][0]["msgId"] == "archive_msg_001"
    assert cursor.status_code == 200
    assert cursor.json()["data"]["seq"] == 101


def test_wecom_archive_pull_reports_missing_sdk_config(client, monkeypatch):
    class MissingArchiveClient:
        corp_id = "ww_archive"

        def pull_and_decrypt(self, seq, limit):
            raise RuntimeError("会话内容存档 SDK 配置不完整: WECOM_ARCHIVE_SDK_LIB_PATH")

    monkeypatch.setattr(settings, "admin_token", "archive-admin")
    client.app.dependency_overrides[get_wecom_archive_client] = lambda: MissingArchiveClient()

    response = client.post("/api/wecom/archive/pull", headers={"X-Admin-Token": "archive-admin"})

    assert response.status_code == 502
    detail = response.json()["detail"]
    assert detail["message"] == "会话内容存档拉取失败"
    assert "WECOM_ARCHIVE_SDK_LIB_PATH" in detail["error"]
    assert detail["cursor"]["status"] == "failed"


def test_wecom_archive_pull_saves_decrypted_messages(client, monkeypatch):
    class FakeArchiveClient:
        corp_id = "ww_archive"

        def pull_and_decrypt(self, seq, limit):
            assert seq == 0
            assert limit == 20
            return {
                "rawCount": 1,
                "messages": [
                    {
                        "seq": 201,
                        "msgid": "archive_pull_msg_001",
                        "action": "send",
                        "from": "wm_customer",
                        "tolist": ["user_sales"],
                        "msgtime": 1781710904435,
                        "msgtype": "text",
                        "decryptedPayload": {
                            "msgid": "archive_pull_msg_001",
                            "action": "send",
                            "from": "wm_customer",
                            "tolist": ["user_sales"],
                            "msgtime": 1781710904435,
                            "msgtype": "text",
                            "text": {"content": "客户想看三房，总价 300 万，电话 13800000000"},
                        },
                    }
                ],
            }

    monkeypatch.setattr(settings, "admin_token", "archive-admin")
    client.app.dependency_overrides[get_wecom_archive_client] = lambda: FakeArchiveClient()

    response = client.post("/api/wecom/archive/pull", params={"limit": 20}, headers={"X-Admin-Token": "archive-admin"})
    messages = client.get("/api/wecom/archive/messages", headers={"X-Admin-Token": "archive-admin"})

    assert response.status_code == 200
    assert response.json()["data"]["savedCount"] == 1
    assert response.json()["data"]["cursor"]["seq"] == 201
    assert messages.json()["data"][0]["msgId"] == "archive_pull_msg_001"
    assert messages.json()["data"][0]["msgTime"].endswith("+08:00")


def test_wecom_archive_process_creates_user_note_and_is_idempotent(client, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", "archive-admin")
    payload = {
        "corpId": "ww_archive",
        "messages": [
            {
                "seq": 301,
                "msgid": "archive_process_msg_001",
                "action": "send",
                "from": "wm_customer",
                "tolist": ["user_sales"],
                "msgtime": "2026-06-17T18:40:00+08:00",
                "msgtype": "text",
                "decryptedPayload": {
                    "msgid": "archive_process_msg_001",
                    "action": "send",
                    "from": "wm_customer",
                    "tolist": ["user_sales"],
                    "msgtime": "2026-06-17T18:40:00+08:00",
                    "msgtype": "text",
                    "text": {"content": "客户要浦东两房，预算 500 万，电话 13900000000"},
                },
            }
        ],
    }
    saved = client.post("/api/wecom/archive/mock-messages", json=payload, headers={"X-Admin-Token": "archive-admin"})
    first = client.post("/api/wecom/archive/process", headers={"X-Admin-Token": "archive-admin"})
    second = client.post("/api/wecom/archive/process", headers={"X-Admin-Token": "archive-admin"})
    messages = client.get("/api/wecom/archive/messages", headers={"X-Admin-Token": "archive-admin"}).json()["data"]
    pending = client.get("/api/imports/pending").json()["data"]

    assert saved.status_code == 200
    assert first.status_code == 200
    assert first.json()["data"]["processedCount"] == 1
    processed = first.json()["data"]["processed"][0]
    note_id = processed["noteId"]
    notification = processed["notification"]
    assert notification["resultPath"].startswith("pages/import-claim/index?token=")
    assert notification["sendStatus"] == "pending"
    assert second.status_code == 200
    assert second.json()["data"]["processedCount"] == 0
    archive_message = next(item for item in messages if item["msgId"] == "archive_process_msg_001")
    assert archive_message["generatedNoteId"] == note_id
    generated = next(item for item in pending if item["generatedNote"] and item["generatedNote"]["id"] == note_id)
    assert generated["generatedNote"] is not None
    notifications = client.get("/api/wecom/notifications").json()["data"]
    saved_notification = next(item for item in notifications if item["id"] == notification["id"])
    assert saved_notification["resultPath"] == notification["resultPath"]


def test_wecom_archive_process_auto_assigns_bound_external_user(client, monkeypatch):
    login = client.post("/api/auth/mock-login", json={"nickname": "自动归属用户"}).json()["data"]
    client.post(
        "/api/wecom/mock-sync",
        json={"externalUserId": "wm_bound_customer", "conversationId": "conv_bound_claim", "fixture": "note"},
    )
    pending = client.get("/api/imports/pending").json()["data"]
    target = pending[-1]
    client.post(f"/api/imports/{target['id']}/claim", json={"userId": login["id"]})
    monkeypatch.setattr(settings, "admin_token", "archive-admin")
    payload = {
        "corpId": "ww_archive_bound",
        "messages": [
            {
                "seq": 303,
                "msgid": "archive_bound_msg_001",
                "action": "send",
                "from": "wm_bound_customer",
                "tolist": ["user_sales"],
                "msgtime": "2026-06-17T18:45:00+08:00",
                "msgtype": "text",
                "decryptedPayload": {
                    "msgid": "archive_bound_msg_001",
                    "action": "send",
                    "from": "wm_bound_customer",
                    "tolist": ["user_sales"],
                    "msgtime": "2026-06-17T18:45:00+08:00",
                    "msgtype": "text",
                    "text": {"content": "绑定后自动进入我的笔记"},
                },
            }
        ],
    }

    saved = client.post("/api/wecom/archive/mock-messages", json=payload, headers={"X-Admin-Token": "archive-admin"})
    processed = client.post("/api/wecom/archive/process", headers={"X-Admin-Token": "archive-admin"})
    notes = client.get("/api/notes", params={"ownerUserId": login["id"]}).json()["data"]
    pending_after = client.get("/api/imports/pending").json()["data"]

    assert saved.status_code == 200
    assert processed.status_code == 200
    result = processed.json()["data"]
    assert result["processedCount"] == 1
    note_id = result["processed"][0]["noteId"]
    assert any(item["id"] == note_id and item["ownerUserId"] == login["id"] for item in notes)
    assert not any(item["generatedNote"] and item["generatedNote"]["id"] == note_id for item in pending_after)


def test_wecom_identity_mapping_resolves_owner_by_openid(client):
    login = client.post(
        "/api/auth/mock-login",
        json={"nickname": "OpenID 用户", "openid": "openid_identity_owner"},
    ).json()["data"]
    service = client.app.dependency_overrides[get_app_service]()
    service.repo.save_wecom_identity_binding(
        WecomIdentityBinding(
            id="wecom_identity_openid_first",
            sourceType="wecom_external_user",
            externalUserId="external_openid_first",
            ownerUserId="stale_internal_user",
            ownerOpenid=login["openid"],
            bindSource="claim_import",
            firstImportBatchId=None,
            lastImportBatchId=None,
            createdAt=now_iso(),
            updatedAt=now_iso(),
        )
    )

    response = client.post(
        "/api/wecom/mock-sync",
        json={"externalUserId": "external_openid_first", "conversationId": "conv_openid_first", "fixture": "note"},
    )
    notes = client.get("/api/notes", params={"ownerUserId": login["id"]}).json()["data"]
    pending = client.get("/api/imports/pending").json()["data"]

    assert response.status_code == 200
    assert any("城南花园" in item["body"] and item["ownerUserId"] == login["id"] for item in notes)
    assert not any(item["externalUserId"] == "external_openid_first" for item in pending)


def test_wecom_bind_intent_auto_claims_first_unbound_message(client, monkeypatch):
    monkeypatch.setattr(settings, "wecom_bind_intent_ttl_seconds", 3600)
    user = client.post(
        "/api/auth/mock-login",
        json={"nickname": "准备绑定用户", "openid": "openid_wecom_bind_intent"},
    ).json()["data"]

    intent = client.post("/api/auth/wecom-bind-intent", json={"userId": user["id"]})
    response = client.post(
        "/api/wecom/mock-sync",
        json={"externalUserId": "external_bind_intent", "conversationId": "conv_bind_intent", "fixture": "note"},
    )
    notes = client.get("/api/notes", params={"ownerUserId": user["id"]}).json()["data"]
    pending = client.get("/api/imports/pending").json()["data"]
    service = client.app.dependency_overrides[get_app_service]()
    binding = service.repo.get_wecom_identity_binding("wecom_external_user", "external_bind_intent")
    state = service.repo.load()
    consumed = [
        item for item in state.wecom_identity_bindings
        if item.sourceType == "wecom_bind_intent" and item.bindSource == "consumed_assistant_bind"
    ]

    assert intent.status_code == 200
    assert response.status_code == 200
    assert binding is not None
    assert binding.ownerUserId == user["id"]
    assert binding.bindSource == "auto_bind_intent"
    assert consumed
    assert any(item["ownerUserId"] == user["id"] and "城南花园" in item["body"] for item in notes)
    assert not any(item["externalUserId"] == "external_bind_intent" for item in pending)


def test_wecom_bind_intent_does_not_auto_claim_when_multiple_active(client, monkeypatch):
    monkeypatch.setattr(settings, "wecom_bind_intent_ttl_seconds", 3600)
    user_a = client.post(
        "/api/auth/mock-login",
        json={"nickname": "绑定用户A", "openid": "openid_bind_a"},
    ).json()["data"]
    user_b = client.post(
        "/api/auth/mock-login",
        json={"nickname": "绑定用户B", "openid": "openid_bind_b"},
    ).json()["data"]
    client.post("/api/auth/wecom-bind-intent", json={"userId": user_a["id"]})
    client.post("/api/auth/wecom-bind-intent", json={"userId": user_b["id"]})

    response = client.post(
        "/api/wecom/mock-sync",
        json={"externalUserId": "external_bind_ambiguous", "conversationId": "conv_bind_ambiguous", "fixture": "note"},
    )
    pending = client.get("/api/imports/pending").json()["data"]
    service = client.app.dependency_overrides[get_app_service]()
    binding = service.repo.get_wecom_identity_binding("wecom_external_user", "external_bind_ambiguous")

    assert response.status_code == 200
    assert binding is None
    assert any(item["externalUserId"] == "external_bind_ambiguous" for item in pending)


def test_wecom_bind_code_binds_external_user_before_import(client, monkeypatch):
    monkeypatch.setattr(settings, "wecom_bind_intent_ttl_seconds", 3600)
    user = client.post(
        "/api/auth/mock-login",
        json={"nickname": "绑定码用户", "openid": "openid_bind_code"},
    ).json()["data"]
    intent = client.post("/api/auth/wecom-bind-intent", json={"userId": user["id"]}).json()["data"]
    service = client.app.dependency_overrides[get_app_service]()

    bind_response = service.trigger_sync_response_import(
        {
            "msg_list": [
                {
                    "msgid": "bind_code_msg_001",
                    "external_userid": "external_bind_code",
                    "token": "conv_bind_code",
                    "msgtype": "text",
                    "text": {"content": intent["bindMessage"]},
                }
            ]
        },
        notification_channel="mock",
    )
    import_response = client.post(
        "/api/wecom/mock-sync",
        json={"externalUserId": "external_bind_code", "conversationId": "conv_bind_code_note", "fixture": "note"},
    )
    notes = client.get("/api/notes", params={"ownerUserId": user["id"]}).json()["data"]
    pending = client.get("/api/imports/pending").json()["data"]
    binding = service.repo.get_wecom_identity_binding("wecom_external_user", "external_bind_code")

    assert bind_response["bindResult"]["status"] == "bound"
    assert bind_response["importBatchIds"] == []
    assert import_response.status_code == 200
    assert binding is not None
    assert binding.ownerUserId == user["id"]
    assert binding.bindSource == "bind_code"
    assert any(item["ownerUserId"] == user["id"] and "城南花园" in item["body"] for item in notes)
    assert not any(item["externalUserId"] == "external_bind_code" for item in pending)


def test_wecom_bind_intent_reuses_active_code_for_same_user(client, monkeypatch):
    monkeypatch.setattr(settings, "wecom_bind_intent_ttl_seconds", 3600)
    user = client.post(
        "/api/auth/mock-login",
        json={"nickname": "复用绑定码用户", "openid": "openid_bind_code_reuse"},
    ).json()["data"]

    first = client.post("/api/auth/wecom-bind-intent", json={"userId": user["id"]}).json()["data"]
    second = client.post("/api/auth/wecom-bind-intent", json={"userId": user["id"]}).json()["data"]

    assert first["status"] == "pending"
    assert second["status"] == "pending"
    assert second["reused"] is True
    assert second["intentId"] == first["intentId"]
    assert second["bindCode"] == first["bindCode"]
    assert second["bindMessage"] == first["bindMessage"]


def test_wecom_bind_intent_returns_bound_after_external_binding(client, monkeypatch):
    monkeypatch.setattr(settings, "wecom_bind_intent_ttl_seconds", 3600)
    user = client.post(
        "/api/auth/mock-login",
        json={"nickname": "已绑定用户", "openid": "openid_bind_code_done"},
    ).json()["data"]
    intent = client.post("/api/auth/wecom-bind-intent", json={"userId": user["id"]}).json()["data"]
    service = client.app.dependency_overrides[get_app_service]()

    service.trigger_sync_response_import(
        {
            "msg_list": [
                {
                    "msgid": "bind_code_done_msg_001",
                    "external_userid": "external_bind_code_done",
                    "token": "conv_bind_code_done",
                    "msgtype": "text",
                    "text": {"content": intent["bindMessage"]},
                }
            ]
        },
        notification_channel="mock",
    )
    after = client.post("/api/auth/wecom-bind-intent", json={"userId": user["id"]}).json()["data"]

    assert after["status"] == "bound"
    assert after["bound"] is True
    assert after["bindMessage"] == ""
    assert after["externalUserId"] == "external_bind_code_done"


def test_wecom_archive_bind_code_binds_external_user_before_note(client, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", "archive-admin")
    monkeypatch.setattr(settings, "wecom_bind_intent_ttl_seconds", 3600)
    user = client.post(
        "/api/auth/mock-login",
        json={"nickname": "归档绑定码用户", "openid": "openid_archive_bind_code"},
    ).json()["data"]
    intent = client.post("/api/auth/wecom-bind-intent", json={"userId": user["id"]}).json()["data"]
    payload = {
        "corpId": "ww_archive_bind_code",
        "messages": [
            {
                "seq": 351,
                "msgid": "archive_bind_code_text_001",
                "action": "send",
                "from": "wm_archive_bind_code",
                "tolist": ["user_sales"],
                "msgtime": 1781725160000,
                "msgtype": "text",
                "decryptedPayload": {
                    "msgtype": "text",
                    "text": {"content": intent["bindMessage"]},
                },
            },
            {
                "seq": 352,
                "msgid": "archive_bind_code_note_001",
                "action": "send",
                "from": "wm_archive_bind_code",
                "tolist": ["user_sales"],
                "msgtime": 1781725168000,
                "msgtype": "note",
                "decryptedPayload": {
                    "msgtype": "note",
                    "info": {
                        "items": [
                            {
                                "msg_type": "text",
                                "content": "{\"content\":\"小区：松涛路200弄\\n户型：朝南次卧\\n价格：3000\"}",
                            }
                        ]
                    },
                },
            },
        ],
    }

    saved = client.post("/api/wecom/archive/mock-messages", json=payload, headers={"X-Admin-Token": "archive-admin"})
    processed = client.post("/api/wecom/archive/process", headers={"X-Admin-Token": "archive-admin"})
    notes = client.get("/api/notes", params={"ownerUserId": user["id"]}).json()["data"]
    pending = client.get("/api/imports/pending").json()["data"]
    service = client.app.dependency_overrides[get_app_service]()
    binding = service.repo.get_wecom_identity_binding("wecom_external_user", "wm_archive_bind_code")

    assert saved.status_code == 200
    assert processed.status_code == 200
    assert binding is not None
    assert binding.ownerUserId == user["id"]
    assert binding.bindSource == "bind_code"
    assert any("松涛路200弄" in item["body"] for item in notes)
    assert not any(item["externalUserId"] == "wm_archive_bind_code" for item in pending)


def test_wecom_archive_import_auto_splits_property_batch_for_bound_user(client, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", "archive-admin")
    user = client.post(
        "/api/auth/mock-login",
        json={"nickname": "归档批量房源用户", "openid": "openid_archive_property_batch"},
    ).json()["data"]
    service = client.app.dependency_overrides[get_app_service]()
    service.repo.save_wecom_identity_binding(
        WecomIdentityBinding(
            id="binding_archive_property_batch",
            sourceType="wecom_external_user",
            externalUserId="wm_archive_property_batch",
            ownerUserId=user["id"],
            ownerOpenid=user["openid"],
            bindSource="test",
            createdAt=now_iso(),
            updatedAt=now_iso(),
        )
    )
    raw_text = "\n".join(
        [
            "挂牌",
            "1）松涛路200弄朝南次卧3000",
            "2）松涛路200弄50号301次卧3100",
            "3）汤臣四期次卧一室户3100",
            "4)玉兰4期122号1401次卧2500",
            "5)万科500号410一室户3500",
            "6）申源苑4号701主卧3380",
            "汤臣四期大厅一室户3700",
            "电话15201882219。",
        ]
    )
    payload = {
        "corpId": "ww_archive_property_batch",
        "messages": [
            {
                "seq": 361,
                "msgid": "archive_property_batch_001",
                "action": "send",
                "from": "wm_archive_property_batch",
                "tolist": ["user_sales"],
                "msgtime": 1781725170000,
                "msgtype": "text",
                "decryptedPayload": {
                    "msgtype": "text",
                    "text": {"content": raw_text},
                },
            }
        ],
    }

    saved = client.post("/api/wecom/archive/mock-messages", json=payload, headers={"X-Admin-Token": "archive-admin"})
    processed = client.post("/api/wecom/archive/process", headers={"X-Admin-Token": "archive-admin"})
    notes = client.get("/api/notes", params={"ownerUserId": user["id"]}).json()["data"]
    property_notes = [
        item for item in notes
        if (item.get("visibilityConfig") or {}).get("sourceType") == "property_batch_text"
    ]

    assert saved.status_code == 200
    assert processed.status_code == 200
    assert processed.json()["data"]["processed"][0]["propertyBatchCount"] == 7
    showcase_id = processed.json()["data"]["processed"][0]["showcaseId"]
    showcase = client.get(
        f"/api/showcases/{showcase_id}",
        params={"ownerUserId": user["id"]},
    ).json()["data"]
    assert showcase["templateId"] == "property_batch_collection"
    assert len(showcase["items"]) == 7
    filters = showcase["displayConfig"]["propertyFilters"]
    assert {item["key"] for item in filters} >= {"area", "layout", "price"}
    assert any(option["value"] == "次卧" for item in filters if item["key"] == "layout" for option in item["options"])
    assert len(property_notes) == 7
    assert any(item["title"] == "松涛路200弄 · 朝南次卧" for item in property_notes)
    assert any(item["title"] == "汤臣四期 · 大厅一室户" for item in property_notes)
    assert all(item["visibilityConfig"]["recognitionConfidence"]["level"] == "high" for item in property_notes)


def test_wecom_archive_process_parses_note_items(client, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", "archive-admin")
    payload = {
        "corpId": "ww_archive",
        "messages": [
            {
                "seq": 302,
                "msgid": "archive_note_msg_001",
                "action": "send",
                "from": "wm_customer",
                "tolist": ["user_sales"],
                "msgtime": 1781725151786,
                "msgtype": "note",
                "decryptedPayload": {
                    "msgid": "archive_note_msg_001",
                    "action": "send",
                    "from": "wm_customer",
                    "tolist": ["user_sales"],
                    "msgtime": 1781725151786,
                    "msgtype": "note",
                    "info": {
                        "items": [
                            {
                                "msg_type": "text",
                                "content": "{\"content\":\"小区：碧桂园城市之光\\n户型：公寓一房\\n价格：1600\"}",
                            },
                            {
                                "msg_type": "location",
                                "content": "{\"address\":\"湖南省长沙市雨花区嘉雨路碧桂园城市之光\",\"title\":\"碧桂园城市之光1栋\"}",
                            },
                            {
                                "msg_type": "image",
                                "content": "{\"md5sum\":\"img-md5\",\"filesize\":100063,\"sdkfileid\":\"sdk-file-001\"}",
                            },
                        ]
                    },
                },
            }
        ],
    }

    saved = client.post("/api/wecom/archive/mock-messages", json=payload, headers={"X-Admin-Token": "archive-admin"})
    processed = client.post("/api/wecom/archive/process", headers={"X-Admin-Token": "archive-admin"})
    pending = client.get("/api/imports/pending").json()["data"]

    assert saved.status_code == 200
    assert processed.status_code == 200
    assert processed.json()["data"]["processedCount"] == 1
    note_id = processed.json()["data"]["processed"][0]["noteId"]
    generated = next(item for item in pending if item["generatedNote"] and item["generatedNote"]["id"] == note_id)
    note = generated["generatedNote"]
    assert "碧桂园城市之光" in note["body"]
    assert "位置：湖南省长沙市雨花区嘉雨路碧桂园城市之光" in note["body"]
    assert note["media"][0]["mediaId"] == "sdk-file-001"


def test_wecom_archive_process_parses_groupbuy_chatrecord_items(client, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", "archive-admin")
    payload = {
        "corpId": "ww_archive_chatrecord_groupbuy",
        "messages": [
            {
                "seq": 303,
                "msgid": "archive_chatrecord_groupbuy_001",
                "action": "send",
                "from": "wm_customer",
                "tolist": ["user_sales"],
                "msgtime": 1781725152786,
                "msgtype": "chatrecord",
                "decryptedPayload": {
                    "msgid": "archive_chatrecord_groupbuy_001",
                    "action": "send",
                    "from": "wm_customer",
                    "tolist": ["user_sales"],
                    "msgtime": 1781725152786,
                    "msgtype": "chatrecord",
                    "chatrecord": {
                        "title": "群聊的聊天记录",
                        "item": [
                            {
                                "type": "ChatRecordText",
                                "content": "{\"content\":\"连续一个月，鸡蛋行情都是上涨状态，活动也是给大家争取了很久，还有优惠。4斤不多，约40多个，会配小礼篮。\"}",
                                "msgtime": 1779852781,
                            },
                            {
                                "type": "ChatRecordText",
                                "content": "{\"content\":\"[图片]\"}",
                                "msgtime": 1779852783,
                            },
                            {
                                "type": "ChatRecordText",
                                "content": "{\"content\":\"挑食宝宝救星来啦！\\n我们的白凤乌鸡蛋\\n精选种鸡，白凤乌鸡\\n简单一煮，蛋香十足\"}",
                                "msgtime": 1779852800,
                            },
                        ],
                    },
                },
            }
        ],
    }

    saved = client.post("/api/wecom/archive/mock-messages", json=payload, headers={"X-Admin-Token": "archive-admin"})
    processed = client.post("/api/wecom/archive/process", headers={"X-Admin-Token": "archive-admin"})
    pending = client.get("/api/imports/pending").json()["data"]

    assert saved.status_code == 200
    assert processed.status_code == 200
    assert processed.json()["data"]["processedCount"] == 1
    note_id = processed.json()["data"]["processed"][0]["noteId"]
    generated = next(item for item in pending if item["generatedNote"] and item["generatedNote"]["id"] == note_id)
    note = generated["generatedNote"]
    config = note["visibilityConfig"]
    assert "白凤乌鸡蛋" in note["body"]
    assert "[图片]" not in note["body"]
    assert config["cardType"] == "groupbuy_product"
    assert config["systemCategory"] == "团购"
    assert config["structuredData"]["productName"] == "白凤乌鸡蛋"
    assert config["structuredData"]["spec"] == "4斤，约40多个"


def test_wecom_archive_process_handles_miniapp_card(client, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", "archive-admin")
    payload = {
        "corpId": "ww_archive",
        "messages": [
            {
                "seq": 305,
                "msgid": "archive_weapp_msg_001",
                "action": "send",
                "from": "wm_customer_weapp",
                "tolist": ["user_sales"],
                "msgtime": "2026-06-19T02:41:16+08:00",
                "msgtype": "weapp",
                "decryptedPayload": {
                    "msgid": "archive_weapp_msg_001",
                    "action": "send",
                    "from": "wm_customer_weapp",
                    "tolist": ["user_sales"],
                    "msgtime": "2026-06-19T02:41:16+08:00",
                    "msgtype": "weapp",
                    "weapp": {
                        "appid": "wxcfd8224218167d98",
                        "title": "三江尊园 全天采光 好楼层 拎包入住",
                        "pagepath": "subpackages/ershoufang/pages/esfDetail/esfDetail.html?cityId=150200&houseCode=101137825091&source=share_beikexcx",
                        "username": "gh_2dbd87cb164c@app",
                        "description": "贝壳找房丨二手房新房租房装修",
                        "displayname": "贝壳找房丨二手房新房租房装修",
                    },
                },
            }
        ],
    }

    saved = client.post("/api/wecom/archive/mock-messages", json=payload, headers={"X-Admin-Token": "archive-admin"})
    processed = client.post("/api/wecom/archive/process", headers={"X-Admin-Token": "archive-admin"})
    pending = client.get("/api/imports/pending").json()["data"]

    assert saved.status_code == 200
    assert processed.status_code == 200
    assert processed.json()["data"]["processedCount"] == 1
    note_id = processed.json()["data"]["processed"][0]["noteId"]
    generated = next(item for item in pending if item["generatedNote"] and item["generatedNote"]["id"] == note_id)
    note = generated["generatedNote"]
    config = note["visibilityConfig"]
    assert generated["sourceType"] == "miniapp_link"
    assert note["title"] == "三江尊园 全天采光 好楼层 拎包入住"
    assert "小程序来源：贝壳找房" in note["body"]
    assert "房源编码：101137825091" in note["body"]
    assert "小程序路径：" not in note["body"]
    assert note["phone"] is None
    assert config["sourceType"] == "miniapp"
    assert config["showPhone"] is False
    assert config["systemCategory"] == "小程序"
    assert "小程序" in config["tags"]
    assert "贝壳找房" in config["tags"]
    suggestion = next(item for item in config["typeSuggestions"] if item["cardType"] == "property_listing")
    assert suggestion["reason"]
    assert "score" in suggestion
    assert config["recognitionExplanation"]["level"] == "medium"
    assert config["recognitionExplanation"]["selectedType"] == "text_note"
    assert any(item["cardType"] == "property_listing" for item in config["recognitionExplanation"]["candidates"])
    assert config["structuredData"]["miniapp"]["houseCode"] == "101137825091"
    assert config["structuredData"]["miniapp"]["pagePath"].startswith("subpackages/ershoufang/pages/esfDetail")
    assert config["structuredData"]["miniapp"]["webUrl"] == "https://m.ke.com/baotou/ershoufang/101137825091.html"
    assert config["sourceUrl"] == "https://m.ke.com/baotou/ershoufang/101137825091.html"
    assert config["conversionConfig"]["enableLightScrm"] is True
    assert config["conversionConfig"]["collectLeads"] is True
    assert config["conversionConfig"]["enableAppointment"] is True
    assert config["conversionConfig"]["enablePrivateConsultation"] is True
    assert config["conversionConfig"]["showContactPhone"] is False

    login = client.post("/api/auth/mock-login", json={"nickname": "房源确认用户"}).json()["data"]
    claim = client.post(f"/api/imports/{generated['id']}/claim", json={"userId": login["id"]})
    confirmed = client.post(
        f"/api/notes/{claim.json()['data']['note']['id']}/confirm-type",
        json={"ownerUserId": login["id"], "cardType": "property_listing"},
    )

    assert confirmed.status_code == 200
    confirmed_config = confirmed.json()["data"]["visibilityConfig"]
    assert confirmed_config["cardType"] == "property_listing"
    assert confirmed_config["cardState"] == "generated"
    assert confirmed_config["typeSuggestions"] == []
    assert confirmed_config["recognitionConfidence"]["level"] == "manual"
    assert confirmed_config["recognitionExplanation"]["manualConfirmation"]["cardType"] == "property_listing"
    assert confirmed_config["structuredData"]["miniapp"]["houseCode"] == "101137825091"
    assert confirmed_config["conversionConfig"]["showContactPhone"] is False


def test_wecom_archive_process_groups_nearby_messages(client, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", "archive-admin")
    payload = {
        "corpId": "ww_archive",
        "messages": [
            {
                "seq": 401,
                "msgid": "archive_group_text_001",
                "action": "send",
                "from": "wm_customer",
                "tolist": ["user_sales"],
                "msgtime": 1781725200000,
                "msgtype": "text",
                "decryptedPayload": {
                    "msgid": "archive_group_text_001",
                    "action": "send",
                    "from": "wm_customer",
                    "tolist": ["user_sales"],
                    "msgtime": 1781725200000,
                    "msgtype": "text",
                    "text": {"content": "房源：碧桂园一房，租金1600"},
                },
            },
            {
                "seq": 402,
                "msgid": "archive_group_image_001",
                "action": "send",
                "from": "wm_customer",
                "tolist": ["user_sales"],
                "msgtime": 1781725203000,
                "msgtype": "image",
                "decryptedPayload": {
                    "msgid": "archive_group_image_001",
                    "action": "send",
                    "from": "wm_customer",
                    "tolist": ["user_sales"],
                    "msgtime": 1781725203000,
                    "msgtype": "image",
                    "image": {"sdkfileid": "image-sdk-file", "md5sum": "image-md5", "filesize": 1024},
                },
            },
        ],
    }

    saved = client.post("/api/wecom/archive/mock-messages", json=payload, headers={"X-Admin-Token": "archive-admin"})
    processed = client.post("/api/wecom/archive/process", headers={"X-Admin-Token": "archive-admin"})
    pending = client.get("/api/imports/pending").json()["data"]

    assert saved.status_code == 200
    assert processed.status_code == 200
    result = processed.json()["data"]
    assert result["processedCount"] == 1
    assert result["processed"][0]["seqs"] == [401, 402]
    note_id = result["processed"][0]["noteId"]
    generated = next(item for item in pending if item["generatedNote"] and item["generatedNote"]["id"] == note_id)
    assert len(generated["rawMessageIds"]) == 2
    assert "房源：碧桂园一房" in generated["generatedNote"]["body"]
    assert generated["generatedNote"]["media"][0]["mediaId"] == "image-sdk-file"


def test_wecom_archive_process_downloads_and_attaches_image_media(client, monkeypatch, tmp_path):
    class FakeArchiveClient:
        def __init__(self):
            self.downloaded_media_ids = []

        def download_media(self, media_id):
            self.downloaded_media_ids.append(media_id)
            return DownloadedMedia(make_test_image_bytes(), "image/png", "archive-cover.png")

    monkeypatch.setattr(settings, "admin_token", "archive-admin")
    service = client.app.dependency_overrides[get_app_service]()
    media_dir = tmp_path / "archive-media"
    service.media_storage_service = MediaStorageService("local", media_dir, "/media")
    fake_archive_client = FakeArchiveClient()
    client.app.dependency_overrides[get_wecom_archive_client] = lambda: fake_archive_client
    payload = {
        "corpId": "ww_archive_media",
        "messages": [
            {
                "seq": 501,
                "msgid": "archive_media_text_001",
                "action": "send",
                "from": "wm_customer",
                "tolist": ["user_sales"],
                "msgtime": 1781725300000,
                "msgtype": "text",
                "decryptedPayload": {
                    "msgid": "archive_media_text_001",
                    "action": "send",
                    "from": "wm_customer",
                    "tolist": ["user_sales"],
                    "msgtime": 1781725300000,
                    "msgtype": "text",
                    "text": {"content": "带图房源：碧桂园一房"},
                },
            },
            {
                "seq": 502,
                "msgid": "archive_media_image_001",
                "action": "send",
                "from": "wm_customer",
                "tolist": ["user_sales"],
                "msgtime": 1781725302000,
                "msgtype": "image",
                "decryptedPayload": {
                    "msgid": "archive_media_image_001",
                    "action": "send",
                    "from": "wm_customer",
                    "tolist": ["user_sales"],
                    "msgtime": 1781725302000,
                    "msgtype": "image",
                    "image": {"sdkfileid": "archive-image-sdk-001", "md5sum": "image-md5", "filesize": 1024},
                },
            },
        ],
    }

    saved = client.post("/api/wecom/archive/mock-messages", json=payload, headers={"X-Admin-Token": "archive-admin"})
    processed = client.post("/api/wecom/archive/process", headers={"X-Admin-Token": "archive-admin"})
    pending = client.get("/api/imports/pending").json()["data"]

    assert saved.status_code == 200
    assert processed.status_code == 200
    result = processed.json()["data"]
    assert result["processedCount"] == 1
    assert result["processed"][0]["media"]["downloadedCount"] == 1
    assert fake_archive_client.downloaded_media_ids == ["archive-image-sdk-001"]
    note_id = result["processed"][0]["noteId"]
    generated = next(item for item in pending if item["generatedNote"] and item["generatedNote"]["id"] == note_id)
    note = generated["generatedNote"]
    card = generated["generatedCard"]
    assert note["media"][0]["url"].startswith("/media/")
    assert note["media"][0]["url"].endswith(".webp")
    assert card["coverUrl"] == note["media"][0]["url"]
    assert card["media"][0]["url"] == note["media"][0]["url"]
    assert len(list(media_dir.iterdir())) == 1


def test_wecom_archive_pure_image_saves_pending_ocr_note(client, monkeypatch, tmp_path):
    class FakeArchiveClient:
        def download_media(self, media_id):
            return DownloadedMedia(make_test_image_bytes(), "image/png", "archive-ocr.png")

    monkeypatch.setattr(settings, "admin_token", "archive-admin")
    service = client.app.dependency_overrides[get_app_service]()
    media_dir = tmp_path / "archive-ocr-media"
    service.media_storage_service = MediaStorageService("local", media_dir, "/media")
    client.app.dependency_overrides[get_wecom_archive_client] = lambda: FakeArchiveClient()
    payload = {
        "corpId": "ww_archive_ocr_image",
        "messages": [
            {
                "seq": 505,
                "msgid": "archive_ocr_image_001",
                "action": "send",
                "from": "wm_customer",
                "tolist": ["user_sales"],
                "msgtime": 1781725350000,
                "msgtype": "image",
                "decryptedPayload": {
                    "msgid": "archive_ocr_image_001",
                    "action": "send",
                    "from": "wm_customer",
                    "tolist": ["user_sales"],
                    "msgtime": 1781725350000,
                    "msgtype": "image",
                    "image": {"sdkfileid": "archive-ocr-image-sdk", "md5sum": "image-md5", "filesize": 1024},
                },
            },
        ],
    }

    saved = client.post("/api/wecom/archive/mock-messages", json=payload, headers={"X-Admin-Token": "archive-admin"})
    processed = client.post("/api/wecom/archive/process", headers={"X-Admin-Token": "archive-admin"})
    pending = client.get("/api/imports/pending").json()["data"]

    assert saved.status_code == 200
    assert processed.status_code == 200
    result = processed.json()["data"]
    assert result["processedCount"] == 1
    assert result["processed"][0]["media"]["downloadedCount"] == 1
    note_id = result["processed"][0]["noteId"]
    generated = next(item for item in pending if item["generatedNote"] and item["generatedNote"]["id"] == note_id)
    note = generated["generatedNote"]
    card = generated["generatedCard"]
    config = note["visibilityConfig"]
    assert note["body"].startswith("图片已保存")
    assert note["media"][0]["mediaId"] == "archive-ocr-image-sdk"
    assert note["media"][0]["url"].startswith("/media/")
    assert card["coverUrl"] == note["media"][0]["url"]
    assert config["cardType"] == "image_ocr"
    assert config["sourceType"] == "ocr"
    assert config["structuredData"]["ocr"]["status"] == "pending"


def test_wecom_archive_media_download_failure_keeps_note_and_records_retry(client, monkeypatch):
    class FailingArchiveClient:
        def download_media(self, media_id):
            raise RuntimeError("temporary archive media failure")

    monkeypatch.setattr(settings, "admin_token", "archive-admin")
    client.app.dependency_overrides[get_wecom_archive_client] = lambda: FailingArchiveClient()
    payload = {
        "corpId": "ww_archive_media_failed",
        "messages": [
            {
                "seq": 511,
                "msgid": "archive_media_failed_text_001",
                "action": "send",
                "from": "wm_customer",
                "tolist": ["user_sales"],
                "msgtime": 1781725400000,
                "msgtype": "text",
                "decryptedPayload": {
                    "msgid": "archive_media_failed_text_001",
                    "action": "send",
                    "from": "wm_customer",
                    "tolist": ["user_sales"],
                    "msgtime": 1781725400000,
                    "msgtype": "text",
                    "text": {"content": "图片先失败，文字仍要入库"},
                },
            },
            {
                "seq": 512,
                "msgid": "archive_media_failed_image_001",
                "action": "send",
                "from": "wm_customer",
                "tolist": ["user_sales"],
                "msgtime": 1781725401000,
                "msgtype": "image",
                "decryptedPayload": {
                    "msgid": "archive_media_failed_image_001",
                    "action": "send",
                    "from": "wm_customer",
                    "tolist": ["user_sales"],
                    "msgtime": 1781725401000,
                    "msgtype": "image",
                    "image": {"sdkfileid": "archive-image-sdk-failed", "md5sum": "image-md5", "filesize": 1024},
                },
            },
        ],
    }

    saved = client.post("/api/wecom/archive/mock-messages", json=payload, headers={"X-Admin-Token": "archive-admin"})
    processed = client.post("/api/wecom/archive/process", headers={"X-Admin-Token": "archive-admin"})
    pending = client.get("/api/imports/pending").json()["data"]
    retries = client.get("/api/wecom/media-retries", headers={"X-Admin-Token": "archive-admin"}).json()["data"]

    assert saved.status_code == 200
    assert processed.status_code == 200
    result = processed.json()["data"]
    assert result["processedCount"] == 1
    assert result["processed"][0]["media"]["failedCount"] == 1
    note_id = result["processed"][0]["noteId"]
    generated = next(item for item in pending if item["generatedNote"] and item["generatedNote"]["id"] == note_id)
    assert "图片先失败" in generated["generatedNote"]["body"]
    assert generated["generatedNote"]["media"][0]["mediaId"] == "archive-image-sdk-failed"
    assert generated["generatedNote"]["media"][0]["url"] is None
    assert retries[-1]["mediaId"] == "archive-image-sdk-failed"
    assert retries[-1]["status"] == "failed"


def test_wecom_archive_media_backfill_updates_existing_note_and_card(client, monkeypatch, tmp_path):
    class FailingArchiveClient:
        def download_media(self, media_id):
            raise RuntimeError("temporary archive media failure")

    class SuccessfulArchiveClient:
        def __init__(self):
            self.downloaded_media_ids = []

        def download_media(self, media_id):
            self.downloaded_media_ids.append(media_id)
            return DownloadedMedia(make_test_image_bytes(), "image/png", "archive-backfill.png")

    monkeypatch.setattr(settings, "admin_token", "archive-admin")
    service = client.app.dependency_overrides[get_app_service]()
    media_dir = tmp_path / "archive-backfill-media"
    service.media_storage_service = MediaStorageService("local", media_dir, "/media")
    client.app.dependency_overrides[get_wecom_archive_client] = lambda: FailingArchiveClient()
    payload = {
        "corpId": "ww_archive_media_backfill",
        "messages": [
            {
                "seq": 521,
                "msgid": "archive_media_backfill_text_001",
                "action": "send",
                "from": "wm_customer",
                "tolist": ["user_sales"],
                "msgtime": 1781725500000,
                "msgtype": "text",
                "decryptedPayload": {
                    "msgid": "archive_media_backfill_text_001",
                    "action": "send",
                    "from": "wm_customer",
                    "tolist": ["user_sales"],
                    "msgtime": 1781725500000,
                    "msgtype": "text",
                    "text": {"content": "历史图片需要回填"},
                },
            },
            {
                "seq": 522,
                "msgid": "archive_media_backfill_image_001",
                "action": "send",
                "from": "wm_customer",
                "tolist": ["user_sales"],
                "msgtime": 1781725501000,
                "msgtype": "image",
                "decryptedPayload": {
                    "msgid": "archive_media_backfill_image_001",
                    "action": "send",
                    "from": "wm_customer",
                    "tolist": ["user_sales"],
                    "msgtime": 1781725501000,
                    "msgtype": "image",
                    "image": {"sdkfileid": "archive-image-sdk-backfill", "md5sum": "image-md5", "filesize": 1024},
                },
            },
        ],
    }

    saved = client.post("/api/wecom/archive/mock-messages", json=payload, headers={"X-Admin-Token": "archive-admin"})
    processed = client.post("/api/wecom/archive/process", headers={"X-Admin-Token": "archive-admin"})
    note_id = processed.json()["data"]["processed"][0]["noteId"]
    pending_before = client.get("/api/imports/pending").json()["data"]
    generated_before = next(item for item in pending_before if item["generatedNote"] and item["generatedNote"]["id"] == note_id)
    assert saved.status_code == 200
    assert generated_before["generatedNote"]["media"][0]["url"] is None
    assert generated_before["generatedCard"]["media"] == []

    successful_client = SuccessfulArchiveClient()
    client.app.dependency_overrides[get_wecom_archive_client] = lambda: successful_client
    backfilled = client.post(
        "/api/wecom/archive/media-backfill",
        params={"limit": 10},
        headers={"X-Admin-Token": "archive-admin"},
    )
    pending_after = client.get("/api/imports/pending").json()["data"]
    generated_after = next(item for item in pending_after if item["generatedNote"] and item["generatedNote"]["id"] == note_id)

    assert backfilled.status_code == 200
    result = backfilled.json()["data"]
    assert result["downloadedCount"] == 1
    assert result["updatedNoteCount"] == 1
    assert result["updatedCardCount"] == 1
    assert successful_client.downloaded_media_ids == ["archive-image-sdk-backfill"]
    assert generated_after["generatedNote"]["media"][0]["url"].startswith("/media/")
    assert generated_after["generatedCard"]["coverUrl"] == generated_after["generatedNote"]["media"][0]["url"]
    assert generated_after["generatedCard"]["media"][0]["url"] == generated_after["generatedNote"]["media"][0]["url"]
    assert len(list(media_dir.iterdir())) == 1


def test_real_sync_uses_mock_real_response_while_mock_enabled(client):
    response = client.post("/api/wecom/real-sync")
    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["source"] == "mock-real-sync-response"
    assert payload["pagesSynced"] == 1
    assert payload["nextCursor"] == "mock_real_cursor_002"
    assert payload["hasMore"] is False
    assert len(payload["importResult"]["importBatchIds"]) >= 1


def test_real_sync_mock_response_is_idempotent(client):
    first = client.post("/api/wecom/real-sync")
    second = client.post("/api/wecom/real-sync")

    assert first.status_code == 200
    assert second.status_code == 200
    second_payload = second.json()["data"]["importResult"]
    assert second_payload["importBatchIds"] == []
    assert second_payload["deduplicatedCount"] == 4


def test_real_sync_paginates_and_persists_cursor(client, monkeypatch):
    class FakeWecomClient:
        def __init__(self):
            self.cursors = []

        async def sync_msg(self, cursor=None, token=None, limit=None):
            self.cursors.append(cursor)
            if cursor is None:
                return {
                    "errcode": 0,
                    "errmsg": "ok",
                    "next_cursor": "cursor_page_2",
                    "has_more": 1,
                    "msg_list": [
                        {
                            "msgid": "paged_msg_001",
                            "open_kfid": "wk_page",
                            "external_userid": "external_page",
                            "send_time": 1780848000,
                            "msgtype": "text",
                            "text": {"content": "first page item"},
                        }
                    ],
                }
            return {
                "errcode": 0,
                "errmsg": "ok",
                "next_cursor": "cursor_done",
                "has_more": 0,
                "msg_list": [
                    {
                        "msgid": "paged_msg_002",
                        "open_kfid": "wk_page",
                        "external_userid": "external_page",
                        "send_time": 1780848010,
                        "msgtype": "link",
                        "link": {"title": "second page item", "url": "https://example.com/page-2"},
                    }
                ],
            }

    fake_client = FakeWecomClient()
    monkeypatch.setattr(settings, "wecom_use_mock", False)
    monkeypatch.setattr(settings, "wecom_open_kfid", "wk_page")
    client.app.dependency_overrides[get_wecom_client] = lambda: fake_client

    response = client.post("/api/wecom/real-sync")

    assert response.status_code == 200
    payload = response.json()["data"]
    assert fake_client.cursors == [None, "cursor_page_2"]
    assert payload["pagesSynced"] == 2
    assert payload["nextCursor"] == "cursor_done"
    assert payload["hasMore"] is False
    assert len(payload["importResult"]["importBatchIds"]) == 2


def test_real_sync_downloads_and_stores_image_video_media(client, monkeypatch, tmp_path):
    class FakeWecomClient:
        def __init__(self):
            self.downloaded_media_ids = []

        async def sync_msg(self, cursor=None, token=None, limit=None):
            return {
                "errcode": 0,
                "errmsg": "ok",
                "next_cursor": "cursor_media_done",
                "has_more": 0,
                "msg_list": [
                    {
                        "msgid": "media_msg_text",
                        "open_kfid": "wk_media",
                        "external_userid": "external_media",
                        "send_time": 1780848000,
                        "msgtype": "text",
                        "text": {"content": "media item with phone 13700000000"},
                    },
                    {
                        "msgid": "media_msg_image",
                        "open_kfid": "wk_media",
                        "external_userid": "external_media",
                        "send_time": 1780848001,
                        "msgtype": "image",
                        "image": {"media_id": "media_image_001", "filename": "cover.png"},
                    },
                    {
                        "msgid": "media_msg_video",
                        "open_kfid": "wk_media",
                        "external_userid": "external_media",
                        "send_time": 1780848002,
                        "msgtype": "video",
                        "video": {"media_id": "media_video_001", "filename": "room.mp4"},
                    },
                ],
            }

        async def download_media(self, media_id):
            self.downloaded_media_ids.append(media_id)
            if media_id == "media_image_001":
                return DownloadedMedia(b"image-bytes", "image/png", "cover.png")
            return DownloadedMedia(b"video-bytes", "video/mp4", "room.mp4")

    service = client.app.dependency_overrides[get_app_service]()
    media_dir = tmp_path / "media"
    service.media_storage_service = MediaStorageService(
        storage_mode="local",
        storage_dir=media_dir,
        public_url_prefix="/media",
    )
    fake_client = FakeWecomClient()
    monkeypatch.setattr(settings, "wecom_use_mock", False)
    monkeypatch.setattr(settings, "wecom_open_kfid", "wk_media")
    client.app.dependency_overrides[get_wecom_client] = lambda: fake_client

    response = client.post("/api/wecom/real-sync")

    assert response.status_code == 200
    assert set(fake_client.downloaded_media_ids) == {"media_image_001", "media_video_001"}
    pending = client.get("/api/imports/pending").json()["data"]
    card = pending[-1]["generatedCard"]
    assert card["coverUrl"].startswith("/media/")
    assert any(item["type"] == "video" and item["url"].startswith("/media/") for item in card["media"])
    assert len(list(media_dir.iterdir())) == 2


def test_real_sync_pure_image_saves_pending_ocr_note(client, monkeypatch, tmp_path):
    class FakeWecomClient:
        async def sync_msg(self, cursor=None, token=None, limit=None):
            return {
                "errcode": 0,
                "errmsg": "ok",
                "next_cursor": "cursor_ocr_image_done",
                "has_more": 0,
                "msg_list": [
                    {
                        "msgid": "ocr_image_msg",
                        "open_kfid": "wk_ocr_image",
                        "external_userid": "external_ocr_image",
                        "send_time": 1780848010,
                        "msgtype": "image",
                        "image": {"media_id": "media_ocr_image_001", "filename": "chat-screenshot.png"},
                    },
                ],
            }

        async def download_media(self, media_id):
            return DownloadedMedia(make_test_image_bytes(), "image/png", "chat-screenshot.png")

    monkeypatch.setattr(settings, "wecom_use_mock", False)
    monkeypatch.setattr(settings, "wecom_open_kfid", "wk_ocr_image")
    service = client.app.dependency_overrides[get_app_service]()
    media_dir = tmp_path / "ocr-image-media"
    service.media_storage_service = MediaStorageService("local", media_dir, "/media")
    client.app.dependency_overrides[get_wecom_client] = lambda: FakeWecomClient()

    response = client.post("/api/wecom/real-sync")

    assert response.status_code == 200
    pending = client.get("/api/imports/pending").json()["data"]
    latest = pending[-1]
    note = latest["generatedNote"]
    card = latest["generatedCard"]
    config = note["visibilityConfig"]
    assert note["body"].startswith("图片已保存")
    assert note["media"][0]["mediaId"] == "media_ocr_image_001"
    assert note["media"][0]["url"].startswith("/media/")
    assert card["coverUrl"] == note["media"][0]["url"]
    assert config["cardType"] == "image_ocr"
    assert config["sourceType"] == "ocr"
    assert config["structuredData"]["ocr"]["status"] == "pending"
    assert config["structuredData"]["images"] == [note["media"][0]["url"]]


def test_real_sync_records_media_retry_job_without_blocking_import(client, monkeypatch):
    class FailingWecomClient:
        async def sync_msg(self, cursor=None, token=None, limit=None):
            return {
                "errcode": 0,
                "errmsg": "ok",
                "next_cursor": "cursor_media_failed",
                "has_more": 0,
                "msg_list": [
                    {
                        "msgid": "media_failed_text",
                        "open_kfid": "wk_media_failed",
                        "external_userid": "external_media_failed",
                        "send_time": 1780847999,
                        "msgtype": "text",
                        "text": {"content": "导入文字仍应生成草稿"},
                    },
                    {
                        "msgid": "media_failed_image",
                        "open_kfid": "wk_media_failed",
                        "external_userid": "external_media_failed",
                        "send_time": 1780848000,
                        "msgtype": "image",
                        "image": {"media_id": "media_failed_001", "filename": "cover.png"},
                    }
                ],
            }

        async def download_media(self, media_id):
            from app.services.wecom_client import WecomClientError

            raise WecomClientError("temporary media download failed")

    monkeypatch.setattr(settings, "wecom_use_mock", False)
    monkeypatch.setattr(settings, "wecom_open_kfid", "wk_media_failed")
    client.app.dependency_overrides[get_wecom_client] = lambda: FailingWecomClient()

    response = client.post("/api/wecom/real-sync")

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["importResult"]["importBatchIds"]
    retries = client.get("/api/wecom/media-retries").json()["data"]
    assert retries[-1]["mediaId"] == "media_failed_001"
    assert retries[-1]["status"] == "failed"
    assert retries[-1]["attempts"] == 1
    pending = client.get("/api/imports/pending").json()["data"]
    card = pending[-1]["generatedCard"]
    assert card["title"] == "导入文字仍应生成草稿"
    assert card["media"] == []


def test_media_retry_success_is_reused_by_next_real_sync(client, monkeypatch, tmp_path):
    class RetryWecomClient:
        def __init__(self):
            self.download_calls = 0

        async def sync_msg(self, cursor=None, token=None, limit=None):
            return {
                "errcode": 0,
                "errmsg": "ok",
                "next_cursor": "cursor_retry_done",
                "has_more": 0,
                "msg_list": [
                    {
                        "msgid": "media_retry_msg",
                        "open_kfid": "wk_retry",
                        "external_userid": "external_retry",
                        "send_time": 1780848000,
                        "msgtype": "image",
                        "image": {"media_id": "media_retry_001", "filename": "cover.png"},
                    }
                ],
            }

        async def download_media(self, media_id):
            self.download_calls += 1
            return DownloadedMedia(b"image-bytes", "image/png", "cover.png")

    service = client.app.dependency_overrides[get_app_service]()
    service.save_media_retry_failure("media_retry_001", "image", "wk_retry", "temporary failure")
    media_dir = tmp_path / "media"
    service.media_storage_service = MediaStorageService("local", media_dir, "/media")
    fake_client = RetryWecomClient()
    monkeypatch.setattr(settings, "admin_token", "test-admin-token")
    monkeypatch.setattr(settings, "wecom_use_mock", False)
    monkeypatch.setattr(settings, "wecom_open_kfid", "wk_retry")
    client.app.dependency_overrides[get_wecom_client] = lambda: fake_client

    retry_response = client.post(
        "/api/wecom/media-retries/retry",
        params={"media_id": "media_retry_001"},
        headers={"X-Admin-Token": "test-admin-token"},
    )
    sync_response = client.post("/api/wecom/real-sync")

    assert retry_response.status_code == 200
    assert retry_response.json()["data"]["retried"][0]["status"] == "success"
    assert sync_response.status_code == 200
    assert fake_client.download_calls == 1
    pending = client.get("/api/imports/pending").json()["data"]
    assert pending[-1]["generatedCard"]["coverUrl"].startswith("/media/")


def test_real_sync_returns_running_status_when_lock_exists(client):
    service = client.app.dependency_overrides[get_app_service]()
    open_kfid = settings.wecom_open_kfid or "default"
    locked = service.acquire_sync_lock(open_kfid, "mock-real-sync-response", 600)
    assert locked is not None

    response = client.post("/api/wecom/real-sync")

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is False
    assert payload["data"]["syncStatus"] == "running"
    assert payload["data"]["lockedAt"] == locked.lockedAt


def test_real_sync_unlock_releases_running_lock(client, monkeypatch):
    service = client.app.dependency_overrides[get_app_service]()
    open_kfid = settings.wecom_open_kfid or "default"
    locked = service.acquire_sync_lock(open_kfid, "mock-real-sync-response", 600)
    assert locked is not None
    monkeypatch.setattr(settings, "admin_token", "test-admin-token")

    response = client.post(
        "/api/wecom/real-sync/unlock",
        params={"reason": "admin unlock"},
        headers={"X-Admin-Token": "test-admin-token"},
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["syncStatus"] == "failed"
    assert payload["lastError"] == "admin unlock"
    assert payload["lockedAt"] is None


def test_real_sync_unlock_rejects_missing_admin_token(client, monkeypatch):
    service = client.app.dependency_overrides[get_app_service]()
    open_kfid = settings.wecom_open_kfid or "default"
    locked = service.acquire_sync_lock(open_kfid, "mock-real-sync-response", 600)
    assert locked is not None
    monkeypatch.setattr(settings, "admin_token", "test-admin-token")

    response = client.post("/api/wecom/real-sync/unlock", params={"reason": "admin unlock"})

    assert response.status_code == 403
    assert service.get_sync_cursor(open_kfid).syncStatus == "running"


def test_real_sync_takes_over_expired_lock(client, monkeypatch):
    service = client.app.dependency_overrides[get_app_service]()
    open_kfid = settings.wecom_open_kfid or "default"
    locked = service.acquire_sync_lock(open_kfid, "mock-real-sync-response", 600)
    assert locked is not None
    monkeypatch.setattr(settings, "wecom_sync_lock_timeout_seconds", 0)

    response = client.post("/api/wecom/real-sync")

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["syncStatus"] == "success"
    assert payload["pagesSynced"] == 1


def test_health_reports_database_configuration(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["database"]["backend"] == "postgres"
    assert isinstance(data["database"]["configured"], bool)
    assert isinstance(data["database"]["missing"], list)


def test_location_geocode_reports_missing_key(client, monkeypatch):
    from app.api import routes_location

    monkeypatch.setattr(routes_location.settings, "tencent_map_key", "")

    response = client.get("/api/location/geocode", params={"address": "长沙市芙蓉区万家丽"})

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["configured"] is False
    assert data["found"] is False


def test_location_geocode_normalizes_tencent_result(client, monkeypatch):
    from app.api import routes_location

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "status": 0,
                "result": {
                    "title": "万国城",
                    "address": "湖南省长沙市芙蓉区远大一路",
                    "location": {"lat": 28.21, "lng": 113.02},
                    "level": "地产小区",
                    "reliability": 8,
                },
            }

    def fake_get(url, params, timeout):
        assert "geocoder" in url
        assert params["key"] == "map-key"
        assert params["address"] == "长沙市芙蓉区万国城"
        assert timeout == 8
        return FakeResponse()

    monkeypatch.setattr(routes_location.settings, "tencent_map_key", "map-key")
    monkeypatch.setattr(routes_location.httpx, "get", fake_get)

    response = client.get("/api/location/geocode", params={"address": "长沙市芙蓉区万国城"})

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["configured"] is True
    assert data["found"] is True
    assert data["latitude"] == 28.21
    assert data["longitude"] == 113.02
    assert data["name"] == "万国城"


def test_enterprise_resource_search_reports_missing_key(client, monkeypatch):
    from app.api import routes_enterprise_resources

    monkeypatch.setattr(routes_enterprise_resources.settings, "tyc_api_key", "")

    response = client.get("/api/enterprise-resources/search", params={"keyword": "长沙装饰"})

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["configured"] is False
    assert data["items"] == []


def test_enterprise_resource_search_normalizes_tyc_result(client, monkeypatch):
    from app.api import routes_enterprise_resources

    def fake_search(keyword, page_size):
        assert keyword == "长沙装饰"
        assert page_size == 10
        return [{
            "id": "123",
            "name": "湖南某某装饰工程有限公司",
            "shortName": "某某装饰",
            "status": "存续",
            "legalPerson": "李某某",
            "capital": "500万元人民币",
            "foundedAt": "2016-05-18",
            "industry": "建筑装饰业",
            "city": "长沙市",
            "address": "长沙市岳麓区某某路88号",
            "creditCode": "91430100MA4LXXXXXX",
            "risk": "暂无重大风险",
            "source": "tyc-mcp",
        }]

    monkeypatch.setattr(routes_enterprise_resources.settings, "tyc_api_key", "tyc-key")
    monkeypatch.setattr(routes_enterprise_resources, "_mcp_search_companies", fake_search)

    response = client.get("/api/enterprise-resources/search", params={"keyword": "长沙装饰"})

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["configured"] is True
    assert data["items"][0]["name"] == "湖南某某装饰工程有限公司"
    assert data["items"][0]["legalPerson"] == "李某某"
    assert data["items"][0]["creditCode"] == "91430100MA4LXXXXXX"


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
    assert "已生成" in notifications[-1]["message"]
    assert notifications[-1]["resultPath"].startswith("/pages/note-edit/index?id=")
    assert notifications[-1]["sendStatus"] == "skipped"


def test_real_sync_sends_wecom_completion_feedback(client, monkeypatch):
    class FakeWecomClient:
        def __init__(self):
            self.sent = []

        async def sync_msg(self, cursor=None, token=None, limit=None):
            return {
                "errcode": 0,
                "errmsg": "ok",
                "next_cursor": "cursor_feedback_done",
                "has_more": 0,
                "msg_list": [
                    {
                        "msgid": "feedback_msg_001",
                        "open_kfid": "wk_feedback",
                        "external_userid": "external_feedback",
                        "send_time": 1780848000,
                        "msgtype": "text",
                        "text": {"content": "龙悦和府 两房 近地铁 可带看 微信 18500001111"},
                    }
                ],
            }

        async def send_customer_service_text(self, external_user_id, content, open_kfid=None):
            self.sent.append({"externalUserId": external_user_id, "content": content, "openKfid": open_kfid})
            return {"errcode": 0, "errmsg": "ok", "msgid": "send_feedback_001"}

    fake_client = FakeWecomClient()
    monkeypatch.setattr(settings, "wecom_use_mock", False)
    monkeypatch.setattr(settings, "wecom_open_kfid", "wk_feedback")
    client.app.dependency_overrides[get_wecom_client] = lambda: fake_client

    response = client.post("/api/wecom/real-sync")

    assert response.status_code == 200
    payload = response.json()["data"]
    assert len(payload["importResult"]["importBatchIds"]) == 1
    assert len(fake_client.sent) == 1
    assert fake_client.sent[0]["externalUserId"] == "external_feedback"
    assert "已完成" in fake_client.sent[0]["content"]
    assert "/pages/note-edit/index?id=" in fake_client.sent[0]["content"]
    notifications = client.get("/api/wecom/notifications").json()["data"]
    latest = notifications[0]
    assert latest["sendStatus"] == "sent"
    assert latest["sentMessageAt"]


def test_wecom_import_uses_content_object_to_note_pipeline(client, monkeypatch):
    service = client.app.dependency_overrides[get_app_service]()
    seen = {}
    original_run = service.skill_router_service.run_content_to_note

    def spy_run_content_to_note(owner_user_id, content):
        seen["ownerUserId"] = owner_user_id
        seen["sourceType"] = content.sourceType
        seen["rawMessageIds"] = content.rawMessageIds
        seen["textBlocks"] = content.textBlocks
        return original_run(owner_user_id, content)

    monkeypatch.setattr(service.skill_router_service, "run_content_to_note", spy_run_content_to_note)

    response = client.post(
        "/api/wecom/mock-sync",
        json={"externalUserId": "external_content_object", "conversationId": "conv_content_object", "fixture": "note"},
    )

    assert response.status_code == 200
    assert seen["ownerUserId"] == "unclaimed"
    assert seen["sourceType"] == "wecom_thread"
    assert seen["rawMessageIds"]
    assert any("联系人" in text or "看房" in text for text in seen["textBlocks"])


def test_wecom_sync_import_handles_miniapp_card(client):
    service = client.app.dependency_overrides[get_app_service]()
    result = service.trigger_sync_response_import(
        {
            "next_cursor": "cursor_weapp",
            "msg_list": [
                {
                    "msgid": "sync_weapp_msg_001",
                    "open_kfid": "wk_weapp",
                    "external_userid": "external_weapp",
                    "send_time": 1781808076,
                    "msgtype": "weapp",
                    "weapp": {
                        "appid": "wxcfd8224218167d98",
                        "title": "三江尊园 全天采光 好楼层 拎包入住",
                        "pagepath": "subpackages/ershoufang/pages/esfDetail/esfDetail.html?cityId=150200&houseCode=101137825091",
                        "username": "gh_2dbd87cb164c@app",
                        "description": "贝壳找房丨二手房新房租房装修",
                        "displayname": "贝壳找房丨二手房新房租房装修",
                    },
                }
            ],
        },
        fallback_open_kfid="wk_weapp",
    )

    assert result["importBatchIds"]
    pending = client.get("/api/imports/pending").json()["data"]
    latest = pending[-1]
    note = latest["generatedNote"]
    assert latest["sourceType"] == "miniapp_link"
    assert note["title"] == "三江尊园 全天采光 好楼层 拎包入住"
    assert note["phone"] is None
    assert note["visibilityConfig"]["sourceType"] == "miniapp"
    assert note["visibilityConfig"]["showPhone"] is False
    assert note["visibilityConfig"]["structuredData"]["miniapp"]["houseCode"] == "101137825091"
    assert note["visibilityConfig"]["structuredData"]["miniapp"]["webUrl"] == "https://m.ke.com/baotou/ershoufang/101137825091.html"
    assert note["visibilityConfig"]["conversionConfig"]["enableLightScrm"] is True
    assert note["visibilityConfig"]["conversionConfig"]["collectLeads"] is True
    assert note["visibilityConfig"]["conversionConfig"]["enableAppointment"] is True


def test_wecom_sync_import_enriches_own_miniapp_note(client, monkeypatch):
    monkeypatch.setattr(settings, "wechat_miniapp_appid", "wx_team_buy")
    owner = client.post("/api/auth/mock-login", json={"nickname": "房源发布者", "openid": "openid_internal_note_owner"}).json()["data"]
    source_note = client.post(
        "/api/notes/manual-draft",
        json={
            "ownerUserId": owner["id"],
            "cardType": "property_listing",
            "inputMode": "paste_text",
            "rawText": "小区：龙悦和府\n户型：两房\n租金：1800元/月\n上游联系人：真实房东A\n电话：13800138000",
        },
    ).json()["data"]

    service = client.app.dependency_overrides[get_app_service]()
    result = service.trigger_sync_response_import(
        {
            "next_cursor": "cursor_internal_note",
            "msg_list": [
                {
                    "msgid": "sync_internal_note_msg_001",
                    "open_kfid": "wk_internal",
                    "external_userid": "external_internal_note",
                    "send_time": 1781808076,
                    "msgtype": "weapp",
                    "weapp": {
                        "appid": "wx_team_buy",
                        "title": "龙悦和府",
                        "pagepath": f"pages/note-preview/index?id={source_note['id']}",
                        "description": "资料整理助手",
                        "displayname": "资料整理助手",
                    },
                }
            ],
        },
        fallback_open_kfid="wk_internal",
    )

    assert result["importBatchIds"]
    pending = client.get("/api/imports/pending").json()["data"]
    generated = pending[-1]["generatedNote"]
    structured = generated["visibilityConfig"]["structuredData"]
    internal = structured["internalMiniapp"]
    assert internal["kind"] == "note"
    assert internal["noteId"] == source_note["id"]
    assert internal["structuredData"]["community"] == "龙悦和府"
    assert "upstream" not in json.dumps(internal["structuredData"], ensure_ascii=False).lower()
    assert "上游" not in json.dumps(internal["structuredData"], ensure_ascii=False)
    assert "隐私边界" in generated["body"]


def test_wecom_sync_import_enriches_own_miniapp_showcase(client, monkeypatch):
    monkeypatch.setattr(settings, "wechat_miniapp_appid", "wx_team_buy")
    owner = client.post("/api/auth/mock-login", json={"nickname": "合集发布者", "openid": "openid_internal_showcase_owner"}).json()["data"]
    note = client.post(
        "/api/notes/manual-draft",
        json={
            "ownerUserId": owner["id"],
            "cardType": "property_listing",
            "inputMode": "paste_text",
            "rawText": "小区：加州都府\n户型：一房\n租金：1500元/月",
        },
    ).json()["data"]
    showcase = client.post(
        "/api/showcases",
        json={
            "ownerUserId": owner["id"],
            "name": "精选房源合集",
            "description": "近期可看",
            "templateId": "catalog_list",
            "contactConfig": {"phone": "13800138000", "wechat": "agent-wx"},
            "displayConfig": {"activeCategory": "房源", "layoutMode": "grid"},
            "items": [{"noteId": note["id"], "sortOrder": 1}],
        },
    ).json()["data"]
    published = client.post(f"/api/showcases/{showcase['id']}/publish", json={"ownerUserId": owner["id"]}).json()["data"]

    service = client.app.dependency_overrides[get_app_service]()
    service.trigger_sync_response_import(
        {
            "next_cursor": "cursor_internal_showcase",
            "msg_list": [
                {
                    "msgid": "sync_internal_showcase_msg_001",
                    "open_kfid": "wk_internal",
                    "external_userid": "external_internal_showcase",
                    "send_time": 1781808076,
                    "msgtype": "weapp",
                    "weapp": {
                        "appid": "wx_team_buy",
                        "title": "精选房源合集",
                        "pagepath": f"pages/showcase-view/index?id={published['id']}",
                        "description": "资料整理助手",
                        "displayname": "资料整理助手",
                    },
                }
            ],
        },
        fallback_open_kfid="wk_internal",
    )

    generated = client.get("/api/imports/pending").json()["data"][-1]["generatedNote"]
    internal = generated["visibilityConfig"]["structuredData"]["internalMiniapp"]
    assert internal["kind"] == "showcase"
    assert internal["showcaseId"] == showcase["id"]
    assert internal["displayConfig"]["layoutMode"] == "grid"
    assert "加州都府" in internal["items"][0]["title"]
    assert "隐私边界" in generated["body"]


def test_wecom_import_persists_successful_skill_run(client):
    response = client.post(
        "/api/wecom/mock-sync",
        json={"externalUserId": "external_skill_run", "conversationId": "conv_skill_run", "fixture": "note"},
    )

    assert response.status_code == 200
    runs = client.get("/api/skills/runs", params={"skillId": "content-to-note"}).json()["data"]
    latest = runs[0]
    assert latest["skillId"] == "content-to-note"
    assert latest["status"] == "success"
    assert latest["outputRef"].startswith("note_")
    assert latest["inputSnapshot"]["importBatchId"] == response.json()["data"]["importBatchIds"][0]


def test_wecom_import_failure_persists_failed_skill_run_and_notification(client, monkeypatch):
    service = client.app.dependency_overrides[get_app_service]()
    original_run = service.skill_router_service.run_content_to_note

    def fail_content_to_note(owner_user_id, content):
        raise RuntimeError("content-to-note failed for test")

    monkeypatch.setattr(service.skill_router_service, "run_content_to_note", fail_content_to_note)

    response = client.post(
        "/api/wecom/mock-sync",
        json={"externalUserId": "external_skill_fail", "conversationId": "conv_skill_fail", "fixture": "note"},
    )

    assert response.status_code == 200
    import_batch_id = response.json()["data"]["importBatchIds"][0]
    failed_runs = client.get("/api/skills/runs", params={"status": "failed"}).json()["data"]
    assert failed_runs[0]["skillId"] == "content-to-note"
    assert failed_runs[0]["outputRef"] == import_batch_id
    assert failed_runs[0]["inputSnapshot"]["importBatchId"] == import_batch_id
    assert "content-to-note failed for test" in failed_runs[0]["errorMessage"]

    failures = client.get("/api/wecom/import-failures").json()["data"]
    assert failures["skillRuns"][0]["id"] == failed_runs[0]["id"]
    assert failures["notifications"][0]["importBatchId"] == import_batch_id
    assert failures["notifications"][0]["status"] == "failed"
    assert "content-to-note failed for test" in failures["notifications"][0]["message"]

    dashboard = client.get("/api/wecom/retry-dashboard").json()["data"]
    assert dashboard["summary"]["failedSkillRunCount"] >= 1
    assert dashboard["actions"]["retryImport"] == "/api/wecom/import-failures/retry"

    monkeypatch.setattr(settings, "admin_token", "test-admin-token")
    monkeypatch.setattr(service.skill_router_service, "run_content_to_note", original_run)
    retry_response = client.post(
        "/api/wecom/import-failures/retry",
        params={"importBatchId": import_batch_id},
        headers={"X-Admin-Token": "test-admin-token"},
    )

    assert retry_response.status_code == 200
    retry_payload = retry_response.json()["data"]
    assert retry_payload["importBatch"]["status"] == "success"
    assert retry_payload["generatedCard"]["id"].startswith("card_")
    assert retry_payload["notification"]["status"] == "success"


def test_mock_import_is_idempotent_for_repeated_wecom_messages(client):
    first = client.post(
        "/api/wecom/mock-sync",
        json={"externalUserId": "external_repeat", "conversationId": "conv_repeat", "fixture": "note"},
    )
    second = client.post(
        "/api/wecom/mock-sync",
        json={"externalUserId": "external_repeat", "conversationId": "conv_repeat", "fixture": "note"},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    second_payload = second.json()["data"]
    assert second_payload["importBatchIds"] == []
    assert second_payload["deduplicatedCount"] == 5
    assert second_payload["message"] == "没有新的企业微信客服消息需要导入"


def test_link_import_uses_thumbnail_and_source_url(client):
    login = client.post("/api/auth/mock-login", json={"nickname": "收藏用户"}).json()["data"]
    response = client.post(
        "/api/wecom/mock-sync",
        json={"externalUserId": "external_link", "conversationId": "conv_link", "fixture": "link"},
    )
    assert response.status_code == 200

    pending = client.get("/api/imports/pending").json()["data"]
    latest = pending[-1]
    card = latest["generatedCard"]
    note = latest["generatedNote"]
    assert latest["sourceType"] == "web_link"
    assert card["sourceUrl"] == "https://example.com/group-buy"
    assert card["coverUrl"] == "https://example.com/cover.jpg"
    assert note["visibilityConfig"]["contentMode"] == "bookmark"
    assert {"链接", "待整理"}.issubset(set(note["visibilityConfig"]["tags"]))
    assert note["visibilityConfig"]["sourceType"] == "link"
    assert note["visibilityConfig"]["systemCategory"] == "文章"
    assert note["visibilityConfig"]["tagLevels"]["rule"] == note["visibilityConfig"]["tags"]
    assert note["visibilityConfig"]["tagStatus"] == "rule_done"
    assert note["visibilityConfig"]["category"] == "文章收藏"
    assert note["visibilityConfig"]["sourceUrl"] == "https://example.com/group-buy"
    assert note["visibilityConfig"]["sourceName"] == "example.com"
    assert note["visibilityConfig"]["sourceLabel"] == "网页链接"

    claim = client.post(f"/api/imports/{latest['id']}/claim", json={"userId": login["id"]})
    note_id = claim.json()["data"]["note"]["id"]
    updated = client.put(
        f"/api/notes/{note_id}",
        json={
            **claim.json()["data"]["note"],
            "ownerUserId": login["id"],
            "visibilityConfig": {
                **claim.json()["data"]["note"]["visibilityConfig"],
                "userTags": ["露营"],
                "tags": [*claim.json()["data"]["note"]["visibilityConfig"]["tags"], "露营"],
            },
        },
    )
    assert updated.status_code == 200
    tagged = client.get("/api/notes", params={"ownerUserId": login["id"], "tag": "露营"}).json()["data"]
    assert any(item["id"] == note_id for item in tagged)

    topic = client.post("/api/notes/topics", json={"ownerUserId": login["id"], "name": "周末亲子露营"})
    assert topic.status_code == 200
    topic_id = topic.json()["data"]["id"]
    added = client.post(f"/api/notes/{note_id}/topics/{topic_id}", json={"ownerUserId": login["id"]})
    assert added.status_code == 200
    assert topic_id in added.json()["data"]["visibilityConfig"]["topicIds"]
    topic_notes = client.get("/api/notes", params={"ownerUserId": login["id"], "topicId": topic_id}).json()["data"]
    assert [item["id"] for item in topic_notes] == [note_id]

    suggestions = client.get("/api/notes/tag-suggestions", params={"ownerUserId": login["id"], "noteId": note_id})
    assert suggestions.status_code == 200
    assert "链接" in suggestions.json()["data"]["suggestedTags"]

    organized = client.post(f"/api/notes/{note_id}/organize", params={"ownerUserId": login["id"]})

    assert organized.status_code == 200
    organized_note = organized.json()["data"]
    assert organized_note["visibilityConfig"]["contentMode"] == "deep_note"
    assert "未整理" not in organized_note["visibilityConfig"]["tags"]
    assert "已整理" in organized_note["visibilityConfig"]["tags"]
    assert organized_note["visibilityConfig"]["structuredData"]["organizeResult"]["generationOptions"] == ["日常合集", "分享摘要", "标签归类"]

    deleted_topic = client.delete(f"/api/notes/topics/{topic_id}", params={"ownerUserId": login["id"]})
    assert deleted_topic.status_code == 200
    assert deleted_topic.json()["data"]["deletedTopicId"] == topic_id
    topic_notes_after_delete = client.get("/api/notes", params={"ownerUserId": login["id"], "topicId": topic_id}).json()["data"]
    assert topic_notes_after_delete == []


def test_explicit_link_organize_command_uses_deep_note(client):
    service = client.app.dependency_overrides[get_app_service]()
    sync_response = {
        "next_cursor": "cursor_deep_link",
        "msg_list": [
            {
                "msgid": "deep_link_text_001",
                "external_userid": "external_deep_link",
                "send_time": 1780848000,
                "msgtype": "text",
                "text": {"content": "整理链接"},
            },
            {
                "msgid": "deep_link_msg_001",
                "external_userid": "external_deep_link",
                "send_time": 1780848001,
                "msgtype": "link",
                "link": {
                    "title": "值得整理的文章",
                    "description": "需要提炼重点",
                    "url": "https://example.com/deep-link",
                    "picurl": "https://example.com/deep-cover.jpg",
                },
            },
        ]
    }

    result = service.trigger_sync_response_import(sync_response, fallback_open_kfid="wk_deep_link")
    pending = client.get("/api/imports/pending").json()["data"]
    generated = next(item for item in pending if item["id"] == result["importBatchIds"][0])

    assert generated["generatedNote"]["visibilityConfig"].get("contentMode") != "bookmark"
    assert "整理链接" in generated["generatedNote"]["body"]


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
    note = claim.json()["data"]["note"]
    assert card["ownerUserId"] == login["id"]
    assert note["ownerUserId"] == login["id"]
    assert note["status"] == "active"
    assert claim.json()["data"]["identityBinding"]["externalUserId"] == "external_claim"
    assert claim.json()["data"]["identityBinding"]["ownerUserId"] == login["id"]
    assert claim.json()["data"]["identityBinding"]["ownerOpenid"] == login["openid"]

    publish = client.post(f"/api/cards/{card['id']}/publish", json={"userId": login["id"]})
    assert publish.status_code == 200
    assert publish.json()["data"]["status"] == "published"

    client.post(
        "/api/wecom/mock-sync",
        json={"externalUserId": "external_claim", "conversationId": "conv_claim_followup", "fixture": "link"},
    )
    notes = client.get("/api/notes", params={"ownerUserId": login["id"]}).json()["data"]
    pending_after = client.get("/api/imports/pending").json()["data"]
    assert len(notes) >= 2
    assert not any(item["externalUserId"] == "external_claim" and item["status"] != "claimed" for item in pending_after)


def test_claim_import_by_token_binds_external_user(client):
    login = client.post(
        "/api/auth/mock-login",
        json={"nickname": "链接认领中介", "openid": "openid_claim_token_owner"},
    ).json()["data"]
    client.post(
        "/api/wecom/mock-sync",
        json={"externalUserId": "external_claim_token", "conversationId": "conv_claim_token", "fixture": "note"},
    )
    pending = client.get("/api/imports/pending").json()["data"]
    target = pending[-1]
    service = client.app.dependency_overrides[get_app_service]()
    claim_link = service.build_import_claim_link(target["id"])

    assert claim_link["pagePath"].startswith("pages/import-claim/index?token=")

    claim = client.post(
        "/api/imports/claim-by-token",
        json={"userId": login["id"], "token": claim_link["token"]},
    )

    assert claim.status_code == 200
    data = claim.json()["data"]
    assert data["card"]["ownerUserId"] == login["id"]
    assert data["note"]["ownerUserId"] == login["id"]
    assert data["identityBinding"]["externalUserId"] == "external_claim_token"
    assert data["identityBinding"]["ownerUserId"] == login["id"]
    assert data["identityBinding"]["ownerOpenid"] == login["openid"]

    client.post(
        "/api/wecom/mock-sync",
        json={"externalUserId": "external_claim_token", "conversationId": "conv_claim_token_followup", "fixture": "link"},
    )
    notes = client.get("/api/notes", params={"ownerUserId": login["id"]}).json()["data"]
    pending_after = client.get("/api/imports/pending").json()["data"]
    assert len(notes) >= 2
    assert not any(item["externalUserId"] == "external_claim_token" and item["status"] != "claimed" for item in pending_after)


def test_import_creates_claimable_user_note_and_note_crud(client):
    login = client.post("/api/auth/mock-login", json={"nickname": "笔记用户"}).json()["data"]
    client.post(
        "/api/wecom/mock-sync",
        json={"externalUserId": "external_note_crud", "conversationId": "conv_note_crud", "fixture": "note"},
    )
    pending = client.get("/api/imports/pending").json()["data"]
    target = pending[-1]
    assert target["generatedNote"]["ownerUserId"] == "unclaimed"
    assert target["generatedNote"]["title"]

    claim = client.post(f"/api/imports/{target['id']}/claim", json={"userId": login["id"]})
    note = claim.json()["data"]["note"]

    notes = client.get("/api/notes", params={"ownerUserId": login["id"]}).json()["data"]
    assert any(item["id"] == note["id"] for item in notes)

    detail = client.get(f"/api/notes/{note['id']}", params={"ownerUserId": login["id"]})
    assert detail.status_code == 200
    assert detail.json()["data"]["sourceCardId"] == claim.json()["data"]["card"]["id"]

    card_detail = client.get(f"/api/cards/{claim.json()['data']['card']['id']}")
    assert card_detail.status_code == 200
    assert card_detail.json()["data"]["sourceNoteId"] == note["id"]
    cards = client.get("/api/cards", params={"ownerUserId": login["id"]}).json()["data"]
    assert any(item["id"] == claim.json()["data"]["card"]["id"] and item["sourceNoteId"] == note["id"] for item in cards)

    updated = client.put(
        f"/api/notes/{note['id']}",
        json={
            "ownerUserId": login["id"],
            "title": "更新后的笔记",
            "summary": "更新摘要",
            "body": "更新正文 13800138000",
            "categoryIds": ["cat_seed_sale"],
            "phone": "13800138000",
            "visibilityConfig": {"showPhone": True},
        },
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["title"] == "更新后的笔记"
    assert updated.json()["data"]["categoryIds"] == ["cat_seed_sale"]

    structured = client.put(
        f"/api/notes/{note['id']}",
        json={
            "ownerUserId": login["id"],
            "title": "碧桂园城市之光1栋1210",
            "summary": "房源字段卡",
            "body": "小区：碧桂园城市之光1栋1210\n户型：公寓一房\n价格：1600元/月\n商圈：万家丽、高桥北",
            "categoryIds": ["cat_seed_sale"],
            "phone": "13800138000",
            "visibilityConfig": {
                "cardType": "property_listing",
                "cardState": "collected",
                "contentMode": "structured_card",
                "systemCategory": "房源",
                "tags": ["房产", "房源"],
                "structuredData": {
                    "community": "碧桂园城市之光1栋1210",
                    "layout": "公寓一房",
                    "price": "1600元/月",
                    "businessArea": "万家丽、高桥北",
                },
                "conversionConfig": {
                    "showContactPhone": True,
                    "enableLightScrm": True,
                    "collectLeads": True,
                    "enableAppointment": True,
                    "enablePrivateConsultation": False,
                    "enableSharePoster": True,
                    "enableGroupRelay": False,
                    "enablePaymentPlaceholder": False,
                },
            },
        },
    )
    assert structured.status_code == 200
    assert structured.json()["data"]["visibilityConfig"]["structuredData"]["businessArea"] == "万家丽、高桥北"

    filtered = client.get(
        "/api/notes",
        params={"ownerUserId": login["id"], "keyword": "万家丽", "categoryId": "cat_seed_sale"},
    ).json()["data"]
    assert [item["id"] for item in filtered] == [note["id"]]

    created_date = structured.json()["data"]["createdAt"].split("T", 1)[0]
    _, month, day = created_date.split("-")
    compact_month_day = f"{int(month)}{int(day)}"
    for keyword in [created_date, f"{int(month)}月", compact_month_day]:
        fuzzy_filtered = client.get(
            "/api/notes",
            params={"ownerUserId": login["id"], "keyword": keyword},
        ).json()["data"]
        assert note["id"] in [item["id"] for item in fuzzy_filtered]

    organized = client.post(f"/api/notes/{note['id']}/organize", params={"ownerUserId": login["id"]})
    assert organized.status_code == 200
    organized_config = organized.json()["data"]["visibilityConfig"]
    assert organized_config["cardState"] == "organized"
    assert organized_config["structuredData"]["organizeResult"]["generationOptions"] == ["房源推广图", "微信群文案", "客户话术", "对比表"]
    assert "轻 SCRM 跟进" in organized_config["structuredData"]["organizeResult"]["enabledFeatures"]
    assert "私聊咨询" not in organized_config["structuredData"]["organizeResult"]["enabledFeatures"]

    generated = client.post(f"/api/notes/{note['id']}/generate", params={"ownerUserId": login["id"]})
    assert generated.status_code == 200
    generated_config = generated.json()["data"]["visibilityConfig"]
    assert generated_config["cardState"] == "generated"
    assert generated_config["structuredData"]["generatedResult"]["pageType"] == "property_promo_page"
    assert "预约看房" in generated_config["structuredData"]["generatedResult"]["enabledActions"]
    assert "私聊咨询" not in generated_config["structuredData"]["generatedResult"]["enabledActions"]

    viewer = client.post("/api/auth/mock-login", json={"nickname": "看房客户"}).json()["data"]
    action_config = client.get(
        f"/api/notes/{note['id']}/customer-actions/config",
        params={"viewerUserId": viewer["id"]},
    )
    assert action_config.status_code == 200
    action_keys = {item["key"] for item in action_config.json()["data"]["actions"]}
    assert {"lead-contact", "appointment"}.issubset(action_keys)

    lead_action = client.post(
        f"/api/notes/{note['id']}/customer-actions/lead-contact",
        json={
            "viewerUserId": viewer["id"],
            "nickname": viewer["nickname"],
            "avatarUrl": viewer["avatarUrl"],
            "payload": {
                "name": "王客户",
                "phone": "13900001111",
                "wechat": "wx_house_001",
                "remark": "周末方便看房",
            },
        },
    )
    assert lead_action.status_code == 200
    lead_projection = lead_action.json()["data"]["projection"]
    assert lead_projection["leadReminderId"].startswith("lead_")

    appointment_action = client.post(
        f"/api/notes/{note['id']}/customer-actions/appointment",
        json={
            "viewerUserId": viewer["id"],
            "nickname": viewer["nickname"],
            "avatarUrl": viewer["avatarUrl"],
            "payload": {
                "date": "2026-06-20",
                "time": "14:30",
                "remark": "两个人看房",
            },
        },
    )
    assert appointment_action.status_code == 200
    assert appointment_action.json()["data"]["projection"]["leadReminderId"] == lead_projection["leadReminderId"]

    lead_rows = client.get("/api/lead-reminders", params={"ownerUserId": login["id"]}).json()["data"]
    customer_lead = next(item for item in lead_rows if item["id"] == lead_projection["leadReminderId"])
    assert customer_lead["cardId"] == claim.json()["data"]["card"]["id"]
    assert customer_lead["sourceNoteId"] == note["id"]
    assert customer_lead["customerPhone"] == "13900001111"
    assert customer_lead["customerWechat"] == "wx_house_001"
    assert customer_lead["nextFollowUpAt"] == "2026-06-20T14:30:00+08:00"
    assert any("客户预约：2026-06-20 14:30" in item["content"] for item in customer_lead["followUpLogs"])

    submitted_config = client.get(
        f"/api/notes/{note['id']}/customer-actions/config",
        params={"viewerUserId": viewer["id"]},
    ).json()["data"]
    submitted = {item["key"]: item for item in submitted_config["actions"]}
    assert submitted["lead-contact"]["submitted"] is True
    assert submitted["appointment"]["submitted"] is True

    note_actions = client.get(
        f"/api/notes/{note['id']}/customer-actions",
        params={"ownerUserId": login["id"]},
    )
    assert note_actions.status_code == 200
    note_action_data = note_actions.json()["data"]
    assert note_action_data["summary"]["total"] == 2
    assert note_action_data["summary"]["leadContact"] == 1
    assert note_action_data["summary"]["appointment"] == 1
    assert note_action_data["summary"]["pending"] == 1
    assert note_action_data["summary"]["hasUnread"] is True
    assert {item["actionKey"] for item in note_action_data["actions"]} == {"lead-contact", "appointment"}
    assert note_action_data["actions"][0]["leadReminderId"] == lead_projection["leadReminderId"]
    assert note_action_data["leads"][0]["id"] == lead_projection["leadReminderId"]

    forbidden_actions = client.get(
        f"/api/notes/{note['id']}/customer-actions",
        params={"ownerUserId": viewer["id"]},
    )
    assert forbidden_actions.status_code == 403

    deleted = client.delete(f"/api/notes/{note['id']}", params={"ownerUserId": login["id"]})
    assert deleted.status_code == 200
    assert client.get("/api/notes", params={"ownerUserId": login["id"]}).json()["data"] == []
    deleted_visible = client.get(
        "/api/notes",
        params={"ownerUserId": login["id"], "includeDeleted": True},
    ).json()["data"]
    assert deleted_visible[0]["status"] == "deleted"


def test_groupbuy_product_relay_intent_uses_customer_actions_without_leads(client):
    service = client.app.dependency_overrides[get_app_service]()
    owner = client.post("/api/auth/mock-login", json={"nickname": "团长"}).json()["data"]
    now = now_iso()
    note = UserNote(
        id=new_id("note"),
        ownerUserId=owner["id"],
        status="active",
        title="丹东草莓团购",
        summary="丹东草莓，按规格接龙。",
        body="丹东草莓 3斤装 39.9元，小区自提。",
        phone="13800008888",
        locationText="小区门口",
        visibilityConfig={
            "cardType": "groupbuy_product",
            "cardState": "generated",
            "contentMode": "generated_card",
            "systemCategory": "团购",
            "structuredData": {
                "productName": "丹东草莓",
                "price": "39.9元",
                "spec": "3斤装",
                "pickupMethod": "小区自提",
                "pickupLocation": "小区门口",
                "contact": "13800008888",
                "skuConfig": {
                    "attributeGroups": [
                        {
                            "id": "taste",
                            "name": "口味",
                            "options": [
                                {"id": "sweet", "label": "甜口"},
                                {"id": "sour", "label": "酸甜"},
                            ],
                        },
                        {
                            "id": "size",
                            "name": "规格",
                            "options": [
                                {"id": "3jin", "label": "3斤装"},
                            ],
                        },
                    ],
                    "skus": [
                        {"id": "sku_1", "key": "sweet|3jin", "name": "甜口 / 3斤装", "price": "39.9元", "soldOut": False},
                        {"id": "sku_2", "key": "sour|3jin", "name": "酸甜 / 3斤装", "price": "42.9元", "soldOut": True},
                    ],
                },
            },
            "conversionConfig": {
                "showContactPhone": True,
                "enableLightScrm": False,
                "collectLeads": False,
                "enableAppointment": False,
                "enablePrivateConsultation": False,
                "enableSharePoster": True,
                "enableGroupRelay": True,
                "enablePaymentPlaceholder": False,
            },
        },
        createdAt=now,
        updatedAt=now,
    )
    service.repo.save_user_note(note)
    viewer = client.post("/api/auth/mock-login", json={"nickname": "买家"}).json()["data"]

    action_config = client.get(f"/api/notes/{note.id}/customer-actions/config", params={"viewerUserId": viewer["id"]})
    assert action_config.status_code == 200
    actions = {item["key"]: item for item in action_config.json()["data"]["actions"]}
    assert set(actions) == {"relay-intent"}
    assert actions["relay-intent"]["skuConfig"]["skus"][1]["soldOut"] is True

    sold_out = client.post(
        f"/api/notes/{note.id}/customer-actions/relay-intent",
        json={
            "viewerUserId": viewer["id"],
            "nickname": viewer["nickname"],
            "avatarUrl": viewer["avatarUrl"],
            "payload": {"skuKey": "sour|3jin", "quantity": 1, "phone": "13900003333", "address": "小区门口"},
        },
    )
    assert sold_out.status_code == 400

    submitted = client.post(
        f"/api/notes/{note.id}/customer-actions/relay-intent",
        json={
            "viewerUserId": viewer["id"],
            "nickname": viewer["nickname"],
            "avatarUrl": viewer["avatarUrl"],
            "payload": {"skuKey": "sweet|3jin", "quantity": 2, "phone": "13900003333", "address": "小区门口", "wechat": "wx_buyer", "remark": "下午自提"},
        },
    )
    assert submitted.status_code == 200
    assert submitted.json()["data"]["projection"] == {}
    assert submitted.json()["data"]["action"]["payload"]["skuName"] == "甜口 / 3斤装"
    assert submitted.json()["data"]["action"]["payload"]["name"] == "买家"
    assert submitted.json()["data"]["action"]["payload"].get("avatarUrl", "") == viewer["avatarUrl"]
    resubmitted_config = client.get(f"/api/notes/{note.id}/customer-actions/config", params={"viewerUserId": viewer["id"]})
    resubmitted_action = resubmitted_config.json()["data"]["actions"][0]
    assert resubmitted_action["submitted"] is True
    assert resubmitted_action["submittedPayload"]["skuKey"] == "sweet|3jin"
    assert resubmitted_action["submittedPayload"]["quantity"] == 2
    assert resubmitted_action["submittedPayload"]["phone"] == "13900003333"
    assert resubmitted_action["submittedPayload"]["address"] == "小区门口"

    duplicate = client.post(
        f"/api/notes/{note.id}/customer-actions/relay-intent",
        json={"viewerUserId": viewer["id"], "payload": {"skuKey": "sweet|3jin", "quantity": 1, "phone": "13900003333", "address": "小区门口"}},
    )
    assert duplicate.status_code == 409
    assert client.get("/api/lead-reminders", params={"ownerUserId": owner["id"]}).json()["data"] == []

    owner_actions = client.get(f"/api/notes/{note.id}/customer-actions", params={"ownerUserId": owner["id"]})
    assert owner_actions.status_code == 200
    data = owner_actions.json()["data"]
    assert data["cardType"] == "groupbuy_product"
    assert data["summary"]["orderIntent"] == 1
    assert data["summary"]["relayIntent"] == 1
    assert data["summary"]["leads"] == 0
    assert data["actions"][0]["customerName"] == "买家"
    assert (data["actions"][0]["customerAvatarUrl"] or "") == viewer["avatarUrl"]
    assert data["actions"][0]["displayRows"][0] == {"label": "规格", "value": "甜口 / 3斤装"}
    assert {"label": "地址", "value": "小区门口"} in data["actions"][0]["displayRows"]

    disabled_note = note.model_copy(deep=True)
    disabled_note.id = new_id("note")
    disabled_note.visibilityConfig["conversionConfig"]["enableGroupRelay"] = False
    service.repo.save_user_note(disabled_note)
    disabled = client.post(
        f"/api/notes/{disabled_note.id}/customer-actions/relay-intent",
        json={"viewerUserId": viewer["id"], "payload": {"skuKey": "sweet|3jin", "quantity": 1, "phone": "13900003333", "address": "小区门口"}},
    )
    assert disabled.status_code == 400

    disabled_config = client.get(f"/api/notes/{disabled_note.id}/customer-actions/config", params={"viewerUserId": viewer["id"]})
    disabled_actions = {item["key"]: item for item in disabled_config.json()["data"]["actions"]}
    assert set(disabled_actions) == {"order-intent"}
    order = client.post(
        f"/api/notes/{disabled_note.id}/customer-actions/order-intent",
        json={
            "viewerUserId": viewer["id"],
            "nickname": viewer["nickname"],
            "avatarUrl": viewer["avatarUrl"],
            "payload": {"skuKey": "sweet|3jin", "quantity": 3, "phone": "13900003333", "address": "小区门口", "remark": "放门卫"},
        },
    )
    assert order.status_code == 200
    assert order.json()["data"]["projection"] == {}
    assert order.json()["data"]["statusText"] == "已下单 甜口 / 3斤装 x 3"
    order_id = order.json()["data"]["action"]["id"]
    same_title_note = disabled_note.model_copy(deep=True)
    same_title_note.id = new_id("note")
    same_title_note.title = disabled_note.title
    same_title_note.visibilityConfig["structuredData"]["productName"] = disabled_note.visibilityConfig["structuredData"]["productName"]
    service.repo.save_user_note(same_title_note)
    same_title_order = client.post(
        f"/api/notes/{same_title_note.id}/customer-actions/order-intent",
        json={
            "viewerUserId": viewer["id"],
            "nickname": viewer["nickname"],
            "avatarUrl": viewer["avatarUrl"],
            "payload": {"skuKey": "sweet|3jin", "quantity": 1, "phone": "13900003333", "address": "小区门口"},
        },
    )
    assert same_title_order.status_code == 200
    same_title_order_id = same_title_order.json()["data"]["action"]["id"]
    disabled_owner_actions = client.get(f"/api/notes/{disabled_note.id}/customer-actions", params={"ownerUserId": owner["id"]})
    disabled_data = disabled_owner_actions.json()["data"]
    assert disabled_data["summary"]["orderIntent"] == 1
    assert disabled_data["summary"]["relayIntent"] == 0
    assert disabled_data["summary"]["leads"] == 0
    assert disabled_data["actions"][0]["actionKey"] == "order-intent"
    assert {"label": "地址", "value": "小区门口"} in disabled_data["actions"][0]["displayRows"]
    assert {"label": "备注", "value": "放门卫"} in disabled_data["actions"][0]["displayRows"]

    duplicated = client.post(
        f"/api/notes/{disabled_note.id}/duplicate",
        json={"ownerUserId": owner["id"]},
    )
    assert duplicated.status_code == 200
    duplicated_note = duplicated.json()["data"]
    assert duplicated_note["id"] != disabled_note.id
    assert duplicated_note["title"].endswith("副本")
    assert duplicated_note["visibilityConfig"]["cardType"] == "groupbuy_product"
    assert duplicated_note["visibilityConfig"]["cardState"] == "editing"
    duplicated_actions = client.get(f"/api/notes/{duplicated_note['id']}/customer-actions", params={"ownerUserId": owner["id"]})
    assert duplicated_actions.status_code == 200
    assert duplicated_actions.json()["data"]["actions"] == []

    showcase = client.post(
        "/api/showcases",
        json={
            "ownerUserId": owner["id"],
            "name": "今日草莓团",
            "description": "今天可接龙",
            "items": [{"noteId": disabled_note.id}],
            "contactConfig": {"contactText": "想下单请联系我"},
            "displayConfig": {"activeCategory": "团购"},
        },
    )
    assert showcase.status_code == 200
    showcase_id = showcase.json()["data"]["id"]
    published_showcase = client.post(
        f"/api/showcases/{showcase_id}/publish",
        json={"ownerUserId": owner["id"]},
    )
    assert published_showcase.status_code == 200
    public_showcase = client.get(f"/api/showcases/public/{showcase_id}")
    assert public_showcase.status_code == 200
    public_item = public_showcase.json()["data"]["items"][0]
    assert public_item["productActionText"] == "查看详情/接龙"
    assert "小区自提" in public_item["productMeta"]

    buyer_orders = client.get("/api/orders", params={"userId": viewer["id"], "role": "buyer"})
    assert buyer_orders.status_code == 200
    buyer_order_ids = {item["id"] for item in buyer_orders.json()["data"]["orders"]}
    assert order_id in buyer_order_ids

    seller_orders = client.get("/api/orders", params={"userId": owner["id"], "role": "seller"})
    assert seller_orders.status_code == 200
    seller_order_data = seller_orders.json()["data"]
    assert seller_order_data["summary"]["pending"] >= 1
    assert seller_order_data["summary"]["order"] >= 1
    seller_order = next(item for item in seller_order_data["orders"] if item["id"] == order_id)
    assert seller_order["address"] == "小区门口"
    assert seller_order["phone"] == "13900003333"
    assert seller_order["remark"] == "放门卫"
    assert seller_order["actionKindText"] == "下单"
    assert seller_order["statusText"] == "待处理"
    filtered_seller_orders = client.get(
        "/api/orders",
        params={"userId": owner["id"], "role": "seller", "noteId": disabled_note.id},
    )
    assert filtered_seller_orders.status_code == 200
    filtered_order_ids = {item["id"] for item in filtered_seller_orders.json()["data"]["orders"]}
    assert order_id in filtered_order_ids
    assert same_title_order_id not in filtered_order_ids
    filtered_buyer_orders = client.get(
        "/api/orders",
        params={"userId": viewer["id"], "role": "buyer", "noteId": disabled_note.id},
    )
    assert filtered_buyer_orders.status_code == 200
    assert {item["noteId"] for item in filtered_buyer_orders.json()["data"]["orders"]} == {disabled_note.id}

    outsider = client.post("/api/auth/mock-login", json={"nickname": "路人"}).json()["data"]
    forbidden_order = client.get(f"/api/orders/{order_id}", params={"userId": outsider["id"]})
    assert forbidden_order.status_code == 403

    updated_status = client.patch(
        f"/api/orders/{order_id}/status",
        json={"userId": owner["id"], "status": "contacted"},
    )
    assert updated_status.status_code == 200
    assert updated_status.json()["data"]["status"] == "contacted"
    assert updated_status.json()["data"]["statusText"] == "已联系"
    refreshed_orders = client.get("/api/orders", params={"userId": owner["id"], "role": "seller"}).json()["data"]
    assert refreshed_orders["summary"]["contacted"] >= 1
    buyer_status_update = client.patch(
        f"/api/orders/{order_id}/status",
        json={"userId": viewer["id"], "status": "completed"},
    )
    assert buyer_status_update.status_code == 403

    thread = client.post(
        "/api/messages/threads",
        json={
            "userId": viewer["id"],
            "noteId": disabled_note.id,
            "orderActionId": order_id,
            "content": "老板，下午可以自提吗？",
        },
    )
    assert thread.status_code == 200
    thread_id = thread.json()["data"]["id"]
    thread_data = thread.json()["data"]
    assert thread_data["participants"][owner["id"]]["role"] == "owner"
    assert thread_data["participants"][viewer["id"]]["role"] == "buyer"
    assert thread_data["participants"][viewer["id"]]["nickname"] == viewer["nickname"]
    owner_threads = client.get("/api/messages/threads", params={"userId": owner["id"]})
    assert owner_threads.json()["data"]["unreadTotal"] == 1
    messages = client.get(f"/api/messages/threads/{thread_id}/messages", params={"userId": owner["id"]})
    assert messages.status_code == 200
    assert messages.json()["data"]["messages"][0]["content"] == "老板，下午可以自提吗？"
    assert messages.json()["data"]["thread"]["participants"][viewer["id"]]["avatarUrl"] == viewer["avatarUrl"]
    read = client.post(f"/api/messages/threads/{thread_id}/read", json={"userId": owner["id"]})
    assert read.status_code == 200
    assert read.json()["data"]["unreadCount"] == 0
    reply = client.post(
        f"/api/messages/threads/{thread_id}/messages",
        json={"userId": owner["id"], "content": "可以，到了发消息。"},
    )
    assert reply.status_code == 200
    outsider_messages = client.get(f"/api/messages/threads/{thread_id}/messages", params={"userId": outsider["id"]})
    assert outsider_messages.status_code == 403


def test_demo_data_includes_product_relay_mock_for_current_user(client):
    owner = client.post("/api/auth/mock-login", json={"nickname": "演示团长"}).json()["data"]
    created = client.post("/api/notes/demo-data", params={"ownerUserId": owner["id"]})
    assert created.status_code == 200
    notes = created.json()["data"]["notes"]
    product = next(item for item in notes if item["visibilityConfig"]["cardType"] == "groupbuy_product")
    assert product["ownerUserId"] == owner["id"]
    assert product["visibilityConfig"]["conversionConfig"]["enableGroupRelay"] is True

    listed = client.get("/api/notes", params={"ownerUserId": owner["id"]}).json()["data"]
    assert any(item["id"] == product["id"] for item in listed)

    owner_actions = client.get(f"/api/notes/{product['id']}/customer-actions", params={"ownerUserId": owner["id"]})
    assert owner_actions.status_code == 200
    action_data = owner_actions.json()["data"]
    assert action_data["summary"]["orderIntent"] == 1
    assert action_data["summary"]["relayIntent"] == 1
    assert action_data["summary"]["leads"] == 0
    assert action_data["actions"][0]["payload"]["skuName"] == "甜口 / 3斤装"


def test_manual_create_card_flow(client):
    login = client.post("/api/auth/mock-login", json={"nickname": "手动发布者"}).json()["data"]
    response = client.post(
        "/api/cards",
        json={
            "ownerUserId": login["id"],
            "title": "手动添加资源",
            "detailText": "这是一条手动添加的资源详情",
            "projectName": "悦享测试",
            "locationText": "上海",
            "phone": "13900000000",
            "relayConfig": {"enabled": True, "requirePhone": True, "requireAddress": False},
        },
    )

    assert response.status_code == 200
    card = response.json()["data"]
    assert card["ownerUserId"] == login["id"]
    assert card["status"] == "draft"
    assert card["title"] == "手动添加资源"

    cards = client.get("/api/cards", params={"ownerUserId": login["id"]}).json()["data"]
    assert any(item["id"] == card["id"] for item in cards)


def test_manual_create_card_persists_media_payload(client):
    login = client.post("/api/auth/mock-login", json={"nickname": "素材资源用户"}).json()["data"]
    response = client.post(
        "/api/cards",
        json={
            "ownerUserId": login["id"],
            "title": "带素材资源",
            "detailText": "包含详情素材",
            "coverUrl": "http://127.0.0.1:8000/media/cover.png",
            "media": [
                {"type": "image", "url": "http://127.0.0.1:8000/media/cover.png", "sortOrder": 1},
                {"type": "image", "url": "http://127.0.0.1:8000/media/detail-1.png", "sortOrder": 2},
                {"type": "video", "url": "http://127.0.0.1:8000/media/detail-2.mp4", "sortOrder": 3},
            ],
        },
    )

    assert response.status_code == 200
    card = response.json()["data"]
    assert len(card["media"]) == 3
    assert card["media"][1]["url"].endswith("detail-1.png")
    assert card["media"][2]["type"] == "video"


def test_update_card_flow_accepts_relay_config_payload(client):
    login = client.post("/api/auth/mock-login", json={"nickname": "编辑资源用户"}).json()["data"]
    created = client.post(
        "/api/cards",
        json={
            "ownerUserId": login["id"],
            "title": "待编辑资源",
            "detailText": "初始内容",
            "projectName": "初始项目",
            "relayConfig": {"enabled": True, "requirePhone": False, "requireAddress": False},
        },
    )
    assert created.status_code == 200
    card = created.json()["data"]

    updated = client.put(
        f"/api/cards/{card['id']}",
        json={
            "ownerUserId": login["id"],
            "title": "已编辑资源",
            "detailText": "编辑后内容",
            "projectName": "编辑后项目",
            "locationText": "上海",
            "phone": "13900000000",
            "relayNotice": "请联系我",
            "sourceUrl": None,
            "enabledFields": [],
            "categoryIds": [],
            "media": [
                {"type": "image", "url": "http://127.0.0.1:8000/media/edit-cover.png", "sortOrder": 1},
                {"type": "video", "url": "http://127.0.0.1:8000/media/edit-video.mp4", "sortOrder": 2},
            ],
            "relayConfig": {"enabled": True, "requirePhone": True, "requireAddress": False},
        },
    )

    assert updated.status_code == 200
    payload = updated.json()["data"]
    assert payload["title"] == "已编辑资源"
    assert payload["relayConfig"]["requirePhone"] is True
    assert len(payload["media"]) == 2


def test_delete_card_flow_removes_card(client):
    login = client.post("/api/auth/mock-login", json={"nickname": "删除资源用户"}).json()["data"]
    created = client.post(
        "/api/cards",
        json={
            "ownerUserId": login["id"],
            "title": "待删除资源",
            "detailText": "删除前内容",
        },
    )
    assert created.status_code == 200
    card_id = created.json()["data"]["id"]

    deleted = client.delete(f"/api/cards/{card_id}", params={"ownerUserId": login["id"]})
    assert deleted.status_code == 200
    assert deleted.json()["data"]["deletedCardId"] == card_id

    missing = client.get(f"/api/cards/{card_id}")
    assert missing.status_code == 404


def test_manual_asset_upload_returns_media_url(client):
    login = client.post("/api/auth/mock-login", json={"nickname": "上传用户"}).json()["data"]

    response = client.post(
        "/api/uploads/asset",
        data={"ownerUserId": login["id"], "mediaType": "image"},
        files={"file": ("cover.png", b"image-bytes", "image/png")},
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["mediaType"] == "image"
    assert payload["name"] == "cover.png"
    assert payload["url"]


def test_manual_image_upload_compresses_before_storage(client, tmp_path):
    service = client.app.dependency_overrides[get_app_service]()
    media_dir = tmp_path / "media"
    service.media_storage_service = MediaStorageService("local", media_dir, "/media")
    service.media_processing_service = MediaProcessingService(image_max_edge=640, image_quality=80)
    login = client.post("/api/auth/mock-login", json={"nickname": "压缩上传用户"}).json()["data"]
    image = Image.new("RGB", (1800, 1200), (200, 60, 60))
    output = BytesIO()
    image.save(output, format="PNG")

    response = client.post(
        "/api/uploads/asset",
        data={"ownerUserId": login["id"], "mediaType": "image"},
        files={"file": ("large.png", output.getvalue(), "image/png")},
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["mediaType"] == "image"
    assert payload["contentType"] == "image/webp"
    assert payload["compressed"] is True
    assert payload["storedSize"] < payload["originalSize"]
    stored_files = list(media_dir.iterdir())
    assert len(stored_files) == 1
    with Image.open(stored_files[0]) as stored:
        assert stored.format == "WEBP"
        assert max(stored.size) <= 640


def test_lead_reminder_flow_persists_status_note_and_filters(client):
    owner = client.post("/api/auth/mock-login", json={"nickname": "线索团长"}).json()["data"]
    other = client.post("/api/auth/mock-login", json={"nickname": "其他用户"}).json()["data"]
    card = client.post(
        "/api/cards",
        json={
            "ownerUserId": owner["id"],
            "title": "高意向资源",
            "detailText": "线索持久化测试",
        },
    ).json()["data"]

    created = client.post(
        "/api/lead-reminders",
        json={
            "ownerUserId": owner["id"],
            "cardId": card["id"],
            "viewerUserId": "viewer-high",
            "nickname": "高意向访客",
            "avatarUrl": "",
            "status": "pending",
            "note": "先问预算",
            "viewCount": 3,
            "lastViewedAt": "2026-06-09T15:00:00+08:00",
        },
    )
    assert created.status_code == 200
    reminder = created.json()["data"]
    assert reminder["status"] == "pending"
    assert reminder["note"] == "先问预算"

    listed = client.get("/api/lead-reminders", params={"ownerUserId": owner["id"]}).json()["data"]
    assert len(listed) == 1
    assert listed[0]["cardTitle"] == "高意向资源"

    detail = client.get(
        f"/api/lead-reminders/{reminder['id']}",
        params={"ownerUserId": owner["id"]},
    )
    assert detail.status_code == 200
    assert detail.json()["data"]["cardTitle"] == "高意向资源"

    profile_update = client.put(
        f"/api/lead-reminders/{reminder['id']}",
        json={
            "ownerUserId": owner["id"],
            "customerPhone": "13800000000",
            "customerWechat": "wx_high_intent",
            "budgetText": "300 万内",
            "intentLevel": "高意向",
            "customerTags": ["改善", "老客户"],
        },
    )
    assert profile_update.status_code == 200
    profile_payload = profile_update.json()["data"]
    assert profile_payload["customerPhone"] == "13800000000"
    assert profile_payload["customerWechat"] == "wx_high_intent"
    assert profile_payload["budgetText"] == "300 万内"
    assert profile_payload["intentLevel"] == "高意向"
    assert profile_payload["customerTags"] == ["改善", "老客户"]

    forbidden_detail = client.get(
        f"/api/lead-reminders/{reminder['id']}",
        params={"ownerUserId": other["id"]},
    )
    assert forbidden_detail.status_code == 403

    forbidden = client.put(
        f"/api/lead-reminders/{reminder['id']}",
        json={"ownerUserId": other["id"], "status": "contacted"},
    )
    assert forbidden.status_code == 403

    contacted = client.put(
        f"/api/lead-reminders/{reminder['id']}",
        json={
            "ownerUserId": owner["id"],
            "status": "contacted",
            "note": "已电话联系",
            "nextFollowUpAt": "2026-06-12",
            "logContent": "电话沟通过，想再看一次详情",
        },
    )
    assert contacted.status_code == 200
    contacted_payload = contacted.json()["data"]
    assert contacted_payload["status"] == "contacted"
    assert contacted_payload["note"] == "已电话联系"
    assert contacted_payload["contactedAt"]
    assert contacted_payload["nextFollowUpAt"] == "2026-06-12"
    assert contacted_payload["followUpLogs"][0]["content"] == "电话沟通过，想再看一次详情"

    archived = client.put(
        f"/api/lead-reminders/{reminder['id']}",
        json={"ownerUserId": owner["id"], "status": "invalid", "conclusionReason": "客户明确不需要"},
    )
    assert archived.status_code == 200
    archived_payload = archived.json()["data"]
    assert archived_payload["status"] == "invalid"
    assert archived_payload["conclusionReason"] == "客户明确不需要"
    assert archived_payload["closedAt"]

    invalid_rows = client.get(
        "/api/lead-reminders",
        params={"ownerUserId": owner["id"], "status": "invalid"},
    ).json()["data"]
    assert len(invalid_rows) == 1

    restored = client.put(
        f"/api/lead-reminders/{reminder['id']}",
        json={"ownerUserId": owner["id"], "status": "pending"},
    )
    assert restored.status_code == 200
    restored_payload = restored.json()["data"]
    assert restored_payload["status"] == "pending"
    assert restored_payload["conclusionReason"] is None
    assert restored_payload["closedAt"] is None

    pending = client.get(
        "/api/lead-reminders",
        params={"ownerUserId": owner["id"], "status": "pending"},
    ).json()["data"]
    assert len(pending) == 1
    contacted_rows = client.get(
        "/api/lead-reminders",
        params={"ownerUserId": owner["id"], "status": "contacted"},
    ).json()["data"]
    assert contacted_rows == []

    deleted = client.delete(
        f"/api/lead-reminders/{reminder['id']}",
        params={"ownerUserId": owner["id"]},
    )
    assert deleted.status_code == 200
    assert client.get("/api/lead-reminders", params={"ownerUserId": owner["id"]}).json()["data"] == []


def test_category_management_and_filtering(client):
    login = client.post("/api/auth/mock-login", json={"nickname": "标签用户"}).json()["data"]
    created = client.post(
        "/api/categories",
        json={"ownerUserId": login["id"], "name": "学区房"},
    )
    assert created.status_code == 200
    category = created.json()["data"]

    card_response = client.post(
        "/api/cards",
        json={
            "ownerUserId": login["id"],
            "title": "带标签资源",
            "detailText": "标签筛选测试",
            "categoryIds": [category["id"]],
        },
    )
    assert card_response.status_code == 200

    filtered = client.get(
        "/api/cards",
        params={"ownerUserId": login["id"], "categoryId": category["id"]},
    ).json()["data"]
    assert len(filtered) == 1
    assert filtered[0]["title"] == "带标签资源"

    delete = client.delete(
        f"/api/categories/{category['id']}",
        params={"ownerUserId": login["id"]},
    )
    assert delete.status_code == 200

    categories = client.get("/api/categories", params={"ownerUserId": login["id"]}).json()["data"]
    assert categories == []
    card = client.get(f"/api/cards/{card_response.json()['data']['id']}").json()["data"]
    assert card["categoryIds"] == []


def test_anonymous_and_logged_in_view_stats_are_isolated(client):
    login = client.post("/api/auth/mock-login", json={"nickname": "浏览用户"}).json()["data"]
    card_id = "card_seed_001"

    client.post(
        f"/api/cards/{card_id}/view",
        json={"viewerUserId": login["id"], "nickname": login["nickname"], "avatarUrl": login["avatarUrl"]},
    )
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
    browser_viewer = next(item for item in owner_stats["loggedInViewers"] if item["nickname"] == "浏览用户")
    assert browser_viewer["viewCount"] == 2
    assert all(item["nickname"] != "匿名用户" for item in owner_stats["loggedInViewers"])


def test_relay_requires_phone_when_enabled(client):
    card_id = "card_seed_001"
    response = client.post(
        f"/api/cards/{card_id}/relay",
        json={"userId": "user_seed_owner", "nickname": "张团长"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "手机号为必填项"


def test_non_owner_stats_masks_relay_private_fields(client):
    card_id = "card_seed_001"
    relay_response = client.post(
        f"/api/cards/{card_id}/relay",
        json={
            "userId": "user_customer_alpha",
            "nickname": "Alice",
            "phone": "13900000000",
            "address": "North Garden 1",
        },
    )
    assert relay_response.status_code == 200

    public_stats = client.get(
        f"/api/cards/{card_id}/stats",
        params={"requesterUserId": "user_customer_beta"},
    ).json()["data"]
    owner_stats = client.get(
        f"/api/cards/{card_id}/stats",
        params={"requesterUserId": "user_seed_owner"},
    ).json()["data"]

    public_entry = next(item for item in public_stats["relayEntries"] if item["userId"] == "user_customer_alpha")
    owner_entry = next(item for item in owner_stats["relayEntries"] if item["userId"] == "user_customer_alpha")

    assert public_entry["nickname"] != "Alice"
    assert public_entry["phone"] is None
    assert public_entry["address"] is None
    assert owner_entry["nickname"] == "Alice"
    assert owner_entry["phone"] == "13900000000"
    assert owner_entry["address"] == "North Garden 1"


def test_customer_relay_submission_is_single_active_entry(client):
    card_id = "card_seed_001"
    payload = {
        "userId": "user_customer_repeat",
        "nickname": "Repeat User",
        "phone": "13900000000",
        "address": "North Garden 2",
    }

    first = client.post(f"/api/cards/{card_id}/relay", json=payload)
    assert first.status_code == 200
    relay_id = first.json()["data"]["id"]

    stats = client.get(
        f"/api/cards/{card_id}/stats",
        params={"requesterUserId": "user_customer_repeat"},
    ).json()["data"]
    assert stats["currentUserRelay"]["userId"] == "user_customer_repeat"
    assert stats["currentUserRelay"]["followUpStatus"] == "pending"

    follow = client.post(
        f"/api/relays/{relay_id}/follow-up",
        json={"operatorUserId": "user_seed_owner"},
    )
    assert follow.status_code == 200

    followed_stats = client.get(
        f"/api/cards/{card_id}/stats",
        params={"requesterUserId": "user_customer_repeat"},
    ).json()["data"]
    assert followed_stats["currentUserRelay"]["followUpStatus"] == "followed"

    second = client.post(f"/api/cards/{card_id}/relay", json=payload)
    assert second.status_code == 409
    assert second.json()["detail"] == "你已经提交过接龙"


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


def test_service_note_resources_are_listed_as_library_cards(client):
    login = client.post("/api/auth/mock-login", json={"nickname": "服务顾问"}).json()["data"]
    created = client.post(
        "/api/notes/manual-draft",
        json={
            "ownerUserId": login["id"],
            "cardType": "service_offer",
            "inputMode": "blank",
            "rawText": "",
            "title": "客户咨询方案",
        },
    )
    assert created.status_code == 200
    note_id = created.json()["data"]["id"]

    updated = client.put(
        f"/api/notes/{note_id}",
        json={
            "ownerUserId": login["id"],
            "title": "客户咨询方案",
            "summary": "先沟通需求，再给清晰建议",
            "body": "需求梳理、问题分析、方案建议、后续跟进",
            "coverUrl": "",
            "media": [],
            "categoryIds": [],
            "phone": "",
            "locationText": "线上 / 本地均可",
            "visibilityConfig": {
                "cardType": "service_offer",
                "systemCategory": "服务",
                "sourceType": "service_offer_studio",
                "structuredData": {
                    "serviceName": "客户咨询方案",
                    "serviceContent": "需求梳理、问题分析、方案建议、后续跟进",
                },
            },
        },
    )
    assert updated.status_code == 200

    cards = client.get("/api/cards", params={"ownerUserId": login["id"]}).json()["data"]
    service_card = next(item for item in cards if item.get("sourceNoteId") == note_id)
    assert service_card["id"] == f"note_card_{note_id}"
    assert service_card["cardType"] == "service_offer"
    assert service_card["categoryName"] == "服务"
    assert service_card["title"] == "客户咨询方案"


def test_owner_can_delete_and_follow_relay(client):
    relay_response = client.post(
        "/api/cards/card_seed_001/relay",
        json={
            "userId": "user_customer_follow",
            "nickname": "Follow User",
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


def test_robot_gateway_requires_token(client, monkeypatch):
    monkeypatch.setattr(settings, "robot_gateway_token", "robot-secret")

    response = client.post(
        "/api/robot/query",
        json={"chatType": "private", "externalUserId": "wm_robot_user", "text": "帮我找资料"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "robot gateway token verification failed"


def test_robot_gateway_self_query_is_bound_to_sender_owner(client, monkeypatch):
    monkeypatch.setattr(settings, "robot_gateway_token", "robot-secret")
    owner = client.post("/api/auth/mock-login", json={"nickname": "机器人用户A", "openid": "openid_robot_owner_a"}).json()["data"]
    other = client.post("/api/auth/mock-login", json={"nickname": "机器人用户B", "openid": "openid_robot_owner_b"}).json()["data"]
    service = client.app.dependency_overrides[get_app_service]()
    now = now_iso()
    service.repo.save_user_note(
        UserNote(
            id="note_robot_owner_a",
            ownerUserId=owner["id"],
            status="active",
            title="长沙房源合集素材",
            summary="A 用户自己的资料",
            body="长沙房源，客户可转发",
            createdAt=now,
            updatedAt=now,
        )
    )
    service.repo.save_user_note(
        UserNote(
            id="note_robot_owner_b",
            ownerUserId=other["id"],
            status="active",
            title="长沙房源合集素材",
            summary="B 用户自己的资料",
            body="这条不应该被 A 查到",
            createdAt=now,
            updatedAt=now,
        )
    )
    service.repo.save_wecom_identity_binding(
        WecomIdentityBinding(
            id="bind_robot_owner_a",
            sourceType="wecom_external_user",
            externalUserId="wm_robot_owner_a",
            ownerUserId=owner["id"],
            ownerOpenid=owner["openid"],
            bindSource="robot_test",
            createdAt=now,
            updatedAt=now,
        )
    )

    missing = client.post(
        "/api/robot/query",
        headers={"Authorization": "Bearer robot-secret"},
        json={"chatType": "private", "externalUserId": "wm_not_bound", "text": "帮我找长沙房源资料"},
    )
    assert missing.status_code == 200
    assert missing.json()["data"]["replyType"] == "bind_required"

    response = client.post(
        "/api/robot/query",
        headers={"Authorization": "Bearer robot-secret"},
        json={"chatType": "private", "externalUserId": "wm_robot_owner_a", "text": "帮我找长沙房源资料"},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["scope"] == "self"
    assert data["replyType"] == "miniapp_list"
    assert [item["id"] for item in data["items"]] == ["note_robot_owner_a"]
    assert data["items"][0]["path"] == "/pages/note-preview/index?id=note_robot_owner_a"


def test_robot_gateway_keeps_self_query_private_in_group(client, monkeypatch):
    monkeypatch.setattr(settings, "robot_gateway_token", "robot-secret")

    response = client.post(
        "/api/robot/query",
        headers={"Authorization": "Bearer robot-secret"},
        json={
            "chatType": "group",
            "roomId": "wr_test_room",
            "externalUserId": "wm_robot_owner_a",
            "text": "我的客户雷达怎么样",
        },
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["replyType"] == "private_required"
    assert "私聊" in data["text"]


def test_wecom_group_bot_config_requires_admin_token(client, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", "group-admin")

    response = client.get("/api/wecom/group-bot/config")

    assert response.status_code == 403
    assert response.json()["detail"] == "admin token verification failed"


def test_wecom_group_bot_broadcast_dry_run_renders_template(client, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", "group-admin")
    monkeypatch.setattr(
        settings,
        "wecom_group_bot_webhooks",
        json.dumps({
            "property": "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=property-secret",
            "resource": "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=resource-secret",
        }),
    )

    config = client.get("/api/wecom/group-bot/config", headers={"X-Admin-Token": "group-admin"})
    assert config.status_code == 200
    assert config.json()["data"]["configured"] is True
    assert config.json()["data"]["groups"][0]["webhook"].endswith("***cret")

    response = client.post(
        "/api/wecom/group-bot/broadcast",
        headers={"X-Admin-Token": "group-admin"},
        json={
            "groupIds": ["property", "resource"],
            "template": "midday",
            "variables": {"topic": "岳麓区房源", "count": 12, "focus": "地铁口两房"},
            "miniappPath": "/pages/showcase-view/index?id=showcase_today",
        },
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["dryRun"] is True
    assert data["targetCount"] == 2
    assert data["sentCount"] == 0
    assert "岳麓区房源 新增 12 条" in data["content"]
    assert data["results"] == [
        {"groupId": "property", "status": "dryRun", "webhook": "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=prop***cret"},
        {"groupId": "resource", "status": "dryRun", "webhook": "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=reso***cret"},
    ]


def test_wecom_group_bot_broadcast_sends_to_configured_groups(client, monkeypatch):
    from app.api import routes_wecom

    sent = []

    async def fake_post_group_bot_webhook(webhook_url, content):
        sent.append({"webhook": webhook_url, "content": content})
        return {"errcode": 0, "errmsg": "ok"}

    monkeypatch.setattr(settings, "admin_token", "group-admin")
    monkeypatch.setattr(
        settings,
        "wecom_group_bot_webhooks",
        json.dumps({"property": "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=property-secret"}),
    )
    monkeypatch.setattr(routes_wecom, "_post_group_bot_webhook", fake_post_group_bot_webhook)

    response = client.post(
        "/api/wecom/group-bot/broadcast",
        headers={"X-Admin-Token": "group-admin"},
        json={"groupId": "property", "content": "今天新增 3 条房源", "dryRun": False},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["sentCount"] == 1
    assert data["results"][0]["status"] == "sent"
    assert sent == [{
        "webhook": "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=property-secret",
        "content": "今天新增 3 条房源",
    }]


def test_ops_admin_group_bot_channel_mapping_can_be_used_for_broadcast(client, monkeypatch):
    from app.api import routes_wecom

    sent = []

    async def fake_post_group_bot_webhook(webhook_url, content):
        sent.append({"webhook": webhook_url, "content": content})
        return {"errcode": 0, "errmsg": "ok"}

    monkeypatch.setattr(settings, "admin_token", "group-admin")
    monkeypatch.setattr(settings, "wecom_group_bot_webhooks", "")
    monkeypatch.setattr(routes_wecom, "_post_group_bot_webhook", fake_post_group_bot_webhook)

    saved = client.post(
        "/api/ops-admin/group-bot-channels",
        headers={"X-Admin-Token": "group-admin"},
        json={
            "groupId": "resource_test",
            "groupName": "资料助手资源测试群",
            "webhook": "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=resource-secret",
            "groupType": "测试群",
            "audience": "运营内测",
            "dailyTemplate": "midday",
            "sendWindow": "12:00",
            "enabled": True,
        },
    )

    assert saved.status_code == 200
    assert saved.json()["data"]["webhook"] == "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=reso***cret"

    listing = client.get("/api/ops-admin/group-bot-channels", headers={"X-Admin-Token": "group-admin"})
    assert listing.status_code == 200
    assert listing.json()["data"][0]["groupId"] == "resource_test"
    assert listing.json()["data"][0]["webhook"].endswith("***cret")

    config = client.get("/api/wecom/group-bot/config", headers={"X-Admin-Token": "group-admin"})
    assert config.status_code == 200
    assert config.json()["data"]["groups"] == [{
        "groupId": "resource_test",
        "webhook": "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=reso***cret",
    }]

    response = client.post(
        "/api/wecom/group-bot/broadcast",
        headers={"X-Admin-Token": "group-admin"},
        json={"groupId": "resource_test", "content": "资料助手日报测试", "dryRun": False},
    )

    assert response.status_code == 200
    assert response.json()["data"]["sentCount"] == 1
    assert sent == [{
        "webhook": "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=resource-secret",
        "content": "资料助手日报测试",
    }]


def test_wecom_group_bot_broadcast_dry_run_builds_miniapp_card(client, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", "group-admin")
    monkeypatch.setattr(settings, "wechat_miniapp_appid", "wx-test-appid")
    monkeypatch.setattr(
        settings,
        "wecom_group_bot_webhooks",
        json.dumps({"resource_test": "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=resource-secret"}),
    )

    response = client.post(
        "/api/wecom/group-bot/broadcast",
        headers={"X-Admin-Token": "group-admin"},
        json={
            "groupId": "resource_test",
            "messageType": "miniapp_card",
            "template": "midday",
            "variables": {"topic": "资料助手内测", "count": 3, "focus": "外部群日报运营演习"},
            "miniappPath": "pages/home/index",
            "cardTitle": "小程序卡片测试",
            "cardDescription": "打开资料整理助手首页",
        },
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["dryRun"] is True
    assert data["messageType"] == "miniapp_card"
    assert data["sendPayload"]["msgtype"] == "template_card"
    assert data["sendPayload"]["template_card"]["card_action"] == {
        "type": 2,
        "appid": "wx-test-appid",
        "pagepath": "pages/home/index",
    }


def test_wecom_group_bot_broadcast_sends_miniapp_card(client, monkeypatch):
    from app.api import routes_wecom

    sent = []

    async def fake_post_group_bot_webhook_payload(webhook_url, payload):
        sent.append({"webhook": webhook_url, "payload": payload})
        return {"errcode": 0, "errmsg": "ok"}

    monkeypatch.setattr(settings, "admin_token", "group-admin")
    monkeypatch.setattr(settings, "wechat_miniapp_appid", "wx-test-appid")
    monkeypatch.setattr(
        settings,
        "wecom_group_bot_webhooks",
        json.dumps({"resource_test": "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=resource-secret"}),
    )
    monkeypatch.setattr(routes_wecom, "_post_group_bot_webhook_payload", fake_post_group_bot_webhook_payload)

    response = client.post(
        "/api/wecom/group-bot/broadcast",
        headers={"X-Admin-Token": "group-admin"},
        json={
            "groupId": "resource_test",
            "messageType": "miniapp_card",
            "content": "资料助手小程序卡片发送测试",
            "miniappPath": "pages/home/index",
            "dryRun": False,
        },
    )

    assert response.status_code == 200
    assert response.json()["data"]["sentCount"] == 1
    assert sent[0]["webhook"] == "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=resource-secret"
    assert sent[0]["payload"]["msgtype"] == "template_card"
    assert sent[0]["payload"]["template_card"]["jump_list"][0]["appid"] == "wx-test-appid"
