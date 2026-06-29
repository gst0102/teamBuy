from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_app_service
from app.schemas.common import ApiResponse
from app.services.app_service import AppService


router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/business", response_model=ApiResponse[dict])
def get_business_dashboard(
    ownerUserId: str = Query(...),
    requesterUserId: str | None = Query(default=None),
    mode: str | None = Query(default=None),
    service: AppService = Depends(get_app_service),
):
    return ApiResponse(data=service.get_business_dashboard(ownerUserId, requesterUserId, mode))
