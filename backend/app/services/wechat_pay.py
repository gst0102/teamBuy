from __future__ import annotations

import base64
import json
import re
import secrets
import time
from pathlib import Path
from typing import Mapping
from urllib.parse import urlparse

import httpx
from Crypto.Cipher import AES
from Crypto.Hash import SHA256
from Crypto.PublicKey import RSA
from Crypto.Signature import pkcs1_15

from app.core.config import Settings, settings


class WechatPayError(RuntimeError):
    """An error from configuration, signing, verification, or the WeChat API."""


class WechatPayClient:
    JSAPI_PREPAY_PATH = "/v3/pay/transactions/jsapi"
    MERCHANT_TRANSFER_PATH = "/v3/fund-app/mch-transfer/transfer-bills"
    MERCHANT_TRANSFER_QUERY_PATH = "/v3/fund-app/mch-transfer/transfer-bills/out-bill-no/{out_bill_no}"
    MERCHANT_TRANSFER_CANCEL_PATH = "/v3/fund-app/mch-transfer/transfer-bills/out-bill-no/{out_bill_no}/cancel"

    def __init__(self, config: Settings | None = None):
        self.settings = config or settings

    def missing_config(self) -> list[str]:
        if not self.settings.wechat_pay_enabled:
            return ["WECHAT_PAY_ENABLED"]
        missing: list[str] = []
        required_values = {
            "WECHAT_MINIAPP_APPID": self.settings.wechat_miniapp_appid,
            "WECHAT_PAY_MCH_ID": self.settings.wechat_pay_mch_id,
            "WECHAT_PAY_API_V3_KEY": self.settings.wechat_pay_api_v3_key,
            "WECHAT_PAY_CERT_SERIAL_NO": self.settings.wechat_pay_cert_serial_no,
            "WECHAT_PAY_PLATFORM_CERT_SERIAL_NO": self.settings.wechat_pay_platform_cert_serial_no,
            "WECHAT_PAY_NOTIFY_URL": self.settings.wechat_pay_notify_url,
        }
        missing.extend(key for key, value in required_values.items() if not str(value or "").strip())
        for key, path in (
            ("WECHAT_PAY_PRIVATE_KEY_PATH", self.settings.wechat_pay_private_key_path),
            ("WECHAT_PAY_PLATFORM_CERT_PATH", self.settings.wechat_pay_platform_cert_path),
        ):
            if not path:
                missing.append(key)
            elif not path.exists():
                missing.append(f"{key}(file not found)")
        if len(self.settings.wechat_pay_api_v3_key.encode("utf-8")) != 32:
            missing.append("WECHAT_PAY_API_V3_KEY(length must be 32)")
        notify_url = urlparse(self.settings.wechat_pay_notify_url or "")
        if (
            self.settings.wechat_pay_notify_url
            and (notify_url.scheme != "https" or not notify_url.netloc or notify_url.query or notify_url.fragment)
        ):
            missing.append("WECHAT_PAY_NOTIFY_URL(https without query or fragment required)")
        return missing

    def ensure_configured(self) -> None:
        missing = self.missing_config()
        if missing:
            if missing == ["WECHAT_PAY_ENABLED"]:
                raise WechatPayError("微信支付未启用")
            raise WechatPayError(f"微信支付配置未完成：{', '.join(missing)}")

    def missing_transfer_config(self) -> list[str]:
        if not self.settings.wechat_transfer_enabled:
            return ["WECHAT_TRANSFER_ENABLED"]
        missing: list[str] = []
        required_values = {
            "WECHAT_MINIAPP_APPID": self.settings.wechat_miniapp_appid,
            "WECHAT_PAY_MCH_ID": self.settings.wechat_pay_mch_id,
            "WECHAT_PAY_API_V3_KEY": self.settings.wechat_pay_api_v3_key,
            "WECHAT_PAY_CERT_SERIAL_NO": self.settings.wechat_pay_cert_serial_no,
            "WECHAT_PAY_PLATFORM_CERT_SERIAL_NO": self.settings.wechat_pay_platform_cert_serial_no,
            "WECHAT_TRANSFER_SCENE_ID": self.settings.wechat_transfer_scene_id,
            "WECHAT_TRANSFER_NOTIFY_URL": self.settings.wechat_transfer_notify_url,
        }
        missing.extend(key for key, value in required_values.items() if not str(value or "").strip())
        if self.settings.wechat_pay_private_key_path is None:
            missing.append("WECHAT_PAY_PRIVATE_KEY_PATH")
        elif not self.settings.wechat_pay_private_key_path.exists():
            missing.append("WECHAT_PAY_PRIVATE_KEY_PATH(file not found)")
        if self.settings.wechat_pay_platform_cert_path is None:
            missing.append("WECHAT_PAY_PLATFORM_CERT_PATH")
        elif not self.settings.wechat_pay_platform_cert_path.exists():
            missing.append("WECHAT_PAY_PLATFORM_CERT_PATH(file not found)")
        if len(self.settings.wechat_pay_api_v3_key.encode("utf-8")) != 32:
            missing.append("WECHAT_PAY_API_V3_KEY(length must be 32)")
        notify_url = urlparse(self.settings.wechat_transfer_notify_url or "")
        if (
            self.settings.wechat_transfer_notify_url
            and (notify_url.scheme != "https" or not notify_url.netloc or notify_url.query or notify_url.fragment)
        ):
            missing.append("WECHAT_TRANSFER_NOTIFY_URL(https without query or fragment required)")
        return missing

    def ensure_transfer_configured(self) -> None:
        missing = self.missing_transfer_config()
        if missing:
            if missing == ["WECHAT_TRANSFER_ENABLED"]:
                raise WechatPayError("微信商家转账未启用")
            raise WechatPayError(f"微信商家转账配置未完成：{', '.join(missing)}")

    @staticmethod
    def _read_key(path: Path | None, label: str) -> RSA.RsaKey:
        if not path:
            raise WechatPayError(f"缺少 {label}")
        try:
            return RSA.import_key(path.read_bytes())
        except Exception as exc:  # pragma: no cover - exact parser errors vary by PyCryptodome version
            raise WechatPayError(f"{label} 无法读取") from exc

    @staticmethod
    def _sign(private_key: RSA.RsaKey, message: str) -> str:
        signature = pkcs1_15.new(private_key).sign(SHA256.new(message.encode("utf-8")))
        return base64.b64encode(signature).decode("ascii")

    @staticmethod
    def _verify(public_key: RSA.RsaKey, message: str, signature: str) -> None:
        try:
            decoded = base64.b64decode(signature, validate=True)
            pkcs1_15.new(public_key).verify(SHA256.new(message.encode("utf-8")), decoded)
        except Exception as exc:
            raise WechatPayError("微信支付回调签名无效") from exc

    def _request_authorization(self, method: str, path: str, body: str) -> str:
        private_key = self._read_key(self.settings.wechat_pay_private_key_path, "WECHAT_PAY_PRIVATE_KEY_PATH")
        timestamp = str(int(time.time()))
        nonce = secrets.token_hex(16)
        message = f"{method}\n{path}\n{timestamp}\n{nonce}\n{body}\n"
        signature = self._sign(private_key, message)
        return (
            f'WECHATPAY2-SHA256-RSA2048 mchid="{self.settings.wechat_pay_mch_id}",'
            f'nonce_str="{nonce}",timestamp="{timestamp}",'
            f'serial_no="{self.settings.wechat_pay_cert_serial_no}",signature="{signature}"'
        )

    def _verify_api_response(self, body: bytes, headers: Mapping[str, str]) -> None:
        timestamp = str(headers.get("Wechatpay-Timestamp") or "").strip()
        nonce = str(headers.get("Wechatpay-Nonce") or "").strip()
        signature = str(headers.get("Wechatpay-Signature") or "").strip()
        serial = str(headers.get("Wechatpay-Serial") or "").strip()
        if not timestamp or not nonce or not signature or not serial:
            raise WechatPayError("微信商家转账响应签名头不完整")
        try:
            if abs(int(timestamp) - int(time.time())) > 300:
                raise WechatPayError("微信商家转账响应已过期")
        except ValueError as exc:
            raise WechatPayError("微信商家转账响应时间戳无效") from exc
        if serial != self.settings.wechat_pay_platform_cert_serial_no:
            raise WechatPayError("微信商家转账响应平台证书序列号不匹配")
        message = f"{timestamp}\n{nonce}\n{body.decode('utf-8')}\n"
        public_key = self._read_key(self.settings.wechat_pay_platform_cert_path, "WECHAT_PAY_PLATFORM_CERT_PATH")
        self._verify(public_key, message, signature)

    def create_jsapi_prepay(self, *, openid: str, out_trade_no: str, total_fen: int, description: str) -> str:
        self.ensure_configured()
        if not openid:
            raise WechatPayError("缺少微信用户身份")
        if not 6 <= len(out_trade_no) <= 32:
            raise WechatPayError("商户订单号长度必须在 6 到 32 个字符之间")
        if total_fen <= 0:
            raise WechatPayError("支付金额必须大于 0")
        body_payload = {
            "appid": self.settings.wechat_miniapp_appid,
            "mchid": self.settings.wechat_pay_mch_id,
            "description": description[:127],
            "out_trade_no": out_trade_no,
            "notify_url": self.settings.wechat_pay_notify_url,
            "amount": {"total": total_fen, "currency": "CNY"},
            "payer": {"openid": openid},
        }
        body = json.dumps(body_payload, ensure_ascii=False, separators=(",", ":"))
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": self._request_authorization("POST", self.JSAPI_PREPAY_PATH, body),
        }
        try:
            response = httpx.post(
                f"{self.settings.wechat_pay_api_base_url.rstrip('/')}{self.JSAPI_PREPAY_PATH}",
                content=body.encode("utf-8"),
                headers=headers,
                timeout=max(5, self.settings.wechat_pay_timeout_seconds),
            )
        except Exception as exc:
            raise WechatPayError("微信支付下单服务暂不可用") from exc
        if response.status_code < 200 or response.status_code >= 300:
            raise WechatPayError("微信支付下单失败，请检查商户号、AppID、证书和支付权限")
        try:
            prepay_id = str(response.json().get("prepay_id") or "").strip()
        except (TypeError, ValueError):
            prepay_id = ""
        if not prepay_id:
            raise WechatPayError("微信支付下单未返回 prepay_id")
        return prepay_id

    def create_merchant_transfer(
        self,
        *,
        openid: str,
        out_bill_no: str,
        amount_fen: int,
        transfer_remark: str = "推广佣金",
        job_type: str = "推广用户",
        reward_description: str = "会员推广佣金",
    ) -> dict:
        """Create a merchant transfer bill without automatically retrying it."""
        self.ensure_transfer_configured()
        if not openid:
            raise WechatPayError("缺少微信收款用户身份")
        if not re.fullmatch(r"[A-Za-z0-9]{6,32}", str(out_bill_no or "")):
            raise WechatPayError("商家转账单号必须为 6 到 32 位字母或数字")
        if amount_fen <= 0:
            raise WechatPayError("商家转账金额必须大于 0")
        if not str(transfer_remark or "").strip():
            raise WechatPayError("商家转账备注不能为空")
        if len(str(transfer_remark)) > 32:
            raise WechatPayError("商家转账备注不能超过 32 个字符")

        body_payload = {
            "appid": self.settings.wechat_miniapp_appid,
            "out_bill_no": out_bill_no,
            "transfer_scene_id": self.settings.wechat_transfer_scene_id,
            "openid": openid,
            "transfer_amount": amount_fen,
            "transfer_remark": transfer_remark,
            "notify_url": self.settings.wechat_transfer_notify_url,
            "user_recv_perception": "劳务报酬",
            "transfer_scene_report_infos": [
                {"info_type": "岗位类型", "info_content": str(job_type)[:32]},
                {"info_type": "报酬说明", "info_content": str(reward_description)[:32]},
            ],
        }
        body = json.dumps(body_payload, ensure_ascii=False, separators=(",", ":"))
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": self._request_authorization("POST", self.MERCHANT_TRANSFER_PATH, body),
        }
        try:
            response = httpx.post(
                f"{self.settings.wechat_pay_api_base_url.rstrip('/')}{self.MERCHANT_TRANSFER_PATH}",
                content=body.encode("utf-8"),
                headers=headers,
                timeout=max(5, self.settings.wechat_pay_timeout_seconds),
            )
        except Exception as exc:
            raise WechatPayError("微信商家转账服务暂不可用，请保留原商户单号后查询") from exc
        if response.status_code < 200 or response.status_code >= 300:
            raise WechatPayError("微信商家转账请求失败，请先查询原商户单号，避免重复打款")
        self._verify_api_response(response.content, response.headers)
        try:
            payload = response.json()
        except (TypeError, ValueError) as exc:
            raise WechatPayError("微信商家转账响应格式无效") from exc
        if not isinstance(payload, dict):
            raise WechatPayError("微信商家转账响应格式无效")
        response_bill_no = str(payload.get("out_bill_no") or "").strip()
        if response_bill_no and response_bill_no != out_bill_no:
            raise WechatPayError("微信商家转账响应单号不一致")
        return payload

    @staticmethod
    def _validate_transfer_bill_no(out_bill_no: str) -> str:
        value = str(out_bill_no or "").strip()
        if not re.fullmatch(r"[A-Za-z0-9]{6,32}", value):
            raise WechatPayError("商家转账单号必须为 6 到 32 位字母或数字")
        return value

    def _merchant_transfer_request(self, method: str, path: str, body: bytes = b"") -> dict:
        body_text = body.decode("utf-8")
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": self._request_authorization(method, path, body_text),
        }
        try:
            if method == "GET":
                response = httpx.get(
                    f"{self.settings.wechat_pay_api_base_url.rstrip('/')}{path}",
                    headers=headers,
                    timeout=max(5, self.settings.wechat_pay_timeout_seconds),
                )
            else:
                response = httpx.post(
                    f"{self.settings.wechat_pay_api_base_url.rstrip('/')}{path}",
                    content=body,
                    headers=headers,
                    timeout=max(5, self.settings.wechat_pay_timeout_seconds),
                )
        except Exception as exc:
            raise WechatPayError("微信商家转账服务暂不可用，请保留原商户单号后重试查询") from exc
        if response.status_code < 200 or response.status_code >= 300:
            raise WechatPayError("微信商家转账接口请求失败，请稍后查询原商户单号")
        self._verify_api_response(response.content, response.headers)
        try:
            payload = response.json()
        except (TypeError, ValueError) as exc:
            raise WechatPayError("微信商家转账响应格式无效") from exc
        if not isinstance(payload, dict):
            raise WechatPayError("微信商家转账响应格式无效")
        return payload

    def query_merchant_transfer(self, *, out_bill_no: str) -> dict:
        """Query the authoritative WeChat state for a transfer bill."""
        self.ensure_transfer_configured()
        bill_no = self._validate_transfer_bill_no(out_bill_no)
        path = self.MERCHANT_TRANSFER_QUERY_PATH.format(out_bill_no=bill_no)
        return self._merchant_transfer_request("GET", path)

    def cancel_merchant_transfer(self, *, out_bill_no: str) -> dict:
        """Request cancellation before user confirmation; final state is async."""
        self.ensure_transfer_configured()
        bill_no = self._validate_transfer_bill_no(out_bill_no)
        path = self.MERCHANT_TRANSFER_CANCEL_PATH.format(out_bill_no=bill_no)
        return self._merchant_transfer_request("POST", path)

    def build_jsapi_payment(self, prepay_id: str) -> dict[str, str]:
        self.ensure_configured()
        prepay_id = str(prepay_id or "").strip()
        if not prepay_id:
            raise WechatPayError("缺少 prepay_id")
        timestamp = str(int(time.time()))
        nonce = secrets.token_hex(16)
        package = f"prepay_id={prepay_id}"
        message = f"{self.settings.wechat_miniapp_appid}\n{timestamp}\n{nonce}\n{package}\n"
        private_key = self._read_key(self.settings.wechat_pay_private_key_path, "WECHAT_PAY_PRIVATE_KEY_PATH")
        return {
            "appId": self.settings.wechat_miniapp_appid,
            "timeStamp": timestamp,
            "nonceStr": nonce,
            "package": package,
            "signType": "RSA",
            "paySign": self._sign(private_key, message),
        }

    def verify_and_decrypt_notification(
        self,
        body: bytes,
        headers: Mapping[str, str],
        *,
        transfer: bool = False,
    ) -> dict:
        if transfer:
            self.ensure_transfer_configured()
        else:
            self.ensure_configured()
        timestamp = str(headers.get("Wechatpay-Timestamp") or "").strip()
        nonce = str(headers.get("Wechatpay-Nonce") or "").strip()
        signature = str(headers.get("Wechatpay-Signature") or "").strip()
        serial = str(headers.get("Wechatpay-Serial") or "").strip()
        if not timestamp or not nonce or not signature or not serial:
            raise WechatPayError("微信支付回调签名头不完整")
        try:
            if abs(int(timestamp) - int(time.time())) > 300:
                raise WechatPayError("微信支付回调已过期")
        except ValueError as exc:
            raise WechatPayError("微信支付回调时间戳无效") from exc
        if serial != self.settings.wechat_pay_platform_cert_serial_no:
            raise WechatPayError("微信支付平台证书序列号不匹配")
        message = f"{timestamp}\n{nonce}\n{body.decode('utf-8')}\n"
        public_key = self._read_key(self.settings.wechat_pay_platform_cert_path, "WECHAT_PAY_PLATFORM_CERT_PATH")
        self._verify(public_key, message, signature)
        try:
            notification = json.loads(body.decode("utf-8"))
            resource = notification["resource"]
            if resource.get("algorithm") != "AEAD_AES_256_GCM":
                raise WechatPayError("不支持的微信支付回调加密算法")
            ciphertext = base64.b64decode(resource["ciphertext"], validate=True)
            associated_data = str(resource.get("associated_data") or "").encode("utf-8")
            resource_nonce = str(resource["nonce"]).encode("utf-8")
            api_v3_key = self.settings.wechat_pay_api_v3_key.encode("utf-8")
            cipher = AES.new(api_v3_key, AES.MODE_GCM, nonce=resource_nonce)
            cipher.update(associated_data)
            decrypted = cipher.decrypt(ciphertext[:-16])
            cipher.verify(ciphertext[-16:])
            transaction = json.loads(decrypted.decode("utf-8"))
        except WechatPayError:
            raise
        except Exception as exc:
            raise WechatPayError("微信支付回调解密失败") from exc
        if not isinstance(notification, dict) or not isinstance(transaction, dict):
            raise WechatPayError("微信支付回调格式无效")
        return {
            "eventType": notification.get("event_type"),
            "notificationId": notification.get("id"),
            "transaction": transaction,
        }
