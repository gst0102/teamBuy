from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile

from app.api.dependencies import get_app_service
from app.core.config import settings
from app.schemas.categories import CategoryCreateRequest
from app.schemas.cards import (
    CardCreateRequest,
    CardUpdateRequest,
    CreateRelayRequest,
    DuplicateCardRequest,
    FollowUpRelayRequest,
    LeadReminderUpdateRequest,
    LeadReminderUpsertRequest,
    PublishCardRequest,
    RecordViewRequest,
)
from app.schemas.common import ApiResponse
from app.services.app_service import AppService
from app.services.helpers import new_id
from app.services.media_storage_service import MediaStorageService


router = APIRouter(prefix="/api", tags=["cards"])


@router.get("/cards", response_model=ApiResponse[list[dict]])
def list_cards(
    ownerUserId: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    categoryId: str | None = Query(default=None),
    service: AppService = Depends(get_app_service),
):
    return ApiResponse(data=service.list_cards(owner_user_id=ownerUserId, keyword=keyword, category_id=categoryId))


@router.get("/categories", response_model=ApiResponse[list[dict]])
def list_categories(ownerUserId: str | None = Query(default=None), service: AppService = Depends(get_app_service)):
    return ApiResponse(data=service.list_categories(owner_user_id=ownerUserId))


@router.post("/categories", response_model=ApiResponse[dict])
def create_category(payload: CategoryCreateRequest, service: AppService = Depends(get_app_service)):
    return ApiResponse(data=service.create_category(payload).model_dump())


@router.delete("/categories/{category_id}", response_model=ApiResponse[dict])
def delete_category(category_id: str, ownerUserId: str = Query(...), service: AppService = Depends(get_app_service)):
    return ApiResponse(data=service.delete_category(category_id, ownerUserId))


@router.post("/cards", response_model=ApiResponse[dict])
def create_card(payload: CardCreateRequest, service: AppService = Depends(get_app_service)):
    return ApiResponse(data=service.create_card(payload).model_dump())


@router.post("/uploads/asset", response_model=ApiResponse[dict])
async def upload_asset(
    ownerUserId: str = Form(default=""),
    mediaType: str = Form(default="image"),
    file: UploadFile = File(...),
    service: AppService = Depends(get_app_service),
):
    if ownerUserId and not service.repo.get_user(ownerUserId):
        raise HTTPException(status_code=404, detail="用户不存在")
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="上传文件不能为空")
    normalized_type = mediaType if mediaType in {"image", "video", "file"} else "image"
    stored_type = "video" if normalized_type == "video" else "image"
    storage = service.media_storage_service
    if storage.storage_mode == "mock":
        storage = MediaStorageService(
            storage_mode="local",
            storage_dir=settings.media_storage_dir,
            public_url_prefix=settings.media_public_url_prefix,
        )
    processed = service.media_processing_service.process_upload(
        media_type=stored_type,
        content=content,
        content_type=file.content_type,
        filename=file.filename,
    )
    stored_url = storage.store_bytes(
        media_id=new_id("manual_asset"),
        media_type=stored_type,
        content=processed.content,
        content_type=processed.content_type,
        filename=processed.filename,
    )
    return ApiResponse(
        data={
            "url": stored_url,
            "name": file.filename or "upload",
            "mediaType": normalized_type,
            "contentType": processed.content_type,
            "originalSize": processed.original_size,
            "storedSize": processed.stored_size,
            "compressed": processed.compressed,
        }
    )


@router.get("/cards/{card_id}", response_model=ApiResponse[dict])
def get_card(card_id: str, service: AppService = Depends(get_app_service)):
    return ApiResponse(data=service.get_card(card_id).model_dump())


@router.put("/cards/{card_id}", response_model=ApiResponse[dict])
def update_card(card_id: str, payload: CardUpdateRequest, service: AppService = Depends(get_app_service)):
    return ApiResponse(data=service.update_card(card_id, payload).model_dump())


@router.delete("/cards/{card_id}", response_model=ApiResponse[dict])
def delete_card(card_id: str, ownerUserId: str = Query(...), service: AppService = Depends(get_app_service)):
    return ApiResponse(data=service.delete_card(card_id, ownerUserId))


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


@router.get("/lead-reminders", response_model=ApiResponse[list[dict]])
def list_lead_reminders(
    ownerUserId: str = Query(...),
    status: str | None = Query(default=None),
    service: AppService = Depends(get_app_service),
):
    return ApiResponse(data=service.list_lead_reminders(ownerUserId, status))


@router.post("/lead-reminders", response_model=ApiResponse[dict])
def upsert_lead_reminder(payload: LeadReminderUpsertRequest, service: AppService = Depends(get_app_service)):
    return ApiResponse(data=service.upsert_lead_reminder(payload).model_dump())


@router.put("/lead-reminders/{reminder_id}", response_model=ApiResponse[dict])
def update_lead_reminder(
    reminder_id: str,
    payload: LeadReminderUpdateRequest,
    service: AppService = Depends(get_app_service),
):
    return ApiResponse(data=service.update_lead_reminder(reminder_id, payload).model_dump())


@router.delete("/lead-reminders/{reminder_id}", response_model=ApiResponse[dict])
def delete_lead_reminder(
    reminder_id: str,
    ownerUserId: str = Query(...),
    service: AppService = Depends(get_app_service),
):
    return ApiResponse(data=service.delete_lead_reminder(reminder_id, ownerUserId))
