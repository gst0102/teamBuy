from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from app.api.dependencies import get_app_service, get_sync_task_queue
from app.schemas.common import ApiResponse
from app.services.app_service import AppService
from app.services.sync_task_queue import SyncTaskQueue


router = APIRouter(prefix="/api/ocr", tags=["ocr"])


class OcrRecognizeRequest(BaseModel):
    ownerUserId: str


@router.post("/images", response_model=ApiResponse[dict])
async def save_image_note(
    ownerUserId: str = Form(...),
    file: UploadFile = File(...),
    service: AppService = Depends(get_app_service),
    sync_task_queue: SyncTaskQueue = Depends(get_sync_task_queue),
):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="请上传图片文件")
    content = await file.read()
    data = service.create_image_note_from_upload(
        owner_user_id=ownerUserId,
        content=content,
        filename=file.filename,
        content_type=file.content_type,
    )
    task = sync_task_queue.enqueue(
        "ocr-recognize-note",
        {"noteId": data["note"]["id"], "ownerUserId": ownerUserId},
        max_attempts=2,
    )
    queued = service.mark_ocr_note_queued(data["note"]["id"], ownerUserId, task.id)
    queued["syncTask"] = task.model_dump()
    return ApiResponse(data=queued, message="image note queued for ocr")


@router.post("/notes/{note_id}/recognize", response_model=ApiResponse[dict])
async def recognize_note_image(
    note_id: str,
    payload: OcrRecognizeRequest,
    service: AppService = Depends(get_app_service),
    sync_task_queue: SyncTaskQueue = Depends(get_sync_task_queue),
):
    task = sync_task_queue.enqueue(
        "ocr-recognize-note",
        {"noteId": note_id, "ownerUserId": payload.ownerUserId},
        max_attempts=2,
    )
    data = service.mark_ocr_note_queued(note_id, payload.ownerUserId, task.id)
    data["syncTask"] = task.model_dump()
    return ApiResponse(data=data, message="ocr recognition queued")


@router.post("/image-to-note", response_model=ApiResponse[dict])
async def image_to_note(
    ownerUserId: str = Form(...),
    file: UploadFile = File(...),
    service: AppService = Depends(get_app_service),
    sync_task_queue: SyncTaskQueue = Depends(get_sync_task_queue),
):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="请上传图片文件")
    content = await file.read()
    data = service.create_image_note_from_upload(
        owner_user_id=ownerUserId,
        content=content,
        filename=file.filename,
        content_type=file.content_type,
    )
    task = sync_task_queue.enqueue(
        "ocr-recognize-note",
        {"noteId": data["note"]["id"], "ownerUserId": ownerUserId},
        max_attempts=2,
    )
    queued = service.mark_ocr_note_queued(data["note"]["id"], ownerUserId, task.id)
    queued["syncTask"] = task.model_dump()
    return ApiResponse(data=queued, message="ocr note queued")
