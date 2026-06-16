from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.dependencies import get_app_service, get_skill_router_service
from app.schemas.common import ApiResponse
from app.schemas.skills import (
    RunContentToNoteRequest,
    RunContentToNoteResponse,
    SkillCommandPayload,
    SkillRouteRequest,
)
from app.services.skill_router_service import SkillRouterService
from app.services.app_service import AppService


router = APIRouter(prefix="/api/skills", tags=["skills"])


@router.get("/commands", response_model=ApiResponse[list[SkillCommandPayload]])
def list_skill_commands(service: SkillRouterService = Depends(get_skill_router_service)):
    return ApiResponse(data=service.list_commands())


@router.get("/runs", response_model=ApiResponse[list[dict]])
def list_skill_runs(
    status: str | None = None,
    skillId: str | None = None,
    limit: int = 100,
    service: AppService = Depends(get_app_service),
):
    return ApiResponse(data=service.list_skill_runs(status=status, skill_id=skillId, limit=limit))


@router.post("/route", response_model=ApiResponse[dict])
def route_skill(payload: SkillRouteRequest, service: SkillRouterService = Depends(get_skill_router_service)):
    return ApiResponse(data=service.route(payload.text, payload.content).model_dump())


@router.post("/content-to-note/run", response_model=ApiResponse[RunContentToNoteResponse])
def run_content_to_note(
    payload: RunContentToNoteRequest,
    service: SkillRouterService = Depends(get_skill_router_service),
):
    return ApiResponse(data=service.run_content_to_note(payload.ownerUserId, payload.content))
