from __future__ import annotations

import base64
import json
import re
import time
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from Crypto.Cipher import AES
from Crypto.Hash import SHA256
from Crypto.PublicKey import RSA
from Crypto.Signature import pkcs1_15

from app.api.dependencies import get_app_service
from app.core.config import settings
from app.models.domain import ReferralReward
from app.services.wechat_pay import WechatPayClient, WechatPayError
from app.services.time_utils import now_iso


def login(client, openid: str):
    return client.post("/api/auth/mock-login", json={"openid": openid, "nickname": "支付测试用户"}).json()["data"]


def configure_payment(monkeypatch, tmp_path: Path):
    merchant_key = RSA.generate(2048)
    platform_key = RSA.generate(2048)
    merchant_path = tmp_path / "merchant.pem"
    platform_path = tmp_path / "platform.pem"
    merchant_path.write_bytes(merchant_key.export_key())
    platform_path.write_bytes(platform_key.publickey().export_key())
    api_v3_key = "0123456789abcdef0123456789abcdef"
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(settings, "wechat_pay_enabled", True)
    monkeypatch.setattr(settings, "wechat_miniapp_appid", "wx-test-pay")
    monkeypatch.setattr(settings, "wechat_pay_mch_id", "1111636477")
    monkeypatch.setattr(settings, "wechat_pay_api_v3_key", api_v3_key)
    monkeypatch.setattr(settings, "wechat_pay_cert_serial_no", "merchant-serial")
    monkeypatch.setattr(settings, "wechat_pay_private_key_path", merchant_path)
    monkeypatch.setattr(settings, "wechat_pay_platform_cert_serial_no", "platform-serial")
    monkeypatch.setattr(settings, "wechat_pay_platform_cert_path", platform_path)
    monkeypatch.setattr(settings, "wechat_pay_notify_url", "https://example.test/api/scrm/wechat-pay/notify")
    return merchant_key, platform_key, api_v3_key


def configure_transfer(monkeypatch, tmp_path: Path):
    merchant_key, platform_key, api_v3_key = configure_payment(monkeypatch, tmp_path)
    monkeypatch.setattr(settings, "wechat_transfer_enabled", True)
    monkeypatch.setattr(settings, "wechat_transfer_scene_id", "1005")
    monkeypatch.setattr(settings, "wechat_transfer_notify_url", "https://example.test/api/scrm/wechat-transfer/notify")
    return merchant_key, platform_key, api_v3_key


def make_notification(merchant_key: RSA.RsaKey, api_v3_key: str, transaction: dict) -> tuple[bytes, dict]:
    resource_nonce = "resource12345"
    associated_data = "transaction"
    cipher = AES.new(api_v3_key.encode("utf-8"), AES.MODE_GCM, nonce=resource_nonce.encode("utf-8"))
    cipher.update(associated_data.encode("utf-8"))
    ciphertext, tag = cipher.encrypt_and_digest(json.dumps(transaction, separators=(",", ":")).encode("utf-8"))
    payload = {
        "id": "notification-test-1",
        "create_time": "2026-08-16T10:00:00+08:00",
        "event_type": "TRANSACTION.SUCCESS",
        "resource_type": "encrypt-resource",
        "resource": {
            "algorithm": "AEAD_AES_256_GCM",
            "ciphertext": base64.b64encode(ciphertext + tag).decode("ascii"),
            "associated_data": associated_data,
            "nonce": resource_nonce,
        },
    }
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    timestamp = str(int(time.time()))
    nonce = "notification-nonce"
    message = f"{timestamp}\n{nonce}\n{body.decode('utf-8')}\n"
    signature = base64.b64encode(
        pkcs1_15.new(merchant_key).sign(SHA256.new(message.encode("utf-8")))
    ).decode("ascii")
    return body, {
        "Wechatpay-Timestamp": timestamp,
        "Wechatpay-Nonce": nonce,
        "Wechatpay-Signature": signature,
        "Wechatpay-Serial": "platform-serial",
    }


def make_api_response_signature(platform_key: RSA.RsaKey, payload: dict) -> tuple[bytes, dict]:
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    timestamp = str(int(time.time()))
    nonce = "response-nonce"
    message = f"{timestamp}\n{nonce}\n{body.decode('utf-8')}\n"
    signature = base64.b64encode(
        pkcs1_15.new(platform_key).sign(SHA256.new(message.encode("utf-8")))
    ).decode("ascii")
    return body, {
        "Wechatpay-Timestamp": timestamp,
        "Wechatpay-Nonce": nonce,
        "Wechatpay-Signature": signature,
        "Wechatpay-Serial": "platform-serial",
    }


def test_merchant_transfer_builds_1005_request_and_verifies_request_signature(monkeypatch, tmp_path):
    merchant_key, platform_key, _ = configure_transfer(monkeypatch, tmp_path)
    captured = {}

    class FakeResponse:
        status_code = 200

        def __init__(self, payload, content, headers):
            self.payload = payload
            self.content = content
            self.headers = headers

        def json(self):
            return self.payload

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured["body"] = kwargs["content"].decode("utf-8")
        captured["headers"] = kwargs["headers"]
        payload = {
            "out_bill_no": "wdTest1005A1",
            "transfer_bill_no": "103000000000000001",
            "state": "WAIT_USER_CONFIRM",
            "package_info": "transfer-package-test",
        }
        body, headers = make_api_response_signature(platform_key, payload)
        return FakeResponse(payload, body, headers)

    monkeypatch.setattr("app.services.wechat_pay.httpx.post", fake_post)
    result = WechatPayClient(settings).create_merchant_transfer(
        openid="openid_transfer_user",
        out_bill_no="wdTest1005A1",
        amount_fen=995,
    )

    assert result["state"] == "WAIT_USER_CONFIRM"
    assert captured["url"].endswith("/v3/fund-app/mch-transfer/transfer-bills")
    body = json.loads(captured["body"])
    assert body["appid"] == "wx-test-pay"
    assert body["transfer_scene_id"] == "1005"
    assert body["openid"] == "openid_transfer_user"
    assert body["transfer_amount"] == 995
    assert body["transfer_remark"] == "推广佣金"
    assert body["transfer_scene_report_infos"] == [
        {"info_type": "岗位类型", "info_content": "推广用户"},
        {"info_type": "报酬说明", "info_content": "会员推广佣金"},
    ]

    auth = captured["headers"]["Authorization"]
    match = re.search(
        r'nonce_str="([^"]+)",timestamp="([^"]+)",serial_no="[^"]+",signature="([^"]+)"',
        auth,
    )
    assert match
    nonce, timestamp, signature = match.groups()
    signed_message = f"POST\n/v3/fund-app/mch-transfer/transfer-bills\n{timestamp}\n{nonce}\n{captured['body']}\n"
    pkcs1_15.new(merchant_key.publickey()).verify(
        SHA256.new(signed_message.encode("utf-8")),
        base64.b64decode(signature),
    )


def test_merchant_transfer_is_disabled_by_default(monkeypatch, tmp_path):
    configure_transfer(monkeypatch, tmp_path)
    monkeypatch.setattr(settings, "wechat_transfer_enabled", False)
    with pytest.raises(WechatPayError, match="商家转账未启用"):
        WechatPayClient(settings).create_merchant_transfer(
            openid="openid_transfer_disabled",
            out_bill_no="wdDisabled1",
            amount_fen=100,
        )


def test_merchant_transfer_does_not_retry_failed_request(monkeypatch, tmp_path):
    configure_transfer(monkeypatch, tmp_path)
    calls = {"count": 0}

    class FakeResponse:
        status_code = 500

        def json(self):
            return {"code": "SYSTEM_ERROR"}

    def fake_post(*args, **kwargs):
        calls["count"] += 1
        return FakeResponse()

    monkeypatch.setattr("app.services.wechat_pay.httpx.post", fake_post)
    with pytest.raises(WechatPayError, match="查询原商户单号"):
        WechatPayClient(settings).create_merchant_transfer(
            openid="openid_transfer_failed",
            out_bill_no="wdFailed1",
            amount_fen=100,
        )
    assert calls["count"] == 1


def test_admin_approval_and_transfer_callback_settle_referral_withdrawal(client, monkeypatch, tmp_path):
    merchant_key, platform_key, api_v3_key = configure_transfer(monkeypatch, tmp_path)
    monkeypatch.setattr(settings, "admin_token", "ops-secret")
    user = login(client, "openid_referral_transfer_user")
    service = client.app.dependency_overrides[get_app_service]()
    now = now_iso()
    state = service._load()
    state.referral_rewards.append(
        ReferralReward(
            id="referral_reward_transfer_test",
            inviterUserId=user["id"],
            inviteeUserId="transfer_test_invitee",
            sourceOrderId="transfer_test_order",
            amountFen=10,
            status="available",
            availableAt=now,
            createdAt=now,
            updatedAt=now,
        )
    )
    service._save(state)
    withdrawal_response = client.post(
        "/api/scrm/referrals/withdrawals",
        json={"userId": user["id"], "amountFen": 10},
    )
    assert withdrawal_response.status_code == 200
    withdrawal = withdrawal_response.json()["data"]

    class FakeResponse:
        status_code = 200

        def __init__(self, payload, content, headers):
            self.payload = payload
            self.content = content
            self.headers = headers

        def json(self):
            return self.payload

    def fake_post(url, **kwargs):
        payload = json.loads(kwargs["content"])
        response_payload = {
            "out_bill_no": payload["out_bill_no"],
            "transfer_bill_no": "103000000000000010",
            "state": "WAIT_USER_CONFIRM",
            "package_info": "transfer-package-integration-test",
        }
        body, headers = make_api_response_signature(platform_key, response_payload)
        return FakeResponse(response_payload, body, headers)

    monkeypatch.setattr("app.services.wechat_pay.httpx.post", fake_post)
    approval = client.post(
        f"/api/ops-admin/referral-withdrawals/{withdrawal['id']}/approve",
        headers={"X-Admin-Token": "ops-secret"},
    )
    assert approval.status_code == 200, approval.text
    approved = approval.json()["data"]
    assert approved["status"] == "waiting_user_confirm"
    assert approved["outBillNo"]
    assert approved["packageInfo"] == "transfer-package-integration-test"

    transfer = {
        "out_bill_no": approved["outBillNo"],
        "transfer_bill_no": "103000000000000010",
        "state": "SUCCESS",
        "transfer_amount": 10,
        "openid": user["openid"],
    }
    body, headers = make_notification(platform_key, api_v3_key, transfer)
    callback = client.post("/api/scrm/wechat-transfer/notify", content=body, headers=headers)
    assert callback.status_code == 200, callback.text
    assert callback.json()["code"] == "SUCCESS"
    duplicate = client.post("/api/scrm/wechat-transfer/notify", content=body, headers=headers)
    assert duplicate.status_code == 200

    center = client.get("/api/scrm/referrals", params={"userId": user["id"]}).json()["data"]
    assert center["totals"]["withdrawn"] == 10
    assert center["totals"]["reserved"] == 0
    assert center["withdrawals"][0]["status"] == "paid"


def test_admin_can_query_and_cancel_transfer_before_user_confirmation(client, monkeypatch, tmp_path):
    merchant_key, platform_key, _ = configure_transfer(monkeypatch, tmp_path)
    monkeypatch.setattr(settings, "admin_token", "ops-secret")
    user = login(client, "openid_referral_transfer_cancel_user")
    service = client.app.dependency_overrides[get_app_service]()
    now = now_iso()
    state = service._load()
    state.referral_rewards.append(
        ReferralReward(
            id="referral_reward_transfer_cancel_test",
            inviterUserId=user["id"],
            inviteeUserId="transfer_cancel_invitee",
            sourceOrderId="transfer_cancel_order",
            amountFen=10,
            status="available",
            availableAt=now,
            createdAt=now,
            updatedAt=now,
        )
    )
    service._save(state)
    withdrawal = client.post(
        "/api/scrm/referrals/withdrawals",
        json={"userId": user["id"], "amountFen": 10},
    ).json()["data"]

    class FakeResponse:
        status_code = 200

        def __init__(self, payload, content, headers):
            self.payload = payload
            self.content = content
            self.headers = headers

        def json(self):
            return self.payload

    def fake_post(url, **kwargs):
        if url.endswith("/cancel"):
            payload = {
                "out_bill_no": approved["outBillNo"],
                "transfer_bill_no": "103000000000000020",
                "state": "CANCELING",
            }
        else:
            request_payload = json.loads(kwargs["content"])
            payload = {
                "out_bill_no": request_payload["out_bill_no"],
                "transfer_bill_no": "103000000000000020",
                "state": "WAIT_USER_CONFIRM",
                "package_info": "transfer-package-cancel-test",
            }
        body, headers = make_api_response_signature(platform_key, payload)
        return FakeResponse(payload, body, headers)

    monkeypatch.setattr("app.services.wechat_pay.httpx.post", fake_post)
    approved = client.post(
        f"/api/ops-admin/referral-withdrawals/{withdrawal['id']}/approve",
        headers={"X-Admin-Token": "ops-secret"},
    ).json()["data"]
    assert approved["status"] == "waiting_user_confirm"

    queried_payload = {
        "out_bill_no": approved["outBillNo"],
        "transfer_bill_no": approved["transferBillNo"],
        "state": "WAIT_USER_CONFIRM",
        "transfer_amount": 10,
        "openid": user["openid"],
    }

    def fake_get(url, **kwargs):
        body, headers = make_api_response_signature(platform_key, queried_payload)
        return FakeResponse(queried_payload, body, headers)

    monkeypatch.setattr("app.services.wechat_pay.httpx.get", fake_get)
    queried = client.post(
        f"/api/ops-admin/referral-withdrawals/{withdrawal['id']}/query",
        headers={"X-Admin-Token": "ops-secret"},
    )
    assert queried.status_code == 200, queried.text
    assert queried.json()["data"]["withdrawal"]["status"] == "waiting_user_confirm"

    cancelling = client.post(
        f"/api/ops-admin/referral-withdrawals/{withdrawal['id']}/cancel",
        headers={"X-Admin-Token": "ops-secret"},
    )
    assert cancelling.status_code == 200, cancelling.text
    assert cancelling.json()["data"]["withdrawal"]["transferState"] == "CANCELING"
    center = client.get("/api/scrm/referrals", params={"userId": user["id"]}).json()["data"]
    assert center["totals"]["reserved"] == 10

    queried_payload["state"] = "CANCELLED"
    settled = client.post(
        f"/api/ops-admin/referral-withdrawals/{withdrawal['id']}/query",
        headers={"X-Admin-Token": "ops-secret"},
    )
    assert settled.status_code == 200, settled.text
    assert settled.json()["data"]["withdrawal"]["status"] == "cancelled"
    center = client.get("/api/scrm/referrals", params={"userId": user["id"]}).json()["data"]
    assert center["totals"]["reserved"] == 0
    assert center["totals"]["available"] == 10


def test_admin_can_manually_settle_legacy_paid_withdrawal(client, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", "ops-secret")
    user = login(client, "openid_referral_legacy_paid_user")
    service = client.app.dependency_overrides[get_app_service]()
    now = now_iso()
    state = service._load()
    state.referral_rewards.append(
        ReferralReward(
            id="referral_reward_legacy_paid_test",
            inviterUserId=user["id"],
            inviteeUserId="legacy_paid_invitee",
            sourceOrderId="legacy_paid_order",
            amountFen=20,
            status="available",
            availableAt=now,
            createdAt=now,
            updatedAt=now,
        )
    )
    service._save(state)
    withdrawal = client.post(
        "/api/scrm/referrals/withdrawals",
        json={"userId": user["id"], "amountFen": 20},
    ).json()["data"]

    settled = client.post(
        f"/api/ops-admin/referral-withdrawals/{withdrawal['id']}/settle",
        headers={"X-Admin-Token": "ops-secret"},
        params={"reason": "已核实微信到账"},
    )
    assert settled.status_code == 200, settled.text
    assert settled.json()["data"]["withdrawal"]["status"] == "paid"
    assert settled.json()["data"]["withdrawal"]["settlementSource"] == "manual"

    duplicate = client.post(
        f"/api/ops-admin/referral-withdrawals/{withdrawal['id']}/settle",
        headers={"X-Admin-Token": "ops-secret"},
    )
    assert duplicate.status_code == 200
    assert duplicate.json()["data"]["duplicate"] is True
    center = client.get("/api/scrm/referrals", params={"userId": user["id"]}).json()["data"]
    assert center["totals"]["withdrawn"] == 20
    assert center["totals"]["reserved"] == 0


def test_wechat_pay_order_signs_jsapi_parameters_and_callback_is_idempotent(client, monkeypatch, tmp_path):
    merchant_key, platform_key, api_v3_key = configure_payment(monkeypatch, tmp_path)
    user = login(client, "openid_wechat_pay_user")
    captured = {}

    class FakeResponse:
        status_code = 200

        def json(self):
            return {"prepay_id": "wx-prepay-test"}

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured["body"] = json.loads(kwargs["content"])
        return FakeResponse()

    monkeypatch.setattr("app.services.wechat_pay.httpx.post", fake_post)
    order_response = client.post("/api/scrm/membership/orders", json={"userId": user["id"]})
    assert order_response.status_code == 200
    order = order_response.json()["data"]["order"]
    payment_response = client.post(
        f"/api/scrm/membership/orders/{order['id']}/pay",
        json={"userId": user["id"]},
    )
    assert payment_response.status_code == 200
    payment = payment_response.json()["data"]["payment"]
    assert captured["url"].endswith("/v3/pay/transactions/jsapi")
    assert captured["body"]["mchid"] == "1111636477"
    assert captured["body"]["payer"]["openid"] == user["openid"]
    assert captured["body"]["amount"]["total"] == 1990
    pay_message = (
        f"wx-test-pay\n{payment['timeStamp']}\n{payment['nonceStr']}\n"
        f"{payment['package']}\n"
    )
    pkcs1_15.new(merchant_key.publickey()).verify(
        SHA256.new(pay_message.encode("utf-8")),
        base64.b64decode(payment["paySign"]),
    )

    transaction = {
        "appid": "wx-test-pay",
        "mchid": "1111636477",
        "out_trade_no": order["id"],
        "transaction_id": "420000000000000001",
        "trade_state": "SUCCESS",
        "amount": {"total": 1990, "currency": "CNY"},
        "payer": {"openid": user["openid"]},
    }
    body, headers = make_notification(platform_key, api_v3_key, transaction)
    callback = client.post("/api/scrm/wechat-pay/notify", content=body, headers=headers)
    assert callback.status_code == 200, callback.text
    assert callback.json()["code"] == "SUCCESS"
    duplicate = client.post("/api/scrm/wechat-pay/notify", content=body, headers=headers)
    assert duplicate.status_code == 200
    membership = client.get("/api/scrm/membership", params={"userId": user["id"]}).json()["data"]
    assert membership["active"] is True
    assert membership["latestOrder"]["paymentTransactionId"] == "420000000000000001"


def test_wechat_pay_callback_rejects_amount_tampering(client, monkeypatch, tmp_path):
    _, platform_key, api_v3_key = configure_payment(monkeypatch, tmp_path)
    user = login(client, "openid_wechat_pay_amount_user")
    order = client.post("/api/scrm/membership/orders", json={"userId": user["id"]}).json()["data"]["order"]
    transaction = {
        "appid": "wx-test-pay",
        "mchid": "1111636477",
        "out_trade_no": order["id"],
        "transaction_id": "420000000000000002",
        "trade_state": "SUCCESS",
        "amount": {"total": 1, "currency": "CNY"},
        "payer": {"openid": user["openid"]},
    }
    body, headers = make_notification(platform_key, api_v3_key, transaction)
    callback = client.post("/api/scrm/wechat-pay/notify", content=body, headers=headers)
    assert callback.status_code == 500, callback.text
    membership = client.get("/api/scrm/membership", params={"userId": user["id"]}).json()["data"]
    assert membership["active"] is False


def test_production_never_allows_test_membership_confirmation(client, monkeypatch):
    user = login(client, "openid_production_payment_user")
    monkeypatch.setattr(settings, "app_env", "production")
    headers = {"Authorization": f"Bearer {user['authToken']}"}
    order = client.post(
        "/api/scrm/membership/orders",
        json={"userId": user["id"]},
        headers=headers,
    ).json()["data"]["order"]
    response = client.post(
        f"/api/scrm/membership/orders/{order['id']}/test-confirm",
        json={"transactionId": "fake-production-transaction"},
        headers=headers,
    )
    assert response.status_code == 403


def test_real_payment_mode_never_allows_test_confirmation_and_reuses_pending_order(client, monkeypatch):
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(settings, "wechat_pay_enabled", True)
    user = login(client, "openid_real_mode_user")
    first = client.post("/api/scrm/membership/orders", json={"userId": user["id"]})
    second = client.post("/api/scrm/membership/orders", json={"userId": user["id"]})
    first_order = first.json()["data"]["order"]
    second_data = second.json()["data"]
    assert second_data["order"]["id"] == first_order["id"]
    assert second_data["reused"] is True
    response = client.post(
        f"/api/scrm/membership/orders/{first_order['id']}/test-confirm",
        json={"transactionId": "fake-real-mode-transaction"},
    )
    assert response.status_code == 403


def test_pending_membership_order_expires_after_thirty_minutes_and_next_attempt_is_new(client, monkeypatch):
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(settings, "wechat_pay_enabled", False)
    user = login(client, "openid_membership_countdown_user")
    clock = {"value": "2026-08-22T20:00:00+08:00"}
    monkeypatch.setattr("app.services.app_service.now_iso", lambda: clock["value"])

    first = client.post("/api/scrm/membership/orders", json={"userId": user["id"]})
    assert first.status_code == 200
    first_data = first.json()["data"]
    first_order = first_data["order"]
    assert first_data["reused"] is False
    assert first_data["pendingOrder"]["secondsRemaining"] == 1800

    status = client.get("/api/scrm/membership", params={"userId": user["id"]}).json()["data"]
    assert status["pendingOrder"]["id"] == first_order["id"]
    assert status["pendingOrder"]["secondsRemaining"] == 1800

    clock["value"] = (datetime.fromisoformat(clock["value"]) + timedelta(seconds=1801)).isoformat()
    expired = client.get("/api/scrm/membership", params={"userId": user["id"]}).json()["data"]
    assert expired["pendingOrder"] is None
    assert expired["latestOrder"]["id"] == first_order["id"]
    assert expired["latestOrder"]["status"] == "closed"

    second = client.post("/api/scrm/membership/orders", json={"userId": user["id"]})
    assert second.status_code == 200
    second_data = second.json()["data"]
    assert second_data["order"]["id"] != first_order["id"]
    assert second_data["reused"] is False


def test_expired_wechat_order_cannot_start_payment_again(client, monkeypatch):
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(settings, "wechat_pay_enabled", True)
    user = login(client, "openid_expired_wechat_order_user")
    clock = {"value": "2026-08-22T20:00:00+08:00"}
    monkeypatch.setattr("app.services.app_service.now_iso", lambda: clock["value"])
    order = client.post("/api/scrm/membership/orders", json={"userId": user["id"]}).json()["data"]["order"]

    clock["value"] = (datetime.fromisoformat(clock["value"]) + timedelta(seconds=1801)).isoformat()
    response = client.post(
        f"/api/scrm/membership/orders/{order['id']}/pay",
        json={"userId": user["id"]},
    )
    assert response.status_code == 409
    assert "超时关闭" in response.json()["detail"]
