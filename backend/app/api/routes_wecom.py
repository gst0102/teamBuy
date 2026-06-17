from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse

from app.api.dependencies import get_app_service, get_sync_task_queue, get_wecom_archive_client, get_wecom_client, get_wecom_mock_service
from app.core.config import settings
from app.schemas.common import ApiResponse
from app.schemas.imports import MockImportRequest
from app.services.app_service import AppService
from app.services.sync_task_queue import SyncTaskQueue
from app.services.wecom_archive_client import WecomArchiveClient
from app.services.wecom_client import WecomClient, WecomClientError
from app.services.wecom_crypto import WecomCryptoError, decrypt_aes_message, verify_signature
from app.services.wecom_event_service import parse_callback_body
from app.services.wecom_mock_service import WecomMockService


router = APIRouter(prefix="/api/wecom", tags=["wecom"])
KF_CALLBACK_PATH = "/kf/teamBuy/callback"
ARCHIVE_CALLBACK_PATH = "/archive/callback"


def _register_real_sync_task(sync_task_queue: SyncTaskQueue) -> None:
    async def run(payload: dict):
        return await _run_real_sync(
            max_pages=int(payload.get("maxPages", 10)),
            service=get_app_service(),
            client=get_wecom_client(),
            mock_service=get_wecom_mock_service(),
        )

    sync_task_queue.register("wecom-callback-real-sync", run)


async def recover_persisted_sync_tasks() -> None:
    sync_task_queue = get_sync_task_queue()
    _register_real_sync_task(sync_task_queue)
    sync_task_queue.start_pending()


def _sync_response_has_more(value) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes"}
    return bool(value)


def _verify_admin_token(provided_token: str | None) -> None:
    if not settings.admin_token:
        raise HTTPException(status_code=403, detail="WECOM_ADMIN_TOKEN is not configured")
    if provided_token != settings.admin_token:
        raise HTTPException(status_code=403, detail="admin token verification failed")


def _read_text_file(path) -> str:
    if not path or not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _mask_path(path) -> str:
    return str(path) if path else ""


async def _download_sync_media(
    messages: list[dict],
    client: WecomClient,
    service: AppService,
) -> dict[str, str]:
    media_urls: dict[str, str] = {}
    for message in messages:
        media_id = message.get("mediaId")
        msg_type = message.get("msgType")
        if not media_id or msg_type not in {"image", "video"} or media_id in media_urls:
            continue
        existing_url = service.get_successful_media_url(media_id)
        if existing_url:
            media_urls[media_id] = existing_url
            continue
        try:
            downloaded = await client.download_media(media_id)
            media_urls[media_id] = service.process_and_store_media(
                media_id=media_id,
                media_type=msg_type,
                content=downloaded.content,
                content_type=downloaded.content_type,
                filename=downloaded.filename,
            )
        except WecomClientError as exc:
            service.save_media_retry_failure(
                media_id=media_id,
                media_type=msg_type,
                open_kfid=message.get("openKfid"),
                error_message=str(exc),
            )
    return media_urls


async def _retry_media_job(job: dict, client: WecomClient, service: AppService):
    downloaded = await client.download_media(job["mediaId"])
    local_url = service.process_and_store_media(
        media_id=job["mediaId"],
        media_type=job["mediaType"],
        content=downloaded.content,
        content_type=downloaded.content_type,
        filename=downloaded.filename,
    )
    return service.save_media_retry_success(
        media_id=job["mediaId"],
        media_type=job["mediaType"],
        open_kfid=job.get("openKfid"),
        local_media_url=local_url,
    )


@router.get(KF_CALLBACK_PATH, response_class=PlainTextResponse)
def verify_callback(
    msg_signature: str | None = Query(default=None),
    timestamp: str | None = Query(default=None),
    nonce: str | None = Query(default=None),
    echostr: str | None = Query(default=None),
    token: str | None = Query(default=None),
):
    if token is not None and token != settings.wecom_callback_token:
        raise HTTPException(status_code=403, detail="token 验证失败")
    if echostr and msg_signature and timestamp and nonce:
        if not verify_signature(settings.wecom_callback_token, timestamp, nonce, echostr, msg_signature):
            raise HTTPException(status_code=403, detail="企业微信签名验证失败")
        if settings.wecom_encoding_aes_key and settings.wecom_corp_id:
            try:
                return PlainTextResponse(decrypt_aes_message(settings.wecom_encoding_aes_key, echostr, settings.wecom_corp_id))
            except WecomCryptoError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
    return PlainTextResponse(echostr or "verified")


@router.post(KF_CALLBACK_PATH, response_model=ApiResponse[dict])
async def receive_callback(
    request: Request,
    service: AppService = Depends(get_app_service),
    client: WecomClient = Depends(get_wecom_client),
    mock_service: WecomMockService = Depends(get_wecom_mock_service),
    sync_task_queue: SyncTaskQueue = Depends(get_sync_task_queue),
):
    raw_body = await request.body()
    try:
        payload = parse_callback_body(
            raw_body,
            request.headers.get("content-type", ""),
            settings,
            {
                "msg_signature": request.query_params.get("msg_signature"),
                "timestamp": request.query_params.get("timestamp"),
                "nonce": request.query_params.get("nonce"),
            },
        )
    except (ValueError, WecomCryptoError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if settings.wecom_use_mock:
        fixture = payload.get("fixture", "note")
        external_user_id = payload.get("externalUserId") or payload.get("ExternalUserID") or "external_demo"
        conversation_id = payload.get("conversationId") or payload.get("Token") or "conv_demo"
        result = service.trigger_mock_import(external_user_id, conversation_id, fixture)
        return ApiResponse(message="callback mock import completed", data={"callback": payload, "syncResult": result})

    _register_real_sync_task(sync_task_queue)
    task = sync_task_queue.enqueue("wecom-callback-real-sync", payload={"maxPages": 10})
    return ApiResponse(
        message="callback real sync queued",
        data={"callback": payload, "syncTask": task.model_dump()},
    )


@router.get(ARCHIVE_CALLBACK_PATH, response_class=PlainTextResponse)
def verify_archive_callback(
    msg_signature: str | None = Query(default=None),
    timestamp: str | None = Query(default=None),
    nonce: str | None = Query(default=None),
    echostr: str | None = Query(default=None),
    token: str | None = Query(default=None),
):
    callback_token = settings.wecom_archive_callback_token or settings.wecom_callback_token
    callback_aes_key = settings.wecom_archive_encoding_aes_key or settings.wecom_encoding_aes_key
    if token is not None and token != callback_token:
        raise HTTPException(status_code=403, detail="token 验证失败")
    if echostr and msg_signature and timestamp and nonce:
        if not verify_signature(callback_token, timestamp, nonce, echostr, msg_signature):
            raise HTTPException(status_code=403, detail="企业微信签名验证失败")
        if callback_aes_key and settings.wecom_corp_id:
            try:
                return PlainTextResponse(decrypt_aes_message(callback_aes_key, echostr, settings.wecom_corp_id))
            except WecomCryptoError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
    return PlainTextResponse(echostr or "verified")


@router.post(ARCHIVE_CALLBACK_PATH, response_model=ApiResponse[dict])
async def receive_archive_callback(request: Request):
    raw_body = await request.body()
    try:
        payload = parse_callback_body(
            raw_body,
            request.headers.get("content-type", ""),
            settings,
            {
                "msg_signature": request.query_params.get("msg_signature"),
                "timestamp": request.query_params.get("timestamp"),
                "nonce": request.query_params.get("nonce"),
            },
            token=settings.wecom_archive_callback_token or settings.wecom_callback_token,
            encoding_aes_key=settings.wecom_archive_encoding_aes_key or settings.wecom_encoding_aes_key,
        )
    except (ValueError, WecomCryptoError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ApiResponse(message="archive callback received", data={"callback": payload})


@router.post("/mock-sync", response_model=ApiResponse[dict])
def mock_sync(payload: MockImportRequest, service: AppService = Depends(get_app_service)):
    result = service.trigger_mock_import(payload.externalUserId, payload.conversationId, payload.fixture)
    return ApiResponse(data=result, message="mock import completed")


@router.get("/notifications", response_model=ApiResponse[list[dict]])
def list_notifications(service: AppService = Depends(get_app_service)):
    return ApiResponse(data=service.list_import_notifications())


@router.get("/sync-tasks", response_model=ApiResponse[list[dict]])
def list_sync_tasks(sync_task_queue: SyncTaskQueue = Depends(get_sync_task_queue)):
    return ApiResponse(data=[item.model_dump() for item in sync_task_queue.list_recent()])


@router.get("/sync-tasks/logs", response_model=ApiResponse[list[dict]])
def list_sync_task_logs(
    task_id: str | None = Query(default=None, alias="taskId"),
    sync_task_queue: SyncTaskQueue = Depends(get_sync_task_queue),
):
    return ApiResponse(data=[item.model_dump() for item in sync_task_queue.list_logs(task_id)])


@router.get("/media-retries", response_model=ApiResponse[list[dict]])
def list_media_retries(status: str | None = Query(default=None), service: AppService = Depends(get_app_service)):
    statuses = {status} if status else None
    return ApiResponse(data=service.list_media_retry_jobs(statuses))


@router.get("/import-failures", response_model=ApiResponse[dict])
def list_import_failures(
    limit: int = Query(default=100, ge=1, le=500),
    service: AppService = Depends(get_app_service),
):
    return ApiResponse(data=service.list_import_failures(limit=limit))


@router.get("/retry-dashboard", response_model=ApiResponse[dict])
def get_retry_dashboard(
    limit: int = Query(default=100, ge=1, le=500),
    service: AppService = Depends(get_app_service),
):
    return ApiResponse(data=service.get_wecom_retry_dashboard(limit=limit))


@router.post("/import-failures/retry", response_model=ApiResponse[dict])
def retry_import_failure(
    import_batch_id: str = Query(..., alias="importBatchId"),
    admin_token: str | None = Query(default=None, alias="adminToken"),
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    service: AppService = Depends(get_app_service),
):
    _verify_admin_token(x_admin_token or admin_token)
    return ApiResponse(data=service.retry_failed_import(import_batch_id, notification_channel="wecom"))


@router.post("/media-retries/retry", response_model=ApiResponse[dict])
async def retry_media_retries(
    media_id: str | None = Query(default=None),
    status: str = Query(default="failed"),
    admin_token: str | None = Query(default=None, alias="adminToken"),
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    service: AppService = Depends(get_app_service),
    client: WecomClient = Depends(get_wecom_client),
):
    _verify_admin_token(x_admin_token or admin_token)
    jobs = service.list_media_retry_jobs({status})
    if media_id:
        jobs = [item for item in jobs if item["mediaId"] == media_id]
    retried = []
    failed = []
    for job in jobs:
        try:
            retried.append((await _retry_media_job(job, client, service)).model_dump())
        except WecomClientError as exc:
            failed_job = service.save_media_retry_failure(
                media_id=job["mediaId"],
                media_type=job["mediaType"],
                open_kfid=job.get("openKfid"),
                error_message=str(exc),
            )
            failed.append(failed_job.model_dump())
    return ApiResponse(data={"retried": retried, "failed": failed})


@router.get("/config-check", response_model=ApiResponse[dict])
def config_check(client: WecomClient = Depends(get_wecom_client)):
    missing = settings.missing_wecom_fields()
    return ApiResponse(
        success=not missing,
        message="wecom config ready" if not missing else "wecom config incomplete",
        data={
            "useMock": settings.wecom_use_mock,
            "callbackUrl": f"{settings.public_base_url.rstrip('/')}/api/wecom{KF_CALLBACK_PATH}" if settings.public_base_url else "",
            "missing": missing,
            "configured": client.is_configured(),
        },
    )


@router.get("/archive/config-check", response_model=ApiResponse[dict])
def archive_config_check():
    missing = settings.missing_wecom_archive_fields()
    public_key = _read_text_file(settings.wecom_archive_public_key_path)
    private_key_exists = bool(settings.wecom_archive_private_key_path and settings.wecom_archive_private_key_path.exists())
    sdk_exists = bool(settings.wecom_archive_sdk_lib_path and settings.wecom_archive_sdk_lib_path.exists())
    return ApiResponse(
        success=not missing,
        message="wecom archive config ready" if not missing else "wecom archive config incomplete",
        data={
            "enabled": settings.wecom_archive_enabled,
            "callbackUrl": f"{settings.public_base_url.rstrip('/')}/api/wecom{ARCHIVE_CALLBACK_PATH}" if settings.public_base_url else "",
            "callbackTokenConfigured": bool(settings.wecom_archive_callback_token or settings.wecom_callback_token),
            "callbackAesKeyConfigured": bool(settings.wecom_archive_encoding_aes_key or settings.wecom_encoding_aes_key),
            "corpIdConfigured": bool(settings.wecom_corp_id),
            "archiveSecretConfigured": bool(settings.wecom_archive_secret),
            "privateKeyPath": _mask_path(settings.wecom_archive_private_key_path),
            "privateKeyReadable": private_key_exists,
            "publicKeyPath": _mask_path(settings.wecom_archive_public_key_path),
            "publicKey": public_key,
            "sdkLibPath": _mask_path(settings.wecom_archive_sdk_lib_path),
            "sdkLibReadable": sdk_exists,
            "sdkConfigured": sdk_exists and bool(settings.wecom_archive_secret and settings.wecom_archive_private_key_path),
            "pullLimit": settings.wecom_archive_pull_limit,
            "workerEnabled": settings.wecom_archive_worker_enabled,
            "workerIntervalSeconds": settings.wecom_archive_worker_interval_seconds,
            "missing": missing,
            "docs": {
                "official": "https://developer.work.weixin.qq.com/document/path/91360",
                "local": "docs/stage2-docs/10-wecom-archive-config.md",
            },
        },
    )


@router.post("/archive/pull", response_model=ApiResponse[dict])
def pull_archive_messages(
    limit: int | None = Query(default=None, ge=1, le=1000),
    admin_token: str | None = Query(default=None, alias="adminToken"),
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    service: AppService = Depends(get_app_service),
    archive_client: WecomArchiveClient = Depends(get_wecom_archive_client),
):
    _verify_admin_token(x_admin_token or admin_token)
    return ApiResponse(
        message="archive messages pulled",
        data=service.pull_wecom_archive_messages(archive_client, limit or settings.wecom_archive_pull_limit),
    )


@router.post("/archive/process", response_model=ApiResponse[dict])
def process_archive_messages(
    limit: int = Query(default=100, ge=1, le=1000),
    admin_token: str | None = Query(default=None, alias="adminToken"),
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    service: AppService = Depends(get_app_service),
    archive_client: WecomArchiveClient = Depends(get_wecom_archive_client),
):
    _verify_admin_token(x_admin_token or admin_token)
    return ApiResponse(
        message="archive messages processed",
        data=service.process_wecom_archive_messages(limit=limit, archive_client=archive_client),
    )


@router.get("/archive/cursor", response_model=ApiResponse[dict | None])
def get_archive_cursor(
    admin_token: str | None = Query(default=None, alias="adminToken"),
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    service: AppService = Depends(get_app_service),
):
    _verify_admin_token(x_admin_token or admin_token)
    corp_id = settings.wecom_corp_id or "default"
    cursor = service.get_wecom_archive_cursor(corp_id)
    return ApiResponse(data=cursor.model_dump() if cursor else None)


@router.get("/archive/messages", response_model=ApiResponse[list[dict]])
def list_archive_messages(
    limit: int = Query(default=100, ge=1, le=500),
    admin_token: str | None = Query(default=None, alias="adminToken"),
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    service: AppService = Depends(get_app_service),
):
    _verify_admin_token(x_admin_token or admin_token)
    return ApiResponse(data=service.list_wecom_archive_messages(limit=limit))


@router.post("/archive/mock-messages", response_model=ApiResponse[dict])
def save_archive_mock_messages(
    payload: dict,
    admin_token: str | None = Query(default=None, alias="adminToken"),
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    service: AppService = Depends(get_app_service),
):
    _verify_admin_token(x_admin_token or admin_token)
    corp_id = payload.get("corpId") or settings.wecom_corp_id or "default"
    messages = payload.get("messages") or []
    if not isinstance(messages, list):
        raise HTTPException(status_code=400, detail="messages must be a list")
    return ApiResponse(data=service.save_wecom_archive_messages(corp_id, messages))


@router.post("/real-sync", response_model=ApiResponse[dict])
async def import_real_sync(
    max_pages: int = Query(default=10, ge=1, le=50),
    service: AppService = Depends(get_app_service),
    client: WecomClient = Depends(get_wecom_client),
    mock_service: WecomMockService = Depends(get_wecom_mock_service),
):
    result = await _run_real_sync(max_pages, service, client, mock_service)
    return ApiResponse(
        success=result.get("syncStatus") != "running",
        message="sync_msg task already running" if result.get("syncStatus") == "running" else "real sync_msg imported",
        data=result,
    )


async def _run_real_sync(
    max_pages: int,
    service: AppService,
    client: WecomClient,
    mock_service: WecomMockService,
) -> dict:
    open_kfid = settings.wecom_open_kfid or "default"
    source = "mock-real-sync-response" if settings.wecom_use_mock else "wecom-sync-msg"
    sync_lock = service.acquire_sync_lock(open_kfid, source, settings.wecom_sync_lock_timeout_seconds)
    if sync_lock is None:
        running = service.get_sync_cursor(open_kfid)
        return {
            "openKfid": open_kfid,
            "syncStatus": "running",
            "lockedAt": running.lockedAt if running else None,
            "lockTimeoutSeconds": settings.wecom_sync_lock_timeout_seconds,
        }

    cursor = sync_lock.cursor or settings.wecom_sync_cursor or None
    page_results = []
    imported_batch_ids: list[str] = []
    deduplicated_count = 0
    last_cursor = cursor
    last_has_more = sync_lock.hasMore
    try:
        for page in range(1, max_pages + 1):
            if settings.wecom_use_mock:
                sync_response = mock_service.load_real_sync_response()
            else:
                try:
                    sync_response = await client.sync_msg(cursor=cursor)
                except WecomClientError as exc:
                    raise HTTPException(status_code=502, detail=str(exc)) from exc

            synced_messages = service.normalize_sync_response(
                sync_response,
                fallback_open_kfid=settings.wecom_open_kfid or None,
            )
            media_url_by_id = {}
            if not settings.wecom_use_mock:
                media_url_by_id = await _download_sync_media(synced_messages, client, service)
            result = service.import_synced_messages(
                synced_messages,
                media_url_by_id=media_url_by_id,
                allow_media_storage_fallback=settings.wecom_use_mock,
                notification_channel="mock" if settings.wecom_use_mock else "wecom",
            )
            next_cursor = sync_response.get("next_cursor") or sync_response.get("cursor") or sync_response.get("token")
            has_more = _sync_response_has_more(sync_response.get("has_more"))
            sync_cursor = service.advance_sync_cursor(
                open_kfid=open_kfid,
                cursor=next_cursor,
                has_more=has_more,
                source=source,
                payload=sync_response,
            )
            page_results.append(
                {
                    "page": page,
                    "cursor": cursor,
                    "nextCursor": next_cursor,
                    "hasMore": has_more,
                    "importResult": result,
                }
            )
            imported_batch_ids.extend(result["importBatchIds"])
            deduplicated_count += result["deduplicatedCount"]
            cursor = next_cursor
            last_cursor = sync_cursor.cursor
            last_has_more = sync_cursor.hasMore
            if settings.wecom_use_mock or not has_more or not next_cursor:
                break
    except Exception as exc:
        service.release_sync_lock(open_kfid, sync_lock.lockToken or "", "failed", str(exc))
        raise
    service.release_sync_lock(open_kfid, sync_lock.lockToken or "", "success")

    return {
        "source": source,
        "openKfid": open_kfid,
        "syncStatus": "success",
        "pagesSynced": len(page_results),
        "nextCursor": last_cursor,
        "hasMore": last_has_more,
        "importResult": {
            "importBatchIds": imported_batch_ids,
            "deduplicatedCount": deduplicated_count,
        },
        "pageResults": page_results,
    }


@router.post("/real-sync/unlock", response_model=ApiResponse[dict])
def unlock_real_sync(
    open_kfid: str | None = Query(default=None),
    reason: str = Query(default="manual force release"),
    admin_token: str | None = Query(default=None, alias="adminToken"),
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    service: AppService = Depends(get_app_service),
):
    _verify_admin_token(x_admin_token or admin_token)
    target_open_kfid = open_kfid or settings.wecom_open_kfid or "default"
    cursor = service.force_release_sync_lock(target_open_kfid, reason)
    if not cursor:
        return ApiResponse(
            success=False,
            message="sync lock not found",
            data={"openKfid": target_open_kfid},
        )
    return ApiResponse(
        message="sync lock released",
        data={
            "openKfid": cursor.openKfid,
            "syncStatus": cursor.syncStatus,
            "lastError": cursor.lastError,
            "lockedAt": cursor.lockedAt,
        },
    )
