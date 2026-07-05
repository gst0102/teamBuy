from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_app_service
from app.schemas.auth import H5TicketRequest, MockLoginRequest, UserProfileUpdateRequest, WechatLoginRequest, WecomBindIntentRequest
from app.schemas.common import ApiResponse
from app.services.app_service import AppService


router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/mock-login", response_model=ApiResponse[dict])
def mock_login(payload: MockLoginRequest, service: AppService = Depends(get_app_service)):
    user = service.mock_login(payload)
    return ApiResponse(data=user.model_dump())


@router.post("/wechat-login", response_model=ApiResponse[dict])
def wechat_login(payload: WechatLoginRequest, service: AppService = Depends(get_app_service)):
    user = service.wechat_login(payload)
    return ApiResponse(data=user.model_dump())


@router.patch("/users/{user_id}/profile", response_model=ApiResponse[dict])
def update_user_profile(
    user_id: str,
    payload: UserProfileUpdateRequest,
    service: AppService = Depends(get_app_service),
):
    user = service.update_user_profile(user_id, payload)
    return ApiResponse(data=user.model_dump())


@router.post("/wecom-bind-intent", response_model=ApiResponse[dict])
def create_wecom_bind_intent(
    payload: WecomBindIntentRequest,
    service: AppService = Depends(get_app_service),
):
    return ApiResponse(data=service.create_wecom_bind_intent(payload.userId))


@router.post("/h5-ticket", response_model=ApiResponse[dict])
def create_h5_ticket(
    payload: H5TicketRequest,
    service: AppService = Depends(get_app_service),
):
    return ApiResponse(data=service.create_h5_session_ticket(payload.userId, payload.entry))


@router.get("/h5-session", response_model=ApiResponse[dict])
def get_h5_session(
    ticket: str = Query(...),
    service: AppService = Depends(get_app_service),
):
    return ApiResponse(data=service.verify_h5_session_ticket(ticket))
