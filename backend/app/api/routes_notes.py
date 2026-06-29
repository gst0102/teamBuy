from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile

from app.api.dependencies import get_app_service
from app.schemas.cards import RecordViewRequest
from app.schemas.common import ApiResponse
from app.schemas.notes import CustomerActionSubmitRequest, ManualNoteDraftRequest, NoteTypeConfirmRequest, PropertyBatchCreateRequest, PropertyBatchParseRequest, PropertySameCloneRequest, QuickNoteCaptureRequest, TopicCreateRequest, TopicNoteRequest, UserNoteUpdateRequest
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


@router.post("/manual-draft", response_model=ApiResponse[dict])
def create_manual_note_draft(payload: ManualNoteDraftRequest, service: AppService = Depends(get_app_service)):
    return ApiResponse(data=service.create_manual_note_draft(payload).model_dump(), message="manual draft created")


@router.post("/property-batch/parse", response_model=ApiResponse[dict])
def parse_property_batch(payload: PropertyBatchParseRequest, service: AppService = Depends(get_app_service)):
    return ApiResponse(data=service.parse_property_batch(payload), message="property batch parsed")


@router.post("/property-batch/create", response_model=ApiResponse[dict])
def create_property_batch(payload: PropertyBatchCreateRequest, service: AppService = Depends(get_app_service)):
    return ApiResponse(data=service.create_property_batch(payload), message="property batch created")


@router.post("/quick-capture", response_model=ApiResponse[dict])
def create_quick_note_capture(payload: QuickNoteCaptureRequest, service: AppService = Depends(get_app_service)):
    return ApiResponse(data=service.create_quick_note_capture(payload).model_dump(), message="quick note captured")


@router.post("/image-capture", response_model=ApiResponse[dict])
async def create_image_note_capture(
    ownerUserId: str = Form(...),
    file: UploadFile = File(...),
    service: AppService = Depends(get_app_service),
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
    return ApiResponse(data=data, message="image note saved")


@router.get("/topics", response_model=ApiResponse[list[dict]])
def list_topics(ownerUserId: str = Query(...), service: AppService = Depends(get_app_service)):
    return ApiResponse(data=service.list_topics(ownerUserId))


@router.post("/topics", response_model=ApiResponse[dict])
def create_topic(payload: TopicCreateRequest, service: AppService = Depends(get_app_service)):
    return ApiResponse(data=service.create_topic(payload).model_dump())


@router.delete("/topics/{topic_id}", response_model=ApiResponse[dict])
def delete_topic(topic_id: str, ownerUserId: str = Query(...), service: AppService = Depends(get_app_service)):
    return ApiResponse(data=service.delete_topic(topic_id, ownerUserId))


@router.post("/demo-data", response_model=ApiResponse[dict])
def create_note_demo_data(ownerUserId: str = Query(...), service: AppService = Depends(get_app_service)):
    return ApiResponse(data=service.create_note_demo_data(ownerUserId), message="demo data created")


@router.post("/demo-data/cleanup", response_model=ApiResponse[dict])
def cleanup_note_demo_data(ownerUserId: str = Query(...), service: AppService = Depends(get_app_service)):
    return ApiResponse(data=service.cleanup_note_demo_data(ownerUserId), message="demo data cleaned")


@router.post("/{note_id}/topics/{topic_id}", response_model=ApiResponse[dict])
def add_note_to_topic(note_id: str, topic_id: str, payload: TopicNoteRequest, service: AppService = Depends(get_app_service)):
    return ApiResponse(data=service.add_note_to_topic(note_id, topic_id, payload.ownerUserId).model_dump())


@router.delete("/{note_id}/topics/{topic_id}", response_model=ApiResponse[dict])
def remove_note_from_topic(note_id: str, topic_id: str, ownerUserId: str = Query(...), service: AppService = Depends(get_app_service)):
    return ApiResponse(data=service.remove_note_from_topic(note_id, topic_id, ownerUserId).model_dump())


@router.get("/public/{note_id}", response_model=ApiResponse[dict])
def get_public_note(note_id: str, service: AppService = Depends(get_app_service)):
    return ApiResponse(data=service.get_public_note(note_id))


@router.post("/property-same/clone", response_model=ApiResponse[dict])
def clone_property_same(payload: PropertySameCloneRequest, service: AppService = Depends(get_app_service)):
    return ApiResponse(data=service.clone_property_same(payload), message="property same cloned")


@router.post("/{note_id}/view", response_model=ApiResponse[dict])
def record_note_view(note_id: str, payload: RecordViewRequest, service: AppService = Depends(get_app_service)):
    return ApiResponse(data=service.record_note_view(note_id, payload).model_dump())


@router.get("/{note_id}", response_model=ApiResponse[dict])
def get_note(note_id: str, ownerUserId: str = Query(...), service: AppService = Depends(get_app_service)):
    return ApiResponse(data=service.get_user_note(note_id, ownerUserId).model_dump())


@router.put("/{note_id}", response_model=ApiResponse[dict])
def update_note(note_id: str, payload: UserNoteUpdateRequest, service: AppService = Depends(get_app_service)):
    return ApiResponse(data=service.update_user_note(note_id, payload).model_dump())


@router.post("/{note_id}/duplicate", response_model=ApiResponse[dict])
def duplicate_note(note_id: str, payload: TopicNoteRequest, service: AppService = Depends(get_app_service)):
    return ApiResponse(data=service.duplicate_user_note(note_id, payload.ownerUserId).model_dump(), message="note duplicated")


@router.post("/{note_id}/organize", response_model=ApiResponse[dict])
def organize_note(note_id: str, ownerUserId: str = Query(...), service: AppService = Depends(get_app_service)):
    return ApiResponse(data=service.organize_bookmark_note(note_id, ownerUserId).model_dump())


@router.post("/{note_id}/generate", response_model=ApiResponse[dict])
def generate_note(note_id: str, ownerUserId: str = Query(...), service: AppService = Depends(get_app_service)):
    return ApiResponse(data=service.generate_note_result(note_id, ownerUserId).model_dump())


@router.post("/{note_id}/confirm-type", response_model=ApiResponse[dict])
def confirm_note_type(note_id: str, payload: NoteTypeConfirmRequest, service: AppService = Depends(get_app_service)):
    return ApiResponse(data=service.confirm_note_type(note_id, payload).model_dump())


@router.get("/{note_id}/customer-actions/config", response_model=ApiResponse[dict])
def get_customer_action_config(
    note_id: str,
    viewerUserId: str | None = Query(default=None),
    anonymousId: str | None = Query(default=None),
    service: AppService = Depends(get_app_service),
):
    return ApiResponse(data=service.get_customer_action_config(note_id, viewerUserId, anonymousId))


@router.get("/{note_id}/customer-actions", response_model=ApiResponse[dict])
def list_customer_actions_for_note(
    note_id: str,
    ownerUserId: str = Query(...),
    service: AppService = Depends(get_app_service),
):
    return ApiResponse(data=service.list_customer_actions_for_note_owner(note_id, ownerUserId))


@router.post("/{note_id}/customer-actions/{action_key}", response_model=ApiResponse[dict])
def submit_customer_action(
    note_id: str,
    action_key: str,
    payload: CustomerActionSubmitRequest,
    service: AppService = Depends(get_app_service),
):
    return ApiResponse(data=service.submit_customer_action(note_id, action_key, payload))


@router.delete("/{note_id}", response_model=ApiResponse[dict])
def delete_note(note_id: str, ownerUserId: str = Query(...), service: AppService = Depends(get_app_service)):
    return ApiResponse(data=service.delete_user_note(note_id, ownerUserId))
