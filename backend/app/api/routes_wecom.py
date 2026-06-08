from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request

from app.api.dependencies import get_app_service, get_wecom_client, get_wecom_mock_service
from app.core.config import settings
from app.schemas.common import ApiResponse
from app.schemas.imports import MockImportRequest
from app.services.app_service import AppService
from app.services.wecom_client import WecomClient, WecomClientError
from app.services.wecom_crypto import WecomCryptoError, decrypt_aes_message, verify_signature
from app.services.wecom_event_service import parse_callback_body
from app.services.wecom_mock_service import WecomMockService


router = APIRouter(prefix="/api/wecom", tags=["wecom"])


def _sync_response_has_more(value) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes"}
    return bool(value)


def _verify_admin_token(provided_token: str | None) -> None:
    if not settings.admin_token:
        raise HTTPException(status_code=403, detail="WECOM_ADMIN_TOKEN is not configured")
    if provided_token != settings.admin_token:
        raise HTTPException(status_code=403, detail="admin token verification failed")


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
        try:
            downloaded = await client.download_media(media_id)
            media_urls[media_id] = service.media_storage_service.store_bytes(
                media_id=media_id,
                media_type=msg_type,
                content=downloaded.content,
                content_type=downloaded.content_type,
                filename=downloaded.filename,
            )
        except WecomClientError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
    return media_urls


@router.get("/callback")
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
                return decrypt_aes_message(settings.wecom_encoding_aes_key, echostr, settings.wecom_corp_id)
            except WecomCryptoError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
    return echostr or "verified"


@router.post("/callback", response_model=ApiResponse[dict])
async def receive_callback(request: Request, service: AppService = Depends(get_app_service)):
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
    fixture = payload.get("fixture", "note")
    external_user_id = payload.get("externalUserId") or payload.get("ExternalUserID") or "external_demo"
    conversation_id = payload.get("conversationId") or payload.get("Token") or "conv_demo"
    result = service.trigger_mock_import(external_user_id, conversation_id, fixture)
    return ApiResponse(message="callback received", data=result)


@router.post("/mock-sync", response_model=ApiResponse[dict])
def mock_sync(payload: MockImportRequest, service: AppService = Depends(get_app_service)):
    result = service.trigger_mock_import(payload.externalUserId, payload.conversationId, payload.fixture)
    return ApiResponse(data=result, message="mock import completed")


@router.get("/notifications", response_model=ApiResponse[list[dict]])
def list_notifications(service: AppService = Depends(get_app_service)):
    return ApiResponse(data=service.list_import_notifications())


@router.get("/config-check", response_model=ApiResponse[dict])
def config_check(client: WecomClient = Depends(get_wecom_client)):
    missing = settings.missing_wecom_fields()
    return ApiResponse(
        success=not missing,
        message="wecom config ready" if not missing else "wecom config incomplete",
        data={
            "useMock": settings.wecom_use_mock,
            "callbackUrl": f"{settings.public_base_url.rstrip('/')}/api/wecom/callback" if settings.public_base_url else "",
            "missing": missing,
            "configured": client.is_configured(),
        },
    )


@router.post("/real-sync", response_model=ApiResponse[dict])
async def import_real_sync(
    max_pages: int = Query(default=10, ge=1, le=50),
    service: AppService = Depends(get_app_service),
    client: WecomClient = Depends(get_wecom_client),
    mock_service: WecomMockService = Depends(get_wecom_mock_service),
):
    open_kfid = settings.wecom_open_kfid or "default"
    source = "mock-real-sync-response" if settings.wecom_use_mock else "wecom-sync-msg"
    sync_lock = service.acquire_sync_lock(open_kfid, source, settings.wecom_sync_lock_timeout_seconds)
    if sync_lock is None:
        running = service.get_sync_cursor(open_kfid)
        return ApiResponse(
            success=False,
            message="sync_msg task already running",
            data={
                "openKfid": open_kfid,
                "syncStatus": "running",
                "lockedAt": running.lockedAt if running else None,
                "lockTimeoutSeconds": settings.wecom_sync_lock_timeout_seconds,
            },
        )

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
            result = service.import_synced_messages(synced_messages, media_url_by_id=media_url_by_id)
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

    return ApiResponse(
        message="real sync_msg imported",
        data={
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
        },
    )


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
