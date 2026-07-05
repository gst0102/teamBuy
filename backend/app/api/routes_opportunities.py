from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_app_service
from app.schemas.common import ApiResponse
from app.schemas.opportunities import (
    OpportunityLeadFollowupRequest,
    OpportunityLeadSaveRequest,
    OpportunityContactUnlockRequest,
    OpportunitySubscriptionUpsertRequest,
    OpportunityPushDigestRequest,
    ResponsePackageCreateRequest,
    ResponsePackageEventRequest,
    ResponsePackagePreviewRequest,
    SupplyDemandApplicationCreateRequest,
    SupplyDemandApplicationReviewRequest,
    SupplyDemandCardUpsertRequest,
)
from app.services.app_service import AppService


router = APIRouter(prefix="/api/opportunity-leads", tags=["opportunity-leads"])
packages_router = APIRouter(prefix="/api/response-packages", tags=["response-packages"])


@router.get("", response_model=ApiResponse[dict | list[dict]])
def list_opportunity_leads(
    keyword: str | None = Query(default=None),
    userId: str | None = Query(default=None),
    city: str | None = Query(default=None),
    industry: str | None = Query(default=None),
    demandType: str | None = Query(default=None),
    contactStatus: str | None = Query(default=None),
    service: AppService = Depends(get_app_service),
):
    if userId:
        return ApiResponse(
            data=service.list_opportunity_leads_for_user(
                user_id=userId,
                keyword=keyword,
                city=city,
                industry=industry,
                demand_type=demandType,
                contact_status=contactStatus,
            )
        )
    return ApiResponse(
        data=service.list_opportunity_leads_public(
            keyword=keyword,
            city=city,
            industry=industry,
            demand_type=demandType,
            contact_status=contactStatus,
        )
    )


@router.get("/saved", response_model=ApiResponse[list[dict]])
def list_saved_opportunity_leads(
    userId: str = Query(...),
    status: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    packageStatus: str | None = Query(default=None),
    service: AppService = Depends(get_app_service),
):
    return ApiResponse(
        data=service.list_saved_opportunity_leads(
            user_id=userId,
            status=status,
            keyword=keyword,
            package_status=packageStatus,
        )
    )


@router.get("/{lead_id}", response_model=ApiResponse[dict])
def get_opportunity_lead(
    lead_id: str,
    service: AppService = Depends(get_app_service),
):
    return ApiResponse(data=service.get_opportunity_lead_detail(lead_id))


@router.post("/{lead_id}/save", response_model=ApiResponse[dict])
def save_opportunity_lead(
    lead_id: str,
    payload: OpportunityLeadSaveRequest,
    service: AppService = Depends(get_app_service),
):
    return ApiResponse(
        data=service.save_opportunity_lead_for_user(
            lead_id=lead_id,
            user_id=payload.userId,
            save_status=payload.status,
            note=payload.note,
            reminder_at=payload.reminderAt,
        )
    )


@router.post("/{lead_id}/followups", response_model=ApiResponse[dict])
def add_opportunity_followup(
    lead_id: str,
    payload: OpportunityLeadFollowupRequest,
    service: AppService = Depends(get_app_service),
):
    return ApiResponse(
        data=service.add_opportunity_followup(
            lead_id=lead_id,
            user_id=payload.userId,
            action_type=payload.actionType,
            note=payload.note,
        )
    )


@router.post("/{lead_id}/unlock-contact", response_model=ApiResponse[dict])
def unlock_opportunity_contact(
    lead_id: str,
    payload: OpportunityContactUnlockRequest,
    service: AppService = Depends(get_app_service),
):
    return ApiResponse(data=service.unlock_opportunity_contact(lead_id=lead_id, user_id=payload.userId))


@router.post("/{lead_id}/response-packages/preview", response_model=ApiResponse[dict])
def preview_response_package(
    lead_id: str,
    payload: ResponsePackagePreviewRequest,
    service: AppService = Depends(get_app_service),
):
    return ApiResponse(
        data=service.preview_response_package(
            lead_id=lead_id,
            owner_user_id=payload.userId,
            selected_asset_ids=payload.selectedAssetIds,
        )
    )


@router.post("/{lead_id}/response-packages", response_model=ApiResponse[dict])
def create_response_package(
    lead_id: str,
    payload: ResponsePackageCreateRequest,
    service: AppService = Depends(get_app_service),
):
    return ApiResponse(
        data=service.create_response_package(
            lead_id=lead_id,
            owner_user_id=payload.userId,
            selected_asset_ids=payload.selectedAssetIds,
        )
    )


@packages_router.get("/{package_id}", response_model=ApiResponse[dict])
def get_response_package(
    package_id: str,
    ownerUserId: str = Query(...),
    service: AppService = Depends(get_app_service),
):
    return ApiResponse(data=service.get_response_package(package_id=package_id, owner_user_id=ownerUserId))


@packages_router.post("/{package_id}/events", response_model=ApiResponse[dict])
def record_response_package_event(
    package_id: str,
    payload: ResponsePackageEventRequest,
    service: AppService = Depends(get_app_service),
):
    return ApiResponse(
        data=service.record_response_package_event(
            package_id=package_id,
            event_type=payload.eventType,
            viewer_id=payload.viewerId,
            anonymous_id=payload.anonymousId,
            metadata=payload.metadata,
        )
    )


@packages_router.get("/{package_id}/radar", response_model=ApiResponse[dict])
def get_response_package_radar(
    package_id: str,
    ownerUserId: str = Query(...),
    service: AppService = Depends(get_app_service),
):
    return ApiResponse(data=service.get_response_package_radar(package_id=package_id, owner_user_id=ownerUserId))


subscriptions_router = APIRouter(prefix="/api/opportunity-subscriptions", tags=["opportunity-subscriptions"])
supply_demand_router = APIRouter(prefix="/api/supply-demand/cards", tags=["supply-demand"])
push_router = APIRouter(prefix="/api/opportunity-push-digests", tags=["opportunity-push-digests"])


@subscriptions_router.get("/me", response_model=ApiResponse[list[dict]])
def list_my_opportunity_subscriptions(
    userId: str = Query(...),
    service: AppService = Depends(get_app_service),
):
    return ApiResponse(data=service.list_opportunity_subscriptions(userId))


@subscriptions_router.post("", response_model=ApiResponse[dict])
def upsert_opportunity_subscription(
    payload: OpportunitySubscriptionUpsertRequest,
    service: AppService = Depends(get_app_service),
):
    return ApiResponse(data=service.upsert_opportunity_subscription(payload))


@subscriptions_router.put("/{subscription_id}", response_model=ApiResponse[dict])
def update_opportunity_subscription(
    subscription_id: str,
    payload: OpportunitySubscriptionUpsertRequest,
    service: AppService = Depends(get_app_service),
):
    payload.id = subscription_id
    return ApiResponse(data=service.upsert_opportunity_subscription(payload))


@subscriptions_router.delete("/{subscription_id}", response_model=ApiResponse[dict])
def delete_opportunity_subscription(
    subscription_id: str,
    userId: str = Query(...),
    service: AppService = Depends(get_app_service),
):
    return ApiResponse(data=service.delete_opportunity_subscription(subscription_id, userId))


@supply_demand_router.get("", response_model=ApiResponse[list[dict]])
def list_supply_demand_cards(
    keyword: str | None = Query(default=None),
    city: str | None = Query(default=None),
    industry: str | None = Query(default=None),
    demandType: str | None = Query(default=None),
    cardType: str | None = Query(default=None),
    contactStatus: str | None = Query(default=None),
    service: AppService = Depends(get_app_service),
):
    return ApiResponse(
        data=service.list_supply_demand_cards_public(
            keyword=keyword,
            city=city,
            industry=industry,
            demand_type=demandType,
            card_type=cardType,
            contact_status=contactStatus,
        )
    )


@supply_demand_router.get("/me", response_model=ApiResponse[list[dict]])
def list_my_supply_demand_cards(
    userId: str = Query(...),
    service: AppService = Depends(get_app_service),
):
    return ApiResponse(data=service.list_my_supply_demand_cards(userId))


@supply_demand_router.get("/applications", response_model=ApiResponse[list[dict]])
def list_supply_demand_applications(
    userId: str = Query(...),
    role: str = Query(default="owner"),
    service: AppService = Depends(get_app_service),
):
    return ApiResponse(data=service.list_supply_demand_applications_for_user(userId, role=role))


@supply_demand_router.get("/{card_id}", response_model=ApiResponse[dict])
def get_supply_demand_card(
    card_id: str,
    userId: str | None = Query(default=None),
    service: AppService = Depends(get_app_service),
):
    return ApiResponse(data=service.get_supply_demand_card_detail(card_id, viewer_user_id=userId))


@supply_demand_router.post("", response_model=ApiResponse[dict])
def upsert_supply_demand_card(
    payload: SupplyDemandCardUpsertRequest,
    service: AppService = Depends(get_app_service),
):
    return ApiResponse(data=service.upsert_supply_demand_card(payload))


@supply_demand_router.put("/{card_id}", response_model=ApiResponse[dict])
def update_supply_demand_card(
    card_id: str,
    payload: SupplyDemandCardUpsertRequest,
    service: AppService = Depends(get_app_service),
):
    payload.id = card_id
    return ApiResponse(data=service.upsert_supply_demand_card(payload))


@supply_demand_router.post("/{card_id}/submit", response_model=ApiResponse[dict])
def submit_supply_demand_card(
    card_id: str,
    payload: OpportunityContactUnlockRequest,
    service: AppService = Depends(get_app_service),
):
    return ApiResponse(data=service.submit_supply_demand_card(card_id, payload.userId))


@supply_demand_router.post("/{card_id}/applications", response_model=ApiResponse[dict])
def apply_supply_demand_card(
    card_id: str,
    payload: SupplyDemandApplicationCreateRequest,
    service: AppService = Depends(get_app_service),
):
    return ApiResponse(data=service.apply_supply_demand_card(card_id, payload.userId, payload.message))


@supply_demand_router.post("/applications/{application_id}/review", response_model=ApiResponse[dict])
def review_supply_demand_application(
    application_id: str,
    payload: SupplyDemandApplicationReviewRequest,
    service: AppService = Depends(get_app_service),
):
    return ApiResponse(data=service.review_supply_demand_application(application_id, payload.userId, payload.status))


@push_router.get("", response_model=ApiResponse[list[dict]])
def list_opportunity_push_digests(
    userId: str = Query(...),
    service: AppService = Depends(get_app_service),
):
    return ApiResponse(data=service.list_opportunity_push_digests(userId))


@push_router.post("/generate", response_model=ApiResponse[dict])
def generate_opportunity_push_digest(
    payload: OpportunityPushDigestRequest,
    service: AppService = Depends(get_app_service),
):
    return ApiResponse(data=service.generate_opportunity_push_digest(payload.userId))


@push_router.post("/{digest_id}/read", response_model=ApiResponse[dict])
def mark_opportunity_push_digest_read(
    digest_id: str,
    payload: OpportunityPushDigestRequest,
    service: AppService = Depends(get_app_service),
):
    return ApiResponse(data=service.mark_opportunity_push_digest_read(digest_id, payload.userId))
