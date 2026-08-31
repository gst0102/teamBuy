from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from app.api.dependencies import get_app_service
from app.schemas.common import ApiResponse
from app.schemas.scrm import (
    MembershipCheckoutRequest,
    MembershipPaymentRequest,
    MutualHelpActivityRequest,
    MutualHelpPaymentRequest,
    MutualHelpRechargeRequest,
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


@router.get("/membership", response_model=ApiResponse[dict])
def membership_status(userId: str = Query(...), service: AppService = Depends(get_app_service)):
    return ApiResponse(data=service.get_membership_status(userId))


@router.get("/notification-config", response_model=ApiResponse[dict])
def notification_config(userId: str = Query(...), service: AppService = Depends(get_app_service)):
    return ApiResponse(data=service.get_notification_config(userId))


@router.get("/mutual-help", response_model=ApiResponse[dict])
def mutual_help_status(userId: str = Query(...), service: AppService = Depends(get_app_service)):
    return ApiResponse(data=service.get_mutual_help_status(userId))


@router.get("/mutual-help/ledger", response_model=ApiResponse[list[dict]])
def mutual_help_ledger(
    userId: str = Query(...),
    limit: int = Query(default=50, ge=1, le=200),
    service: AppService = Depends(get_app_service),
):
    return ApiResponse(data=service.list_points_ledgers(userId, limit=limit))


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


@router.post("/mutual-help/activity", response_model=ApiResponse[dict])
def record_mutual_help_activity(
    payload: MutualHelpActivityRequest,
    service: AppService = Depends(get_app_service),
):
    return ApiResponse(
        data=service.record_mutual_help_activity(
            payload.userId,
            payload.eventType,
            payload.taskId,
            payload.taskKind,
            payload.idempotencyKey,
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
