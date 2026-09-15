from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class CustomerInfoChainToggleRequest(BaseModel):
    enabled: bool | None = None
    paymentRequired: bool | None = None
    operatorName: str | None = None


class MutualHelpConfigUpdateRequest(BaseModel):
    rechargeEnabled: bool | None = None
    rechargeVisible: bool | None = None
    withdrawalEnabled: bool | None = None
    withdrawalVisible: bool | None = None
    operatorName: str | None = None


class ContentPinUpdateRequest(BaseModel):
    pinned: bool
    operatorName: str = Field(default="ops", min_length=1, max_length=80)


class ContentSafetyRuleCreateRequest(BaseModel):
    term: str = Field(min_length=1, max_length=200)
    matchType: Literal["contains", "exact"] = "contains"
    category: str = Field(default="platform_custom", min_length=1, max_length=80)
    severity: Literal["high", "medium", "low"] = "medium"
    action: Literal["block", "review", "warn"] = "review"
    scopes: list[str] = Field(default_factory=list, max_length=30)
    enabled: bool = True
    expiresAt: str | None = None
    reason: str = Field(default="", max_length=240)
    operatorName: str = Field(default="ops", min_length=1, max_length=80)


class ContentSafetyRuleUpdateRequest(BaseModel):
    term: str | None = Field(default=None, min_length=1, max_length=200)
    matchType: Literal["contains", "exact"] | None = None
    category: str | None = Field(default=None, min_length=1, max_length=80)
    severity: Literal["high", "medium", "low"] | None = None
    action: Literal["block", "review", "warn"] | None = None
    scopes: list[str] | None = Field(default=None, max_length=30)
    enabled: bool | None = None
    expiresAt: str | None = None
    reason: str | None = Field(default=None, max_length=240)
    operatorName: str = Field(default="ops", min_length=1, max_length=80)


class ContentSafetyTestRequest(BaseModel):
    contentType: str = Field(min_length=1, max_length=80)
    fields: dict = Field(default_factory=dict)
    contentRevision: str = Field(default="", max_length=160)


class ContentModerationReviewRequest(BaseModel):
    action: Literal["approve", "reject"]
    operatorName: str = Field(default="ops", min_length=1, max_length=80)
    note: str = Field(default="", max_length=240)


class GroupResourceAdminUpdateRequest(BaseModel):
    enabled: bool
    operatorName: str = Field(default="ops", min_length=1, max_length=80)


class MobileToolAdminUpdateRequest(BaseModel):
    tool: Literal["mutual_help", "group_resource", "business_opportunity"]
    enabled: bool
    operatorName: str = Field(default="ops", min_length=1, max_length=80)


class ToolRecordsBulkActionRequest(BaseModel):
    tool: Literal["mutual_help", "group_resource", "business_opportunity"]
    recordIds: list[str] = Field(default_factory=list, max_length=100)
    action: Literal["archive", "mark_test", "delete"]
    testOnly: bool = False
    operatorName: str = Field(default="ops", min_length=1, max_length=80)
    reason: str = Field(default="运营清理", max_length=240)


class MutualHelpAdminTaskCreateRequest(BaseModel):
    """Small operator-facing form for publishing a platform task."""

    ownerUserId: str | None = Field(default=None, max_length=160)
    taskKind: Literal["miniapp", "ordinary", "wool"] = "ordinary"
    title: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=500)
    acceptanceText: str = Field(default="", max_length=1000)
    shortLink: str = Field(default="", max_length=1000)
    rewardPointType: Literal["base", "reward"] = "base"
    rewardPoints: int = Field(default=5, ge=0, le=10000)
    executorReward: int = Field(default=4, ge=0, le=10000)
    remaining: int | None = Field(default=None, ge=0, le=100000)
    repeatPolicy: Literal["once", "daily"] = "once"
    deadlineText: str = Field(default="长期开放", max_length=60)
    operatorName: str = Field(default="ops", min_length=1, max_length=80)


class MutualPlatformBudgetAdjustRequest(BaseModel):
    delta: int = Field(ge=-1000000, le=1000000)
    reason: str = Field(default="平台充值积分任务预算调整", max_length=240)
    operatorName: str = Field(default="ops", min_length=1, max_length=80)


class GroupUploadPreviewRequest(BaseModel):
    rawText: str = Field(default="")


class GroupUploadCreateRequest(BaseModel):
    rawText: str = Field(default="")
    batchName: str | None = None
    operatorName: str | None = None


class SingleGroupResourceCreateRequest(BaseModel):
    name: str = Field(default="")
    cityMode: str = Field(default="city")
    cityLabel: str = Field(default="")
    region: list[str] = Field(default_factory=list)
    groupType: str = Field(default="房源")
    purposes: list[str] = Field(default_factory=list)
    memberRange: str = Field(default="")
    activeLevel: str = Field(default="")
    expiresInDays: int = 5
    remark: str | None = None
    customTags: list[str] = Field(default_factory=list)
    qrImageData: str | None = None
    operatorName: str | None = None


class GroupResourceReviewActionRequest(BaseModel):
    operatorName: str = Field(default="ops", min_length=1, max_length=80)
    reason: str = Field(default="", max_length=240)
    extraPenalty: int = Field(default=0, ge=0, le=1000)
    refundViewers: bool = True
    pausePublisher: bool = False


class GroupResourceComplaintRequest(BaseModel):
    userId: str = Field(default="", min_length=1, max_length=160)
    reason: str = Field(default="", min_length=1, max_length=120)


class WecomGroupJoinWayCreateRequest(BaseModel):
    remark: str = Field(default="资料助手资源群")
    chatIdList: list[str] = Field(default_factory=list)
    roomBaseName: str = Field(default="资料助手资源群")
    roomBaseId: int = 1
    autoCreateRoom: int = 1
    state: str = Field(default="teambuy_resource_group")
    operatorName: str | None = None
    dryRun: bool = True


class GroupBotChannelUpsertRequest(BaseModel):
    groupId: str = Field(default="")
    groupName: str = Field(default="")
    webhook: str = Field(default="")
    groupType: str = Field(default="资源群")
    audience: str = Field(default="")
    cityLabel: str = Field(default="")
    dailyTemplate: str = Field(default="midday")
    sendWindow: str = Field(default="")
    ownerName: str | None = None
    remark: str | None = None
    enabled: bool = True


class FeedbackTicketCreateRequest(BaseModel):
    type: str = Field(default="bug")
    userId: str | None = None
    userNickname: str | None = None
    contact: str | None = None
    content: str = Field(default="")


class FeedbackTicketUpdateRequest(BaseModel):
    status: str | None = None
    replyText: str | None = None
    rewardNote: str | None = None
    operatorName: str | None = None


class RuleLearningSampleUpdateRequest(BaseModel):
    status: str | None = None
    operatorName: str | None = None
    reviewNote: str | None = None


class LiveQrCodeCreateRequest(BaseModel):
    name: str = Field(default="", max_length=80)
    targetUrl: str = Field(default="", max_length=2000)
    description: str | None = Field(default=None, max_length=240)
    targetExpiresAt: str | None = Field(default=None, max_length=80)
    groupMemberCount: int | None = Field(default=None, ge=0, le=10000)
    automationGroupCandidateId: str | None = Field(default=None, max_length=128)


class LiveQrCodeUpdateRequest(BaseModel):
    name: str | None = Field(default=None, max_length=80)
    targetUrl: str | None = Field(default=None, max_length=2000)
    description: str | None = Field(default=None, max_length=240)
    targetExpiresAt: str | None = Field(default=None, max_length=80)
    status: str | None = None
    groupMemberCount: int | None = Field(default=None, ge=0, le=10000)
    automationGroupCandidateId: str | None = Field(default=None, max_length=128)


class LiveQrStyleUpdateRequest(BaseModel):
    ownerUserId: str = Field(default="", min_length=1, max_length=128)
    styleMode: Literal["plain", "source"] = "plain"


class OpportunityLeadContactPayload(BaseModel):
    contactType: str = Field(default="wechat")
    contactValue: str = Field(default="")
    contactMasked: str | None = None
    verifyStatus: str = Field(default="pending")


class OpportunityLeadSourcePayload(BaseModel):
    sourcePlatform: str | None = None
    sourceUrl: str | None = None
    sourceAuthor: str | None = None
    sourcePublishedAt: str | None = None
    rawText: str = Field(default="")
    rawImages: list[str] = Field(default_factory=list)


class OpportunityLeadUpsertRequest(BaseModel):
    id: str | None = None
    title: str = Field(default="")
    summary: str = Field(default="")
    city: str | None = None
    district: str | None = None
    industry: str | None = None
    demandType: str = Field(default="需求")
    content: str = Field(default="")
    tags: list[str] = Field(default_factory=list)
    contactStatus: str = Field(default="pending_verify")
    trustStatus: str = Field(default="pending")
    status: str = Field(default="draft")
    priority: str | None = None
    expiresAt: str | None = None
    source: OpportunityLeadSourcePayload | None = None
    contacts: list[OpportunityLeadContactPayload] = Field(default_factory=list)


class SupplyDemandReviewRequest(BaseModel):
    status: str = Field(default="published")
    reviewNote: str | None = None
