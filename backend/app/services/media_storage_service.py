from __future__ import annotations

from app.services.helpers import new_id


class MediaStorageService:
    def download_and_store(self, media_id: str, media_type: str = "image") -> str:
        extension = "mp4" if media_type == "video" else "jpg"
        return f"/mock-media/{new_id('media')}-{media_id}.{extension}"
