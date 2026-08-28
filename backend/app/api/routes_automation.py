from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from app.api.dependencies import get_automation_control_service
from app.core.config import settings
from app.schemas.automation import (
    AutomationDeviceHeartbeatRequest,
    AutomationGroupCandidateUpsertRequest,
    AutomationGroupCandidateReviewRequest,
    AutomationMarketingCardRouteRequest,
    AutomationMarketingCardTaskRequest,
    AutomationTaskClaimRequest,
    AutomationTaskCompleteRequest,
    AutomationTaskCreateRequest,
    AutomationTaskFailRequest,
)
from app.schemas.common import ApiResponse
from app.services.automation_control_service import AutomationControlError, AutomationControlService


router = APIRouter(prefix="/api/automation", tags=["automation"])


def _provided_tokens(authorization: str | None, *headers: str | None) -> list[str]:
    provided = [str(value).strip() for value in headers if str(value or "").strip()]
    if authorization:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() == "bearer" and token.strip():
            provided.append(token.strip())
    return provided


def _verify_token(expected: str, authorization: str | None, provided_header: str | None, detail: str) -> None:
    _verify_any_token((expected,), authorization, (provided_header,), detail)


def _verify_any_token(
    expected_tokens: tuple[str | None, ...],
    authorization: str | None,
    provided_headers: tuple[str | None, ...],
    detail: str,
) -> None:
    provided_tokens = _provided_tokens(authorization, *provided_headers)
    expected = [str(value).strip() for value in expected_tokens if str(value or "").strip()]
    if not expected or not any(
        secrets.compare_digest(provided, candidate)
        for provided in provided_tokens
        for candidate in expected
    ):
        raise HTTPException(status_code=403, detail=detail)


def require_automation_operator_token(
    authorization: str | None = Header(default=None),
    x_automation_operator_token: str | None = Header(default=None, alias="X-Automation-Operator-Token"),
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
) -> None:
    _verify_any_token(
        (settings.automation_operator_token, settings.admin_token),
        authorization,
        (x_automation_operator_token, x_admin_token),
        "automation operator token verification failed",
    )


def require_automation_device_token(
    authorization: str | None = Header(default=None),
    x_automation_device_token: str | None = Header(default=None, alias="X-Automation-Device-Token"),
) -> None:
    _verify_token(
        str(settings.automation_device_token or ""),
        authorization,
        x_automation_device_token,
        "automation device token verification failed",
    )


def _raise_control_error(exc: AutomationControlError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


def _candidate_response(candidate, service: AutomationControlService) -> dict:
    data = candidate.model_dump()
    data["wechatAccountName"] = service.account_name_for_candidate(candidate)
    data["sendEligibility"] = service.group_send_eligibility(candidate)
    return data


@router.post("/devices/heartbeat", response_model=ApiResponse[dict], dependencies=[Depends(require_automation_device_token)])
def heartbeat(payload: AutomationDeviceHeartbeatRequest, service: AutomationControlService = Depends(get_automation_control_service)):
    try:
        device = service.heartbeat(
            device_id=payload.deviceId,
            name=payload.name,
            hid_device_id=payload.hidDeviceId,
            status=payload.status,
            active_wechat_account_id=payload.activeWechatAccountId,
            capabilities=payload.capabilities,
            metadata=payload.metadata,
        )
    except AutomationControlError as exc:
        _raise_control_error(exc)
    return ApiResponse(data=device.model_dump())


@router.get("/devices", response_model=ApiResponse[list[dict]], dependencies=[Depends(require_automation_operator_token)])
def list_devices(
    deviceId: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=200),
    service: AutomationControlService = Depends(get_automation_control_service),
):
    devices = service.list_devices(deviceId, limit)
    return ApiResponse(data=[device.model_dump() for device in devices])


@router.post("/tasks", response_model=ApiResponse[dict], dependencies=[Depends(require_automation_operator_token)])
def create_task(payload: AutomationTaskCreateRequest, service: AutomationControlService = Depends(get_automation_control_service)):
    try:
        task = service.create_task(
            function_id=payload.functionId,
            device_id=payload.deviceId,
            target_wechat_account_id=payload.targetWechatAccountId,
            payload=payload.payload,
            idempotency_key=payload.idempotencyKey,
        )
    except AutomationControlError as exc:
        _raise_control_error(exc)
    return ApiResponse(data=task.model_dump())


@router.get("/marketing-cards", response_model=ApiResponse[list[dict]], dependencies=[Depends(require_automation_operator_token)])
def list_marketing_cards(
    limit: int = Query(default=100, ge=1, le=200),
    service: AutomationControlService = Depends(get_automation_control_service),
):
    return ApiResponse(data=service.list_marketing_cards(limit))


@router.patch(
    "/marketing-cards/{note_id}/route",
    response_model=ApiResponse[dict],
    dependencies=[Depends(require_automation_operator_token)],
)
def update_marketing_card_route(
    note_id: str,
    payload: AutomationMarketingCardRouteRequest,
    service: AutomationControlService = Depends(get_automation_control_service),
):
    try:
        card = service.update_marketing_card_route(
            note_id=note_id,
            topic=payload.topic,
            region=payload.region,
            content_type=payload.contentType,
        )
    except AutomationControlError as exc:
        _raise_control_error(exc)
    return ApiResponse(data=card)


@router.post("/marketing-card-tasks", response_model=ApiResponse[dict], dependencies=[Depends(require_automation_operator_token)])
def create_marketing_card_task(
    payload: AutomationMarketingCardTaskRequest,
    service: AutomationControlService = Depends(get_automation_control_service),
):
    try:
        task = service.create_marketing_card_task(
            candidate_id=payload.candidateId,
            note_id=payload.noteId,
            device_id=payload.deviceId,
            idempotency_key=payload.idempotencyKey,
        )
    except AutomationControlError as exc:
        _raise_control_error(exc)
    return ApiResponse(data=task.model_dump())


@router.get("/tasks", response_model=ApiResponse[list[dict]], dependencies=[Depends(require_automation_operator_token)])
def list_tasks(
    deviceId: str | None = Query(default=None),
    status: list[str] | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    service: AutomationControlService = Depends(get_automation_control_service),
):
    tasks = service.repo.list_automation_tasks(device_id=deviceId, statuses=set(status) if status else None, limit=limit)
    return ApiResponse(data=[task.model_dump() for task in tasks])


@router.post("/tasks/claim", response_model=ApiResponse[dict | None], dependencies=[Depends(require_automation_device_token)])
def claim_task(payload: AutomationTaskClaimRequest, service: AutomationControlService = Depends(get_automation_control_service)):
    try:
        task = service.claim_task(
            device_id=payload.deviceId,
            active_wechat_account_id=payload.activeWechatAccountId,
            lease_seconds=payload.leaseSeconds,
        )
    except AutomationControlError as exc:
        _raise_control_error(exc)
    return ApiResponse(data=task.model_dump() if task else None, message="task claimed" if task else "no task for the active account")


@router.get("/tasks/{task_id}", response_model=ApiResponse[dict], dependencies=[Depends(require_automation_operator_token)])
def get_task(task_id: str, service: AutomationControlService = Depends(get_automation_control_service)):
    task = service.repo.get_automation_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="automation task not found")
    return ApiResponse(data=task.model_dump())


@router.post("/tasks/{task_id}/complete", response_model=ApiResponse[dict], dependencies=[Depends(require_automation_device_token)])
def complete_task(
    task_id: str,
    payload: AutomationTaskCompleteRequest,
    service: AutomationControlService = Depends(get_automation_control_service),
):
    try:
        task = service.complete_task(
            task_id=task_id,
            device_id=payload.deviceId,
            lease_token=payload.leaseToken,
            active_wechat_account_id=payload.activeWechatAccountId,
            result=payload.result,
        )
    except AutomationControlError as exc:
        _raise_control_error(exc)
    return ApiResponse(data=task.model_dump())


@router.post("/tasks/{task_id}/fail", response_model=ApiResponse[dict], dependencies=[Depends(require_automation_device_token)])
def fail_task(
    task_id: str,
    payload: AutomationTaskFailRequest,
    service: AutomationControlService = Depends(get_automation_control_service),
):
    try:
        task = service.fail_task(
            task_id=task_id,
            device_id=payload.deviceId,
            lease_token=payload.leaseToken,
            active_wechat_account_id=payload.activeWechatAccountId,
            error_message=payload.errorMessage,
            result=payload.result,
        )
    except AutomationControlError as exc:
        _raise_control_error(exc)
    return ApiResponse(data=task.model_dump())


@router.post("/group-candidates", response_model=ApiResponse[dict], dependencies=[Depends(require_automation_device_token)])
def upsert_group_candidate(
    payload: AutomationGroupCandidateUpsertRequest,
    service: AutomationControlService = Depends(get_automation_control_service),
):
    try:
        candidate = service.upsert_group_candidate(
            candidate_id=payload.id,
            device_id=payload.deviceId,
            wechat_account_id=payload.wechatAccountId,
            source=payload.source,
            group_qr_code=payload.groupQRCode,
            group_name=payload.groupName,
            wechat_account_name=payload.wechatAccountName,
            saved_at=payload.savedAt,
            join_status=payload.joinStatus,
            # canSend is an administrator-only decision; device discovery must not set it.
            can_send=None,
            remark=payload.remark,
            last_seen_at=payload.lastSeenAt,
            idempotency_key=payload.idempotencyKey,
            last_error=payload.lastError,
        )
    except AutomationControlError as exc:
        _raise_control_error(exc)
    return ApiResponse(data=candidate.model_dump())


@router.get("/group-candidates", response_model=ApiResponse[list[dict]], dependencies=[Depends(require_automation_operator_token)])
def list_group_candidates(
    wechatAccountId: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    service: AutomationControlService = Depends(get_automation_control_service),
):
    candidates = service.list_group_candidates(wechatAccountId, limit)
    return ApiResponse(data=[_candidate_response(candidate, service) for candidate in candidates])


@router.patch(
    "/group-candidates/{candidate_id}",
    response_model=ApiResponse[dict],
    dependencies=[Depends(require_automation_operator_token)],
)
def review_group_candidate(
    candidate_id: str,
    payload: AutomationGroupCandidateReviewRequest,
    service: AutomationControlService = Depends(get_automation_control_service),
):
    try:
        candidate = service.review_group_candidate(
            candidate_id=candidate_id,
            updates=payload.model_dump(exclude_unset=True),
        )
    except AutomationControlError as exc:
        _raise_control_error(exc)
    return ApiResponse(data=_candidate_response(candidate, service))
