from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, Response

from app.api.dependencies import get_app_service, get_ops_console_store, get_sync_task_queue, get_wecom_client
from app.core.config import settings
from app.schemas.common import ApiResponse
from app.schemas.ops_admin import (
    FeedbackTicketCreateRequest,
    FeedbackTicketUpdateRequest,
    GroupBotChannelUpsertRequest,
    GroupUploadCreateRequest,
    GroupUploadPreviewRequest,
    OpportunityLeadUpsertRequest,
    RuleLearningSampleUpdateRequest,
    SingleGroupResourceCreateRequest,
    SupplyDemandReviewRequest,
    WecomGroupJoinWayCreateRequest,
)
from app.schemas.resource_wallet import ResourceWalletAdjustRequest
from app.services.app_service import AppService
from app.services.ops_console_store import OpsConsoleStore
from app.services.sync_task_queue import SyncTaskQueue
from app.services.time_utils import SHANGHAI, parse_iso
from app.services.wecom_client import WecomClient, WecomClientError


router = APIRouter(tags=["ops-admin"])
OPS_INDEX_FILE = Path(__file__).resolve().parents[1] / "static" / "ops-admin" / "index.html"


def _verify_admin_token(provided_token: str | None) -> None:
    if not settings.admin_token:
        raise HTTPException(status_code=403, detail="WECOM_ADMIN_TOKEN is not configured")
    if provided_token != settings.admin_token:
        raise HTTPException(status_code=403, detail="admin token verification failed")


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return parse_iso(value).astimezone(SHANGHAI)
    except Exception:
        return None


def _today_start() -> datetime:
    now = datetime.now(tz=SHANGHAI)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def _is_since(value: str | None, start: datetime) -> bool:
    parsed = _parse_datetime(value)
    return bool(parsed and parsed >= start)


def _last_days_keys(days: int = 7) -> list[str]:
    today = _today_start().date()
    return [(today - timedelta(days=offset)).isoformat() for offset in range(days - 1, -1, -1)]


def _build_trend(days: int, state) -> list[dict]:
    keys = _last_days_keys(days)
    counters = {
        "users": Counter(),
        "notes": Counter(),
        "showcases": Counter(),
        "actions": Counter(),
        "showcaseViews": Counter(),
    }
    for user in state.users:
        parsed = _parse_datetime(user.createdAt)
        if parsed:
            counters["users"][parsed.date().isoformat()] += 1
    for note in state.user_notes:
        parsed = _parse_datetime(note.createdAt)
        if parsed:
            counters["notes"][parsed.date().isoformat()] += 1
    for showcase in state.showcase_pages:
        parsed = _parse_datetime(showcase.createdAt)
        if parsed:
            counters["showcases"][parsed.date().isoformat()] += 1
    for action in state.customer_actions:
        parsed = _parse_datetime(action.createdAt)
        if parsed:
            counters["actions"][parsed.date().isoformat()] += 1
    for event in state.showcase_events:
        if event.eventType != "view":
            continue
        parsed = _parse_datetime(event.createdAt)
        if parsed:
            counters["showcaseViews"][parsed.date().isoformat()] += 1
    return [
        {
            "date": date_key,
            "users": counters["users"][date_key],
            "notes": counters["notes"][date_key],
            "showcases": counters["showcases"][date_key],
            "actions": counters["actions"][date_key],
            "showcaseViews": counters["showcaseViews"][date_key],
        }
        for date_key in keys
    ]


def _user_label_map(state) -> dict[str, str]:
    return {item.id: item.nickname or item.id for item in state.users}


def _system_queue(service: AppService, sync_task_queue: SyncTaskQueue) -> dict:
    notifications = service.list_import_notifications()
    pending_notifications = [item for item in notifications if item.get("sendStatus") == "pending"]
    import_failures = service.list_import_failures(limit=50)
    failed_media = service.list_media_retry_jobs({"failed"})
    sync_tasks = []
    for item in sync_task_queue.list_recent():
        payload = item.model_dump() if hasattr(item, "model_dump") else item
        if payload.get("status") in {"failed", "retrying"}:
            sync_tasks.append(payload)
    return {
        "summary": {
            "pendingNotificationCount": len(pending_notifications),
            "failedImportCount": len(import_failures.get("notifications", [])) + len(import_failures.get("skillRuns", [])),
            "failedMediaCount": len(failed_media),
            "failedSyncTaskCount": len(sync_tasks),
        },
        "pendingNotifications": pending_notifications[:20],
        "importFailures": import_failures,
        "failedMedia": failed_media[:20],
        "failedSyncTasks": sync_tasks[:20],
    }


@router.get("/ops")
def ops_console_page():
    return FileResponse(OPS_INDEX_FILE)


@router.get("/api/ops-admin/overview", response_model=ApiResponse[dict])
def get_ops_admin_overview(
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    service: AppService = Depends(get_app_service),
    sync_task_queue: SyncTaskQueue = Depends(get_sync_task_queue),
):
    _verify_admin_token(x_admin_token)
    state = service.repo.load()
    today_start = _today_start()
    today_user_count = sum(1 for item in state.users if _is_since(item.createdAt, today_start))
    today_note_count = sum(1 for item in state.user_notes if _is_since(item.createdAt, today_start))
    today_showcase_count = sum(1 for item in state.showcase_pages if _is_since(item.createdAt, today_start))
    today_action_count = sum(1 for item in state.customer_actions if _is_since(item.createdAt, today_start))
    today_showcase_views = sum(1 for item in state.showcase_events if item.eventType == "view" and _is_since(item.createdAt, today_start))
    notifications = service.list_import_notifications()
    today_notification_count = sum(1 for item in notifications if _is_since(item.get("sentAt"), today_start))
    queue = _system_queue(service, sync_task_queue)

    showcase_by_id = {item.id: item for item in state.showcase_pages}
    showcase_open_counter: dict[str, int] = defaultdict(int)
    for event in state.showcase_events:
        if event.eventType == "view":
            showcase_open_counter[event.showcaseId] += 1
    top_showcase = None
    if showcase_open_counter:
        top_showcase_id = max(showcase_open_counter.items(), key=lambda item: item[1])[0]
        showcase = showcase_by_id.get(top_showcase_id)
        top_showcase = {
            "showcaseId": top_showcase_id,
            "name": showcase.name if showcase else top_showcase_id,
            "ownerUserId": showcase.ownerUserId if showcase else None,
            "openCount": showcase_open_counter[top_showcase_id],
        }

    return ApiResponse(
        data={
            "summary": {
                "todayNewUsers": today_user_count,
                "todayNewNotes": today_note_count,
                "todayNewShowcases": today_showcase_count,
                "todayCustomerActions": today_action_count,
                "todayShowcaseViews": today_showcase_views,
                "todayNotifications": today_notification_count,
                "totalUsers": len(state.users),
                "totalNotes": len(state.user_notes),
                "totalShowcases": len(state.showcase_pages),
                "pendingNotifications": queue["summary"]["pendingNotificationCount"],
                "pendingIssues": (
                    queue["summary"]["failedImportCount"]
                    + queue["summary"]["failedMediaCount"]
                    + queue["summary"]["failedSyncTaskCount"]
                ),
            },
            "trend7d": _build_trend(7, state),
            "topShowcase": top_showcase,
            "resourceStatus": [
                {"key": "group-resource-library", "label": "群资源库", "status": "partial", "desc": "积分账本已后端化，使用记录待接"},
                {"key": "enterprise-resource-search", "label": "企业资源搜索", "status": "partial", "desc": "积分账本已后端化，查询记录待接"},
                {"key": "opportunity-leads", "label": "商机线索", "status": "partial", "desc": "录入、下架、回应包和积分后台可用"},
                {"key": "help-feedback", "label": "帮助与反馈", "status": "partial", "desc": "PC 工单可用，小程序前台提交通路待接"},
            ],
            "systemQueue": queue["summary"],
        }
    )


@router.get("/api/ops-admin/user-leaderboard", response_model=ApiResponse[dict])
def get_user_leaderboard(
    keyword: str | None = Query(default=None),
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    service: AppService = Depends(get_app_service),
):
    _verify_admin_token(x_admin_token)
    state = service.repo.load()
    notes_by_owner = Counter(item.ownerUserId for item in state.user_notes)
    showcases_by_owner = Counter(item.ownerUserId for item in state.showcase_pages)
    actions_by_owner = Counter(item.ownerUserId for item in state.customer_actions)
    views_by_owner = Counter(item.ownerUserId for item in state.showcase_events if item.eventType == "view")
    last_active_map: dict[str, str] = {}

    def mark_active(user_id: str, value: str | None) -> None:
        if not user_id or not value:
            return
        current = last_active_map.get(user_id)
        if not current or value > current:
            last_active_map[user_id] = value

    for note in state.user_notes:
        mark_active(note.ownerUserId, note.updatedAt)
    for showcase in state.showcase_pages:
        mark_active(showcase.ownerUserId, showcase.updatedAt)
    for action in state.customer_actions:
        mark_active(action.ownerUserId, action.updatedAt)
    for event in state.showcase_events:
        mark_active(event.ownerUserId, event.createdAt)

    rows = []
    q = (keyword or "").strip().lower()
    for user in state.users:
        searchable = f"{user.nickname} {user.id} {user.openid}".lower()
        if q and q not in searchable:
            continue
        row = {
            "userId": user.id,
            "nickname": user.nickname,
            "openid": user.openid,
            "createdAt": user.createdAt,
            "noteCount": notes_by_owner[user.id],
            "showcaseCount": showcases_by_owner[user.id],
            "customerActionCount": actions_by_owner[user.id],
            "showcaseViewCount": views_by_owner[user.id],
            "lastActiveAt": last_active_map.get(user.id) or user.updatedAt,
        }
        row["activeScore"] = row["noteCount"] + row["showcaseCount"] * 3 + row["customerActionCount"] * 5 + row["showcaseViewCount"]
        rows.append(row)
    rows.sort(key=lambda item: (item["activeScore"], item["showcaseViewCount"], item["customerActionCount"], item["lastActiveAt"]), reverse=True)
    return ApiResponse(data={"items": rows[:100], "total": len(rows)})


@router.get("/api/ops-admin/content-leaderboard", response_model=ApiResponse[dict])
def get_content_leaderboard(
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    service: AppService = Depends(get_app_service),
):
    _verify_admin_token(x_admin_token)
    state = service.repo.load()
    users_by_id = {item.id: item for item in state.users}
    showcases = {item.id: item for item in state.showcase_pages}
    notes = {item.id: item for item in state.user_notes}

    showcase_stats: dict[str, dict] = defaultdict(lambda: {"openCount": 0, "noteClickCount": 0, "consultCount": 0, "shareCount": 0, "lastEventAt": ""})
    for event in state.showcase_events:
        stats = showcase_stats[event.showcaseId]
        if event.eventType == "view":
            stats["openCount"] += 1
        elif event.eventType == "note_click":
            stats["noteClickCount"] += 1
        elif event.eventType in {"phone_click", "wechat_copy"}:
            stats["consultCount"] += 1
        elif event.eventType == "share":
            stats["shareCount"] += 1
        if event.createdAt > stats["lastEventAt"]:
            stats["lastEventAt"] = event.createdAt

    showcase_rows = []
    for showcase_id, showcase in showcases.items():
        stats = showcase_stats.get(showcase_id, {})
        owner = users_by_id.get(showcase.ownerUserId)
        showcase_rows.append(
            {
                "showcaseId": showcase_id,
                "name": showcase.name,
                "status": showcase.status,
                "ownerUserId": showcase.ownerUserId,
                "ownerNickname": owner.nickname if owner else showcase.ownerUserId,
                "openCount": stats.get("openCount", 0),
                "noteClickCount": stats.get("noteClickCount", 0),
                "consultCount": stats.get("consultCount", 0),
                "shareCount": stats.get("shareCount", 0),
                "lastEventAt": stats.get("lastEventAt") or showcase.updatedAt,
            }
        )
    showcase_rows.sort(key=lambda item: (item["openCount"], item["consultCount"], item["noteClickCount"], item["lastEventAt"]), reverse=True)

    note_action_count = Counter(item.noteId for item in state.customer_actions)
    note_showcase_click_count = Counter(item.noteId for item in state.showcase_events if item.eventType == "note_click" and item.noteId)
    note_last_active: dict[str, str] = {}
    for action in state.customer_actions:
        if action.noteId and action.updatedAt > note_last_active.get(action.noteId, ""):
            note_last_active[action.noteId] = action.updatedAt
    for event in state.showcase_events:
        if event.noteId and event.createdAt > note_last_active.get(event.noteId, ""):
            note_last_active[event.noteId] = event.createdAt

    note_rows = []
    for note_id, note in notes.items():
        owner = users_by_id.get(note.ownerUserId)
        note_rows.append(
            {
                "noteId": note_id,
                "title": note.title,
                "status": note.status,
                "ownerUserId": note.ownerUserId,
                "ownerNickname": owner.nickname if owner else note.ownerUserId,
                "actionCount": note_action_count[note_id],
                "showcaseClickCount": note_showcase_click_count[note_id],
                "lastActiveAt": note_last_active.get(note_id) or note.updatedAt,
            }
        )
    note_rows.sort(key=lambda item: (item["actionCount"], item["showcaseClickCount"], item["lastActiveAt"]), reverse=True)
    return ApiResponse(data={"showcases": showcase_rows[:100], "notes": note_rows[:100]})


@router.get("/api/ops-admin/system-queue", response_model=ApiResponse[dict])
def get_system_queue(
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    service: AppService = Depends(get_app_service),
    sync_task_queue: SyncTaskQueue = Depends(get_sync_task_queue),
):
    _verify_admin_token(x_admin_token)
    return ApiResponse(data=_system_queue(service, sync_task_queue))


@router.post("/api/ops-admin/group-upload/preview", response_model=ApiResponse[dict])
def preview_group_upload(
    payload: GroupUploadPreviewRequest,
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    store: OpsConsoleStore = Depends(get_ops_console_store),
):
    _verify_admin_token(x_admin_token)
    return ApiResponse(data=store.preview_group_upload(payload.rawText))


@router.post("/api/ops-admin/group-upload/preview-file", response_model=ApiResponse[dict])
async def preview_group_upload_file(
    file: UploadFile = File(...),
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    store: OpsConsoleStore = Depends(get_ops_console_store),
):
    _verify_admin_token(x_admin_token)
    try:
        content = await file.read()
        return ApiResponse(data=store.preview_group_upload_file(file.filename or "", content))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/api/ops-admin/group-resources", response_model=ApiResponse[list[dict]])
def list_single_group_resources(
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    store: OpsConsoleStore = Depends(get_ops_console_store),
):
    _verify_admin_token(x_admin_token)
    return ApiResponse(data=store.list_single_group_resources())


@router.post("/api/ops-admin/group-resources", response_model=ApiResponse[dict])
def create_single_group_resource(
    payload: SingleGroupResourceCreateRequest,
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    store: OpsConsoleStore = Depends(get_ops_console_store),
):
    _verify_admin_token(x_admin_token)
    if not payload.name.strip():
        raise HTTPException(status_code=400, detail="群名称不能为空")
    if not payload.purposes:
        raise HTTPException(status_code=400, detail="至少选择一个用途")
    if not payload.qrImageData:
        raise HTTPException(status_code=400, detail="请先上传群二维码")
    return ApiResponse(
        data=store.create_single_group_resource(
            name=payload.name,
            city_mode=payload.cityMode,
            city_label=payload.cityLabel,
            region=payload.region,
            group_type=payload.groupType,
            purposes=payload.purposes,
            member_range=payload.memberRange,
            active_level=payload.activeLevel,
            expires_in_days=payload.expiresInDays,
            remark=payload.remark,
            custom_tags=payload.customTags,
            qr_image_data=payload.qrImageData,
            operator_name=payload.operatorName,
        )
    )


@router.get("/api/ops-admin/wecom-group-join-ways", response_model=ApiResponse[list[dict]])
def list_wecom_group_join_ways(
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    store: OpsConsoleStore = Depends(get_ops_console_store),
):
    _verify_admin_token(x_admin_token)
    return ApiResponse(data=store.list_wecom_group_join_ways())


@router.get("/api/ops-admin/group-bot-channels", response_model=ApiResponse[list[dict]])
def list_group_bot_channels(
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    store: OpsConsoleStore = Depends(get_ops_console_store),
):
    _verify_admin_token(x_admin_token)
    return ApiResponse(data=store.list_group_bot_channels())


@router.post("/api/ops-admin/group-bot-channels", response_model=ApiResponse[dict])
def upsert_group_bot_channel(
    payload: GroupBotChannelUpsertRequest,
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    store: OpsConsoleStore = Depends(get_ops_console_store),
):
    _verify_admin_token(x_admin_token)
    try:
        channel = store.upsert_group_bot_channel(
            group_id=payload.groupId,
            group_name=payload.groupName,
            webhook=payload.webhook,
            group_type=payload.groupType,
            audience=payload.audience,
            city_label=payload.cityLabel,
            daily_template=payload.dailyTemplate,
            send_window=payload.sendWindow,
            owner_name=payload.ownerName,
            remark=payload.remark,
            enabled=payload.enabled,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ApiResponse(message="group bot channel saved", data=channel)


@router.get("/api/ops-admin/wecom-customer-groups", response_model=ApiResponse[dict])
async def list_wecom_customer_groups(
    status_filter: int = Query(default=0, alias="statusFilter"),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    client: WecomClient = Depends(get_wecom_client),
):
    _verify_admin_token(x_admin_token)
    try:
        response = await client.list_customer_groups(status_filter=status_filter, cursor=cursor, limit=limit)
    except WecomClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    groups = response.get("group_chat_list") or response.get("groupChatList") or []
    items = [
        {
            "chatId": item.get("chat_id") or item.get("chatId"),
            "name": item.get("name") or "未命名客户群",
            "owner": item.get("owner"),
            "status": item.get("status"),
            "createTime": item.get("create_time") or item.get("createTime"),
        }
        for item in groups
    ]
    return ApiResponse(
        data={
            "items": [item for item in items if item["chatId"]],
            "nextCursor": response.get("next_cursor") or response.get("nextCursor") or "",
            "rawCount": len(groups),
        }
    )


@router.post("/api/ops-admin/wecom-group-join-ways", response_model=ApiResponse[dict])
async def create_wecom_group_join_way(
    payload: WecomGroupJoinWayCreateRequest,
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    store: OpsConsoleStore = Depends(get_ops_console_store),
    client: WecomClient = Depends(get_wecom_client),
):
    _verify_admin_token(x_admin_token)
    chat_id_list = [item.strip() for item in payload.chatIdList if item and item.strip()]
    if not chat_id_list:
        raise HTTPException(status_code=400, detail="至少填写一个客户群 chat_id")
    if not payload.remark.strip():
        raise HTTPException(status_code=400, detail="配置备注不能为空")
    if not payload.roomBaseName.strip():
        raise HTTPException(status_code=400, detail="群名规则不能为空")

    request_payload = {
        "scene": 2,
        "remark": payload.remark.strip(),
        "chatIdList": chat_id_list,
        "autoCreateRoom": 1 if payload.autoCreateRoom else 0,
        "roomBaseName": payload.roomBaseName.strip(),
        "roomBaseId": max(1, int(payload.roomBaseId or 1)),
        "state": payload.state.strip() if payload.state else "",
    }
    if payload.dryRun:
        return ApiResponse(
            message="wecom group join way dry run",
            data={
                "dryRun": True,
                "request": request_payload,
                "note": "dryRun 不会调用企业微信；确认 chat_id 后把 dryRun 改为 false 生成 config_id。",
            },
        )
    try:
        response = await client.create_group_join_way(
            scene=request_payload["scene"],
            remark=request_payload["remark"],
            chat_id_list=chat_id_list,
            auto_create_room=request_payload["autoCreateRoom"],
            room_base_name=request_payload["roomBaseName"],
            room_base_id=request_payload["roomBaseId"],
            state=request_payload["state"],
        )
    except WecomClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    config_id = response.get("config_id") or response.get("configId")
    if not config_id:
        raise HTTPException(status_code=502, detail=f"企业微信未返回 config_id: {response}")
    record = store.save_wecom_group_join_way(
        config_id=config_id,
        remark=request_payload["remark"],
        chat_id_list=chat_id_list,
        room_base_name=request_payload["roomBaseName"],
        room_base_id=request_payload["roomBaseId"],
        auto_create_room=request_payload["autoCreateRoom"],
        state_value=request_payload["state"],
        operator_name=payload.operatorName,
        raw_response=response,
    )
    return ApiResponse(message="wecom group join way created", data=record)


@router.post("/api/ops-admin/group-upload/batches", response_model=ApiResponse[dict])
def create_group_upload_batch(
    payload: GroupUploadCreateRequest,
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    store: OpsConsoleStore = Depends(get_ops_console_store),
):
    _verify_admin_token(x_admin_token)
    return ApiResponse(data=store.create_group_upload_batch(payload.rawText, payload.batchName, payload.operatorName))


@router.post("/api/ops-admin/group-upload/batches-file", response_model=ApiResponse[dict])
async def create_group_upload_batch_from_file(
    file: UploadFile = File(...),
    batchName: str | None = Form(default=None),
    operatorName: str | None = Form(default=None),
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    store: OpsConsoleStore = Depends(get_ops_console_store),
):
    _verify_admin_token(x_admin_token)
    try:
        content = await file.read()
        return ApiResponse(data=store.create_group_upload_batch_from_file(file.filename or "", content, batchName, operatorName))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/api/ops-admin/group-upload/batches", response_model=ApiResponse[list[dict]])
def list_group_upload_batches(
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    store: OpsConsoleStore = Depends(get_ops_console_store),
):
    _verify_admin_token(x_admin_token)
    return ApiResponse(data=store.list_group_upload_batches())


@router.get("/api/ops-admin/group-upload/template.csv")
def download_group_upload_template_csv(
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    store: OpsConsoleStore = Depends(get_ops_console_store),
):
    _verify_admin_token(x_admin_token)
    return Response(
        content=store.group_upload_template_csv_bytes(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="group-upload-template.csv"'},
    )


@router.get("/api/ops-admin/group-upload/template.xlsx")
def download_group_upload_template_xlsx(
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    store: OpsConsoleStore = Depends(get_ops_console_store),
):
    _verify_admin_token(x_admin_token)
    return Response(
        content=store.group_upload_template_xlsx_bytes(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="group-upload-template.xlsx"'},
    )


@router.get("/api/ops-admin/feedback", response_model=ApiResponse[list[dict]])
def list_feedback_tickets(
    status: str | None = Query(default=None),
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    store: OpsConsoleStore = Depends(get_ops_console_store),
):
    _verify_admin_token(x_admin_token)
    return ApiResponse(data=store.list_feedback_tickets(status=status))


@router.get("/api/ops/opportunity-leads", response_model=ApiResponse[list[dict]])
def list_ops_opportunity_leads(
    keyword: str | None = Query(default=None),
    status: str | None = Query(default=None),
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    service: AppService = Depends(get_app_service),
):
    _verify_admin_token(x_admin_token)
    return ApiResponse(data=service.list_opportunity_leads_ops(keyword=keyword, status=status))


@router.get("/api/ops/opportunity-leads/{lead_id}", response_model=ApiResponse[dict])
def get_ops_opportunity_lead(
    lead_id: str,
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    service: AppService = Depends(get_app_service),
):
    _verify_admin_token(x_admin_token)
    return ApiResponse(data=service.get_opportunity_lead_detail(lead_id, include_ops=True))


@router.post("/api/ops/opportunity-leads", response_model=ApiResponse[dict])
def upsert_ops_opportunity_lead(
    payload: OpportunityLeadUpsertRequest,
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    service: AppService = Depends(get_app_service),
):
    _verify_admin_token(x_admin_token)
    return ApiResponse(data=service.upsert_opportunity_lead(payload))


@router.post("/api/ops/opportunity-leads/{lead_id}/offline", response_model=ApiResponse[dict])
def offline_ops_opportunity_lead(
    lead_id: str,
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    service: AppService = Depends(get_app_service),
):
    _verify_admin_token(x_admin_token)
    lead = service.repo.get_opportunity_lead(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="商机线索不存在")
    lead.status = "archived"
    lead.updatedAt = datetime.now(tz=SHANGHAI).isoformat()
    service.repo.save_opportunity_lead(lead)
    return ApiResponse(data=service.get_opportunity_lead_detail(lead_id, include_ops=True))


@router.get("/api/ops/opportunity-dashboard", response_model=ApiResponse[dict])
def get_ops_opportunity_dashboard(
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    service: AppService = Depends(get_app_service),
):
    _verify_admin_token(x_admin_token)
    state = service.repo.load()
    today_start = _today_start()
    today_ledgers = [item for item in state.resource_point_ledgers if _is_since(item.createdAt, today_start)]
    consumed_ledgers = [item for item in state.resource_point_ledgers if item.pointsDelta < 0]
    today_consumed_ledgers = [item for item in today_ledgers if item.pointsDelta < 0]
    today_resource_users = {item.ownerUserId for item in today_ledgers if item.actionType != "initial_grant"}
    status_counter = Counter(item.status for item in state.opportunity_leads)
    package_today_count = sum(1 for item in state.response_packages if _is_since(item.createdAt, today_start))
    generated_lead_ids = {item.leadId for item in state.response_packages}
    saved_lead_ids = {item.leadId for item in state.opportunity_lead_saves}
    user_labels = _user_label_map(state)
    consumed_by_user: dict[str, int] = defaultdict(int)
    for item in consumed_ledgers:
        consumed_by_user[item.ownerUserId] += abs(item.pointsDelta)
    rank_rows = [
        {
            "userId": user_id,
            "nickname": user_labels.get(user_id, user_id),
            "pointsConsumed": points,
        }
        for user_id, points in sorted(consumed_by_user.items(), key=lambda row: row[1], reverse=True)[:20]
    ]
    return ApiResponse(
        data={
            "summary": {
                "todayResourceUsers": len(today_resource_users),
                "todayPointsConsumed": sum(abs(item.pointsDelta) for item in today_consumed_ledgers),
                "todayResponsePackages": package_today_count,
                "publishedLeads": status_counter["published"],
                "draftLeads": status_counter["draft"],
                "archivedLeads": status_counter["archived"],
                "savedLeadCount": len(saved_lead_ids),
                "responsePackageLeadCount": len(generated_lead_ids),
            },
            "pointsRank": rank_rows,
            "leadStatus": dict(status_counter),
        }
    )


@router.get("/api/ops/resource-wallet/users", response_model=ApiResponse[dict])
def list_ops_resource_wallet_users(
    keyword: str | None = Query(default=None),
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    service: AppService = Depends(get_app_service),
):
    _verify_admin_token(x_admin_token)
    state = service.repo.load()
    q = (keyword or "").strip().lower()
    ledger_count = Counter(item.ownerUserId for item in state.resource_point_ledgers)
    last_ledger_at: dict[str, str] = {}
    for item in state.resource_point_ledgers:
        if not last_ledger_at.get(item.ownerUserId) or item.createdAt > last_ledger_at[item.ownerUserId]:
            last_ledger_at[item.ownerUserId] = item.createdAt
    wallet_map = {item.ownerUserId: item for item in state.resource_wallets}
    rows = []
    for user in state.users:
        searchable = f"{user.nickname} {user.id} {user.openid}".lower()
        if q and q not in searchable:
            continue
        wallet = wallet_map.get(user.id)
        rows.append(
            {
                "userId": user.id,
                "nickname": user.nickname,
                "openid": user.openid,
                "balance": wallet.balance if wallet else None,
                "totalGranted": wallet.totalGranted if wallet else 0,
                "totalConsumed": wallet.totalConsumed if wallet else 0,
                "ledgerCount": ledger_count[user.id],
                "lastLedgerAt": last_ledger_at.get(user.id),
                "createdAt": user.createdAt,
            }
        )
    rows.sort(key=lambda item: (item["totalConsumed"], item["ledgerCount"], item["lastLedgerAt"] or ""), reverse=True)
    return ApiResponse(data={"items": rows[:100], "total": len(rows)})


@router.post("/api/ops/resource-wallet/users/{user_id}/adjust", response_model=ApiResponse[dict])
def adjust_ops_resource_wallet_user(
    user_id: str,
    payload: ResourceWalletAdjustRequest,
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    service: AppService = Depends(get_app_service),
):
    _verify_admin_token(x_admin_token)
    return ApiResponse(
        data=service.adjust_resource_wallet(
            owner_user_id=user_id,
            points_delta=payload.pointsDelta,
            reason=payload.reason,
            operator_id=payload.operatorId,
        )
    )


@router.get("/api/ops/response-packages", response_model=ApiResponse[dict])
def list_ops_response_packages(
    keyword: str | None = Query(default=None),
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    service: AppService = Depends(get_app_service),
):
    _verify_admin_token(x_admin_token)
    state = service.repo.load()
    user_labels = _user_label_map(state)
    lead_map = {item.id: item for item in state.opportunity_leads}
    q = (keyword or "").strip().lower()
    rows = []
    for item in state.response_packages:
        lead = lead_map.get(item.leadId)
        searchable = f"{item.title} {item.ownerUserId} {user_labels.get(item.ownerUserId, '')} {lead.title if lead else ''}".lower()
        if q and q not in searchable:
            continue
        rows.append(
            {
                **item.model_dump(),
                "ownerNickname": user_labels.get(item.ownerUserId, item.ownerUserId),
                "leadTitle": lead.title if lead else item.leadId,
                "itemCount": len(service.repo.list_response_package_items(item.id)),
            }
        )
    rows.sort(key=lambda row: row["createdAt"], reverse=True)
    return ApiResponse(data={"items": rows[:100], "total": len(rows)})


@router.get("/api/ops/supply-demand/cards", response_model=ApiResponse[dict])
def list_ops_supply_demand_cards(
    keyword: str | None = Query(default=None),
    status: str | None = Query(default=None),
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    service: AppService = Depends(get_app_service),
):
    _verify_admin_token(x_admin_token)
    statuses = {status} if status else None
    rows = [service._supply_demand_card_payload(item) for item in service.repo.list_supply_demand_cards(statuses=statuses, keyword=keyword)]
    return ApiResponse(data={"items": rows, "total": len(rows)})


@router.post("/api/ops/supply-demand/cards/{card_id}/review", response_model=ApiResponse[dict])
def review_ops_supply_demand_card(
    card_id: str,
    payload: SupplyDemandReviewRequest,
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    service: AppService = Depends(get_app_service),
):
    _verify_admin_token(x_admin_token)
    return ApiResponse(data=service.review_supply_demand_card(card_id, payload.status, payload.reviewNote))


@router.post("/api/ops/opportunity-push-digests/generate", response_model=ApiResponse[dict])
def generate_ops_opportunity_push_digests(
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    service: AppService = Depends(get_app_service),
):
    _verify_admin_token(x_admin_token)
    return ApiResponse(data=service.generate_opportunity_push_digests_for_active_subscriptions())


@router.post("/api/ops-admin/feedback", response_model=ApiResponse[dict])
def create_feedback_ticket(
    payload: FeedbackTicketCreateRequest,
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    store: OpsConsoleStore = Depends(get_ops_console_store),
):
    _verify_admin_token(x_admin_token)
    return ApiResponse(
        data=store.create_feedback_ticket(
            ticket_type=payload.type,
            content=payload.content,
            user_id=payload.userId,
            user_nickname=payload.userNickname,
            contact=payload.contact,
        )
    )


@router.patch("/api/ops-admin/feedback/{ticket_id}", response_model=ApiResponse[dict])
def update_feedback_ticket(
    ticket_id: str,
    payload: FeedbackTicketUpdateRequest,
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    store: OpsConsoleStore = Depends(get_ops_console_store),
):
    _verify_admin_token(x_admin_token)
    updated = store.update_feedback_ticket(
        ticket_id=ticket_id,
        status=payload.status,
        reply_text=payload.replyText,
        reward_note=payload.rewardNote,
        operator_name=payload.operatorName,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="反馈工单不存在")
    return ApiResponse(data=updated)


@router.get("/api/ops-admin/rule-learning-samples", response_model=ApiResponse[list[dict]])
def list_rule_learning_samples(
    status: str | None = Query(default=None),
    cardType: str | None = Query(default=None),
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    store: OpsConsoleStore = Depends(get_ops_console_store),
):
    _verify_admin_token(x_admin_token)
    return ApiResponse(data=store.list_rule_learning_samples(status=status, card_type=cardType))


@router.patch("/api/ops-admin/rule-learning-samples/{sample_id}", response_model=ApiResponse[dict])
def update_rule_learning_sample(
    sample_id: str,
    payload: RuleLearningSampleUpdateRequest,
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    store: OpsConsoleStore = Depends(get_ops_console_store),
):
    _verify_admin_token(x_admin_token)
    if payload.status and payload.status not in {"pending", "approved", "rejected", "published"}:
        raise HTTPException(status_code=400, detail="不支持的样本状态")
    updated = store.update_rule_learning_sample(
        sample_id,
        status=payload.status,
        operator_name=payload.operatorName,
        review_note=payload.reviewNote,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="规则样本不存在")
    return ApiResponse(data=updated)
