from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx

from app.core.config import Settings


class WechatMiniappClientError(RuntimeError):
    def __init__(self, message: str, *, errcode: int | None = None, retryable: bool = True):
        super().__init__(message)
        self.errcode = errcode
        self.retryable = retryable


class WechatMiniappClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._access_token: str | None = None
        self._expires_at = datetime.min.replace(tzinfo=timezone.utc)

    def is_configured(self) -> bool:
        return bool(
            self.settings.wechat_miniapp_appid
            and self.settings.wechat_miniapp_secret
            and (
                (
                    self.settings.wechat_miniapp_subscribe_template_id
                    and self.settings.wechat_miniapp_subscribe_field_keys()
                )
                or (
                    self.settings.wechat_miniapp_mutual_help_subscribe_template_id
                    and self.settings.wechat_miniapp_mutual_help_subscribe_field_keys()
                )
                or (
                    self.settings.wechat_miniapp_live_qr_subscribe_template_id
                    and self.settings.wechat_miniapp_live_qr_subscribe_field_keys()
                )
            )
        )

    async def get_access_token(self) -> str:
        if self._access_token and datetime.now(timezone.utc) < self._expires_at:
            return self._access_token
        if not self.settings.wechat_miniapp_appid or not self.settings.wechat_miniapp_secret:
            raise WechatMiniappClientError("缺少 WECHAT_MINIAPP_APPID 或 WECHAT_MINIAPP_SECRET", retryable=False)
        async with httpx.AsyncClient(base_url=self.settings.wechat_miniapp_api_base_url, timeout=15) as client:
            response = await client.get(
                "/cgi-bin/token",
                params={
                    "grant_type": "client_credential",
                    "appid": self.settings.wechat_miniapp_appid,
                    "secret": self.settings.wechat_miniapp_secret,
                },
            )
            response.raise_for_status()
            data = response.json()
        if data.get("errcode", 0) != 0:
            raise WechatMiniappClientError(f"获取小程序 access_token 失败: {data}", errcode=data.get("errcode"), retryable=False)
        token = str(data.get("access_token") or "")
        if not token:
            raise WechatMiniappClientError("获取小程序 access_token 返回为空")
        self._access_token = token
        expires_in = int(data.get("expires_in", 7200))
        self._expires_at = datetime.now(timezone.utc) + timedelta(seconds=max(expires_in - 300, 60))
        return token

    async def send_subscribe_message(
        self,
        *,
        openid: str,
        page: str,
        data: dict,
        template_id: str | None = None,
    ) -> dict:
        template_id = str(template_id or self.settings.wechat_miniapp_subscribe_template_id).strip()
        if not template_id:
            raise WechatMiniappClientError("缺少小程序订阅消息模板 ID", retryable=False)
        access_token = await self.get_access_token()
        payload = {
            "touser": openid,
            "template_id": template_id,
            "page": page,
            "data": data,
            "lang": "zh_CN",
        }
        async with httpx.AsyncClient(base_url=self.settings.wechat_miniapp_api_base_url, timeout=15) as client:
            response = await client.post(
                "/cgi-bin/message/subscribe/send",
                params={"access_token": access_token},
                json=payload,
            )
            response.raise_for_status()
            result = response.json()
        errcode = int(result.get("errcode", 0) or 0)
        if errcode:
            # 43101 means the user rejected/cancelled the one-time grant; retrying
            # cannot recreate that grant.  47003 is a permanent template-field
            # configuration error until an operator fixes the env mapping.
            retryable = errcode not in {40003, 40037, 41030, 43101, 47003}
            raise WechatMiniappClientError(
                f"发送小程序订阅消息失败: {result}",
                errcode=errcode,
                retryable=retryable,
            )
        return result
