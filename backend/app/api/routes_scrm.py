from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from app.api.dependencies import get_app_service
from app.schemas.common import ApiResponse
from app.schemas.scrm import (
    MembershipCheckoutRequest,
    MembershipPaymentRequest,
    MutualHelpActivityRequest,
    MutualHelpTaskCreateRequest,
    MutualHelpTaskUpdateRequest,
    MutualHelpSubmissionCreateRequest,
    MutualHelpSubmissionApproveRequest,
    MutualHelpSubmissionRejectRequest,
    MutualHelpChatConversationRequest,
    MutualHelpChatMessageRequest,
    MutualHelpWoolUnlockRequest,
    MutualHelpCommentRequest,
    MutualHelpCommentReportRequest,
    MutualHelpTipRequest,
    MutualHelpWoolRefundRequest,
    MutualHelpPaymentRequest,
    MutualHelpRechargeRequest,
    MutualPointWithdrawalCreateRequest,
    CustomerFollowupEnsureRequest,
    CustomerFollowupActionRequest,
    ReferralBindRequest,
    ReferralShareBindRequest,
    SameStyleGenerateRequest,
    NotificationPreferenceRequest,
    NotificationSubscriptionRequest,
    TestPaymentConfirmRequest,
    TestPaymentRefundRequest,
    WithdrawalCreateRequest,
)
from app.services.app_service import AppService
from app.services.wechat_pay import WechatPayClient, WechatPayError


router = APIRouter(prefix="/api/scrm", tags=["sales-scrm"])


def _mutual_help_user_id(request: Request, fallback: str | None = None) -> str | None:
    if getattr(request.app.state, "production_auth_enabled", False):
        return str(getattr(request.state, "authenticated_user_id", "") or "").strip() or None
    return str(fallback or "").strip() or None


@router.get("/membership", response_model=ApiResponse[dict])
def membership_status(userId: str = Query(...), service: AppService = Depends(get_app_service)):
    return ApiResponse(data=service.get_membership_status(userId))


@router.get("/notification-config", response_model=ApiResponse[dict])
def notification_config(userId: str = Query(...), service: AppService = Depends(get_app_service)):
    return ApiResponse(data=service.get_notification_config(userId))


@router.get("/mutual-help", response_model=ApiResponse[dict])
def mutual_help_status(userId: str = Query(...), service: AppService = Depends(get_app_service)):
    return ApiResponse(data=service.get_mutual_help_status(userId))


@router.get("/mutual-help/tasks", response_model=ApiResponse[dict])
def list_mutual_help_tasks(
    request: Request,
    userId: str | None = Query(default=None),
    ownerOnly: bool = Query(default=False),
    taskId: str | None = Query(default=None),
    taskKind: str | None = Query(default=None),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=50),
    service: AppService = Depends(get_app_service),
):
    viewer_id = getattr(request.state, "authenticated_user_id", None) if getattr(request.app.state, "production_auth_enabled", False) else userId
    return ApiResponse(data=service.list_mutual_help_tasks(
        user_id=viewer_id,
        owner_only=ownerOnly,
        task_id=taskId,
        task_kind=taskKind,
        cursor=cursor,
        limit=limit,
    ))


@router.get("/mutual-help/tasks/{task_id}", response_model=ApiResponse[dict])
def get_mutual_help_task_detail(
    task_id: str,
    request: Request,
    userId: str | None = Query(default=None),
    service: AppService = Depends(get_app_service),
):
    viewer_id = getattr(request.state, "authenticated_user_id", None) if getattr(request.app.state, "production_auth_enabled", False) else userId
    return ApiResponse(data=service.get_mutual_help_task_detail(task_id, viewer_id))


@router.get("/mutual-help/tasks/{task_id}/share-snapshot", response_model=ApiResponse[dict])
def prepare_mutual_help_task_share_snapshot(
    task_id: str,
    styleId: str = Query(default="mutual_task_backend_v5"),
    fingerprint: str = Query(default=""),
    service: AppService = Depends(get_app_service),
):
    return ApiResponse(data=service.prepare_mutual_help_task_share_snapshot(task_id, style_id=styleId, fingerprint=fingerprint))


@router.post("/mutual-help/tasks", response_model=ApiResponse[dict])
def create_mutual_help_task(
    request: Request,
    payload: MutualHelpTaskCreateRequest,
    service: AppService = Depends(get_app_service),
):
    user_id = _mutual_help_user_id(request, payload.ownerUserId)
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录后发布任务")
    values = payload.model_dump()
    values["ownerUserId"] = user_id
    data = service.create_mutual_help_task(values)
    message = "任务已提交人工审核" if data.get("task", {}).get("status") == "pending_review" else "任务已发布"
    return ApiResponse(data=data, message=message)


@router.patch("/mutual-help/tasks/{task_id}", response_model=ApiResponse[dict])
def update_mutual_help_task(
    task_id: str,
    request: Request,
    payload: MutualHelpTaskUpdateRequest,
    service: AppService = Depends(get_app_service),
):
    user_id = _mutual_help_user_id(request, payload.ownerUserId)
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录后管理任务")
    return ApiResponse(data=service.update_mutual_help_task(task_id, user_id, payload.status))


@router.get("/mutual-help/tasks/{task_id}/submissions", response_model=ApiResponse[dict])
def list_mutual_help_submissions(
    task_id: str,
    request: Request,
    userId: str = Query(...),
    service: AppService = Depends(get_app_service),
):
    viewer_id = getattr(request.state, "authenticated_user_id", None) if getattr(request.app.state, "production_auth_enabled", False) else userId
    return ApiResponse(data=service.list_mutual_help_submissions(task_id, viewer_id or ""))


@router.get("/mutual-help/tasks/{task_id}/chat/participants", response_model=ApiResponse[dict])
def list_mutual_help_chat_participants(
    task_id: str,
    request: Request,
    userId: str = Query(..., min_length=1),
    service: AppService = Depends(get_app_service),
):
    user_id = _mutual_help_user_id(request, userId)
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录后查看沟通列表")
    return ApiResponse(data=service.list_mutual_help_chat_participants(task_id, user_id))


@router.post("/mutual-help/tasks/{task_id}/chat/conversation", response_model=ApiResponse[dict])
def open_mutual_help_conversation(
    task_id: str,
    request: Request,
    payload: MutualHelpChatConversationRequest,
    service: AppService = Depends(get_app_service),
):
    user_id = _mutual_help_user_id(request, payload.userId)
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录后开始沟通")
    return ApiResponse(data=service.open_mutual_help_conversation(task_id, user_id, payload.executorUserId))


@router.get("/mutual-help/chat/{conversation_id}/messages", response_model=ApiResponse[dict])
def list_mutual_help_chat_messages(
    conversation_id: str,
    request: Request,
    userId: str = Query(..., min_length=1),
    before: str | None = Query(default=None, max_length=80),
    limit: int = Query(default=50, ge=1, le=100),
    service: AppService = Depends(get_app_service),
):
    user_id = _mutual_help_user_id(request, userId)
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录后查看消息")
    return ApiResponse(data=service.list_mutual_help_chat_messages(conversation_id, user_id, before, limit))


@router.post("/mutual-help/chat/{conversation_id}/messages", response_model=ApiResponse[dict])
def send_mutual_help_chat_message(
    conversation_id: str,
    request: Request,
    payload: MutualHelpChatMessageRequest,
    service: AppService = Depends(get_app_service),
):
    user_id = _mutual_help_user_id(request, payload.userId)
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录后发送消息")
    return ApiResponse(data=service.send_mutual_help_chat_message(conversation_id, user_id, payload.model_dump()))


@router.get("/mutual-help/report", response_model=ApiResponse[dict])
def mutual_help_executor_report(
    request: Request,
    userId: str = Query(..., min_length=1),
    service: AppService = Depends(get_app_service),
):
    user_id = _mutual_help_user_id(request, userId)
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录后查看任务报表")
    return ApiResponse(data=service.get_mutual_help_executor_report(user_id))


@router.post("/mutual-help/tasks/{task_id}/submissions", response_model=ApiResponse[dict])
def create_mutual_help_submission(
    task_id: str,
    request: Request,
    payload: MutualHelpSubmissionCreateRequest,
    service: AppService = Depends(get_app_service),
):
    user_id = _mutual_help_user_id(request, payload.userId)
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录后提交任务")
    values = payload.model_dump()
    values["userId"] = user_id
    data = service.create_mutual_help_submission(task_id, user_id, values)
    message = "提交已进入人工复核" if data.get("submission", {}).get("status") == "reviewing" else "提交已保存"
    return ApiResponse(data=data, message=message)


@router.post("/mutual-help/tasks/{task_id}/submissions/{submission_id}/approve", response_model=ApiResponse[dict])
def approve_mutual_help_submission(
    task_id: str,
    submission_id: str,
    request: Request,
    payload: MutualHelpSubmissionApproveRequest,
    service: AppService = Depends(get_app_service),
):
    user_id = _mutual_help_user_id(request, payload.userId)
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录后验收任务")
    return ApiResponse(data=service.approve_mutual_help_submission(task_id, submission_id, user_id), message="已通过并结算")


@router.post("/mutual-help/tasks/{task_id}/submissions/{submission_id}/reject", response_model=ApiResponse[dict])
def reject_mutual_help_submission(
    task_id: str,
    submission_id: str,
    request: Request,
    payload: MutualHelpSubmissionRejectRequest,
    service: AppService = Depends(get_app_service),
):
    user_id = _mutual_help_user_id(request, payload.userId)
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录后退回任务")
    return ApiResponse(data=service.reject_mutual_help_submission(task_id, submission_id, user_id, payload.reason), message="已退回提交")


@router.post("/mutual-help/tasks/{task_id}/wool-unlock", response_model=ApiResponse[dict])
def unlock_mutual_help_wool(
    task_id: str,
    request: Request,
    payload: MutualHelpWoolUnlockRequest,
    service: AppService = Depends(get_app_service),
):
    user_id = _mutual_help_user_id(request, payload.userId)
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录后解锁羊毛任务")
    return ApiResponse(data=service.unlock_mutual_help_wool(task_id, user_id))


@router.post("/mutual-help/tasks/{task_id}/comments", response_model=ApiResponse[dict])
def add_mutual_help_comment(
    task_id: str,
    request: Request,
    payload: MutualHelpCommentRequest,
    service: AppService = Depends(get_app_service),
):
    user_id = _mutual_help_user_id(request, payload.userId)
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录后发表评论")
    values = payload.model_dump()
    values["userId"] = user_id
    data = service.add_mutual_help_comment(task_id, user_id, values)
    message = "评论已进入人工复核" if data.get("comment", {}).get("status") == "reviewing" else "评论已发布"
    return ApiResponse(data=data, message=message)


@router.post("/mutual-help/tasks/{task_id}/comments/{comment_id}/reports", response_model=ApiResponse[dict])
def report_mutual_help_comment(
    task_id: str,
    comment_id: str,
    request: Request,
    payload: MutualHelpCommentReportRequest,
    service: AppService = Depends(get_app_service),
):
    user_id = _mutual_help_user_id(request, payload.userId)
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录后举报评论")
    return ApiResponse(data=service.report_mutual_help_comment(task_id, comment_id, user_id, payload.reason))


@router.post("/mutual-help/tasks/{task_id}/tips", response_model=ApiResponse[dict])
def tip_mutual_help_publisher(
    task_id: str,
    request: Request,
    payload: MutualHelpTipRequest,
    service: AppService = Depends(get_app_service),
):
    user_id = _mutual_help_user_id(request, payload.userId)
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录后打赏")
    return ApiResponse(data=service.tip_mutual_help_publisher(task_id, user_id, payload.amount))


@router.post("/mutual-help/tasks/{task_id}/refunds", response_model=ApiResponse[dict])
def request_mutual_help_wool_refund(
    task_id: str,
    request: Request,
    payload: MutualHelpWoolRefundRequest,
    service: AppService = Depends(get_app_service),
):
    user_id = _mutual_help_user_id(request, payload.userId)
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录后申请退款")
    return ApiResponse(data=service.request_mutual_help_wool_refund(task_id, user_id, payload.reason))


@router.get("/mutual-help/ledger", response_model=ApiResponse[list[dict]])
def mutual_help_ledger(
    userId: str = Query(...),
    pointType: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    service: AppService = Depends(get_app_service),
):
    return ApiResponse(data=service.list_points_ledgers(userId, point_type=pointType, limit=limit))


@router.post("/mutual-help/recharge/orders", response_model=ApiResponse[dict])
def create_mutual_help_recharge_order(
    payload: MutualHelpRechargeRequest,
    service: AppService = Depends(get_app_service),
):
    return ApiResponse(data=service.create_mutual_recharge_order(payload.userId, payload.points))


@router.post("/mutual-help/recharge/orders/{order_id}/pay", response_model=ApiResponse[dict])
def create_mutual_help_recharge_payment(
    order_id: str,
    payload: MutualHelpPaymentRequest,
    service: AppService = Depends(get_app_service),
):
    return ApiResponse(data=service.create_mutual_recharge_payment(order_id, payload.userId))


@router.post("/mutual-help/recharge/orders/{order_id}/test-confirm", response_model=ApiResponse[dict])
def confirm_test_mutual_help_recharge(
    order_id: str,
    payload: TestPaymentConfirmRequest,
    service: AppService = Depends(get_app_service),
):
    return ApiResponse(data=service.confirm_test_mutual_recharge_payment(order_id, payload.transactionId))


@router.post("/mutual-help/withdrawals", response_model=ApiResponse[dict])
def create_mutual_point_withdrawal(
    request: Request,
    payload: MutualPointWithdrawalCreateRequest,
    service: AppService = Depends(get_app_service),
):
    user_id = _mutual_help_user_id(request, payload.userId)
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录后申请提现")
    return ApiResponse(data=service.create_mutual_point_withdrawal(user_id, payload.points))


@router.get("/mutual-help/withdrawals", response_model=ApiResponse[list[dict]])
def list_mutual_point_withdrawals(
    request: Request,
    userId: str = Query(...),
    service: AppService = Depends(get_app_service),
):
    user_id = getattr(request.state, "authenticated_user_id", None) if getattr(request.app.state, "production_auth_enabled", False) else userId
    return ApiResponse(data=service.list_mutual_point_withdrawals(user_id=user_id))


@router.post("/mutual-help/activity", response_model=ApiResponse[dict])
def record_mutual_help_activity(
    request: Request,
    payload: MutualHelpActivityRequest,
    service: AppService = Depends(get_app_service),
):
    user_id = _mutual_help_user_id(request, payload.userId)
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录后记录任务行为")
    return ApiResponse(
        data=service.record_mutual_help_activity(
            user_id,
            payload.eventType,
            payload.taskId,
            payload.taskKind,
            payload.idempotencyKey,
            payload.linkId,
            payload.sessionId,
            payload.metadata,
        )
    )


@router.post("/notification-subscriptions", response_model=ApiResponse[dict])
def record_notification_subscription(payload: NotificationSubscriptionRequest, service: AppService = Depends(get_app_service)):
    return ApiResponse(
        data=service.record_notification_subscription(
            payload.userId,
            payload.templateId,
            payload.status,
            payload.source,
            payload.requestId,
            payload.purpose,
        )
    )


@router.put("/notification-preferences", response_model=ApiResponse[dict])
def update_notification_preferences(payload: NotificationPreferenceRequest, service: AppService = Depends(get_app_service)):
    return ApiResponse(
        data=service.update_notification_preferences(
            payload.userId,
            payload.importantCustomerViewEnabled,
            payload.ordinaryAnonymousViewEnabled,
        )
    )


@router.post("/membership/orders", response_model=ApiResponse[dict])
def create_membership_order(payload: MembershipCheckoutRequest, service: AppService = Depends(get_app_service)):
    return ApiResponse(data=service.create_membership_order(payload.userId, payload.planCode))


@router.post("/membership/orders/{order_id}/pay", response_model=ApiResponse[dict])
def create_membership_payment(
    order_id: str,
    payload: MembershipPaymentRequest,
    service: AppService = Depends(get_app_service),
):
    return ApiResponse(data=service.create_wechat_membership_payment(order_id, payload.userId))


@router.post("/membership/orders/{order_id}/test-confirm", response_model=ApiResponse[dict])
def confirm_test_payment(
    order_id: str,
    payload: TestPaymentConfirmRequest,
    service: AppService = Depends(get_app_service),
):
    return ApiResponse(data=service.confirm_test_membership_payment(order_id, payload.transactionId))


@router.post("/membership/orders/{order_id}/test-refund", response_model=ApiResponse[dict])
def refund_test_payment(
    order_id: str,
    payload: TestPaymentRefundRequest,
    service: AppService = Depends(get_app_service),
):
    return ApiResponse(data=service.refund_test_membership_payment(order_id, payload.operatorUserId))


@router.post("/wechat-pay/notify")
async def receive_wechat_pay_notification(request: Request, service: AppService = Depends(get_app_service)):
    body = await request.body()
    try:
        notification = WechatPayClient().verify_and_decrypt_notification(body, request.headers)
        if notification.get("eventType") != "TRANSACTION.SUCCESS":
            return JSONResponse(content={"code": "SUCCESS", "message": "成功"})
        service.handle_wechat_pay_success(notification["transaction"])
    except WechatPayError as exc:
        return JSONResponse(status_code=401, content={"code": "FAIL", "message": str(exc)})
    except HTTPException as exc:
        return JSONResponse(status_code=500, content={"code": "FAIL", "message": "订单处理失败"})
    except Exception:
        return JSONResponse(status_code=500, content={"code": "FAIL", "message": "订单处理失败"})
    return JSONResponse(content={"code": "SUCCESS", "message": "成功"})


@router.post("/wechat-transfer/notify")
async def receive_wechat_transfer_notification(request: Request, service: AppService = Depends(get_app_service)):
    body = await request.body()
    try:
        notification = WechatPayClient().verify_and_decrypt_notification(
            body,
            request.headers,
            transfer=True,
        )
        service.handle_wechat_transfer_notification(notification["transaction"])
    except WechatPayError as exc:
        return JSONResponse(status_code=401, content={"code": "FAIL", "message": str(exc)})
    except HTTPException:
        return JSONResponse(status_code=500, content={"code": "FAIL", "message": "转账结果处理失败"})
    except Exception:
        return JSONResponse(status_code=500, content={"code": "FAIL", "message": "转账结果处理失败"})
    return JSONResponse(content={"code": "SUCCESS", "message": "成功"})


@router.get("/customer-intelligence", response_model=ApiResponse[dict])
def customer_intelligence(
    ownerUserId: str = Query(...),
    requesterUserId: str = Query(...),
    mode: str | None = Query(default=None),
    refresh: bool = Query(default=False),
    service: AppService = Depends(get_app_service),
):
    return ApiResponse(data=service.get_customer_intelligence(ownerUserId, requesterUserId, mode, force_refresh=refresh))


@router.get("/customer-intelligence/summary", response_model=ApiResponse[dict])
def customer_intelligence_summary(
    ownerUserId: str = Query(...),
    requesterUserId: str = Query(...),
    mode: str | None = Query(default=None),
    refresh: bool = Query(default=False),
    service: AppService = Depends(get_app_service),
):
    return ApiResponse(
        data=service.get_customer_intelligence_summary(
            ownerUserId,
            requesterUserId,
            mode,
            force_refresh=refresh,
        )
    )


@router.get("/customer-detail", response_model=ApiResponse[dict])
def customer_detail(
    ownerUserId: str = Query(...),
    requesterUserId: str = Query(...),
    customerId: str = Query(default=""),
    leadId: str | None = Query(default=None),
    mode: str | None = Query(default=None),
    service: AppService = Depends(get_app_service),
):
    return ApiResponse(
        data=service.get_customer_detail(
            ownerUserId,
            requesterUserId,
            customerId,
            mode,
            leadId,
        )
    )


@router.post("/customer-followups/ensure", response_model=ApiResponse[dict])
def ensure_customer_followup(
    payload: CustomerFollowupEnsureRequest,
    service: AppService = Depends(get_app_service),
):
    return ApiResponse(
        data=service.ensure_customer_followup(
            payload.ownerUserId,
            payload.requesterUserId,
            payload.customerId,
            payload.mode,
            payload.leadId,
        )
    )


@router.post("/customer-followups/action", response_model=ApiResponse[dict])
def act_on_customer_followup(
    payload: CustomerFollowupActionRequest,
    service: AppService = Depends(get_app_service),
):
    return ApiResponse(
        data=service.act_on_customer_followup(
            payload.ownerUserId,
            payload.requesterUserId,
            payload.customerId,
            payload.action,
            payload.mode,
            payload.leadId,
            payload.operationId,
            payload.expectedVersion,
            profile_hint={
                "visitorIdentityId": payload.visitorIdentityId,
                "viewerUserId": payload.viewerUserId,
                "anonymousId": payload.anonymousId,
                "sourceNoteId": payload.sourceNoteId,
                "nickname": payload.nickname,
                "avatarUrl": payload.avatarUrl,
                "viewCount": payload.viewCount,
                "lastActivityAt": payload.lastActivityAt,
            },
            follow_up_tags=payload.followUpTags,
            log_content=payload.logContent,
            next_follow_up_at=payload.nextFollowUpAt,
        )
    )


@router.get("/referrals", response_model=ApiResponse[dict])
def referral_center(userId: str = Query(...), service: AppService = Depends(get_app_service)):
    return ApiResponse(data=service.get_referral_center(userId))


@router.post("/referrals/bind", response_model=ApiResponse[dict])
def bind_referral(payload: ReferralBindRequest, service: AppService = Depends(get_app_service)):
    return ApiResponse(data=service.bind_referral(payload.inviteeUserId, payload.inviteCode))


@router.post("/referrals/share-bind", response_model=ApiResponse[dict])
def bind_referral_from_share(
    payload: ReferralShareBindRequest,
    service: AppService = Depends(get_app_service),
):
    return ApiResponse(
        data=service.bind_referral_from_share(
            payload.inviteeUserId,
            payload.inviterUserId,
            payload.source,
        )
    )


@router.post("/referrals/withdrawals", response_model=ApiResponse[dict])
def create_withdrawal(payload: WithdrawalCreateRequest, service: AppService = Depends(get_app_service)):
    return ApiResponse(data=service.create_referral_withdrawal(payload.userId, payload.amountFen))


@router.post("/same-style/generate", response_model=ApiResponse[dict])
def generate_same_style(payload: SameStyleGenerateRequest, service: AppService = Depends(get_app_service)):
    return ApiResponse(data=service.generate_same_style(payload))
