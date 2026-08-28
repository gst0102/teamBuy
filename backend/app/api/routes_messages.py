from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.api.dependencies import get_app_service, get_sync_task_queue
from app.schemas.common import ApiResponse
from app.services.app_service import AppService
from app.services.sync_task_queue import SyncTaskQueue


router = APIRouter(prefix="/api/messages", tags=["messages"])


class MessageThreadCreateRequest(BaseModel):
    userId: str
    noteId: str
    orderActionId: str | None = None
    buyerUserId: str | None = None
    content: str | None = None


class MessageCreateRequest(BaseModel):
    userId: str
    content: str


class MessageReadRequest(BaseModel):
    userId: str


@router.get("/threads", response_model=ApiResponse[dict])
def list_threads(userId: str = Query(...), service: AppService = Depends(get_app_service)):
    return ApiResponse(data=service.list_message_threads(userId))


@router.post("/threads", response_model=ApiResponse[dict])
def create_thread(
    payload: MessageThreadCreateRequest,
    service: AppService = Depends(get_app_service),
    queue: SyncTaskQueue = Depends(get_sync_task_queue),
):
    data = service.create_message_thread(payload.model_dump())
    message = data.get("message")
    notification = service.queue_message_notification(data["id"], message["id"], queue) if message else None
    if notification and notification.get("queued"):
        data["notification"] = notification
    return ApiResponse(data=data)


@router.get("/threads/{thread_id}/messages", response_model=ApiResponse[dict])
def list_messages(thread_id: str, userId: str = Query(...), service: AppService = Depends(get_app_service)):
    return ApiResponse(data=service.list_thread_messages(thread_id, userId))


@router.post("/threads/{thread_id}/messages", response_model=ApiResponse[dict])
def send_message(
    thread_id: str,
    payload: MessageCreateRequest,
    service: AppService = Depends(get_app_service),
    queue: SyncTaskQueue = Depends(get_sync_task_queue),
):
    data = service.send_thread_message(thread_id, payload.userId, payload.content)
    message = data.get("message")
    notification = service.queue_message_notification(thread_id, message["id"], queue) if message else None
    if notification and notification.get("queued"):
        data["notification"] = notification
    return ApiResponse(data=data)


@router.post("/threads/{thread_id}/read", response_model=ApiResponse[dict])
def mark_read(thread_id: str, payload: MessageReadRequest, service: AppService = Depends(get_app_service)):
    return ApiResponse(data=service.mark_message_thread_read(thread_id, payload.userId))
