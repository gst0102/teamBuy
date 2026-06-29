from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.api.dependencies import get_app_service
from app.schemas.common import ApiResponse
from app.services.app_service import AppService


router = APIRouter(prefix="/api/orders", tags=["orders"])


class OrderStatusUpdateRequest(BaseModel):
    userId: str
    status: str


@router.get("", response_model=ApiResponse[dict])
def list_orders(
    userId: str = Query(...),
    role: str = Query(...),
    noteId: str | None = Query(default=None),
    service: AppService = Depends(get_app_service),
):
    return ApiResponse(data=service.list_orders(userId, role, noteId))


@router.get("/{order_id}", response_model=ApiResponse[dict])
def get_order(order_id: str, userId: str = Query(...), service: AppService = Depends(get_app_service)):
    return ApiResponse(data=service.get_order(order_id, userId))


@router.patch("/{order_id}/status", response_model=ApiResponse[dict])
def update_order_status(order_id: str, payload: OrderStatusUpdateRequest, service: AppService = Depends(get_app_service)):
    return ApiResponse(data=service.update_order_status(order_id, payload.userId, payload.status))
