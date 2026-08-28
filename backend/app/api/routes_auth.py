from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.api.dependencies import get_app_service
from app.schemas.auth import H5TicketRequest, MockLoginRequest, UserProfileUpdateRequest, WechatLoginRequest, WecomBindCardRequest, WecomBindIntentRequest
from app.schemas.common import ApiResponse
from app.services.app_service import AppService


router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/mock-login", response_model=ApiResponse[dict])
def mock_login(payload: MockLoginRequest, service: AppService = Depends(get_app_service)):
    user = service.mock_login(payload)
    return ApiResponse(data=service.login_payload(user))


@router.post("/wechat-login", response_model=ApiResponse[dict])
def wechat_login(payload: WechatLoginRequest, service: AppService = Depends(get_app_service)):
    user = service.wechat_login(payload)
    return ApiResponse(data=service.login_payload(user))


@router.patch("/users/{user_id}/profile", response_model=ApiResponse[dict])
def update_user_profile(
    user_id: str,
    payload: UserProfileUpdateRequest,
    request: Request,
    service: AppService = Depends(get_app_service),
):
    if request.app.state.production_auth_enabled and request.state.authenticated_user_id != user_id:
        raise HTTPException(status_code=403, detail="只能修改自己的资料")
    user = service.update_user_profile(user_id, payload)
    return ApiResponse(data=service.login_payload(user))


@router.post("/wecom-bind-intent", response_model=ApiResponse[dict])
def create_wecom_bind_intent(
    payload: WecomBindIntentRequest,
    request: Request,
    service: AppService = Depends(get_app_service),
):
    if request.app.state.production_auth_enabled and request.state.authenticated_user_id != payload.userId:
        raise HTTPException(status_code=403, detail="只能绑定自己的账号")
    return ApiResponse(data=service.create_wecom_bind_intent(payload.userId))


@router.get("/wecom-bind-status", response_model=ApiResponse[dict])
def get_wecom_bind_status(
    request: Request,
    user_id: str = Query(..., alias="userId"),
    service: AppService = Depends(get_app_service),
):
    if request.app.state.production_auth_enabled and request.state.authenticated_user_id != user_id:
        raise HTTPException(status_code=403, detail="只能查看自己的绑定状态")
    return ApiResponse(data=service.get_wecom_bind_status(user_id))


@router.post("/wecom-bind-card", response_model=ApiResponse[dict])
def bind_wecom_card(
    payload: WecomBindCardRequest,
    request: Request,
    service: AppService = Depends(get_app_service),
):
    if request.app.state.production_auth_enabled and request.state.authenticated_user_id != payload.userId:
        raise HTTPException(status_code=403, detail="只能绑定自己的账号")
    return ApiResponse(data=service.bind_wecom_contact_card(payload.token, payload.userId))


@router.post("/h5-ticket", response_model=ApiResponse[dict])
def create_h5_ticket(
    payload: H5TicketRequest,
    request: Request,
    service: AppService = Depends(get_app_service),
):
    if request.app.state.production_auth_enabled and request.state.authenticated_user_id != payload.userId:
        raise HTTPException(status_code=403, detail="只能为自己的账号创建登录票据")
    return ApiResponse(data=service.create_h5_session_ticket(payload.userId, payload.entry))


@router.get("/h5-session", response_model=ApiResponse[dict])
def get_h5_session(
    ticket: str = Query(...),
    service: AppService = Depends(get_app_service),
):
    return ApiResponse(data=service.verify_h5_session_ticket(ticket))
