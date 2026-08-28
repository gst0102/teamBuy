from __future__ import annotations

import base64
import hashlib
from datetime import datetime, timedelta

from app.core.config import Settings
from app.models.domain import WecomBindCardAsset
from app.services.helpers import new_id
from app.services.time_utils import SHANGHAI, now_iso, parse_iso
from app.services.wecom_client import WecomClient, WecomClientError


ALLOWED_IMAGE_TYPES = {"image/png", "image/jpeg", "image/webp"}


class WecomBindCardAssetService:
    """Own the durable source image and the expiring WeCom media_id."""

    def __init__(self, repo, client: WecomClient, settings: Settings):
        self.repo = repo
        self.client = client
        self.settings = settings

    def status(self) -> dict:
        asset = self.repo.get_active_wecom_bind_card_asset()
        latest = self.repo.get_latest_wecom_bind_card_asset()
        if not asset and self.settings.wecom_bind_card_pic_media_id:
            return {
                "configured": True,
                "status": "legacy_configured",
                "mediaIdConfigured": True,
                "autoRefresh": False,
                "message": "当前使用旧环境变量 media_id，请在 PC 后台重新上传封面以启用自动刷新。",
                "updatedAt": None,
                "mediaIdExpiresAt": None,
                "lastError": None,
            }
        if not asset:
            return {
                "configured": False,
                "status": "missing",
                "mediaIdConfigured": False,
                "autoRefresh": False,
                "message": "尚未上传绑定卡片封面。",
                "updatedAt": latest.updatedAt if latest else None,
                "mediaIdExpiresAt": None,
                "lastError": latest.errorMessage if latest and latest.status == "failed" else None,
            }
        expires_at = self._parse_optional(asset.mediaIdExpiresAt)
        now = datetime.now(tz=SHANGHAI)
        remaining = int((expires_at - now).total_seconds()) if expires_at else None
        last_error = (
            latest.errorMessage
            if latest and latest.status == "failed"
            else asset.errorMessage
        )
        return {
            "configured": bool(asset.mediaId),
            "status": "expired" if expires_at and expires_at <= now else asset.status,
            "mediaIdConfigured": bool(asset.mediaId),
            "mediaIdSuffix": asset.mediaId[-8:] if asset.mediaId else None,
            "autoRefresh": bool(asset.sourceContentBase64),
            "filename": asset.filename,
            "contentType": asset.contentType,
            "sourceSha256": asset.sourceSha256,
            "updatedAt": asset.updatedAt,
            "mediaIdExpiresAt": asset.mediaIdExpiresAt,
            "remainingSeconds": remaining,
            "lastError": last_error,
        }

    async def upload_source(self, content: bytes, filename: str, content_type: str | None) -> WecomBindCardAsset:
        normalized_type = (content_type or "").split(";", 1)[0].strip().lower()
        self._validate_image(content, normalized_type)
        source_hash = hashlib.sha256(content).hexdigest()
        now = now_iso()
        try:
            media_id = await self._upload_to_wecom(content, filename, normalized_type)
        except Exception as exc:
            failed = WecomBindCardAsset(
                id=new_id("wecom_bind_card_asset"),
                sourceContentBase64=base64.b64encode(content).decode("ascii"),
                filename=filename or "wecom-bind-card.png",
                contentType=normalized_type,
                sourceSha256=source_hash,
                status="failed",
                errorMessage=str(exc)[:500],
                createdAt=now,
                updatedAt=now,
            )
            self.repo.save_wecom_bind_card_asset(failed)
            raise
        return self._activate(
            source_content=content,
            filename=filename,
            content_type=normalized_type,
            source_hash=source_hash,
            media_id=media_id,
            now=now,
        )

    async def ensure_valid(self) -> WecomBindCardAsset:
        asset = self.repo.get_active_wecom_bind_card_asset()
        if not asset:
            if self.settings.wecom_bind_card_pic_media_id:
                return WecomBindCardAsset(
                    id="legacy_wecom_bind_card_asset",
                    sourceSha256="",
                    mediaId=self.settings.wecom_bind_card_pic_media_id,
                    status="active",
                    createdAt=now_iso(),
                    updatedAt=now_iso(),
                )
            raise WecomClientError("尚未配置企业微信绑定卡片封面，请先在 PC 后台上传")
        if self._is_valid_for_send(asset):
            return asset
        if not asset.sourceContentBase64:
            if self._is_not_expired(asset):
                return asset
            raise WecomClientError("企业微信绑定卡片封面素材已过期，请在 PC 后台重新上传")
        try:
            return await self._refresh(asset, allow_fallback=True)
        except Exception:
            if self._is_not_expired(asset):
                return asset
            raise

    async def refresh(self) -> WecomBindCardAsset:
        asset = self.repo.get_active_wecom_bind_card_asset()
        if not asset or not asset.sourceContentBase64:
            raise WecomClientError("没有可自动刷新的绑定卡片源图片，请先在 PC 后台上传")
        return await self._refresh(asset, allow_fallback=False)

    async def _refresh(self, asset: WecomBindCardAsset, allow_fallback: bool) -> WecomBindCardAsset:
        content = base64.b64decode(asset.sourceContentBase64.encode("ascii"))
        try:
            media_id = await self._upload_to_wecom(content, asset.filename, asset.contentType)
            return self._activate(
                source_content=content,
                filename=asset.filename,
                content_type=asset.contentType,
                source_hash=asset.sourceSha256,
                media_id=media_id,
                now=now_iso(),
            )
        except Exception as exc:
            failed = asset.model_copy(update={"errorMessage": str(exc)[:500], "updatedAt": now_iso()})
            self.repo.save_wecom_bind_card_asset(failed)
            if allow_fallback and self._is_not_expired(asset):
                return asset
            raise

    async def _upload_to_wecom(self, content: bytes, filename: str, content_type: str) -> str:
        if self.settings.wecom_use_mock:
            return f"mock_bind_card_{hashlib.sha256(content).hexdigest()[:16]}"
        result = await self.client.upload_image(content, filename or "wecom-bind-card.png", content_type)
        return str(result["media_id"])

    def _activate(
        self,
        *,
        source_content: bytes,
        filename: str,
        content_type: str,
        source_hash: str,
        media_id: str,
        now: str,
    ) -> WecomBindCardAsset:
        previous = self.repo.get_active_wecom_bind_card_asset()
        expires_at = (
            datetime.now(tz=SHANGHAI)
            + timedelta(seconds=max(self.settings.wecom_bind_card_media_ttl_seconds, 3600))
        ).isoformat()
        asset = WecomBindCardAsset(
            id=new_id("wecom_bind_card_asset"),
            sourceContentBase64=base64.b64encode(source_content).decode("ascii"),
            filename=filename or "wecom-bind-card.png",
            contentType=content_type,
            sourceSha256=source_hash,
            mediaId=media_id,
            mediaIdExpiresAt=expires_at,
            status="active",
            createdAt=now,
            updatedAt=now,
        )
        # Persist the new usable asset first. If the follow-up retirement write
        # fails, the newest active row still wins and the previous source stays
        # recoverable instead of leaving the system with no active card.
        self.repo.save_wecom_bind_card_asset(asset)
        if previous and previous.id != asset.id:
            self.repo.save_wecom_bind_card_asset(previous.model_copy(update={"status": "retired", "updatedAt": now}))
        return asset

    def _is_valid_for_send(self, asset: WecomBindCardAsset) -> bool:
        expires_at = self._parse_optional(asset.mediaIdExpiresAt)
        return bool(asset.mediaId) and (expires_at is None or expires_at > datetime.now(tz=SHANGHAI) + timedelta(seconds=max(self.settings.wecom_bind_card_media_refresh_margin_seconds, 0)))

    def _is_not_expired(self, asset: WecomBindCardAsset) -> bool:
        expires_at = self._parse_optional(asset.mediaIdExpiresAt)
        return bool(asset.mediaId) and (expires_at is None or expires_at > datetime.now(tz=SHANGHAI))

    @staticmethod
    def _parse_optional(value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            return parse_iso(value).astimezone(SHANGHAI)
        except Exception:
            return None

    def _validate_image(self, content: bytes, content_type: str) -> None:
        if not content or len(content) > max(self.settings.wecom_bind_card_max_bytes, 1024):
            raise ValueError("绑定卡片封面必须是 2MB 以内的图片")
        signatures = {
            "image/png": content.startswith(b"\x89PNG\r\n\x1a\n"),
            "image/jpeg": content.startswith(b"\xff\xd8\xff"),
            "image/webp": content.startswith(b"RIFF") and content[8:12] == b"WEBP",
        }
        if content_type not in ALLOWED_IMAGE_TYPES or not signatures.get(content_type, False):
            raise ValueError("只支持真实的 PNG、JPEG 或 WebP 图片")
