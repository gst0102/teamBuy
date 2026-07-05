from __future__ import annotations

from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.api.dependencies import get_app_service, get_ops_console_store, get_sync_task_queue
from app.core.config import ROOT_DIR
from app.main import app
from app.services.app_service import AppService
from app.services.bootstrap import seed_runtime_state
from app.services.card_parser_service import CardParserService
from app.services.import_notification_service import ImportNotificationService
from app.services.media_storage_service import MediaStorageService
from app.services.message_aggregator import MessageAggregator
from app.services.ocr_service import OcrService
from app.services.ops_console_store import OpsConsoleStore
from app.services.repository import JsonRepository
from app.services.sync_task_queue import SyncTaskQueue
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
    ops_store = OpsConsoleStore(tmp_path / "ops-console-state.json")
    sync_task_queue = SyncTaskQueue(repo, retry_delay_seconds=1, auto_schedule=False)

    async def run_ocr(payload):
        return service.recognize_ocr_note_image(str(payload.get("noteId")), str(payload.get("ownerUserId")))

    async def run_property_table_ocr(payload):
        return service.recognize_property_table_ocr_note_image(str(payload.get("noteId")), str(payload.get("ownerUserId")))

    sync_task_queue.register("ocr-recognize-note", run_ocr)
    sync_task_queue.register("property-table-ocr", run_property_table_ocr)

    app.dependency_overrides[get_app_service] = lambda: service
    app.dependency_overrides[get_ops_console_store] = lambda: ops_store
    app.dependency_overrides[get_sync_task_queue] = lambda: sync_task_queue
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
