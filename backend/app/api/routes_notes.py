from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_app_service
from app.schemas.common import ApiResponse
from app.schemas.notes import TopicCreateRequest, TopicNoteRequest, UserNoteUpdateRequest
from app.services.app_service import AppService


router = APIRouter(prefix="/api/notes", tags=["notes"])


@router.get("", response_model=ApiResponse[list[dict]])
def list_notes(
    ownerUserId: str = Query(...),
    keyword: str | None = Query(default=None),
    categoryId: str | None = Query(default=None),
    sourceType: str | None = Query(default=None),
    systemCategory: str | None = Query(default=None),
    tag: str | None = Query(default=None),
    topicId: str | None = Query(default=None),
    sort: str = Query(default="updated"),
    includeDeleted: bool = Query(default=False),
    service: AppService = Depends(get_app_service),
):
    return ApiResponse(
        data=service.list_user_notes(
            owner_user_id=ownerUserId,
            keyword=keyword,
            category_id=categoryId,
            source_type=sourceType,
            system_category=systemCategory,
            tag=tag,
            topic_id=topicId,
            sort=sort,
            include_deleted=includeDeleted,
        )
    )


@router.get("/tag-suggestions", response_model=ApiResponse[dict])
def suggest_tags(
    ownerUserId: str = Query(...),
    noteId: str | None = Query(default=None),
    text: str | None = Query(default=None),
    service: AppService = Depends(get_app_service),
):
    return ApiResponse(data=service.suggest_note_tags(ownerUserId, noteId, text))


@router.get("/topics", response_model=ApiResponse[list[dict]])
def list_topics(ownerUserId: str = Query(...), service: AppService = Depends(get_app_service)):
    return ApiResponse(data=service.list_topics(ownerUserId))


@router.post("/topics", response_model=ApiResponse[dict])
def create_topic(payload: TopicCreateRequest, service: AppService = Depends(get_app_service)):
    return ApiResponse(data=service.create_topic(payload).model_dump())


@router.post("/{note_id}/topics/{topic_id}", response_model=ApiResponse[dict])
def add_note_to_topic(note_id: str, topic_id: str, payload: TopicNoteRequest, service: AppService = Depends(get_app_service)):
    return ApiResponse(data=service.add_note_to_topic(note_id, topic_id, payload.ownerUserId).model_dump())


@router.delete("/{note_id}/topics/{topic_id}", response_model=ApiResponse[dict])
def remove_note_from_topic(note_id: str, topic_id: str, ownerUserId: str = Query(...), service: AppService = Depends(get_app_service)):
    return ApiResponse(data=service.remove_note_from_topic(note_id, topic_id, ownerUserId).model_dump())


@router.get("/{note_id}", response_model=ApiResponse[dict])
def get_note(note_id: str, ownerUserId: str = Query(...), service: AppService = Depends(get_app_service)):
    return ApiResponse(data=service.get_user_note(note_id, ownerUserId).model_dump())


@router.put("/{note_id}", response_model=ApiResponse[dict])
def update_note(note_id: str, payload: UserNoteUpdateRequest, service: AppService = Depends(get_app_service)):
    return ApiResponse(data=service.update_user_note(note_id, payload).model_dump())


@router.post("/{note_id}/organize", response_model=ApiResponse[dict])
def organize_note(note_id: str, ownerUserId: str = Query(...), service: AppService = Depends(get_app_service)):
    return ApiResponse(data=service.organize_bookmark_note(note_id, ownerUserId).model_dump())


@router.delete("/{note_id}", response_model=ApiResponse[dict])
def delete_note(note_id: str, ownerUserId: str = Query(...), service: AppService = Depends(get_app_service)):
    return ApiResponse(data=service.delete_user_note(note_id, ownerUserId))
