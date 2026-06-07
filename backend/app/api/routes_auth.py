from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.dependencies import get_app_service
from app.schemas.auth import MockLoginRequest
from app.schemas.common import ApiResponse
from app.services.app_service import AppService


router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/mock-login", response_model=ApiResponse[dict])
def mock_login(payload: MockLoginRequest, service: AppService = Depends(get_app_service)):
    user = service.mock_login(payload)
    return ApiResponse(data=user.model_dump())

