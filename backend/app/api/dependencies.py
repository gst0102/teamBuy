from __future__ import annotations

import asyncio

from app.core.config import BACKEND_DIR, settings
from app.services.app_service import AppService
from app.services.background_task_worker import BackgroundTaskWorker
from app.services.bootstrap import seed_runtime_state
from app.services.card_parser_service import CardParserService
from app.services.content_object_adapter import ContentObjectAdapter
from app.services.import_notification_service import ImportNotificationService
from app.services.media_storage_service import MediaStorageService
from app.services.media_processing_service import MediaProcessingService
from app.services.message_aggregator import MessageAggregator
from app.services.ops_console_store import OpsConsoleStore
from app.services.repository import build_repository
from app.services.skill_router_service import SkillRouterService
from app.services.sync_task_queue import SyncTaskQueue
from app.services.wecom_archive_client import WecomArchiveClient
from app.services.wecom_archive_worker import WecomArchiveWorker
from app.services.wecom_client import WecomClient
from app.services.wecom_message_normalizer import WecomMessageNormalizer
from app.services.wecom_mock_service import WecomMockService


_repo = build_repository(settings.database_backend, settings.database_url, settings.data_file)
seed_runtime_state(_repo, BACKEND_DIR / "mock")
_wecom_mock_service = WecomMockService(BACKEND_DIR / "mock")
_skill_router_service = SkillRouterService()
_service = AppService(
    repo=_repo,
    wecom_mock_service=_wecom_mock_service,
    media_storage_service=MediaStorageService(
        storage_mode=settings.storage_mode,
        storage_dir=settings.media_storage_dir,
        public_url_prefix=settings.media_public_url_prefix,
        object_storage_endpoint=settings.object_storage_endpoint,
        object_storage_region=settings.object_storage_region,
        object_storage_bucket=settings.object_storage_bucket,
        object_storage_access_key_id=settings.object_storage_access_key_id,
        object_storage_secret_access_key=settings.object_storage_secret_access_key,
        object_storage_public_base_url=settings.object_storage_public_base_url,
        object_storage_key_prefix=settings.object_storage_key_prefix,
    ),
    parser_service=CardParserService(),
    aggregator=MessageAggregator(),
    notification_service=ImportNotificationService(),
    normalizer=WecomMessageNormalizer(),
    skill_router_service=_skill_router_service,
    content_object_adapter=ContentObjectAdapter(),
    media_processing_service=MediaProcessingService(
        image_max_edge=settings.media_image_max_edge,
        image_quality=settings.media_image_quality,
        video_max_width=settings.media_video_max_width,
        video_crf=settings.media_video_crf,
        ffmpeg_bin=settings.ffmpeg_bin,
    ),
)
_wecom_client = WecomClient(settings)
_wecom_archive_client = WecomArchiveClient(
    corp_id=settings.wecom_corp_id,
    secret=settings.wecom_archive_secret,
    private_key_path=settings.wecom_archive_private_key_path,
    sdk_lib_path=settings.wecom_archive_sdk_lib_path,
    proxy=settings.wecom_archive_proxy,
    proxy_password=settings.wecom_archive_proxy_password,
    timeout_seconds=settings.wecom_archive_sdk_timeout_seconds,
)
_sync_task_queue = SyncTaskQueue(
    _repo,
    lock_timeout_seconds=settings.wecom_sync_lock_timeout_seconds,
    auto_schedule=settings.sync_task_auto_schedule,
)
OCR_TASK_NAMES = {"ocr-recognize-note", "property-table-ocr"}
_ocr_task_worker = BackgroundTaskWorker(
    _sync_task_queue,
    enabled=settings.sync_task_worker_enabled,
    interval_seconds=settings.sync_task_worker_interval_seconds,
    task_names=OCR_TASK_NAMES,
    max_running=max(settings.ocr_task_concurrency, 1),
)
_ops_console_store = OpsConsoleStore(settings.data_file.parent / "ops-console-state.json")


async def _run_ocr_recognize_task(payload: dict) -> dict:
    note_id = str(payload.get("noteId") or "")
    owner_user_id = str(payload.get("ownerUserId") or "")
    if not note_id or not owner_user_id:
        raise ValueError("OCR task missing noteId or ownerUserId")
    return await asyncio.to_thread(_service.recognize_ocr_note_image, note_id, owner_user_id)


async def _run_property_table_ocr_task(payload: dict) -> dict:
    note_id = str(payload.get("noteId") or "")
    owner_user_id = str(payload.get("ownerUserId") or "")
    if not note_id or not owner_user_id:
        raise ValueError("Property table OCR task missing noteId or ownerUserId")
    return await asyncio.to_thread(_service.recognize_property_table_ocr_note_image, note_id, owner_user_id)


def register_background_task_handlers() -> None:
    _sync_task_queue.register("ocr-recognize-note", _run_ocr_recognize_task)
    _sync_task_queue.register("property-table-ocr", _run_property_table_ocr_task)


register_background_task_handlers()


def _notification_reply_text(notification: dict) -> str:
    title = notification.get("title") or "房源资料"
    message = notification.get("message") or ""
    path = notification.get("resultPath") or ""
    if notification.get("status") == "success":
        lines = [
            f"已完成：{title}",
            message,
            "上游电话、中介费、密码锁等敏感信息只在你的账号里查看。",
        ]
        if path:
            lines.append(f"打开小程序查看：{path}")
        return "\n".join([line for line in lines if line])
    return f"整理失败：{title}\n{message}"


async def _send_archive_import_notifications(notifications: list[dict]) -> list[dict]:
    results = []
    if settings.wecom_use_mock:
        return results
    for notification in notifications:
        notification_id = notification.get("id")
        external_user_id = notification.get("externalUserId")
        if not notification_id or not external_user_id:
            continue
        try:
            response = await _wecom_client.send_customer_service_text(
                external_user_id=external_user_id,
                content=_notification_reply_text(notification),
                open_kfid=settings.wecom_open_kfid or None,
            )
            updated = _service.update_import_notification_delivery(notification_id, "sent")
            results.append({"notificationId": notification_id, "status": "sent", "response": response, "notification": updated})
        except Exception as exc:
            updated = _service.update_import_notification_delivery(notification_id, "failed", str(exc))
            results.append({"notificationId": notification_id, "status": "failed", "error": str(exc), "notification": updated})
    return results


_wecom_archive_worker = WecomArchiveWorker(
    _service,
    _wecom_archive_client,
    enabled=settings.wecom_archive_worker_enabled,
    interval_seconds=settings.wecom_archive_worker_interval_seconds,
    pull_limit=settings.wecom_archive_pull_limit,
    notification_sender=_send_archive_import_notifications,
)


def get_app_service() -> AppService:
    return _service


def get_wecom_client() -> WecomClient:
    return _wecom_client


def get_wecom_archive_client() -> WecomArchiveClient:
    return _wecom_archive_client


def get_wecom_mock_service() -> WecomMockService:
    return _wecom_mock_service


def get_sync_task_queue() -> SyncTaskQueue:
    return _sync_task_queue


def get_ocr_task_worker() -> BackgroundTaskWorker:
    return _ocr_task_worker


def get_wecom_archive_worker() -> WecomArchiveWorker:
    return _wecom_archive_worker


def get_skill_router_service() -> SkillRouterService:
    return _skill_router_service


def get_ops_console_store() -> OpsConsoleStore:
    return _ops_console_store
