from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, Response

from app.api.dependencies import get_app_service, get_ops_console_store, get_sync_task_queue, get_wecom_client
from app.api.upload_utils import read_upload_with_limit
from app.core.config import settings
from app.schemas.common import ApiResponse
from app.schemas.ops_admin import (
    FeedbackTicketCreateRequest,
    FeedbackTicketUpdateRequest,
    CustomerInfoChainToggleRequest,
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
from app.services.wecom_bind_card_asset_service import WecomBindCardAssetService


router = APIRouter(tags=["ops-admin"])
OPS_INDEX_FILE = Path(__file__).resolve().parents[1] / "static" / "ops-admin" / "index.html"
OPS_PERIODS = {
    "today": (1, "今日"),
    "7d": (7, "近 7 日"),
    "30d": (30, "近 30 日"),
}


def _verify_admin_token(provided_token: str | None) -> None:
    if not settings.admin_token:
        raise HTTPException(status_code=403, detail="WECOM_ADMIN_TOKEN is not configured")
    if provided_token != settings.admin_token:
        raise HTTPException(status_code=403, detail="admin token verification failed")


@router.get("/api/ops-admin/referral-withdrawals", response_model=ApiResponse[dict])
def list_ops_referral_withdrawals(
    status: str | None = Query(default=None),
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    service: AppService = Depends(get_app_service),
):
    _verify_admin_token(x_admin_token)
    return ApiResponse(
        data={
            "items": service.list_referral_withdrawals(status=status),
            "minimumWithdrawalFen": service.referral_withdrawal_min_amount_fen(),
        }
    )


@router.post("/api/ops-admin/referral-withdrawals/{withdrawal_id}/approve", response_model=ApiResponse[dict])
def approve_ops_referral_withdrawal(
    withdrawal_id: str,
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    service: AppService = Depends(get_app_service),
):
    _verify_admin_token(x_admin_token)
    return ApiResponse(data=service.approve_referral_withdrawal(withdrawal_id))


@router.post("/api/ops-admin/referral-withdrawals/{withdrawal_id}/query", response_model=ApiResponse[dict])
def query_ops_referral_withdrawal(
    withdrawal_id: str,
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    service: AppService = Depends(get_app_service),
):
    _verify_admin_token(x_admin_token)
    return ApiResponse(data=service.query_referral_withdrawal(withdrawal_id))


@router.post("/api/ops-admin/referral-withdrawals/{withdrawal_id}/settle", response_model=ApiResponse[dict])
def settle_ops_referral_withdrawal(
    withdrawal_id: str,
    reason: str = Query(default="已核实微信到账"),
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    service: AppService = Depends(get_app_service),
):
    _verify_admin_token(x_admin_token)
    return ApiResponse(data=service.settle_referral_withdrawal_manually(withdrawal_id, reason))


@router.post("/api/ops-admin/referral-withdrawals/{withdrawal_id}/cancel", response_model=ApiResponse[dict])
def cancel_ops_referral_withdrawal(
    withdrawal_id: str,
    reason: str = Query(default="运营人工撤销"),
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    service: AppService = Depends(get_app_service),
):
    _verify_admin_token(x_admin_token)
    return ApiResponse(data=service.cancel_referral_withdrawal(withdrawal_id, reason))


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


def _period_config(period: str | None) -> tuple[str, int, str]:
    key = str(period or "today").strip().lower()
    if key not in OPS_PERIODS:
        raise HTTPException(status_code=400, detail="时间范围只支持 today、7d 或 30d")
    days, label = OPS_PERIODS[key]
    return key, days, label


def _period_start(period: str | None) -> tuple[str, int, str, datetime]:
    key, days, label = _period_config(period)
    return key, days, label, _today_start() - timedelta(days=days - 1)


def _period_metadata(period_key: str, period_days: int, period_label: str, period_start: datetime) -> dict:
    now = datetime.now(tz=SHANGHAI)
    if period_key == "today":
        range_label = f"{period_start:%Y-%m-%d} 00:00—{now:%H:%M}"
    else:
        range_label = f"{period_start:%Y-%m-%d}—{now:%Y-%m-%d}"
    return {
        "key": period_key,
        "days": period_days,
        "label": period_label,
        "startAt": period_start.isoformat(),
        "endAt": now.isoformat(),
        "rangeLabel": range_label,
        "generatedAt": now.isoformat(),
    }


def _is_since(value: str | None, start: datetime) -> bool:
    parsed = _parse_datetime(value)
    return bool(parsed and parsed >= start)


def _is_note_updated_since(note, start: datetime) -> bool:
    updated_at = _parse_datetime(note.updatedAt)
    created_at = _parse_datetime(note.createdAt)
    return bool(updated_at and updated_at >= start and created_at and updated_at > created_at)


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
        "anonymousVisitors": defaultdict(set),
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
            if not event.viewerUserId and event.anonymousId:
                counters["anonymousVisitors"][parsed.date().isoformat()].add(event.anonymousId)
    return [
        {
            "date": date_key,
            "users": counters["users"][date_key],
            "notes": counters["notes"][date_key],
            "showcases": counters["showcases"][date_key],
            "actions": counters["actions"][date_key],
            "showcaseViews": counters["showcaseViews"][date_key],
            "anonymousVisitors": len(counters["anonymousVisitors"][date_key]),
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


def _visitor_key(event) -> str:
    return str(event.viewerUserId or event.anonymousId or event.sessionId or event.id)


def _visitor_stats(items: list) -> dict:
    visitor_keys = Counter(_visitor_key(item) for item in items)
    anonymous_keys = {
        str(item.anonymousId)
        for item in items
        if not item.viewerUserId and item.anonymousId
    }
    return {
        "views": len(items),
        "uniqueVisitors": len(visitor_keys),
        "anonymousUniqueVisitors": len(anonymous_keys),
        "repeatVisitors": sum(1 for count in visitor_keys.values() if count >= 2),
    }


def _build_activation_funnel(state, period_start: datetime, anonymous_unique_visitors: int) -> dict:
    users_in_period = {
        item.id
        for item in state.users
        if _is_since(item.createdAt, period_start)
    }
    notes_in_period = [
        item for item in state.user_notes if _is_since(item.createdAt, period_start)
    ]
    showcases_in_period = [
        item for item in state.showcase_pages if _is_since(item.createdAt, period_start)
    ]

    first_note_at: dict[str, datetime] = {}
    for note in state.user_notes:
        parsed = _parse_datetime(note.createdAt)
        if not parsed:
            continue
        current = first_note_at.get(note.ownerUserId)
        if current is None or parsed < current:
            first_note_at[note.ownerUserId] = parsed

    first_showcase_at: dict[str, datetime] = {}
    for showcase in state.showcase_pages:
        parsed = _parse_datetime(showcase.createdAt)
        if not parsed:
            continue
        current = first_showcase_at.get(showcase.ownerUserId)
        if current is None or parsed < current:
            first_showcase_at[showcase.ownerUserId] = parsed

    first_note_users = {
        owner_id for owner_id, created_at in first_note_at.items()
        if created_at >= period_start and owner_id in users_in_period
    }
    first_showcase_users = {
        owner_id for owner_id, created_at in first_showcase_at.items()
        if created_at >= period_start and owner_id in users_in_period
    }
    first_content_users = first_note_users | first_showcase_users
    published_users = {
        item.ownerUserId for item in notes_in_period
        if item.shareState == "published"
    }
    published_users.update(
        item.ownerUserId for item in showcases_in_period
        if item.status == "published" or item.publishedAt
    )
    published_users &= users_in_period
    shared_users = {
        item.ownerUserId for item in state.showcase_events
        if item.eventType == "share"
        and _is_since(item.createdAt, period_start)
        and item.ownerUserId in users_in_period
    }
    high_intent_keys = {"lead-contact", "appointment", "order-intent", "relay-intent", "consult-click"}
    signal_users = {
        item.ownerUserId for item in state.customer_actions
        if item.actionKey in high_intent_keys
        and _is_since(item.createdAt, period_start)
        and item.ownerUserId in users_in_period
    }

    values = [
        ("anonymousVisitors", "匿名独立访客", anonymous_unique_visitors),
        ("newUsers", "新增注册用户", len(users_in_period)),
        ("firstContentUsers", "首次创建内容", len(first_content_users)),
        ("publishedUsers", "首次发布", len(published_users)),
        ("sharedUsers", "首次发客户", len(shared_users)),
        ("signalUsers", "产生客户信号", len(signal_users)),
    ]
    stages = []
    for index, (key, label, value) in enumerate(values):
        previous = values[index - 1][2] if index else 0
        stages.append({
            "key": key,
            "label": label,
            "value": value,
            "conversionRate": round(value / previous * 100, 1) if previous else None,
        })
    return {
        "stages": stages,
        "branches": [
            {"key": "firstNotes", "label": "首次新建资料", "value": len(first_note_users)},
            {"key": "firstShowcases", "label": "首次新建合集", "value": len(first_showcase_users)},
        ],
        "attributionNote": "匿名访客按匿名 ID 去重；匿名访客与注册用户尚未做跨身份合并，首段比例仅作参考。",
    }


def _customer_operations(state, store: OpsConsoleStore, period: str = "today") -> dict:
    """Build operator metrics from persisted customer, order and queue facts.

    This deliberately returns counts and follow-up work, not customer contact
    fields.  The PC console is for operating the product; it should not become
    an unbounded export endpoint for phone numbers or WeChat IDs.
    """
    period_key, period_days, period_label, selected_start = _period_start(period)
    now = datetime.now(tz=SHANGHAI)
    today_start = _today_start()
    seven_days_start = today_start - timedelta(days=6)
    view_events = [item for item in state.showcase_events if item.eventType == "view"]
    today_views = [item for item in view_events if _is_since(item.createdAt, today_start)]
    seven_day_views = [item for item in view_events if _is_since(item.createdAt, seven_days_start)]
    selected_views = [item for item in view_events if _is_since(item.createdAt, selected_start)]

    high_intent_keys = {"lead-contact", "appointment", "order-intent", "relay-intent", "consult-click"}
    today_actions = [item for item in state.customer_actions if _is_since(item.createdAt, today_start)]
    seven_day_actions = [item for item in state.customer_actions if _is_since(item.createdAt, seven_days_start)]
    selected_actions = [item for item in state.customer_actions if _is_since(item.createdAt, selected_start)]
    today_high_intent = [item for item in today_actions if str(item.actionKey) in high_intent_keys]
    selected_high_intent = [item for item in selected_actions if str(item.actionKey) in high_intent_keys]
    pending_followups = [item for item in state.lead_reminders if item.status in {"pending", "following", "contacted"}]
    due_followups = []
    for item in pending_followups:
        follow_up_at = _parse_datetime(item.nextFollowUpAt)
        if follow_up_at and follow_up_at <= now:
            due_followups.append(item)
    user_labels = _user_label_map(state)
    follow_up_rows = sorted(
        pending_followups,
        key=lambda item: item.nextFollowUpAt or item.updatedAt or item.createdAt,
    )[:20]

    def paid_at_today(order) -> bool:
        return bool(order.paymentChannel == "wechat_pay" and order.status == "paid" and _is_since(order.paidAt, today_start))

    def paid_at_seven_days(order) -> bool:
        return bool(order.paymentChannel == "wechat_pay" and order.status == "paid" and _is_since(order.paidAt, seven_days_start))

    wechat_order_ids = {
        item.id for item in state.membership_orders if item.paymentChannel == "wechat_pay"
    }
    orders_today = [
        item for item in state.membership_orders
        if item.paymentChannel == "wechat_pay" and _is_since(item.createdAt, today_start)
    ]
    period_orders = [
        item for item in state.membership_orders
        if item.paymentChannel == "wechat_pay" and _is_since(item.createdAt, selected_start)
    ]
    paid_today = [item for item in state.membership_orders if paid_at_today(item)]
    paid_seven_days = [item for item in state.membership_orders if paid_at_seven_days(item)]
    period_paid = [
        item for item in state.membership_orders
        if item.paymentChannel == "wechat_pay"
        and item.status == "paid"
        and _is_since(item.paidAt, selected_start)
    ]
    active_member_ids = {
        item.userId
        for item in state.membership_entitlements
        if item.status == "active"
        and item.sourceOrderId in wechat_order_ids
        and (_parse_datetime(item.expiresAt) or now) > now
    }
    subscription_counts = Counter(item.status for item in state.wechat_subscription_deliveries)
    archive_unprocessed = [item for item in state.wecom_archive_messages if not item.processedAt]
    archive_failed = [item for item in state.wecom_archive_messages if item.processError]
    today_media_assets = [item for item in state.media_assets if _is_since(item.createdAt, today_start)]
    period_media_assets = [item for item in state.media_assets if _is_since(item.createdAt, selected_start)]
    total_original_bytes = sum(int(item.originalSize or 0) for item in state.media_assets)
    total_stored_bytes = sum(int(item.storedSize or 0) for item in state.media_assets)

    return {
        "feature": store.get_customer_info_chain_config(),
        "period": {
            **_period_metadata(period_key, period_days, period_label, selected_start),
            **_visitor_stats(selected_views),
            "customerActions": len(selected_actions),
            "highIntentActions": len(selected_high_intent),
            "paidOrders": len(period_paid),
            "paidRevenueFen": sum(int(item.amountFen or 0) for item in period_paid),
            "mediaAssets": len(period_media_assets),
        },
        "today": {
            **_visitor_stats(today_views),
            "customerActions": len(today_actions),
            "highIntentActions": len(today_high_intent),
            "newLeads": sum(1 for item in state.lead_reminders if _is_since(item.createdAt, today_start)),
            "pendingFollowUps": len(pending_followups),
            "dueFollowUps": len(due_followups),
        },
        "sevenDays": {
            **_visitor_stats(seven_day_views),
            "customerActions": len(seven_day_actions),
            "highIntentActions": sum(1 for item in seven_day_actions if str(item.actionKey) in high_intent_keys),
        },
        "payment": {
            "channel": "wechat_pay",
            "channelLabel": "普通微信支付",
            "activeMemberships": len(active_member_ids),
            "todayOrders": len(orders_today),
            "todayPaidOrders": len(paid_today),
            "todayPendingOrders": sum(1 for item in orders_today if item.status == "pending"),
            "todayRefundedOrders": sum(1 for item in orders_today if item.status == "refunded"),
            "todayPaidRevenueFen": sum(int(item.amountFen or 0) for item in paid_today),
            "sevenDayPaidRevenueFen": sum(int(item.amountFen or 0) for item in paid_seven_days),
            "todayWechatPayOrders": sum(1 for item in paid_today if item.paymentChannel == "wechat_pay"),
            "periodOrders": len(period_orders),
            "periodPaidOrders": len(period_paid),
            "periodPaidRevenueFen": sum(int(item.amountFen or 0) for item in period_paid),
        },
        "followUps": [
            {
                "id": item.id,
                "ownerUserId": item.ownerUserId,
                "ownerLabel": user_labels.get(item.ownerUserId, item.ownerUserId),
                "nickname": item.nickname or "未命名客户",
                "status": item.status,
                "intentLevel": item.intentLevel,
                "viewCount": item.viewCount,
                "nextFollowUpAt": item.nextFollowUpAt,
                "updatedAt": item.updatedAt,
            }
            for item in follow_up_rows
        ],
        "queues": {
            "subscriptionQueued": subscription_counts["queued"],
            "subscriptionSending": subscription_counts["sending"],
            "subscriptionFailed": subscription_counts["failed"],
            "archiveUnprocessed": len(archive_unprocessed),
            "archiveFailed": len(archive_failed),
            "todayMediaAssets": len(today_media_assets),
            "periodMediaAssets": len(period_media_assets),
            "mediaOriginalBytes": total_original_bytes,
            "mediaStoredBytes": total_stored_bytes,
            "mediaAssetCount": len(state.media_assets),
            "mediaReferenceCount": len(state.media_asset_refs),
        },
    }


@router.get("/ops")
def ops_console_page():
    return FileResponse(
        OPS_INDEX_FILE,
        headers={"Cache-Control": "no-store, max-age=0"},
    )


@router.get("/api/ops-admin/customer-info-chain", response_model=ApiResponse[dict])
def get_customer_info_chain_config(
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    store: OpsConsoleStore = Depends(get_ops_console_store),
):
    _verify_admin_token(x_admin_token)
    return ApiResponse(data=store.get_customer_info_chain_config())


@router.put("/api/ops-admin/customer-info-chain", response_model=ApiResponse[dict])
def update_customer_info_chain_config(
    payload: CustomerInfoChainToggleRequest,
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    store: OpsConsoleStore = Depends(get_ops_console_store),
):
    _verify_admin_token(x_admin_token)
    if payload.enabled is None and payload.paymentRequired is None:
        raise HTTPException(status_code=400, detail="至少提供一个客户信息链配置项")
    return ApiResponse(data=store.set_customer_info_chain_config(
        enabled=payload.enabled,
        payment_required=payload.paymentRequired,
        operator_name=payload.operatorName,
    ))


@router.get("/api/ops-admin/wecom-bind-card-asset", response_model=ApiResponse[dict])
def get_wecom_bind_card_asset_status(
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    service: AppService = Depends(get_app_service),
    client: WecomClient = Depends(get_wecom_client),
):
    _verify_admin_token(x_admin_token)
    return ApiResponse(data=WecomBindCardAssetService(service.repo, client, settings).status())


@router.post("/api/ops-admin/wecom-bind-card-asset", response_model=ApiResponse[dict])
async def upload_wecom_bind_card_asset(
    file: UploadFile = File(...),
    operator_name: str = Form(default="ops"),
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    service: AppService = Depends(get_app_service),
    client: WecomClient = Depends(get_wecom_client),
):
    _verify_admin_token(x_admin_token)
    content = await read_upload_with_limit(
        file,
        settings.wecom_bind_card_max_bytes,
        "绑定卡片封面不能超过2MB",
    )
    asset_service = WecomBindCardAssetService(service.repo, client, settings)
    try:
        asset = await asset_service.upload_source(content, file.filename or "wecom-bind-card.png", file.content_type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except WecomClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="上传企业微信绑定卡片封面失败") from exc
    return ApiResponse(
        message=f"绑定卡片封面已更新（操作人：{operator_name.strip() or 'ops'}）",
        data=asset_service.status(),
    )


@router.post("/api/ops-admin/wecom-bind-card-asset/refresh", response_model=ApiResponse[dict])
async def refresh_wecom_bind_card_asset(
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    service: AppService = Depends(get_app_service),
    client: WecomClient = Depends(get_wecom_client),
):
    _verify_admin_token(x_admin_token)
    try:
        asset_service = WecomBindCardAssetService(service.repo, client, settings)
        await asset_service.refresh()
    except WecomClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return ApiResponse(data=asset_service.status())


@router.get("/api/ops-admin/customer-operations", response_model=ApiResponse[dict])
def get_customer_operations(
    period: str = Query(default="today"),
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    service: AppService = Depends(get_app_service),
    store: OpsConsoleStore = Depends(get_ops_console_store),
):
    _verify_admin_token(x_admin_token)
    _period_config(period)
    return ApiResponse(data=_customer_operations(service.repo.load(), store, period))


@router.get("/api/ops-admin/overview", response_model=ApiResponse[dict])
def get_ops_admin_overview(
    period: str = Query(default="today"),
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    service: AppService = Depends(get_app_service),
    sync_task_queue: SyncTaskQueue = Depends(get_sync_task_queue),
    store: OpsConsoleStore = Depends(get_ops_console_store),
):
    _verify_admin_token(x_admin_token)
    period_key, period_days, period_label, selected_start = _period_start(period)
    state = service.repo.load()
    today_start = _today_start()
    selected_users = [item for item in state.users if _is_since(item.createdAt, selected_start)]
    selected_notes = [item for item in state.user_notes if _is_since(item.createdAt, selected_start)]
    selected_updated_notes = [item for item in state.user_notes if _is_note_updated_since(item, selected_start)]
    selected_showcases = [item for item in state.showcase_pages if _is_since(item.createdAt, selected_start)]
    selected_actions = [item for item in state.customer_actions if _is_since(item.createdAt, selected_start)]
    selected_showcase_views = [
        item for item in state.showcase_events
        if item.eventType == "view" and _is_since(item.createdAt, selected_start)
    ]
    today_user_count = sum(1 for item in state.users if _is_since(item.createdAt, today_start))
    today_note_count = sum(1 for item in state.user_notes if _is_since(item.createdAt, today_start))
    today_updated_note_count = sum(1 for item in state.user_notes if _is_note_updated_since(item, today_start))
    today_showcase_count = sum(1 for item in state.showcase_pages if _is_since(item.createdAt, today_start))
    today_action_count = sum(1 for item in state.customer_actions if _is_since(item.createdAt, today_start))
    today_showcase_views = sum(1 for item in state.showcase_events if item.eventType == "view" and _is_since(item.createdAt, today_start))
    notifications = service.list_import_notifications()
    today_notification_count = sum(1 for item in notifications if _is_since(item.get("sentAt"), today_start))
    selected_notification_count = sum(1 for item in notifications if _is_since(item.get("sentAt"), selected_start))
    queue = _system_queue(service, sync_task_queue)
    customer_operations = _customer_operations(state, store, period_key)
    selected_visitors = _visitor_stats(selected_showcase_views)
    selected_paid_orders = [
        item for item in state.membership_orders
        if item.paymentChannel == "wechat_pay"
        and item.status == "paid"
        and _is_since(item.paidAt, selected_start)
    ]

    showcase_by_id = {item.id: item for item in state.showcase_pages}
    showcase_open_counter: dict[str, int] = defaultdict(int)
    for event in state.showcase_events:
        if event.eventType == "view":
            showcase_open_counter[event.showcaseId] += 1
    top_showcase = None
    if selected_showcase_views:
        showcase_open_counter = defaultdict(int)
        for event in selected_showcase_views:
            showcase_open_counter[event.showcaseId] += 1
        top_showcase_id = max(showcase_open_counter.items(), key=lambda item: item[1])[0]
        showcase = showcase_by_id.get(top_showcase_id)
        top_showcase = {
            "showcaseId": top_showcase_id,
            "name": showcase.name if showcase else top_showcase_id,
            "ownerUserId": showcase.ownerUserId if showcase else None,
            "openCount": showcase_open_counter[top_showcase_id],
        }

    period_summary = {
        **_period_metadata(period_key, period_days, period_label, selected_start),
        "newUsers": len(selected_users),
        "newNotes": len(selected_notes),
        "updatedNotes": len(selected_updated_notes),
        "newShowcases": len(selected_showcases),
        "customerActions": len(selected_actions),
        "showcaseViews": len(selected_showcase_views),
        "anonymousUniqueVisitors": selected_visitors["anonymousUniqueVisitors"],
        "uniqueVisitors": selected_visitors["uniqueVisitors"],
        "highIntentActions": customer_operations["period"]["highIntentActions"],
        "notifications": selected_notification_count,
        "paidRevenueFen": sum(int(item.amountFen or 0) for item in selected_paid_orders),
    }

    return ApiResponse(
        data={
            "period": period_summary,
            "summary": {
                "period": period_key,
                "periodDays": period_days,
                "periodLabel": period_label,
                "todayNewUsers": today_user_count,
                "todayNewNotes": today_note_count,
                "todayUpdatedNotes": today_updated_note_count,
                "todayNewShowcases": today_showcase_count,
                "todayCustomerActions": today_action_count,
                "todayShowcaseViews": today_showcase_views,
                "todayNotifications": today_notification_count,
                "customerInfoChainEnabled": customer_operations["feature"]["enabled"],
                "todayUniqueVisitors": customer_operations["today"]["uniqueVisitors"],
                "todayHighIntentActions": customer_operations["today"]["highIntentActions"],
                "pendingFollowUps": customer_operations["today"]["pendingFollowUps"],
                "activeMemberships": customer_operations["payment"]["activeMemberships"],
                "todayPaidRevenueFen": customer_operations["payment"]["todayPaidRevenueFen"],
                "periodNewUsers": period_summary["newUsers"],
                "periodNewNotes": period_summary["newNotes"],
                "periodUpdatedNotes": period_summary["updatedNotes"],
                "periodNewShowcases": period_summary["newShowcases"],
                "periodCustomerActions": period_summary["customerActions"],
                "periodShowcaseViews": period_summary["showcaseViews"],
                "periodNotifications": period_summary["notifications"],
                "periodUniqueVisitors": period_summary["uniqueVisitors"],
                "periodAnonymousUniqueVisitors": period_summary["anonymousUniqueVisitors"],
                "periodHighIntentActions": period_summary["highIntentActions"],
                "periodPaidRevenueFen": period_summary["paidRevenueFen"],
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
            "trend": _build_trend(period_days, state),
            "trend7d": _build_trend(7, state),
            "funnel": _build_activation_funnel(
                state,
                selected_start,
                period_summary["anonymousUniqueVisitors"],
            ),
            "customerOperations": customer_operations,
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


_OVERVIEW_DETAIL_LABELS = {
    "anonymousVisitors": "匿名独立访客",
    "newUsers": "新增用户",
    "newNotes": "新增资料",
    "updatedNotes": "资料更新",
    "newShowcases": "新增合集",
    "customerActions": "客户动作",
    "showcaseViews": "展示页打开",
    "notifications": "导入通知",
    "highIntentActions": "高意向动作",
    "pendingNotifications": "待发送通知",
    "pendingIssues": "待处理异常",
    "pendingFollowUps": "待跟进客户",
    "activeMemberships": "有效会员",
    "paidRevenue": "微信支付收入",
}

_OVERVIEW_DETAIL_DEFINITIONS = {
    "anonymousVisitors": "按匿名标识去重后的展示页访客，不把匿名访客识别为实名用户。",
    "newUsers": "用户注册记录的 createdAt 落在所选时间范围内。",
    "newNotes": "资料创建记录的 createdAt 落在所选时间范围内。",
    "updatedNotes": "资料的 updatedAt 落在所选时间范围内，且晚于 createdAt，表示已有资料被编辑更新。",
    "newShowcases": "合集创建记录的 createdAt 落在所选时间范围内。",
    "customerActions": "客户动作记录的 createdAt 落在所选时间范围内。",
    "showcaseViews": "展示页 view 事件的 createdAt 落在所选时间范围内。",
    "notifications": "导入通知 sentAt 落在所选时间范围内。",
    "highIntentActions": "咨询、留资、预约、下单意向等高意向客户动作。",
    "pendingNotifications": "当前 sendStatus 为 pending 的导入通知。",
    "pendingIssues": "当前导入、媒体和同步队列中的失败或重试异常。",
    "pendingFollowUps": "当前状态为 pending、following 或 contacted 的跟进客户。",
    "activeMemberships": "当前未过期且状态为 active 的客户信息链会员权益。",
    "paidRevenue": "微信支付订单中已支付且 paidAt 落在所选时间范围内的收入。",
}

_CURRENT_OVERVIEW_DETAIL_METRICS = {
    "pendingNotifications",
    "pendingIssues",
    "pendingFollowUps",
    "activeMemberships",
}


def _overview_detail_row(time_value: str | None, title: str, detail: str = "", status: str = "") -> dict:
    return {
        "time": time_value,
        "title": title or "-",
        "detail": detail or "-",
        "status": status or "-",
    }


_OVERVIEW_DEFAULT_PROFILE_NICKNAMES = {"", "微信用户", "未设置昵称", "微信客户"}


def _overview_user_label(user, *, missing_label: str = "已登录用户（资料未同步）") -> str:
    if not user:
        return missing_label
    nickname = str(user.nickname or "").strip()
    if nickname and nickname not in _OVERVIEW_DEFAULT_PROFILE_NICKNAMES:
        return nickname
    return "微信用户（未设置昵称）"


def _overview_identity_label(
    user_id: str | None,
    users: dict[str, object],
    *,
    anonymous_label: str = "匿名访客（未登录）",
) -> str:
    if not user_id:
        return anonymous_label
    return _overview_user_label(users.get(user_id))


def _sort_overview_detail_rows(rows: list[dict]) -> list[dict]:
    minimum = datetime.min.replace(tzinfo=SHANGHAI)
    return sorted(rows, key=lambda item: _parse_datetime(item.get("time")) or minimum, reverse=True)


def _overview_detail_rows(
    state,
    metric: str,
    period_start: datetime,
    service: AppService,
    sync_task_queue: SyncTaskQueue,
) -> tuple[int, list[dict]]:
    users = {item.id: item for item in state.users}
    notes = {item.id: item for item in state.user_notes}
    showcases = {item.id: item for item in state.showcase_pages}
    user_label = lambda user_id: _overview_identity_label(
        user_id,
        users,
        anonymous_label="未命名运营用户",
    )
    view_events = [
        item for item in state.showcase_events
        if item.eventType == "view" and _is_since(item.createdAt, period_start)
    ]
    selected_actions = [item for item in state.customer_actions if _is_since(item.createdAt, period_start)]
    high_intent_keys = {"lead-contact", "appointment", "order-intent", "relay-intent", "consult-click"}

    if metric == "anonymousVisitors":
        grouped: dict[str, dict] = {}
        for event in view_events:
            if event.viewerUserId or not event.anonymousId:
                continue
            key = str(event.anonymousId)
            current = grouped.setdefault(key, {
                "time": event.createdAt,
                "title": "匿名访客（未登录）",
                "detail": "",
                "status": "匿名",
                "viewCount": 0,
            })
            current["viewCount"] += 1
            event_time = _parse_datetime(event.createdAt)
            current_time = _parse_datetime(current["time"])
            if event_time and (not current_time or event_time > current_time):
                current["time"] = event.createdAt
            showcase = showcases.get(event.showcaseId)
            source = showcase.name if showcase else event.showcaseId
            current["detail"] = f"查看 {current['viewCount']} 次 · 最近资料：{source}"
        rows = list(grouped.values())
        return len(rows), _sort_overview_detail_rows(rows)

    if metric == "newUsers":
        rows = []
        for item in state.users:
            if not _is_since(item.createdAt, period_start):
                continue
            label = _overview_user_label(item)
            profile_status = "已注册 · 已设置昵称" if label != "微信用户（未设置昵称）" else "已注册 · 未设置昵称"
            rows.append(_overview_detail_row(
                item.createdAt,
                label,
                f"登录身份：已登录 · 用户 ID：{item.id}",
                profile_status,
            ))
        return len(rows), _sort_overview_detail_rows(rows)

    if metric == "newNotes":
        rows = [
            _overview_detail_row(
                item.createdAt,
                item.title,
                f"{user_label(item.ownerUserId)} · 资料 ID：{item.id}",
                item.status,
            )
            for item in state.user_notes if _is_since(item.createdAt, period_start)
        ]
        return len(rows), _sort_overview_detail_rows(rows)

    if metric == "updatedNotes":
        rows = [
            _overview_detail_row(
                item.updatedAt,
                item.title,
                f"{user_label(item.ownerUserId)} · 资料 ID：{item.id} · 创建于：{item.createdAt}",
                "已更新",
            )
            for item in state.user_notes if _is_note_updated_since(item, period_start)
        ]
        return len(rows), _sort_overview_detail_rows(rows)

    if metric == "newShowcases":
        rows = [
            _overview_detail_row(
                item.createdAt,
                item.name,
                f"{user_label(item.ownerUserId)} · 合集 ID：{item.id}",
                item.status,
            )
            for item in state.showcase_pages if _is_since(item.createdAt, period_start)
        ]
        return len(rows), _sort_overview_detail_rows(rows)

    if metric in {"customerActions", "highIntentActions"}:
        actions = selected_actions
        if metric == "highIntentActions":
            actions = [item for item in actions if str(item.actionKey) in high_intent_keys]
        rows = []
        for item in actions:
            note = notes.get(item.noteId)
            viewer = _overview_identity_label(item.viewerUserId, users)
            source = note.title if note else item.noteId
            rows.append(_overview_detail_row(
                item.createdAt,
                item.actionLabel or item.actionKey,
                f"{viewer} · 来源：{source}",
                item.actionKey,
            ))
        return len(rows), _sort_overview_detail_rows(rows)

    if metric == "showcaseViews":
        rows = []
        for item in view_events:
            showcase = showcases.get(item.showcaseId)
            viewer = _overview_identity_label(item.viewerUserId, users)
            rows.append(_overview_detail_row(
                item.createdAt,
                showcase.name if showcase else item.showcaseId,
                f"{viewer} · {item.viewType}",
                f"停留 {item.durationSeconds or 0} 秒",
            ))
        return len(rows), _sort_overview_detail_rows(rows)

    if metric == "notifications":
        rows = [
            _overview_detail_row(
                item.get("sentAt"),
                item.get("title") or "导入通知",
                f"{item.get('channel') or '-'} · {item.get('message') or ''}"[:180],
                item.get("sendStatus") or item.get("status") or "-",
            )
            for item in service.list_import_notifications()
            if _is_since(item.get("sentAt"), period_start)
        ]
        return len(rows), _sort_overview_detail_rows(rows)

    if metric == "paidRevenue":
        rows = [
            _overview_detail_row(
                item.paidAt,
                user_label(item.userId),
                f"订单：{item.id} · 方案：{item.planCode}",
                f"¥{int(item.amountFen or 0) / 100:.2f}",
            )
            for item in state.membership_orders
            if item.paymentChannel == "wechat_pay"
            and item.status == "paid"
            and _is_since(item.paidAt, period_start)
        ]
        return len(rows), _sort_overview_detail_rows(rows)

    if metric == "pendingNotifications":
        items = [item for item in service.list_import_notifications() if item.get("sendStatus") == "pending"]
        rows = [
            _overview_detail_row(
                item.get("sentAt"),
                item.get("title") or "导入通知",
                item.get("channel") or "-",
                item.get("sendStatus") or "pending",
            )
            for item in items
        ]
        return len(rows), _sort_overview_detail_rows(rows)

    if metric == "pendingFollowUps":
        items = [item for item in state.lead_reminders if item.status in {"pending", "following", "contacted"}]
        rows = [
            _overview_detail_row(
                item.nextFollowUpAt or item.updatedAt or item.createdAt,
                item.nickname or "未命名客户",
                f"{user_label(item.ownerUserId)} · 浏览 {item.viewCount} 次",
                item.status,
            )
            for item in items
        ]
        return len(rows), _sort_overview_detail_rows(rows)

    if metric == "activeMemberships":
        now = datetime.now(tz=SHANGHAI)
        order_ids = {item.id for item in state.membership_orders if item.paymentChannel == "wechat_pay"}
        items = [
            item for item in state.membership_entitlements
            if item.status == "active"
            and item.sourceOrderId in order_ids
            and (_parse_datetime(item.expiresAt) or now) > now
        ]
        rows = [
            _overview_detail_row(
                item.updatedAt,
                user_label(item.userId),
                f"权益：{item.entitlementKey} · 到期：{item.expiresAt}",
                "有效",
            )
            for item in items
        ]
        return len(rows), _sort_overview_detail_rows(rows)

    if metric == "pendingIssues":
        queue = _system_queue(service, sync_task_queue)
        rows = []
        for item in queue["importFailures"].get("notifications", []):
            rows.append(_overview_detail_row(item.get("sentAt"), item.get("title") or "导入通知失败", item.get("message") or "-", "导入失败"))
        for item in queue["importFailures"].get("skillRuns", []):
            rows.append(_overview_detail_row(item.get("startedAt"), item.get("skillId") or "技能运行失败", item.get("errorMessage") or "-", "技能失败"))
        for item in queue["failedMedia"]:
            rows.append(_overview_detail_row(item.get("updatedAt"), item.get("mediaId") or "媒体资产", "媒体转存或处理失败", "媒体失败"))
        for item in queue["failedSyncTasks"]:
            rows.append(_overview_detail_row(item.get("updatedAt"), item.get("name") or "同步任务", item.get("error") or item.get("status") or "-", "同步异常"))
        return len(rows), _sort_overview_detail_rows(rows)

    raise HTTPException(status_code=400, detail="不支持的运营指标")


@router.get("/api/ops-admin/overview-detail", response_model=ApiResponse[dict])
def get_ops_admin_overview_detail(
    metric: str = Query(...),
    period: str = Query(default="today"),
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    service: AppService = Depends(get_app_service),
    sync_task_queue: SyncTaskQueue = Depends(get_sync_task_queue),
):
    _verify_admin_token(x_admin_token)
    period_key, period_days, period_label, period_start = _period_start(period)
    if metric not in _OVERVIEW_DETAIL_LABELS:
        raise HTTPException(status_code=400, detail="不支持的运营指标")
    total, rows = _overview_detail_rows(state=service.repo.load(), metric=metric, period_start=period_start, service=service, sync_task_queue=sync_task_queue)
    return ApiResponse(data={
        "metric": metric,
        "label": _OVERVIEW_DETAIL_LABELS[metric],
        "definition": _OVERVIEW_DETAIL_DEFINITIONS[metric],
        "scope": "current" if metric in _CURRENT_OVERVIEW_DETAIL_METRICS else "period",
        "period": _period_metadata(period_key, period_days, period_label, period_start),
        "total": total,
        "items": rows[:100],
        "truncated": max(total - 100, 0),
    })


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
        content = await read_upload_with_limit(file, 5 * 1024 * 1024, "群上传预览文件不能超过5MB")
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
        content = await read_upload_with_limit(file, 5 * 1024 * 1024, "群上传文件不能超过5MB")
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
