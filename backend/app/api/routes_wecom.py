from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.api.dependencies import get_app_service, get_wecom_client
from app.core.config import settings
from app.schemas.common import ApiResponse
from app.schemas.imports import MockImportRequest
from app.services.app_service import AppService
from app.services.wecom_client import WecomClient, WecomClientError
from app.services.wecom_crypto import WecomCryptoError, decrypt_aes_message, verify_signature
from app.services.wecom_event_service import parse_callback_body


router = APIRouter(prefix="/api/wecom", tags=["wecom"])


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
async def real_sync(client: WecomClient = Depends(get_wecom_client)):
    if settings.wecom_use_mock:
        raise HTTPException(status_code=400, detail="WECOM_USE_MOCK=true，当前不会调用真实 sync_msg")
    try:
        data = await client.sync_msg(cursor=settings.wecom_sync_cursor or None)
    except WecomClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return ApiResponse(message="real sync_msg completed", data=data)
