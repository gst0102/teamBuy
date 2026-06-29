from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_app_service
from app.schemas.common import ApiResponse
from app.schemas.showcases import ShowcaseEventRequest, ShowcasePageRequest, ShowcaseStatusRequest
from app.services.app_service import AppService


router = APIRouter(prefix="/api/showcases", tags=["showcases"])


@router.get("", response_model=ApiResponse[list[dict]])
def list_showcases(ownerUserId: str = Query(...), service: AppService = Depends(get_app_service)):
    return ApiResponse(data=service.list_showcases(ownerUserId))


@router.post("", response_model=ApiResponse[dict])
def create_showcase(payload: ShowcasePageRequest, service: AppService = Depends(get_app_service)):
    return ApiResponse(data=service.create_showcase(payload).model_dump())


@router.get("/public/{showcase_id}", response_model=ApiResponse[dict])
def get_public_showcase(showcase_id: str, service: AppService = Depends(get_app_service)):
    return ApiResponse(data=service.get_public_showcase(showcase_id))


@router.get("/{showcase_id}", response_model=ApiResponse[dict])
def get_showcase(showcase_id: str, ownerUserId: str = Query(...), service: AppService = Depends(get_app_service)):
    return ApiResponse(data=service.get_showcase_for_owner(showcase_id, ownerUserId).model_dump())


@router.get("/{showcase_id}/analytics", response_model=ApiResponse[dict])
def get_showcase_analytics(showcase_id: str, ownerUserId: str = Query(...), service: AppService = Depends(get_app_service)):
    return ApiResponse(data=service.get_showcase_analytics(showcase_id, ownerUserId))


@router.post("/{showcase_id}/events", response_model=ApiResponse[dict])
def record_showcase_event(showcase_id: str, payload: ShowcaseEventRequest, service: AppService = Depends(get_app_service)):
    return ApiResponse(data=service.record_showcase_event(showcase_id, payload))


@router.put("/{showcase_id}", response_model=ApiResponse[dict])
def update_showcase(showcase_id: str, payload: ShowcasePageRequest, service: AppService = Depends(get_app_service)):
    return ApiResponse(data=service.update_showcase(showcase_id, payload).model_dump())


@router.post("/{showcase_id}/publish", response_model=ApiResponse[dict])
def publish_showcase(showcase_id: str, payload: ShowcaseStatusRequest, service: AppService = Depends(get_app_service)):
    return ApiResponse(data=service.publish_showcase(showcase_id, payload.ownerUserId).model_dump())


@router.post("/{showcase_id}/archive", response_model=ApiResponse[dict])
def archive_showcase(showcase_id: str, payload: ShowcaseStatusRequest, service: AppService = Depends(get_app_service)):
    return ApiResponse(data=service.archive_showcase(showcase_id, payload.ownerUserId).model_dump())


@router.delete("/{showcase_id}", response_model=ApiResponse[dict])
def delete_showcase(showcase_id: str, ownerUserId: str = Query(...), service: AppService = Depends(get_app_service)):
    return ApiResponse(data=service.delete_showcase(showcase_id, ownerUserId))


@router.post("/{showcase_id}/delete", response_model=ApiResponse[dict])
def delete_showcase_by_post(showcase_id: str, payload: ShowcaseStatusRequest, service: AppService = Depends(get_app_service)):
    return ApiResponse(data=service.delete_showcase(showcase_id, payload.ownerUserId))
