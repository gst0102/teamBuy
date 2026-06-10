from __future__ import annotations

import re
from pathlib import Path
from typing import Protocol

from app.services.helpers import new_id


class MediaStorageBackend(Protocol):
    def store_bytes(
        self,
        media_id: str,
        media_type: str,
        content: bytes,
        content_type: str | None = None,
        filename: str | None = None,
    ) -> str:
        ...

    def build_fallback_url(self, media_id: str, media_type: str = "image") -> str:
        ...


class MockMediaStorageBackend:
    def store_bytes(
        self,
        media_id: str,
        media_type: str,
        content: bytes,
        content_type: str | None = None,
        filename: str | None = None,
    ) -> str:
        return self.build_fallback_url(media_id, media_type)

    def build_fallback_url(self, media_id: str, media_type: str = "image") -> str:
        extension = "mp4" if media_type == "video" else "webp"
        return f"/mock-media/{new_id('media')}-{media_id}.{extension}"


class LocalMediaStorageBackend:
    def __init__(self, storage_dir: Path, public_url_prefix: str = "/media"):
        self.storage_dir = storage_dir
        self.public_url_prefix = public_url_prefix.rstrip("/") or "/media"

    def store_bytes(
        self,
        media_id: str,
        media_type: str,
        content: bytes,
        content_type: str | None = None,
        filename: str | None = None,
    ) -> str:
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        file_name = build_media_file_name(media_id, media_type, content_type, filename)
        (self.storage_dir / file_name).write_bytes(content)
        return f"{self.public_url_prefix}/{file_name}"

    def build_fallback_url(self, media_id: str, media_type: str = "image") -> str:
        return MockMediaStorageBackend().build_fallback_url(media_id, media_type)


class ObjectStorageMediaBackend:
    def __init__(
        self,
        bucket: str,
        public_base_url: str,
        endpoint_url: str = "",
        region: str = "",
        access_key_id: str = "",
        secret_access_key: str = "",
        key_prefix: str = "wecom-media",
        client=None,
    ):
        self.bucket = bucket
        self.public_base_url = public_base_url.rstrip("/")
        self.endpoint_url = endpoint_url
        self.region = region
        self.access_key_id = access_key_id
        self.secret_access_key = secret_access_key
        self.key_prefix = key_prefix.strip("/")
        self.client = client

    def store_bytes(
        self,
        media_id: str,
        media_type: str,
        content: bytes,
        content_type: str | None = None,
        filename: str | None = None,
    ) -> str:
        if not self.bucket or not self.public_base_url:
            raise ValueError("object storage bucket and public base url are required")
        object_key = self._object_key(media_id, media_type, content_type, filename)
        self._client().put_object(
            Bucket=self.bucket,
            Key=object_key,
            Body=content,
            ContentType=content_type or default_content_type(media_type),
        )
        return f"{self.public_base_url}/{object_key}"

    def build_fallback_url(self, media_id: str, media_type: str = "image") -> str:
        return MockMediaStorageBackend().build_fallback_url(media_id, media_type)

    def _object_key(self, media_id: str, media_type: str, content_type: str | None, filename: str | None) -> str:
        file_name = build_media_file_name(media_id, media_type, content_type, filename)
        return f"{self.key_prefix}/{file_name}" if self.key_prefix else file_name

    def _client(self):
        if self.client:
            return self.client
        try:
            import boto3
        except ImportError as exc:
            raise RuntimeError("boto3 is required for STORAGE_MODE=cos or STORAGE_MODE=s3") from exc
        self.client = boto3.client(
            "s3",
            endpoint_url=self.endpoint_url or None,
            region_name=self.region or None,
            aws_access_key_id=self.access_key_id or None,
            aws_secret_access_key=self.secret_access_key or None,
        )
        return self.client


class MediaStorageService:
    def __init__(
        self,
        storage_mode: str = "mock",
        storage_dir: Path | None = None,
        public_url_prefix: str = "/media",
        object_storage_endpoint: str = "",
        object_storage_region: str = "",
        object_storage_bucket: str = "",
        object_storage_access_key_id: str = "",
        object_storage_secret_access_key: str = "",
        object_storage_public_base_url: str = "",
        object_storage_key_prefix: str = "wecom-media",
        backend: MediaStorageBackend | None = None,
    ):
        self.storage_mode = storage_mode
        self.storage_dir = storage_dir
        self.public_url_prefix = public_url_prefix.rstrip("/") or "/media"
        self.backend = backend or self._build_backend(
            storage_mode=storage_mode,
            storage_dir=storage_dir,
            public_url_prefix=public_url_prefix,
            object_storage_endpoint=object_storage_endpoint,
            object_storage_region=object_storage_region,
            object_storage_bucket=object_storage_bucket,
            object_storage_access_key_id=object_storage_access_key_id,
            object_storage_secret_access_key=object_storage_secret_access_key,
            object_storage_public_base_url=object_storage_public_base_url,
            object_storage_key_prefix=object_storage_key_prefix,
        )

    def download_and_store(self, media_id: str, media_type: str = "image") -> str:
        return self.backend.build_fallback_url(media_id, media_type)

    def store_bytes(
        self,
        media_id: str,
        media_type: str,
        content: bytes,
        content_type: str | None = None,
        filename: str | None = None,
    ) -> str:
        return self.backend.store_bytes(media_id, media_type, content, content_type, filename)

    def build_mock_url(self, media_id: str, media_type: str = "image") -> str:
        return MockMediaStorageBackend().build_fallback_url(media_id, media_type)

    def _build_backend(
        self,
        storage_mode: str,
        storage_dir: Path | None,
        public_url_prefix: str,
        object_storage_endpoint: str,
        object_storage_region: str,
        object_storage_bucket: str,
        object_storage_access_key_id: str,
        object_storage_secret_access_key: str,
        object_storage_public_base_url: str,
        object_storage_key_prefix: str,
    ) -> MediaStorageBackend:
        if storage_mode == "local":
            if not storage_dir:
                raise ValueError("media storage dir is required for STORAGE_MODE=local")
            return LocalMediaStorageBackend(storage_dir, public_url_prefix)
        if storage_mode in {"cos", "s3"}:
            return ObjectStorageMediaBackend(
                bucket=object_storage_bucket,
                public_base_url=object_storage_public_base_url,
                endpoint_url=object_storage_endpoint,
                region=object_storage_region,
                access_key_id=object_storage_access_key_id,
                secret_access_key=object_storage_secret_access_key,
                key_prefix=object_storage_key_prefix,
            )
        return MockMediaStorageBackend()


def build_media_file_name(media_id: str, media_type: str, content_type: str | None, filename: str | None) -> str:
    extension = resolve_extension(media_type, content_type, filename)
    safe_media_id = re.sub(r"[^A-Za-z0-9_.-]+", "_", media_id).strip("_") or "media"
    return f"{new_id('media')}-{safe_media_id}.{extension}"


def resolve_extension(media_type: str, content_type: str | None, filename: str | None) -> str:
    if filename and "." in filename:
        return filename.rsplit(".", 1)[-1].lower()
    if content_type:
        subtype = content_type.split(";")[0].split("/")[-1].lower()
        if subtype in {"jpeg", "jpg"}:
            return "jpg"
        if subtype in {"png", "gif", "webp", "mp4", "mov"}:
            return subtype
    return "mp4" if media_type == "video" else "webp"


def default_content_type(media_type: str) -> str:
    return "video/mp4" if media_type == "video" else "image/webp"
