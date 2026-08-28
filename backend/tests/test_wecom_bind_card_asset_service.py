import base64
import asyncio
from datetime import datetime, timedelta

from app.core.config import settings
from app.services.repository import JsonRepository
from app.services.time_utils import SHANGHAI, now_iso
from app.services.wecom_bind_card_asset_service import WecomBindCardAssetService


ONE_PIXEL_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


class FakeWecomClient:
    def __init__(self):
        self.calls = 0
        self.fail = False

    async def upload_image(self, content, filename, content_type):
        self.calls += 1
        if self.fail:
            raise RuntimeError("wecom upload unavailable")
        return {"media_id": f"media-{self.calls}"}


def test_upload_persists_source_and_refreshes_expiring_media(tmp_path, monkeypatch):
    repo = JsonRepository(tmp_path / "state.json")
    client = FakeWecomClient()
    monkeypatch.setattr(settings, "wecom_use_mock", False)
    monkeypatch.setattr(settings, "wecom_bind_card_pic_media_id", "")
    monkeypatch.setattr(settings, "wecom_bind_card_media_ttl_seconds", 3600)
    monkeypatch.setattr(settings, "wecom_bind_card_media_refresh_margin_seconds", 600)
    service = WecomBindCardAssetService(repo, client, settings)

    async def scenario():
        first = await service.upload_source(ONE_PIXEL_PNG, "bind.png", "image/png")
        assert first.status == "active"
        assert first.mediaId == "media-1"
        assert first.sourceContentBase64
        assert service.status()["autoRefresh"] is True

        expired = first.model_copy(
            update={
                "mediaIdExpiresAt": (datetime.now(tz=SHANGHAI) - timedelta(seconds=1)).isoformat(),
                "updatedAt": now_iso(),
            }
        )
        repo.save_wecom_bind_card_asset(expired)
        refreshed = await service.ensure_valid()

        assert refreshed.mediaId == "media-2"
        assert repo.get_active_wecom_bind_card_asset().id == refreshed.id
        old = next(item for item in repo.load().wecom_bind_card_assets if item.id == expired.id)
        assert old.status == "retired"

    asyncio.run(scenario())


def test_failed_replacement_keeps_current_asset_and_records_error(tmp_path, monkeypatch):
    repo = JsonRepository(tmp_path / "state.json")
    client = FakeWecomClient()
    monkeypatch.setattr(settings, "wecom_use_mock", False)
    monkeypatch.setattr(settings, "wecom_bind_card_pic_media_id", "")
    monkeypatch.setattr(settings, "wecom_bind_card_media_ttl_seconds", 3600)
    monkeypatch.setattr(settings, "wecom_bind_card_media_refresh_margin_seconds", 600)
    service = WecomBindCardAssetService(repo, client, settings)

    async def scenario():
        current = await service.upload_source(ONE_PIXEL_PNG, "bind.png", "image/png")
        client.fail = True

        try:
            await service.upload_source(ONE_PIXEL_PNG + b"x", "bind-new.png", "image/png")
        except RuntimeError:
            pass
        else:
            raise AssertionError("expected upload failure")

        assert repo.get_active_wecom_bind_card_asset().id == current.id
        assert repo.get_latest_wecom_bind_card_asset().status == "failed"

    asyncio.run(scenario())
