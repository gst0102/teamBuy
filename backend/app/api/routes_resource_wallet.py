from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from app.api.dependencies import get_app_service
from app.core.config import settings
from app.schemas.common import ApiResponse
from app.schemas.resource_wallet import ResourceWalletAdjustRequest, ResourceWalletConsumeRequest
from app.services.app_service import AppService


router = APIRouter(tags=["resource-wallet"])


def _verify_admin_token(provided_token: str | None) -> None:
    if not settings.admin_token:
        raise HTTPException(status_code=403, detail="WECOM_ADMIN_TOKEN is not configured")
    if provided_token != settings.admin_token:
        raise HTTPException(status_code=403, detail="admin token verification failed")


@router.get("/api/resource-wallet/me", response_model=ApiResponse[dict])
def get_resource_wallet(
    ownerUserId: str = Query(...),
    service: AppService = Depends(get_app_service),
):
    return ApiResponse(data=service.get_resource_wallet(ownerUserId))


@router.get("/api/resource-wallet/ledger", response_model=ApiResponse[list[dict]])
def list_resource_wallet_ledgers(
    ownerUserId: str = Query(...),
    limit: int = Query(default=100, ge=1, le=200),
    service: AppService = Depends(get_app_service),
):
    return ApiResponse(data=service.list_resource_point_ledgers(ownerUserId, limit=limit))


@router.post("/api/resource-wallet/consume", response_model=ApiResponse[dict])
def consume_resource_wallet(
    payload: ResourceWalletConsumeRequest,
    service: AppService = Depends(get_app_service),
):
    result = service.consume_resource_points(
        owner_user_id=payload.ownerUserId,
        action_type=payload.actionType,
        target_type=payload.targetType,
        target_id=payload.targetId,
        points_cost=payload.pointsCost,
        reason=payload.reason,
        quota_type=payload.freeQuotaType,
        free_quota_limit=payload.freeQuotaLimit,
        period_key=payload.periodKey,
        metadata=payload.metadata,
    )
    return ApiResponse(data=result)


@router.post("/api/ops/resource-wallet/adjust", response_model=ApiResponse[dict])
def adjust_resource_wallet(
    payload: ResourceWalletAdjustRequest,
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    service: AppService = Depends(get_app_service),
):
    _verify_admin_token(x_admin_token)
    return ApiResponse(
        data=service.adjust_resource_wallet(
            owner_user_id=payload.userId,
            points_delta=payload.pointsDelta,
            reason=payload.reason,
            operator_id=payload.operatorId,
        )
    )
