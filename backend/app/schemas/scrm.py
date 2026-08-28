from __future__ import annotations

from pydantic import BaseModel, Field


class MembershipCheckoutRequest(BaseModel):
    userId: str
    planCode: str = "sales_scrm_monthly"


class TestPaymentConfirmRequest(BaseModel):
    transactionId: str


class TestPaymentRefundRequest(BaseModel):
    operatorUserId: str


class MembershipPaymentRequest(BaseModel):
    userId: str


class CustomerFollowupEnsureRequest(BaseModel):
    ownerUserId: str
    requesterUserId: str
    customerId: str
    mode: str | None = None
    leadId: str | None = None


class CustomerFollowupActionRequest(BaseModel):
    ownerUserId: str
    requesterUserId: str
    customerId: str
    action: str
    mode: str | None = None
    leadId: str | None = None
    operationId: str | None = None
    expectedVersion: int | None = Field(default=None, ge=0)
    # Radar cards already contain the minimum owner-scoped identity/source
    # projection needed to create a first follow-up record. Sending it avoids
    # rebuilding the full customer-intelligence dashboard on this hot path.
    visitorIdentityId: str | None = None
    viewerUserId: str | None = None
    anonymousId: str | None = None
    sourceNoteId: str | None = None
    nickname: str | None = None
    avatarUrl: str | None = None
    viewCount: int = Field(default=0, ge=0)
    lastActivityAt: str | None = None
    # The detail page submits the complete follow-up draft with the state
    # transition so one action writes the lead and its structured log together.
    followUpTags: list[str] | None = None
    logContent: str | None = None
    nextFollowUpAt: str | None = None


class ReferralBindRequest(BaseModel):
    inviteeUserId: str
    inviteCode: str


class ReferralShareBindRequest(BaseModel):
    inviteeUserId: str
    inviterUserId: str
    source: str = "share_link"


class WithdrawalCreateRequest(BaseModel):
    userId: str
    amountFen: int = Field(gt=0)


class SameStyleGenerateRequest(BaseModel):
    ownerUserId: str
    mode: str
    sourceNoteId: str | None = None
    sourceShowcaseId: str | None = None
    ownNoteIds: list[str] = Field(default_factory=list)
    idempotencyKey: str


class NotificationSubscriptionRequest(BaseModel):
    userId: str
    templateId: str
    status: str
    source: str = "share"
    requestId: str | None = None


class NotificationPreferenceRequest(BaseModel):
    userId: str
    importantCustomerViewEnabled: bool = True
    ordinaryAnonymousViewEnabled: bool = True
