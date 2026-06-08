from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx

from app.core.config import Settings


class WecomClientError(RuntimeError):
    pass


class DownloadedMedia:
    def __init__(self, content: bytes, content_type: str | None = None, filename: str | None = None):
        self.content = content
        self.content_type = content_type
        self.filename = filename


class WecomClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._access_token: str | None = None
        self._expires_at = datetime.min.replace(tzinfo=timezone.utc)

    def is_configured(self) -> bool:
        return not self.settings.missing_wecom_fields()

    async def get_access_token(self) -> str:
        if self._access_token and datetime.now(timezone.utc) < self._expires_at:
            return self._access_token
        if not self.settings.wecom_corp_id or not self.settings.wecom_secret:
            raise WecomClientError("缺少 WECOM_CORP_ID 或 WECOM_SECRET")

        async with httpx.AsyncClient(base_url=self.settings.wecom_api_base_url, timeout=15) as client:
            response = await client.get(
                "/cgi-bin/gettoken",
                params={"corpid": self.settings.wecom_corp_id, "corpsecret": self.settings.wecom_secret},
            )
            data = response.json()
        if data.get("errcode") != 0:
            raise WecomClientError(f"获取 access_token 失败: {data}")

        self._access_token = data["access_token"]
        expires_in = int(data.get("expires_in", 7200))
        self._expires_at = datetime.now(timezone.utc) + timedelta(seconds=max(expires_in - 300, 60))
        return self._access_token

    async def sync_msg(self, cursor: str | None = None, token: str | None = None, limit: int | None = None) -> dict:
        access_token = await self.get_access_token()
        payload = {
            "open_kfid": self.settings.wecom_open_kfid,
            "limit": limit or self.settings.wecom_sync_limit,
        }
        if cursor:
            payload["cursor"] = cursor
        if token:
            payload["token"] = token

        async with httpx.AsyncClient(base_url=self.settings.wecom_api_base_url, timeout=20) as client:
            response = await client.post(
                "/cgi-bin/kf/sync_msg",
                params={"access_token": access_token},
                json=payload,
            )
            data = response.json()
        if data.get("errcode") != 0:
            raise WecomClientError(f"sync_msg 失败: {data}")
        return data

    async def download_media(self, media_id: str) -> DownloadedMedia:
        access_token = await self.get_access_token()
        async with httpx.AsyncClient(base_url=self.settings.wecom_api_base_url, timeout=30) as client:
            response = await client.get(
                "/cgi-bin/media/get",
                params={"access_token": access_token, "media_id": media_id},
            )
        content_type = response.headers.get("content-type", "")
        if "application/json" in content_type:
            data = response.json()
            if data.get("errcode") != 0:
                raise WecomClientError(f"download media failed: {data}")
        response.raise_for_status()
        return DownloadedMedia(
            content=response.content,
            content_type=content_type,
            filename=self._filename_from_disposition(response.headers.get("content-disposition", "")),
        )

    def _filename_from_disposition(self, disposition: str) -> str | None:
        marker = "filename="
        if marker not in disposition:
            return None
        value = disposition.split(marker, 1)[-1].strip().strip('"')
        return value or None
