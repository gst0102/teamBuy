from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile

from app.api.dependencies import get_app_service, get_sync_task_queue
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
from app.services.sync_task_queue import SyncTaskQueue
from app.services.helpers import new_id
from app.services.media_storage_service import MediaStorageService
from app.api.upload_utils import read_upload_with_limit


router = APIRouter(prefix="/api", tags=["cards"])


@router.get("/cards", response_model=ApiResponse[list[dict]])
def list_cards(
    ownerUserId: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    categoryId: str | None = Query(default=None),
    limit: int | None = Query(default=None, ge=1, le=50),
    offset: int = Query(default=0, ge=0, le=10000),
    service: AppService = Depends(get_app_service),
):
    return ApiResponse(data=service.list_cards(owner_user_id=ownerUserId, keyword=keyword, category_id=categoryId, limit=limit, offset=offset))


@router.get("/categories", response_model=ApiResponse[list[dict]])
def list_categories(ownerUserId: str | None = Query(default=None), service: AppService = Depends(get_app_service)):
    return ApiResponse(data=service.list_categories(owner_user_id=ownerUserId))


@router.get("/view-history", response_model=ApiResponse[list[dict]])
def list_view_history(
    request: Request,
    userId: str = Query(...),
    limit: int = Query(default=30, ge=1, le=50),
    service: AppService = Depends(get_app_service),
):
    authenticated_user_id = getattr(request.state, "authenticated_user_id", None)
    if request.app.state.production_auth_enabled and authenticated_user_id != userId:
        raise HTTPException(status_code=403, detail="只能查看自己的浏览记录")
    return ApiResponse(data=service.list_view_history(userId, limit=limit))


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
    normalized_type = "pdf" if mediaType in {"file", "pdf"} else mediaType if mediaType in {"image", "video"} else "image"
    upload_limits = {
        "image": (settings.media_max_image_bytes, "图片不能超过10MB"),
        "video": (settings.media_max_video_bytes, "视频不能超过50MB"),
        "pdf": (settings.media_max_pdf_bytes, "PDF不能超过20MB"),
    }
    max_bytes, too_large_detail = upload_limits[normalized_type]
    content = await read_upload_with_limit(file, max_bytes, too_large_detail)
    if normalized_type == "pdf":
        filename = (file.filename or "").lower()
        content_type = (file.content_type or "").split(";", 1)[0].lower()
        if not filename.endswith(".pdf") or content_type != "application/pdf" or not content.startswith(b"%PDF-"):
            raise HTTPException(status_code=400, detail="请上传真实PDF文件")
        stored_type = "pdf"
    else:
        stored_type = normalized_type
    storage = service.media_storage_service
    if storage.storage_mode == "mock":
        storage = MediaStorageService(
            storage_mode="local",
            storage_dir=settings.media_storage_dir,
            public_url_prefix=settings.media_public_url_prefix,
            public_base_url=settings.public_base_url,
        )
    attachment_id = new_id("att")
    stored_url = await asyncio.to_thread(
        service.process_and_store_media,
        media_id=new_id("manual_asset"),
        media_type=stored_type,
        content=content,
        content_type=file.content_type,
        filename=file.filename,
        owner_user_id=ownerUserId or None,
        ref_type="manual_upload",
        ref_id=attachment_id,
        usage="attachment",
        storage_service=storage,
    )
    asset = await asyncio.to_thread(service.repo.get_media_asset_by_url, stored_url)
    return ApiResponse(
        data={
            "id": attachment_id,
            "url": stored_url,
            "name": file.filename or "upload",
            "mediaType": normalized_type,
            "type": normalized_type,
            "contentType": asset.contentType if asset else file.content_type,
            "mimeType": asset.contentType if asset else file.content_type,
            "sizeBytes": asset.storedSize if asset else len(content),
            "sortOrder": 0,
            "source": "upload",
            "status": "ready",
            "originalSize": asset.originalSize if asset else len(content),
            "storedSize": asset.storedSize if asset else len(content),
            "compressed": bool(asset and asset.storedSize < asset.originalSize),
            "originalSha256": asset.originalSha256 if asset else "",
            "storageSha256": asset.storageSha256 if asset else "",
        }
    )


@router.post("/uploads/share-snapshot", response_model=ApiResponse[dict])
async def upload_share_snapshot(
    ownerUserId: str = Form(...),
    file: UploadFile = File(...),
    service: AppService = Depends(get_app_service),
):
    if not service.repo.get_user(ownerUserId):
        raise HTTPException(status_code=404, detail="用户不存在")
    content = await read_upload_with_limit(
        file,
        settings.media_max_share_snapshot_bytes,
        "分享图不能超过5MB",
    )
    storage = service.media_storage_service
    if storage.storage_mode == "mock":
        storage = MediaStorageService(
            storage_mode="local",
            storage_dir=settings.media_storage_dir,
            public_url_prefix=settings.media_public_url_prefix,
            public_base_url=settings.public_base_url,
        )
    attachment_id = new_id("share_snapshot")
    try:
        stored_url = await asyncio.to_thread(
            service.process_and_store_media,
            media_id=attachment_id,
            media_type="image",
            content=content,
            content_type=file.content_type,
            filename=file.filename or "share-snapshot.jpg",
            owner_user_id=ownerUserId,
            ref_type="share_snapshot",
            ref_id=attachment_id,
            usage="share_snapshot",
            storage_service=storage,
            preserve_share_format=True,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    asset = await asyncio.to_thread(service.repo.get_media_asset_by_url, stored_url)
    return ApiResponse(
        data={
            "id": attachment_id,
            "url": stored_url,
            "name": file.filename or "share-snapshot.jpg",
            "mediaType": "image",
            "type": "image",
            "contentType": asset.contentType if asset else "image/jpeg",
            "mimeType": asset.contentType if asset else "image/jpeg",
            "sizeBytes": asset.storedSize if asset else len(content),
            "sortOrder": 0,
            "source": "share_snapshot",
            "status": "ready",
            "originalSize": asset.originalSize if asset else len(content),
            "storedSize": asset.storedSize if asset else len(content),
            "compressed": bool(asset and asset.storedSize < asset.originalSize),
            "originalSha256": asset.originalSha256 if asset else "",
            "storageSha256": asset.storageSha256 if asset else "",
        }
    )


@router.get("/cards/{card_id}", response_model=ApiResponse[dict])
def get_card(card_id: str, service: AppService = Depends(get_app_service)):
    return ApiResponse(data=service.get_card_detail(card_id))


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
def record_view(
    card_id: str,
    payload: RecordViewRequest,
    request: Request,
    service: AppService = Depends(get_app_service),
    queue: SyncTaskQueue = Depends(get_sync_task_queue),
):
    event = service.record_view(card_id, payload, authenticated_user_id=getattr(request.state, "authenticated_user_id", None))
    notification = service.queue_card_view_notification(card_id, event, queue)
    return ApiResponse(data={**event.model_dump(), "notification": notification})


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
    service.require_customer_intelligence(ownerUserId)
    return ApiResponse(data=service.list_lead_reminders(ownerUserId, status))


@router.get("/lead-reminders/{reminder_id}", response_model=ApiResponse[dict])
def get_lead_reminder(
    reminder_id: str,
    ownerUserId: str = Query(...),
    service: AppService = Depends(get_app_service),
):
    data = service.get_lead_reminder_detail(reminder_id, ownerUserId)
    service.require_customer_intelligence(ownerUserId)
    return ApiResponse(data=data)


@router.post("/lead-reminders", response_model=ApiResponse[dict])
def upsert_lead_reminder(payload: LeadReminderUpsertRequest, service: AppService = Depends(get_app_service)):
    service.require_customer_intelligence(payload.ownerUserId)
    return ApiResponse(data=service.upsert_lead_reminder(payload).model_dump())


@router.put("/lead-reminders/{reminder_id}", response_model=ApiResponse[dict])
def update_lead_reminder(
    reminder_id: str,
    payload: LeadReminderUpdateRequest,
    service: AppService = Depends(get_app_service),
):
    service.get_lead_reminder_detail(reminder_id, payload.ownerUserId)
    service.require_customer_intelligence(payload.ownerUserId)
    return ApiResponse(data=service.update_lead_reminder(reminder_id, payload).model_dump())


@router.delete("/lead-reminders/{reminder_id}", response_model=ApiResponse[dict])
def delete_lead_reminder(
    reminder_id: str,
    ownerUserId: str = Query(...),
    service: AppService = Depends(get_app_service),
):
    service.get_lead_reminder_detail(reminder_id, ownerUserId)
    service.require_customer_intelligence(ownerUserId)
    return ApiResponse(data=service.delete_lead_reminder(reminder_id, ownerUserId))
