from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_app_service
from app.schemas.cards import (
    CardUpdateRequest,
    CreateRelayRequest,
    DuplicateCardRequest,
    FollowUpRelayRequest,
    PublishCardRequest,
    RecordViewRequest,
)
from app.schemas.common import ApiResponse
from app.services.app_service import AppService


router = APIRouter(prefix="/api", tags=["cards"])


@router.get("/cards", response_model=ApiResponse[list[dict]])
def list_cards(
    ownerUserId: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    categoryId: str | None = Query(default=None),
    service: AppService = Depends(get_app_service),
):
    return ApiResponse(data=service.list_cards(owner_user_id=ownerUserId, keyword=keyword, category_id=categoryId))


@router.get("/cards/{card_id}", response_model=ApiResponse[dict])
def get_card(card_id: str, service: AppService = Depends(get_app_service)):
    return ApiResponse(data=service.get_card(card_id).model_dump())


@router.put("/cards/{card_id}", response_model=ApiResponse[dict])
def update_card(card_id: str, payload: CardUpdateRequest, service: AppService = Depends(get_app_service)):
    return ApiResponse(data=service.update_card(card_id, payload).model_dump())


@router.post("/cards/{card_id}/publish", response_model=ApiResponse[dict])
def publish_card(card_id: str, payload: PublishCardRequest, service: AppService = Depends(get_app_service)):
    return ApiResponse(data=service.publish_card(card_id, payload.userId).model_dump())


@router.post("/cards/{card_id}/duplicate", response_model=ApiResponse[dict])
def duplicate_card(card_id: str, payload: DuplicateCardRequest, service: AppService = Depends(get_app_service)):
    return ApiResponse(data=service.duplicate_card(card_id, payload.userId).model_dump())


@router.post("/cards/{card_id}/view", response_model=ApiResponse[dict])
def record_view(card_id: str, payload: RecordViewRequest, service: AppService = Depends(get_app_service)):
    return ApiResponse(data=service.record_view(card_id, payload).model_dump())


@router.get("/cards/{card_id}/stats", response_model=ApiResponse[dict])
def get_stats(card_id: str, requesterUserId: str | None = Query(default=None), service: AppService = Depends(get_app_service)):
    return ApiResponse(data=service.get_card_stats(card_id, requester_user_id=requesterUserId))


@router.post("/cards/{card_id}/relay", response_model=ApiResponse[dict])
def create_relay(card_id: str, payload: CreateRelayRequest, service: AppService = Depends(get_app_service)):
    return ApiResponse(data=service.create_relay(card_id, payload).model_dump())


@router.get("/cards/{card_id}/relays", response_model=ApiResponse[list[dict]])
def list_relays(card_id: str, requesterUserId: str = Query(...), service: AppService = Depends(get_app_service)):
    return ApiResponse(data=service.list_relays(card_id, requesterUserId))


@router.delete("/relays/{relay_id}", response_model=ApiResponse[dict])
def delete_relay(relay_id: str, operatorUserId: str = Query(...), service: AppService = Depends(get_app_service)):
    return ApiResponse(data=service.delete_relay(relay_id, operatorUserId).model_dump())


@router.post("/relays/{relay_id}/follow-up", response_model=ApiResponse[dict])
def mark_followed(relay_id: str, payload: FollowUpRelayRequest, service: AppService = Depends(get_app_service)):
    return ApiResponse(data=service.mark_followed(relay_id, payload.operatorUserId).model_dump())

