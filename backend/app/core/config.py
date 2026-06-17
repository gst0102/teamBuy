from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


BACKEND_DIR = Path(__file__).resolve().parents[2]
ROOT_DIR = Path(__file__).resolve().parents[3]

load_dotenv(ROOT_DIR / ".env")
load_dotenv(BACKEND_DIR / ".env")


def env_value(name: str, default: str = "") -> str:
    value = os.getenv(name)
    return value if value not in {None, ""} else default


def env_int(name: str, default: int) -> int:
    value = env_value(name, str(default))
    return int(value)


def env_path(name: str, default: str = "") -> Path | None:
    value = env_value(name, default)
    if not value:
        return None
    path = Path(value)
    return path if path.is_absolute() else ROOT_DIR / path


@dataclass(slots=True)
class Settings:
    app_env: str = env_value("APP_ENV", "development")
    app_host: str = env_value("APP_HOST", "127.0.0.1")
    app_port: int = env_int("APP_PORT", 8000)
    public_base_url: str = env_value("PUBLIC_BASE_URL", "")
    admin_token: str = env_value("WECOM_ADMIN_TOKEN", "")
    database_backend: str = env_value("DATABASE_BACKEND", "postgres")
    database_url: str = env_value("DATABASE_URL", "")
    wecom_callback_token: str = env_value("WECOM_CALLBACK_TOKEN", "teamBuy-dev-token")
    wecom_corp_id: str = env_value("WECOM_CORP_ID", "")
    wecom_secret: str = env_value("WECOM_SECRET", "")
    wecom_encoding_aes_key: str = env_value("WECOM_ENCODING_AES_KEY", "")
    wecom_open_kfid: str = env_value("WECOM_OPEN_KFID", "")
    wecom_sync_cursor: str = env_value("WECOM_SYNC_CURSOR", "")
    wecom_sync_limit: int = env_int("WECOM_SYNC_LIMIT", 100)
    wecom_sync_lock_timeout_seconds: int = env_int("WECOM_SYNC_LOCK_TIMEOUT_SECONDS", 600)
    wecom_api_base_url: str = env_value("WECOM_API_BASE_URL", "https://qyapi.weixin.qq.com")
    wecom_use_mock: bool = env_value("WECOM_USE_MOCK", "true").lower() in {"1", "true", "yes"}
    wecom_archive_enabled: bool = env_value("WECOM_ARCHIVE_ENABLED", "false").lower() in {"1", "true", "yes"}
    wecom_archive_secret: str = env_value("WECOM_ARCHIVE_SECRET", "")
    wecom_archive_callback_token: str = env_value("WECOM_ARCHIVE_CALLBACK_TOKEN", wecom_callback_token)
    wecom_archive_encoding_aes_key: str = env_value("WECOM_ARCHIVE_ENCODING_AES_KEY", wecom_encoding_aes_key)
    wecom_archive_private_key_path: Path | None = env_path("WECOM_ARCHIVE_PRIVATE_KEY_PATH", "backend/secrets/wecom_archive_private.pem")
    wecom_archive_public_key_path: Path | None = env_path("WECOM_ARCHIVE_PUBLIC_KEY_PATH", "backend/secrets/wecom_archive_public.pem")
    wecom_archive_sdk_lib_path: Path | None = env_path("WECOM_ARCHIVE_SDK_LIB_PATH", "")
    storage_mode: str = env_value("STORAGE_MODE", "mock")
    media_storage_dir: Path = ROOT_DIR / env_value("MEDIA_STORAGE_DIR", "backend/mock/media")
    media_public_url_prefix: str = env_value("MEDIA_PUBLIC_URL_PREFIX", "/media")
    media_image_max_edge: int = env_int("MEDIA_IMAGE_MAX_EDGE", 1600)
    media_image_quality: int = env_int("MEDIA_IMAGE_QUALITY", 82)
    media_video_max_width: int = env_int("MEDIA_VIDEO_MAX_WIDTH", 1280)
    media_video_crf: int = env_int("MEDIA_VIDEO_CRF", 28)
    ffmpeg_bin: str = env_value("FFMPEG_BIN", "ffmpeg")
    object_storage_endpoint: str = env_value("OBJECT_STORAGE_ENDPOINT", "")
    object_storage_region: str = env_value("OBJECT_STORAGE_REGION", "")
    object_storage_bucket: str = env_value("OBJECT_STORAGE_BUCKET", "")
    object_storage_access_key_id: str = env_value("OBJECT_STORAGE_ACCESS_KEY_ID", "")
    object_storage_secret_access_key: str = env_value("OBJECT_STORAGE_SECRET_ACCESS_KEY", "")
    object_storage_public_base_url: str = env_value("OBJECT_STORAGE_PUBLIC_BASE_URL", "")
    object_storage_key_prefix: str = env_value("OBJECT_STORAGE_KEY_PREFIX", "wecom-media")
    data_file: Path = ROOT_DIR / env_value("DATA_FILE", "backend/mock/runtime-state.json")

    def missing_database_fields(self) -> list[str]:
        if self.database_backend == "postgres" and not self.database_url:
            return ["DATABASE_URL"]
        return []

    def missing_wecom_fields(self) -> list[str]:
        required = {
            "PUBLIC_BASE_URL": self.public_base_url,
            "WECOM_CALLBACK_TOKEN": self.wecom_callback_token,
            "WECOM_CORP_ID": self.wecom_corp_id,
            "WECOM_SECRET": self.wecom_secret,
            "WECOM_ENCODING_AES_KEY": self.wecom_encoding_aes_key,
            "WECOM_OPEN_KFID": self.wecom_open_kfid,
        }
        return [key for key, value in required.items() if not value]

    def missing_wecom_archive_fields(self) -> list[str]:
        missing: list[str] = []
        if not self.wecom_corp_id:
            missing.append("WECOM_CORP_ID")
        if not self.wecom_archive_secret:
            missing.append("WECOM_ARCHIVE_SECRET")
        if not self.wecom_archive_private_key_path:
            missing.append("WECOM_ARCHIVE_PRIVATE_KEY_PATH")
        elif not self.wecom_archive_private_key_path.exists():
            missing.append("WECOM_ARCHIVE_PRIVATE_KEY_PATH(file not found)")
        if not self.wecom_archive_public_key_path:
            missing.append("WECOM_ARCHIVE_PUBLIC_KEY_PATH")
        elif not self.wecom_archive_public_key_path.exists():
            missing.append("WECOM_ARCHIVE_PUBLIC_KEY_PATH(file not found)")
        return missing


settings = Settings()
