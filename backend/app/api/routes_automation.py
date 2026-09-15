from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from app.api.dependencies import get_automation_control_service, get_sync_task_queue
from app.core.config import settings
from app.schemas.automation import (
    AutomationDeviceHeartbeatRequest,
    AutomationGroupCandidateUpsertRequest,
    AutomationGroupCandidateReviewRequest,
    AutomationBatchContentBulkReplaceRequest,
    AutomationCardAssetUpsertRequest,
    AutomationGroupContentPlanBulkReplaceRequest,
    AutomationGroupContentPlanUpsertRequest,
    AutomationGroupBatchTaskRequest,
    AutomationDeviceBatchRunRequest,
    AutomationGroupScanConfigRequest,
    AutomationNativeGroupScanRequest,
    AutomationRunCompletionRequest,
    AutomationLiveQrMemberCountRequest,
    AutomationMarketingCardRouteRequest,
    AutomationMarketingCardTaskRequest,
    AutomationTaskClaimRequest,
    AutomationTaskCompleteRequest,
    AutomationTaskCreateRequest,
    AutomationTaskFailRequest,
)
from app.schemas.common import ApiResponse
from app.services.automation_control_service import AutomationControlError, AutomationControlService
from app.services.sync_task_queue import SyncTaskQueue


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


@router.get(
    "/devices/{device_id}/group-scan-config",
    response_model=ApiResponse[dict],
    dependencies=[Depends(require_automation_device_token)],
)
def get_device_group_scan_config(
    device_id: str,
    service: AutomationControlService = Depends(get_automation_control_service),
):
    """Serve the PC-selected scan scope to the registered AScript device."""
    try:
        config = service.get_native_group_scan_config(device_id)
    except AutomationControlError as exc:
        _raise_control_error(exc)
    return ApiResponse(data=config)


@router.put(
    "/devices/{device_id}/group-scan-config",
    response_model=ApiResponse[dict],
    dependencies=[Depends(require_automation_operator_token)],
)
def update_device_group_scan_config(
    device_id: str,
    payload: AutomationGroupScanConfigRequest,
    service: AutomationControlService = Depends(get_automation_control_service),
):
    """Persist scan prefixes and scan-only mode from the PC operator panel."""
    try:
        config = service.update_native_group_scan_config(
            device_id=device_id,
            search_prefixes=payload.searchPrefixes,
            scan_only=payload.scanOnly,
        )
    except AutomationControlError as exc:
        _raise_control_error(exc)
    return ApiResponse(data=config)


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
            run_id=payload.runId,
            lease_seconds=payload.leaseSeconds,
            function_ids=set(payload.functionIds) or None,
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
            group_identity=payload.groupIdentity,
            wechat_account_name=payload.wechatAccountName,
            saved_at=payload.savedAt,
            join_status=payload.joinStatus,
            # canSend is an administrator-only decision; device discovery must not set it.
            can_send=None,
            remark=payload.remark,
            last_seen_at=payload.lastSeenAt,
            idempotency_key=payload.idempotencyKey,
            last_error=payload.lastError,
            group_member_count=payload.groupMemberCount,
            group_occurrence_count=payload.groupOccurrenceCount,
        )
    except AutomationControlError as exc:
        _raise_control_error(exc)
    return ApiResponse(data=candidate.model_dump())


@router.post(
    "/group-candidates/reconcile",
    response_model=ApiResponse[dict],
    dependencies=[Depends(require_automation_device_token)],
)
def reconcile_native_group_scan(
    payload: AutomationNativeGroupScanRequest,
    service: AutomationControlService = Depends(get_automation_control_service),
):
    try:
        result = service.reconcile_native_group_scan(
            device_id=payload.deviceId,
            wechat_account_id=payload.wechatAccountId,
            wechat_account_name=payload.wechatAccountName,
            scan_id=payload.scanId,
            scan_mode=payload.scanMode,
            coverage=payload.coverage,
            contacts_scan_stop_reason=payload.contactsScanStopReason,
            chat_list_scan_stop_reason=payload.chatListScanStopReason,
            contacts_group_count=payload.contactsGroupCount,
            chat_list_group_count=payload.chatListGroupCount,
            group_names=payload.groupNames,
            delete_missing=payload.deleteMissing,
            group_mappings=payload.groupMappings,
        )
    except AutomationControlError as exc:
        _raise_control_error(exc)
    return ApiResponse(data=result)


@router.post(
    "/runs/complete",
    response_model=ApiResponse[dict],
    dependencies=[Depends(require_automation_device_token)],
)
async def complete_automation_run(
    payload: AutomationRunCompletionRequest,
    sync_task_queue: SyncTaskQueue = Depends(get_sync_task_queue),
):
    """Persist the completion report before the independent mail worker sends it."""

    # The run identity is stable across HTTP retries, so a device retry cannot
    # enqueue duplicate completion emails for the same run.
    task, created = sync_task_queue.enqueue_once(
        "automation-completion-email",
        {"report": payload.model_dump()},
        idempotency_key=f"automation-completion-email:{payload.deviceId}:{payload.runId}",
        max_attempts=5,
    )
    completed_email = task.result.get("email") if isinstance(task.result, dict) else None
    if task.status == "success" and isinstance(completed_email, dict):
        notification = {
            **completed_email,
            "queued": False,
            "taskId": task.id,
            "taskStatus": task.status,
            "deduplicated": not created,
        }
    elif task.status == "failed":
        notification = {
            "sent": False,
            "queued": False,
            "reason": "delivery_failed",
            "taskId": task.id,
            "taskStatus": task.status,
            "deduplicated": not created,
        }
    else:
        notification = {
            "sent": None,
            "queued": True,
            "reason": "queued",
            "taskId": task.id,
            "taskStatus": task.status,
            "deduplicated": not created,
        }
    return ApiResponse(data={
        "runId": payload.runId,
        "status": payload.status,
        "email": notification,
    })


@router.post(
    "/live-qr/member-count",
    response_model=ApiResponse[dict],
    dependencies=[Depends(require_automation_device_token)],
)
def record_live_qr_member_count(
    payload: AutomationLiveQrMemberCountRequest,
    service: AutomationControlService = Depends(get_automation_control_service),
):
    try:
        result = service.record_live_qr_member_count(
            device_id=payload.deviceId,
            candidate_id=payload.candidateId,
            live_qr_code_id=payload.liveQrCodeId,
            wechat_account_id=payload.wechatAccountId,
            group_name=payload.groupName,
            group_member_count=payload.groupMemberCount,
        )
    except AutomationControlError as exc:
        _raise_control_error(exc)
    return ApiResponse(data=result)


@router.get("/group-candidates", response_model=ApiResponse[list[dict]], dependencies=[Depends(require_automation_operator_token)])
def list_group_candidates(
    wechatAccountId: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    service: AutomationControlService = Depends(get_automation_control_service),
):
    candidates = service.list_group_candidates(wechatAccountId, limit)
    return ApiResponse(data=[_candidate_response(candidate, service) for candidate in candidates])


@router.get("/card-assets", response_model=ApiResponse[list[dict]], dependencies=[Depends(require_automation_operator_token)])
def list_automation_card_assets(
    limit: int = Query(default=200, ge=1, le=500),
    service: AutomationControlService = Depends(get_automation_control_service),
):
    return ApiResponse(data=[asset.model_dump() for asset in service.list_card_assets(limit)])


@router.post("/card-assets", response_model=ApiResponse[dict], dependencies=[Depends(require_automation_operator_token)])
def upsert_automation_card_asset(
    payload: AutomationCardAssetUpsertRequest,
    service: AutomationControlService = Depends(get_automation_control_service),
):
    try:
        asset = service.upsert_card_asset(
            card_id=payload.cardId,
            deep_link=payload.deepLink,
            card_title=payload.cardTitle,
            status=payload.status,
        )
    except AutomationControlError as exc:
        _raise_control_error(exc)
    return ApiResponse(data=asset.model_dump())


@router.get("/group-content-plans", response_model=ApiResponse[list[dict]], dependencies=[Depends(require_automation_operator_token)])
def list_automation_group_content_plans(
    limit: int = Query(default=200, ge=1, le=500),
    service: AutomationControlService = Depends(get_automation_control_service),
):
    return ApiResponse(data=[plan.model_dump() for plan in service.list_group_content_plans(limit)])


@router.post("/group-content-plans", response_model=ApiResponse[dict], dependencies=[Depends(require_automation_operator_token)])
def upsert_automation_group_content_plan(
    payload: AutomationGroupContentPlanUpsertRequest,
    service: AutomationControlService = Depends(get_automation_control_service),
):
    try:
        plan = service.upsert_group_content_plan(
            group_code=payload.groupCode,
            remark=payload.remark,
            status=payload.status,
            batch_contents=payload.batchContents,
        )
    except AutomationControlError as exc:
        _raise_control_error(exc)
    return ApiResponse(data=plan.model_dump())


@router.post(
    "/group-content-plans/tasks",
    response_model=ApiResponse[dict],
    dependencies=[Depends(require_automation_operator_token)],
)
def create_group_content_plan_tasks(
    payload: AutomationGroupBatchTaskRequest,
    service: AutomationControlService = Depends(get_automation_control_service),
):
    """Queue one selected batch for the real groups bound to a PC code."""
    try:
        result = service.create_group_batch_tasks(
            group_code=payload.groupCode,
            batch_no=payload.batchNo,
            device_id=payload.deviceId,
            wechat_account_id=payload.wechatAccountId,
            max_targets=payload.maxTargets,
        )
    except AutomationControlError as exc:
        _raise_control_error(exc)
    return ApiResponse(data={
        **{key: value for key, value in result.items() if key != "tasks"},
        "tasks": [task.model_dump() for task in result["tasks"]],
    })


@router.post(
    "/group-content-plans/device-run",
    response_model=ApiResponse[dict],
    dependencies=[Depends(require_automation_device_token)],
)
def create_device_group_batch_run(
    payload: AutomationDeviceBatchRunRequest,
    service: AutomationControlService = Depends(get_automation_control_service),
):
    """Let AScript create the selected batch without exposing operator APIs."""
    try:
        result = service.create_device_batch_tasks(
            device_id=payload.deviceId,
            batch_no=payload.batchNo,
            wechat_account_ids=payload.wechatAccountIds,
            group_codes=payload.groupCodes,
            max_targets=payload.maxTargets,
            run_id=payload.runId,
        )
    except AutomationControlError as exc:
        _raise_control_error(exc)
    return ApiResponse(data={
        **{key: value for key, value in result.items() if key != "tasks"},
        "tasks": [task.model_dump() for task in result["tasks"]],
    })


@router.post(
    "/group-candidates/batch-contents/bulk-replace",
    response_model=ApiResponse[dict],
    dependencies=[Depends(require_automation_operator_token)],
)
def bulk_replace_group_batch_contents(
    payload: AutomationBatchContentBulkReplaceRequest,
    service: AutomationControlService = Depends(get_automation_control_service),
):
    try:
        result = service.bulk_replace_batch_contents(
            group_code=None,
            old_card_id=payload.oldCardId,
            new_card_id=payload.newCardId,
            old_text=payload.oldText,
            new_text=payload.newText,
        )
    except AutomationControlError as exc:
        _raise_control_error(exc)
    return ApiResponse(data={
        "updatedGroups": result.get("updatedGroups", 0),
        "updatedBatches": result.get("updatedBatches", 0),
    })


@router.post(
    "/group-content-plans/bulk-replace",
    response_model=ApiResponse[dict],
    dependencies=[Depends(require_automation_operator_token)],
)
def bulk_replace_group_content_plans(
    payload: AutomationGroupContentPlanBulkReplaceRequest,
    service: AutomationControlService = Depends(get_automation_control_service),
):
    try:
        result = service.bulk_replace_batch_contents(
            group_code=payload.groupCode,
            old_card_id=payload.oldCardId,
            new_card_id=payload.newCardId,
            old_text=payload.oldText,
            new_text=payload.newText,
        )
    except AutomationControlError as exc:
        _raise_control_error(exc)
    return ApiResponse(data=result)


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
