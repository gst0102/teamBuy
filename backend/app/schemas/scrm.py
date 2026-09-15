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


class MutualHelpRechargeRequest(BaseModel):
    userId: str
    points: int = Field(default=100, ge=100, le=100000)


class MutualPointWithdrawalCreateRequest(BaseModel):
    userId: str
    points: int = Field(ge=100, le=1000000)


class MutualHelpPaymentRequest(BaseModel):
    userId: str


class MutualHelpActivityRequest(BaseModel):
    userId: str
    eventType: str
    taskId: str
    taskKind: str = "ordinary"
    idempotencyKey: str = Field(default="", max_length=160)
    linkId: str = Field(default="", max_length=160)
    sessionId: str = Field(default="", max_length=160)
    metadata: dict = Field(default_factory=dict)


class MutualHelpTaskCreateRequest(BaseModel):
    id: str | None = Field(default=None, max_length=160)
    ownerUserId: str = Field(min_length=1, max_length=160)
    taskKind: str = Field(default="ordinary", max_length=20)
    title: str = Field(min_length=1, max_length=120)
    category: str = Field(default="其他", max_length=60)
    description: str = Field(default="", max_length=500)
    contentBlocks: list[dict] = Field(default_factory=list, max_length=20)
    acceptanceCriteriaBlocks: list[dict] = Field(default_factory=list, max_length=20)
    taskLinks: list[dict] = Field(default_factory=list, max_length=10)
    shortLink: str = Field(default="", max_length=1000)
    rewardPointType: str = Field(default="base", max_length=20)
    repeatPolicy: str = Field(default="once", max_length=20)
    woolPolicy: dict = Field(default_factory=dict)
    rewardPoints: int = Field(default=0, ge=0, le=10000)
    executorReward: int = Field(default=0, ge=0, le=10000)
    remaining: int | None = Field(default=None, ge=0, le=100000)
    deadlineText: str = Field(default="长期开放", max_length=60)


class MutualHelpTaskUpdateRequest(BaseModel):
    ownerUserId: str = Field(min_length=1, max_length=160)
    status: str = Field(min_length=1, max_length=20)


class MutualHelpSubmissionCreateRequest(BaseModel):
    userId: str = Field(min_length=1, max_length=160)
    text: str = Field(default="", max_length=5000)
    images: list[str] = Field(default_factory=list, max_length=6)


class MutualHelpSubmissionApproveRequest(BaseModel):
    userId: str = Field(min_length=1, max_length=160)


class MutualHelpSubmissionRejectRequest(BaseModel):
    userId: str = Field(min_length=1, max_length=160)
    reason: str = Field(min_length=1, max_length=300)


class MutualHelpChatConversationRequest(BaseModel):
    userId: str = Field(min_length=1, max_length=160)
    executorUserId: str = Field(default="", max_length=160)


class MutualHelpChatMessageRequest(BaseModel):
    userId: str = Field(min_length=1, max_length=160)
    messageType: str = Field(default="text", max_length=20)
    text: str = Field(default="", max_length=2000)
    imageUrl: str = Field(default="", max_length=2000)
    miniProgram: dict = Field(default_factory=dict)
    idempotencyKey: str = Field(default="", max_length=160)


class MutualHelpWoolUnlockRequest(BaseModel):
    userId: str = Field(min_length=1, max_length=160)


class MutualHelpCommentRequest(BaseModel):
    userId: str = Field(min_length=1, max_length=160)
    text: str = Field(default="", max_length=300)
    recommendChoice: str = Field(default="", max_length=20)


class MutualHelpCommentReportRequest(BaseModel):
    userId: str = Field(min_length=1, max_length=160)
    reason: str = Field(default="内容不实或违规", max_length=60)


class MutualHelpTipRequest(BaseModel):
    userId: str = Field(min_length=1, max_length=160)
    amount: int = Field(ge=1, le=10000)


class MutualHelpWoolRefundRequest(BaseModel):
    userId: str = Field(min_length=1, max_length=160)
    reason: str = Field(default="任务内容或链接失效", max_length=120)


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
    purpose: str = "customer"


class NotificationPreferenceRequest(BaseModel):
    userId: str
    importantCustomerViewEnabled: bool = True
    ordinaryAnonymousViewEnabled: bool = True
