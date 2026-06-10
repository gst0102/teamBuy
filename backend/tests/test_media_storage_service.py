from __future__ import annotations

from app.services.media_storage_service import MediaStorageService


class FakeObjectClient:
    def __init__(self):
        self.calls = []

    def put_object(self, **kwargs):
        self.calls.append(kwargs)


def test_media_storage_mock_backend_returns_placeholder_url():
    service = MediaStorageService(storage_mode="mock")

    url = service.store_bytes("media_001", "image", b"image")

    assert url.startswith("/mock-media/")
    assert url.endswith("-media_001.webp")


def test_media_storage_local_backend_writes_file(tmp_path):
    service = MediaStorageService(storage_mode="local", storage_dir=tmp_path, public_url_prefix="/media")

    url = service.store_bytes("media/local 001", "image", b"image", "image/png", "cover.png")

    assert url.startswith("/media/")
    assert url.endswith("_001.png")
    stored_files = list(tmp_path.iterdir())
    assert len(stored_files) == 1
    assert stored_files[0].read_bytes() == b"image"


def test_media_storage_object_backend_uploads_to_s3_compatible_client():
    fake_client = FakeObjectClient()
    service = MediaStorageService(
        storage_mode="cos",
        object_storage_bucket="teambuy-media",
        object_storage_public_base_url="https://cdn.example.com",
        object_storage_key_prefix="wecom",
        backend=None,
    )
    service.backend.client = fake_client

    url = service.store_bytes("media_cos_001", "video", b"video", "video/mp4", "room.mp4")

    assert url.startswith("https://cdn.example.com/wecom/")
    assert url.endswith("-media_cos_001.mp4")
    assert fake_client.calls[0]["Bucket"] == "teambuy-media"
    assert fake_client.calls[0]["Body"] == b"video"
    assert fake_client.calls[0]["ContentType"] == "video/mp4"
