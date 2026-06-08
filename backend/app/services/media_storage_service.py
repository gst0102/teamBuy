from __future__ import annotations

import re
from pathlib import Path

from app.services.helpers import new_id


class MediaStorageService:
    def __init__(
        self,
        storage_mode: str = "mock",
        storage_dir: Path | None = None,
        public_url_prefix: str = "/media",
    ):
        self.storage_mode = storage_mode
        self.storage_dir = storage_dir
        self.public_url_prefix = public_url_prefix.rstrip("/") or "/media"

    def download_and_store(self, media_id: str, media_type: str = "image") -> str:
        if self.storage_mode != "mock":
            return self.build_mock_url(media_id, media_type)
        return self.build_mock_url(media_id, media_type)

    def store_bytes(
        self,
        media_id: str,
        media_type: str,
        content: bytes,
        content_type: str | None = None,
        filename: str | None = None,
    ) -> str:
        if self.storage_mode == "mock":
            return self.build_mock_url(media_id, media_type)
        if not self.storage_dir:
            raise ValueError("media storage dir is required when STORAGE_MODE is not mock")

        self.storage_dir.mkdir(parents=True, exist_ok=True)
        extension = self._extension(media_type, content_type, filename)
        safe_media_id = re.sub(r"[^A-Za-z0-9_.-]+", "_", media_id).strip("_") or "media"
        file_name = f"{new_id('media')}-{safe_media_id}.{extension}"
        (self.storage_dir / file_name).write_bytes(content)
        return f"{self.public_url_prefix}/{file_name}"

    def build_mock_url(self, media_id: str, media_type: str = "image") -> str:
        extension = "mp4" if media_type == "video" else "jpg"
        return f"/mock-media/{new_id('media')}-{media_id}.{extension}"

    def _extension(self, media_type: str, content_type: str | None, filename: str | None) -> str:
        if filename and "." in filename:
            return filename.rsplit(".", 1)[-1].lower()
        if content_type:
            subtype = content_type.split(";")[0].split("/")[-1].lower()
            if subtype in {"jpeg", "jpg"}:
                return "jpg"
            if subtype in {"png", "gif", "webp", "mp4", "mov"}:
                return subtype
        return "mp4" if media_type == "video" else "jpg"
