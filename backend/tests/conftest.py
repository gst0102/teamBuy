from __future__ import annotations

from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.api.dependencies import get_app_service
from app.core.config import ROOT_DIR
from app.main import app
from app.services.app_service import AppService
from app.services.bootstrap import seed_runtime_state
from app.services.card_parser_service import CardParserService
from app.services.import_notification_service import ImportNotificationService
from app.services.media_storage_service import MediaStorageService
from app.services.message_aggregator import MessageAggregator
from app.services.ocr_service import OcrService
from app.services.repository import JsonRepository
from app.services.wecom_message_normalizer import WecomMessageNormalizer
from app.services.wecom_mock_service import WecomMockService


@pytest.fixture()
def client(tmp_path: Path):
    data_file = tmp_path / "runtime-state.json"
    repo = JsonRepository(data_file)
    mock_dir = ROOT_DIR / "backend" / "mock"
    seed_runtime_state(repo, mock_dir)
    service = AppService(
        repo=repo,
        wecom_mock_service=WecomMockService(mock_dir),
        media_storage_service=MediaStorageService(),
        parser_service=CardParserService(),
        aggregator=MessageAggregator(),
        notification_service=ImportNotificationService(),
        normalizer=WecomMessageNormalizer(),
        ocr_service=OcrService(provider="mock", mock_text=""),
    )

    app.dependency_overrides[get_app_service] = lambda: service
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
