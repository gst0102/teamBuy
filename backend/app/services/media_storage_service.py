from __future__ import annotations

from app.services.helpers import new_id


class MediaStorageService:
    def download_and_store(self, media_id: str) -> str:
        return f"/mock-media/{new_id('media')}-{media_id}.jpg"

