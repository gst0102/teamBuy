from __future__ import annotations

import base64
import binascii
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")


def _env(name: str, default: str = "") -> str:
    value = os.getenv(name)
    return default if value in {None, ""} else value


def _bool(name: str, default: bool = False) -> bool:
    return _env(name, "true" if default else "false").lower() in {"1", "true", "yes"}


def _int(name: str, default: int) -> int:
    return int(_env(name, str(default)))


def _key(value: str, name: str) -> bytes:
    raw = value.strip()
    if not raw:
        return b""
    try:
        decoded = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))
        if len(decoded) in {16, 24, 32}:
            return decoded
    except (ValueError, binascii.Error):
        pass
    try:
        decoded = bytes.fromhex(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be base64 or hexadecimal") from exc
    if len(decoded) not in {16, 24, 32}:
        raise ValueError(f"{name} must decode to 16, 24 or 32 bytes")
    return decoded


@dataclass(frozen=True)
class ProjectRoute:
    project_id: str
    endpoint_url: str
    token: str
    chat_ids: frozenset[str] = field(default_factory=frozenset)
    from_user_ids: frozenset[str] = field(default_factory=frozenset)
    to_user_ids: frozenset[str] = field(default_factory=frozenset)
    message_types: frozenset[str] = field(default_factory=frozenset)
    allow_all_chats: bool = False
    include_direct_messages: bool = False
    enabled: bool = True

    def matches(
        self,
        room_id: str,
        message_type: str,
        *,
        from_user: str = "",
        to_user_ids: tuple[str, ...] = (),
    ) -> bool:
        if not self.enabled:
            return False
        if room_id:
            if self.chat_ids:
                if room_id not in self.chat_ids:
                    return False
            elif not self.allow_all_chats:
                return False
        else:
            if not self.include_direct_messages:
                return False
            if self.from_user_ids and from_user not in self.from_user_ids:
                return False
            if self.to_user_ids and not self.to_user_ids.intersection(to_user_ids):
                return False
        return not self.message_types or message_type in self.message_types


@dataclass(frozen=True)
class Settings:
    environment: str
    database_url: str
    corp_id: str
    archive_secret: str
    admin_token: str
    callback_token: str
    encoding_aes_key: str
    private_key_path: Path
    sdk_lib_path: Path
    proxy: str
    proxy_password: str
    sdk_timeout_seconds: int
    data_key: bytes
    media_token_key: bytes
    enabled: bool
    worker_enabled: bool
    poll_interval_seconds: int
    batch_limit: int
    delivery_limit: int
    delivery_timeout_seconds: float
    projects: tuple[ProjectRoute, ...]
    raw_retention_hours: int = 24

    @classmethod
    def from_env(cls) -> "Settings":
        raw_projects = _env("WECOM_ARCHIVE_CORE_PROJECTS_JSON", "[]")
        try:
            parsed: Any = json.loads(raw_projects)
        except json.JSONDecodeError as exc:
            raise ValueError("WECOM_ARCHIVE_CORE_PROJECTS_JSON must be valid JSON") from exc
        if not isinstance(parsed, list):
            raise ValueError("WECOM_ARCHIVE_CORE_PROJECTS_JSON must be a JSON array")
        projects: list[ProjectRoute] = []
        project_ids: set[str] = set()
        for item in parsed:
            if not isinstance(item, dict):
                raise ValueError("Each archive project route must be an object")
            project_id = str(item.get("projectId") or item.get("project_id") or "").strip()
            endpoint_url = str(item.get("endpointUrl") or item.get("endpoint_url") or "").strip()
            token = str(item.get("token") or "")
            if not project_id or not endpoint_url or not token:
                raise ValueError("Each archive project route requires projectId, endpointUrl and token")
            if project_id in project_ids:
                raise ValueError(f"Duplicate archive project route: {project_id}")
            project_ids.add(project_id)
            projects.append(
                ProjectRoute(
                    project_id=project_id,
                    endpoint_url=endpoint_url,
                    token=token,
                    chat_ids=frozenset(str(value).strip() for value in item.get("chatIds", []) if str(value).strip()),
                    from_user_ids=frozenset(
                        str(value).strip()
                        for value in item.get("fromUserIds", item.get("from_user_ids", []))
                        if str(value).strip()
                    ),
                    to_user_ids=frozenset(
                        str(value).strip()
                        for value in item.get("toUserIds", item.get("to_user_ids", []))
                        if str(value).strip()
                    ),
                    message_types=frozenset(str(value).strip() for value in item.get("messageTypes", []) if str(value).strip()),
                    allow_all_chats=bool(item.get("allowAllChats", False)),
                    include_direct_messages=bool(
                        item.get("includeDirectMessages", item.get("include_direct_messages", False))
                    ),
                    enabled=bool(item.get("enabled", True)),
                )
            )
        return cls(
            environment=_env("WECOM_ARCHIVE_CORE_ENVIRONMENT", "development"),
            database_url=_env("WECOM_ARCHIVE_CORE_DATABASE_URL"),
            corp_id=_env("WECOM_ARCHIVE_CORE_CORP_ID"),
            archive_secret=_env("WECOM_ARCHIVE_CORE_SECRET"),
            admin_token=_env("WECOM_ARCHIVE_CORE_ADMIN_TOKEN"),
            callback_token=_env("WECOM_ARCHIVE_CORE_CALLBACK_TOKEN"),
            encoding_aes_key=_env("WECOM_ARCHIVE_CORE_ENCODING_AES_KEY"),
            private_key_path=Path(_env("WECOM_ARCHIVE_CORE_PRIVATE_KEY_PATH")),
            sdk_lib_path=Path(_env("WECOM_ARCHIVE_CORE_SDK_LIB_PATH")),
            proxy=_env("WECOM_ARCHIVE_CORE_PROXY"),
            proxy_password=_env("WECOM_ARCHIVE_CORE_PROXY_PASSWORD"),
            sdk_timeout_seconds=max(_int("WECOM_ARCHIVE_CORE_SDK_TIMEOUT_SECONDS", 30), 5),
            data_key=_key(_env("WECOM_ARCHIVE_CORE_DATA_KEY"), "WECOM_ARCHIVE_CORE_DATA_KEY"),
            media_token_key=_key(
                _env("WECOM_ARCHIVE_CORE_MEDIA_TOKEN_KEY"),
                "WECOM_ARCHIVE_CORE_MEDIA_TOKEN_KEY",
            ),
            enabled=_bool("WECOM_ARCHIVE_CORE_ENABLED"),
            worker_enabled=_bool("WECOM_ARCHIVE_CORE_WORKER_ENABLED"),
            poll_interval_seconds=max(_int("WECOM_ARCHIVE_CORE_POLL_INTERVAL_SECONDS", 60), 10),
            batch_limit=max(min(_int("WECOM_ARCHIVE_CORE_BATCH_LIMIT", 50), 100), 1),
            delivery_limit=max(min(_int("WECOM_ARCHIVE_CORE_DELIVERY_LIMIT", 50), 200), 1),
            delivery_timeout_seconds=max(float(_env("WECOM_ARCHIVE_CORE_DELIVERY_TIMEOUT_SECONDS", "15")), 1.0),
            projects=tuple(projects),
            raw_retention_hours=max(min(_int("WECOM_ARCHIVE_CORE_RAW_RETENTION_HOURS", 24), 168), 1),
        )

    def missing_fields(self) -> list[str]:
        missing: list[str] = []
        for name, value in (
            ("WECOM_ARCHIVE_CORE_DATABASE_URL", self.database_url),
            ("WECOM_ARCHIVE_CORE_CORP_ID", self.corp_id),
            ("WECOM_ARCHIVE_CORE_SECRET", self.archive_secret),
        ):
            if not value:
                missing.append(name)
        if self.enabled and self.worker_enabled:
            if not self.private_key_path.is_file():
                missing.append("WECOM_ARCHIVE_CORE_PRIVATE_KEY_PATH(file not found)")
            if not self.sdk_lib_path.is_file():
                missing.append("WECOM_ARCHIVE_CORE_SDK_LIB_PATH(file not found)")
            if not self.data_key:
                missing.append("WECOM_ARCHIVE_CORE_DATA_KEY")
            if not self.media_token_key:
                missing.append("WECOM_ARCHIVE_CORE_MEDIA_TOKEN_KEY")
        return missing
