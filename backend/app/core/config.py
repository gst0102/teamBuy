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
    storage_mode: str = env_value("STORAGE_MODE", "mock")
    media_storage_dir: Path = ROOT_DIR / env_value("MEDIA_STORAGE_DIR", "backend/mock/media")
    media_public_url_prefix: str = env_value("MEDIA_PUBLIC_URL_PREFIX", "/media")
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


settings = Settings()
