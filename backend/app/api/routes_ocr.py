from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.api.dependencies import get_app_service
from app.schemas.common import ApiResponse
from app.services.app_service import AppService


router = APIRouter(prefix="/api/ocr", tags=["ocr"])


@router.post("/image-to-note", response_model=ApiResponse[dict])
async def image_to_note(
    ownerUserId: str = Form(...),
    file: UploadFile = File(...),
    service: AppService = Depends(get_app_service),
):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="请上传图片文件")
    content = await file.read()
    data = service.create_ocr_note_from_image(
        owner_user_id=ownerUserId,
        content=content,
        filename=file.filename,
        content_type=file.content_type,
    )
    return ApiResponse(data=data, message="ocr note created")
