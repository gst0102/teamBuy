from __future__ import annotations

import json
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
        if not self.settings.wecom_corp_id or not self.settings.wecom_kf_secret:
            raise WecomClientError("缺少 WECOM_CORP_ID 或 WECOM_KF_SECRET")

        async with httpx.AsyncClient(base_url=self.settings.wecom_api_base_url, timeout=15) as client:
            response = await client.get(
                "/cgi-bin/gettoken",
                params={"corpid": self.settings.wecom_corp_id, "corpsecret": self.settings.wecom_kf_secret},
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
        max_bytes = max(int(getattr(self.settings, "media_max_video_bytes", 50 * 1024 * 1024)), 1)
        async with httpx.AsyncClient(base_url=self.settings.wecom_api_base_url, timeout=30) as client:
            async with client.stream(
                "GET",
                "/cgi-bin/media/get",
                params={"access_token": access_token, "media_id": media_id},
            ) as response:
                content_type = response.headers.get("content-type", "")
                if "application/json" in content_type:
                    data = (await response.aread()).decode("utf-8", errors="replace")
                    try:
                        payload = json.loads(data)
                    except ValueError:
                        payload = {"errmsg": data[:200]}
                    if payload.get("errcode") != 0:
                        raise WecomClientError(f"download media failed: {payload}")
                response.raise_for_status()
                content_length = response.headers.get("content-length")
                try:
                    declared_length = int(content_length) if content_length else None
                except ValueError:
                    declared_length = None
                if declared_length and declared_length > max_bytes:
                    raise WecomClientError("企业微信媒体超过服务器允许的大小")
                filename = self._filename_from_disposition(response.headers.get("content-disposition", ""))
                chunks: list[bytes] = []
                total = 0
                async for chunk in response.aiter_bytes():
                    total += len(chunk)
                    if total > max_bytes:
                        raise WecomClientError("企业微信媒体超过服务器允许的大小")
                    chunks.append(chunk)
                content = b"".join(chunks)
        return DownloadedMedia(
            content=content,
            content_type=content_type,
            filename=filename,
        )

    async def upload_image(self, content: bytes, filename: str, content_type: str = "image/png") -> dict:
        if not content:
            raise WecomClientError("上传企业微信素材不能为空")
        access_token = await self.get_access_token()
        async with httpx.AsyncClient(base_url=self.settings.wecom_api_base_url, timeout=30) as client:
            response = await client.post(
                "/cgi-bin/media/upload",
                params={"access_token": access_token, "type": "image"},
                files={"media": (filename or "wecom-bind-card.png", content, content_type)},
            )
            data = response.json()
        if data.get("errcode") != 0 or not data.get("media_id"):
            raise WecomClientError(f"上传企业微信绑定卡片封面失败: {data}")
        return data

    async def send_customer_service_text(self, external_user_id: str, content: str, open_kfid: str | None = None) -> dict:
        access_token = await self.get_access_token()
        payload = {
            "touser": external_user_id,
            "open_kfid": open_kfid or self.settings.wecom_open_kfid,
            "msgtype": "text",
            "text": {"content": content[:2048]},
        }
        async with httpx.AsyncClient(base_url=self.settings.wecom_api_base_url, timeout=15) as client:
            response = await client.post(
                "/cgi-bin/kf/send_msg",
                params={"access_token": access_token},
                json=payload,
            )
            data = response.json()
        if data.get("errcode") != 0:
            raise WecomClientError(f"send customer service text failed: {data}")
        return data

    async def send_contact_welcome_mini_program(
        self,
        *,
        welcome_code: str,
        appid: str,
        page: str,
        title: str,
        pic_media_id: str,
        text_content: str | None = None,
    ) -> dict:
        """Send a welcome text and one-time mini-program card after an add event.

        Enterprise WeChat only accepts ``welcome_code`` for a short window and
        consumes it after one successful send, so this must stay synchronous at
        the callback boundary rather than enter the normal background queue.
        """
        if not welcome_code or not appid or not page or not pic_media_id:
            raise WecomClientError("发送绑定小程序卡片缺少 welcome_code、appid、page 或 pic_media_id")
        access_token = await self.get_access_token()
        payload = {
            "welcome_code": welcome_code,
            "text": {"content": (text_content or "").strip()[:2048]},
            "miniprogram": {
                "title": title[:40],
                "pic_media_id": pic_media_id,
                "appid": appid,
                "page": page,
            },
        }
        async with httpx.AsyncClient(base_url=self.settings.wecom_api_base_url, timeout=15) as client:
            response = await client.post(
                "/cgi-bin/externalcontact/send_welcome_msg",
                params={"access_token": access_token},
                json=payload,
            )
            data = response.json()
        if data.get("errcode") != 0:
            raise WecomClientError(f"send contact welcome mini program failed: {data}")
        return data

    async def create_group_join_way(
        self,
        *,
        scene: int,
        remark: str,
        chat_id_list: list[str],
        auto_create_room: int = 1,
        room_base_name: str = "",
        room_base_id: int = 1,
        state: str = "",
    ) -> dict:
        access_token = await self.get_access_token()
        payload = {
            "scene": scene,
            "remark": remark[:30],
            "auto_create_room": auto_create_room,
            "room_base_name": room_base_name[:40],
            "room_base_id": room_base_id,
            "chat_id_list": chat_id_list[:5],
            "state": state[:30],
        }
        async with httpx.AsyncClient(base_url=self.settings.wecom_api_base_url, timeout=15) as client:
            response = await client.post(
                "/cgi-bin/externalcontact/groupchat/add_join_way",
                params={"access_token": access_token},
                json=payload,
            )
            data = response.json()
        if data.get("errcode") != 0:
            raise WecomClientError(f"create group join way failed: {data}")
        return data

    async def list_customer_groups(
        self,
        *,
        status_filter: int = 0,
        cursor: str | None = None,
        limit: int = 100,
    ) -> dict:
        access_token = await self.get_access_token()
        payload = {
            "status_filter": status_filter,
            "limit": max(1, min(limit, 1000)),
        }
        if cursor:
            payload["cursor"] = cursor
        async with httpx.AsyncClient(base_url=self.settings.wecom_api_base_url, timeout=15) as client:
            response = await client.post(
                "/cgi-bin/externalcontact/groupchat/list",
                params={"access_token": access_token},
                json=payload,
            )
            data = response.json()
        if data.get("errcode") != 0:
            raise WecomClientError(f"list customer groups failed: {data}")
        return data

    def _filename_from_disposition(self, disposition: str) -> str | None:
        marker = "filename="
        if marker not in disposition:
            return None
        value = disposition.split(marker, 1)[-1].strip().strip('"')
        return value or None
