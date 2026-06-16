from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_app_service
from app.schemas.common import ApiResponse
from app.schemas.notes import UserNoteUpdateRequest
from app.services.app_service import AppService


router = APIRouter(prefix="/api/notes", tags=["notes"])


@router.get("", response_model=ApiResponse[list[dict]])
def list_notes(
    ownerUserId: str = Query(...),
    keyword: str | None = Query(default=None),
    categoryId: str | None = Query(default=None),
    includeDeleted: bool = Query(default=False),
    service: AppService = Depends(get_app_service),
):
    return ApiResponse(
        data=service.list_user_notes(
            owner_user_id=ownerUserId,
            keyword=keyword,
            category_id=categoryId,
            include_deleted=includeDeleted,
        )
    )


@router.get("/{note_id}", response_model=ApiResponse[dict])
def get_note(note_id: str, ownerUserId: str = Query(...), service: AppService = Depends(get_app_service)):
    return ApiResponse(data=service.get_user_note(note_id, ownerUserId).model_dump())


@router.put("/{note_id}", response_model=ApiResponse[dict])
def update_note(note_id: str, payload: UserNoteUpdateRequest, service: AppService = Depends(get_app_service)):
    return ApiResponse(data=service.update_user_note(note_id, payload).model_dump())


@router.delete("/{note_id}", response_model=ApiResponse[dict])
def delete_note(note_id: str, ownerUserId: str = Query(...), service: AppService = Depends(get_app_service)):
    return ApiResponse(data=service.delete_user_note(note_id, ownerUserId))
