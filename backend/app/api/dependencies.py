from __future__ import annotations

from app.core.config import BACKEND_DIR, settings
from app.services.app_service import AppService
from app.services.bootstrap import seed_runtime_state
from app.services.card_parser_service import CardParserService
from app.services.import_notification_service import ImportNotificationService
from app.services.media_storage_service import MediaStorageService
from app.services.message_aggregator import MessageAggregator
from app.services.repository import build_repository
from app.services.wecom_mock_service import WecomMockService
from app.services.wecom_client import WecomClient


_repo = build_repository(settings.database_backend, settings.database_url, settings.data_file)
seed_runtime_state(_repo, BACKEND_DIR / "mock")
_service = AppService(
    repo=_repo,
    wecom_mock_service=WecomMockService(BACKEND_DIR / "mock"),
    media_storage_service=MediaStorageService(),
    parser_service=CardParserService(),
    aggregator=MessageAggregator(),
    notification_service=ImportNotificationService(),
)
_wecom_client = WecomClient(settings)


def get_app_service() -> AppService:
    return _service


def get_wecom_client() -> WecomClient:
    return _wecom_client
