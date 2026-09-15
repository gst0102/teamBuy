from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


ImportStatus = Literal["pending", "success", "failed", "claimed"]
CardStatus = Literal["draft", "published", "archived"]
UserNoteStatus = Literal["draft", "active", "deleted"]
UserNoteShareState = Literal["private", "published", "revoked"]
ViewType = Literal["logged_in", "anonymous", "share"]
RelayStatus = Literal["active", "deleted"]
FollowUpStatus = Literal["pending", "followed"]
LeadReminderStatus = Literal["pending", "following", "contacted", "invalid", "paused", "completed", "deleted"]
MessageType = Literal["text", "image", "link", "location", "video", "file", "weapp", "unknown"]
SourceType = Literal["wechat_note", "miniapp_link", "mp_link", "web_link", "unknown"]
SyncStatus = Literal["idle", "running", "success", "failed"]
MediaRetryStatus = Literal["pending", "success", "failed"]
SyncTaskStatus = Literal["queued", "running", "success", "failed", "retrying", "skipped"]
SkillRunStatus = Literal["pending", "success", "failed", "needs_confirm"]
AutomationDeviceStatus = Literal["offline", "ready", "busy", "paused", "degraded"]
AutomationTaskStatus = Literal["pending", "running", "success", "failed", "cancelled"]
AutomationJoinStatus = Literal["pending", "success", "failed", "unknown"]
AutomationGroupSource = Literal["xiaohongshu", "wechat_native"]
AutomationMembershipStatus = Literal["unknown", "active", "removed"]
ArchiveCursorStatus = Literal["idle", "running", "success", "failed"]
MediaAssetStatus = Literal["active", "deleted"]
CustomerActionKey = Literal[
    "lead-contact",
    "appointment",
    "order-intent",
    "relay-intent",
    "consult-click",
    "navigation-click",
    "external-open",
    "image-open",
    "pdf-open",
    "link-open",
    "source-open",
    "contact-click",
    "phone-click",
    "wechat-qr-open",
    "featured-note-open",
    "map-open",
]
MessageThreadStatus = Literal["active", "archived"]
ShowcaseStatus = Literal["draft", "published", "archived"]
ResourceLedgerType = Literal["grant", "consume", "refund", "adjust", "free_quota"]
OpportunityLeadStatus = Literal["draft", "published", "archived", "rejected"]
OpportunityContactStatus = Literal["none", "available", "masked", "locked", "pending_verify"]
OpportunityTrustStatus = Literal["verified", "pending", "risk"]
OpportunityMatchStatus = Literal["new", "viewed", "saved", "dismissed", "contacted"]
OpportunitySaveStatus = Literal["saved", "contacted", "following", "invalid", "archived"]
ResponsePackageStatus = Literal["draft", "ready", "sent", "archived"]
OpportunitySubscriptionStatus = Literal["active", "paused", "deleted"]
SupplyDemandCardType = Literal["demand", "supply"]
SupplyDemandCardStatus = Literal["draft", "pending_review", "published", "rejected", "archived"]
SupplyDemandApplicationStatus = Literal["pending", "accepted", "rejected", "closed"]
OpportunityPushDigestStatus = Literal["pending", "read", "dismissed"]
MembershipOrderStatus = Literal["pending", "paid", "refunded", "closed"]
MembershipEntitlementStatus = Literal["active", "expired", "revoked"]
MutualRechargeOrderStatus = Literal["pending", "paid", "closed", "refunded"]
MutualActivityEventType = Literal[
    "published",
    "completed",
    "opened",
    "returned",
    "open_cancelled",
    "open_failed",
]
ReferralRewardStatus = Literal["pending", "available", "reserved", "withdrawn", "revoked"]
ReferralWithdrawalStatus = Literal[
    "pending",
    "approved",
    "waiting_user_confirm",
    "processing",
    "paid",
    "failed",
    "cancelled",
    "rejected",
]
MutualPointWithdrawalStatus = Literal[
    "pending",
    "approved",
    "waiting_user_confirm",
    "processing",
    "paid",
    "failed",
    "cancelled",
    "rejected",
]
WechatSubscriptionGrantStatus = Literal["available", "reserved", "consumed", "invalid", "rejected"]
WechatSubscriptionDeliveryStatus = Literal["queued", "sending", "sent", "failed", "skipped"]
WechatSubscriptionNotificationType = Literal["view", "message", "live_qr_expiry"]
ContentSafetyRuleMatchType = Literal["contains", "exact"]
ContentSafetyRuleSeverity = Literal["high", "medium", "low"]
ContentSafetyRuleAction = Literal["block", "review", "warn"]
ContentModerationStatus = Literal["allowed", "reviewing", "blocked", "overridden", "stale"]
ContentModerationDecision = Literal["allow", "warn", "review", "block"]


class User(BaseModel):
    id: str
    openid: str
    unionid: str | None = None
    nickname: str
    avatarUrl: str
    wechat: str | None = None
    phone: str | None = None
    salesProfile: dict = Field(default_factory=dict)
    # Narrow, server-authorized capabilities.  The mini program never grants
    # itself a role; the ops console is the only writer for these values.
    roles: list[str] = Field(default_factory=list)
    groupResourcePenaltyDebt: int = 0
    groupResourcePublishingPaused: bool = False
    createdAt: str
    updatedAt: str


class WecomIdentityBinding(BaseModel):
    id: str
    sourceType: str = "wecom_archive"
    externalUserId: str
    ownerUserId: str
    ownerOpenid: str | None = None
    bindSource: str = "claim_import"
    firstImportBatchId: str | None = None
    lastImportBatchId: str | None = None
    createdAt: str
    updatedAt: str


class WecomBindCardToken(BaseModel):
    id: str
    tokenHash: str
    welcomeCodeHash: str
    externalUserId: str
    status: Literal["issued", "consumed", "invalid"] = "issued"
    deliveryStatus: Literal["pending", "sent", "failed"] = "pending"
    expiresAt: str
    usedAt: str | None = None
    ownerUserId: str | None = None
    ownerOpenid: str | None = None
    createdAt: str
    updatedAt: str


class WecomBindCardAsset(BaseModel):
    id: str
    sourceContentBase64: str = ""
    filename: str = "wecom-bind-card.png"
    contentType: str = "image/png"
    sourceSha256: str
    mediaId: str = ""
    mediaIdExpiresAt: str | None = None
    status: Literal["active", "retired", "failed"] = "active"
    errorMessage: str | None = None
    createdAt: str
    updatedAt: str


class ImportBatch(BaseModel):
    id: str
    externalUserId: str
    conversationId: str
    claimedByUserId: str | None = None
    status: ImportStatus
    titleCandidate: str
    sourceType: SourceType
    errorMessage: str | None = None
    rawMessageIds: list[str] = Field(default_factory=list)
    generatedCardId: str | None = None
    generatedNoteId: str | None = None
    startedAt: str
    endedAt: str | None = None
    createdAt: str
    updatedAt: str


class RawMessage(BaseModel):
    id: str
    importBatchId: str | None = None
    wecomMsgId: str | None = None
    wecomToken: str | None = None
    openKfid: str | None = None
    externalUserId: str
    conversationId: str
    msgType: MessageType
    content: dict
    mediaId: str | None = None
    localMediaUrl: str | None = None
    receivedAt: str
    createdAt: str


class RelayConfig(BaseModel):
    enabled: bool = True
    requirePhone: bool = False
    requireAddress: bool = False


class CardMedia(BaseModel):
    id: str
    cardId: str
    type: Literal["image", "video"]
    url: str
    sortOrder: int
    sourceMediaId: str | None = None
    createdAt: str


class Card(BaseModel):
    id: str
    ownerUserId: str
    importBatchId: str | None = None
    sourceCardId: str | None = None
    status: CardStatus
    title: str
    coverUrl: str | None = None
    detailText: str
    projectName: str | None = None
    locationText: str | None = None
    phone: str | None = None
    relayNotice: str | None = None
    sourceUrl: str | None = None
    enabledFields: list[str] = Field(default_factory=list)
    categoryIds: list[str] = Field(default_factory=list)
    media: list[CardMedia] = Field(default_factory=list)
    relayConfig: RelayConfig = Field(default_factory=RelayConfig)
    publishedAt: str | None = None
    createdAt: str
    updatedAt: str


class UserNote(BaseModel):
    id: str
    ownerUserId: str
    importBatchId: str | None = None
    sourceCardId: str | None = None
    status: UserNoteStatus = "draft"
    # Legacy notes without an explicit lifecycle marker remain compatible.
    # New intake paths override this to private before publishing.
    shareState: UserNoteShareState = "published"
    revision: int = 1
    intakeId: str | None = None
    idempotencyKey: str | None = None
    title: str
    summary: str
    body: str
    # Canonical order for text and visible media in the customer-facing body.
    # ``media`` remains the storage/reference registry for all media types.
    contentBlocks: list[dict] = Field(default_factory=list)
    coverUrl: str | None = None
    media: list[dict] = Field(default_factory=list)
    categoryIds: list[str] = Field(default_factory=list)
    phone: str | None = None
    locationText: str | None = None
    sourceRefs: list[str] = Field(default_factory=list)
    visibilityConfig: dict = Field(default_factory=dict)
    # Platform operators may promote business-card entries in the public
    # cooperation directory. These fields are intentionally removed from
    # public payload builders; clients only receive the resulting order.
    isPinned: bool = False
    pinnedAt: str | None = None
    pinnedBy: str | None = None
    createdAt: str
    updatedAt: str


class ShowcaseItem(BaseModel):
    noteId: str
    sortOrder: int = 0
    sectionTitle: str | None = None
    displayTitle: str | None = None
    visible: bool = True
    fieldConfig: dict = Field(default_factory=dict)


class ShowcasePage(BaseModel):
    id: str
    ownerUserId: str
    status: ShowcaseStatus = "draft"
    name: str
    description: str | None = None
    bannerUrl: str | None = None
    sceneType: str = "notes"
    templateId: str = "featured_window"
    intakeId: str | None = None
    idempotencyKey: str | None = None
    shareTitle: str | None = None
    contactConfig: dict = Field(default_factory=dict)
    displayConfig: dict = Field(default_factory=dict)
    items: list[ShowcaseItem] = Field(default_factory=list)
    publicSnapshot: dict = Field(default_factory=dict)
    snapshotVersion: int = 0
    snapshotCreatedAt: str | None = None
    shareSnapshot: dict = Field(default_factory=dict)
    shareSnapshotHistory: list[dict] = Field(default_factory=list)
    publishedAt: str | None = None
    createdAt: str
    updatedAt: str


class ViewEvent(BaseModel):
    id: str
    cardId: str
    viewerUserId: str | None = None
    viewType: ViewType
    anonymousId: str | None = None
    visitorIdentityId: str | None = None
    nickname: str | None = None
    avatarUrl: str | None = None
    shareId: str | None = None
    shareFromUserId: str | None = None
    scene: str | None = None
    referrer: str | None = None
    sessionId: str | None = None
    durationSeconds: int = 0
    maxScrollPercent: int = 0
    focusSections: list[str] = Field(default_factory=list)
    viewedAt: str
    dateKey: str


class ShowcaseEvent(BaseModel):
    id: str
    showcaseId: str
    ownerUserId: str
    eventType: str
    noteId: str | None = None
    shareId: str | None = None
    shareFromUserId: str | None = None
    scene: str | None = None
    referrer: str | None = None
    viewerUserId: str | None = None
    viewType: ViewType
    anonymousId: str | None = None
    visitorIdentityId: str | None = None
    nickname: str | None = None
    avatarUrl: str | None = None
    sessionId: str | None = None
    durationSeconds: int = 0
    maxScrollPercent: int = 0
    focusSections: list[str] = Field(default_factory=list)
    createdAt: str
    dateKey: str


class RelayEntry(BaseModel):
    id: str
    cardId: str
    userId: str
    nickname: str
    avatarUrl: str
    maskedNickname: str
    phone: str | None = None
    address: str | None = None
    status: RelayStatus
    followUpStatus: FollowUpStatus
    createdAt: str
    updatedAt: str


class LeadFollowUpLog(BaseModel):
    id: str
    content: str
    createdAt: str
    # A follow-up record is one auditable unit: the operator's action, the
    # selected tags, the note, and the next reminder time share one timestamp.
    # These fields are optional so existing persisted logs remain readable.
    action: str | None = None
    actionLabel: str | None = None
    tags: list[str] = Field(default_factory=list)
    note: str | None = None
    nextFollowUpAt: str | None = None


class LeadReminder(BaseModel):
    id: str
    ownerUserId: str
    cardId: str
    viewerUserId: str
    visitorIdentityId: str | None = None
    nickname: str
    avatarUrl: str | None = None
    status: LeadReminderStatus
    note: str | None = None
    customerPhone: str | None = None
    customerWechat: str | None = None
    customerEmail: str | None = None
    budgetText: str | None = None
    intentLevel: str | None = None
    customerTags: list[str] = Field(default_factory=list)
    viewCount: int = 0
    lastViewedAt: str | None = None
    contactedAt: str | None = None
    closedAt: str | None = None
    conclusionReason: str | None = None
    nextFollowUpAt: str | None = None
    followUpLogs: list[LeadFollowUpLog] = Field(default_factory=list)
    # Monotonic version and idempotency marker make radar actions durable and
    # safe to retry after a client timeout.
    version: int = 0
    lastOperationId: str | None = None
    createdAt: str
    updatedAt: str


class CustomerRadarSummary(BaseModel):
    """Count-only projection used by the radar first screen.

    This table intentionally contains no customer identity, contact details,
    lead history, or event payloads.  It is a rebuildable aggregate keyed by
    owner and workspace mode.
    """

    id: str
    ownerUserId: str
    mode: str = ""
    pendingCount: int = 0
    visitorCount: int = 0
    followingCount: int = 0
    abandonedCount: int = 0
    highIntentCount: int = 0
    interactionCount: int = 0
    revivalCount: int = 0
    filteredCount: int = 0
    isDirty: bool = True
    refreshedAt: str | None = None
    createdAt: str
    updatedAt: str


class CustomerAction(BaseModel):
    id: str
    ownerUserId: str
    noteId: str
    sourceCardId: str | None = None
    viewerUserId: str | None = None
    anonymousId: str | None = None
    visitorIdentityId: str | None = None
    actionKey: CustomerActionKey
    actionLabel: str
    payload: dict = Field(default_factory=dict)
    projectionRefs: dict = Field(default_factory=dict)
    createdAt: str
    updatedAt: str


class MessageThread(BaseModel):
    id: str
    noteId: str
    orderActionId: str | None = None
    ownerUserId: str
    buyerUserId: str
    participantUserIds: list[str] = Field(default_factory=list)
    title: str
    lastMessage: str = ""
    lastMessageAt: str | None = None
    unreadByUser: dict[str, int] = Field(default_factory=dict)
    status: MessageThreadStatus = "active"
    createdAt: str
    updatedAt: str


class MessageRecord(BaseModel):
    id: str
    threadId: str
    senderUserId: str
    content: str
    createdAt: str


class Category(BaseModel):
    id: str
    ownerUserId: str
    name: str
    sortOrder: int
    createdAt: str


class Topic(BaseModel):
    id: str
    ownerUserId: str
    name: str
    description: str | None = None
    color: str | None = None
    createdAt: str
    updatedAt: str


class ImportNotification(BaseModel):
    id: str
    importBatchId: str
    externalUserId: str
    conversationId: str
    status: Literal["success", "failed"]
    title: str
    message: str
    channel: Literal["mock", "wecom"]
    sentAt: str
    errorMessage: str | None = None
    resultType: str | None = None
    resultRefId: str | None = None
    resultPath: str | None = None
    actions: list[dict] = Field(default_factory=list)
    sendStatus: Literal["pending", "sent", "failed", "skipped"] = "pending"
    sendError: str | None = None
    sentMessageAt: str | None = None


class SyncCursor(BaseModel):
    id: str
    openKfid: str
    cursor: str | None = None
    hasMore: bool = False
    lastSource: str
    lastPayload: dict = Field(default_factory=dict)
    lastSyncedAt: str
    syncStatus: SyncStatus = "idle"
    lockToken: str | None = None
    lockedAt: str | None = None
    lastError: str | None = None
    createdAt: str
    updatedAt: str


class MediaRetryJob(BaseModel):
    id: str
    mediaId: str
    mediaType: MessageType
    openKfid: str | None = None
    status: MediaRetryStatus
    attempts: int = 0
    localMediaUrl: str | None = None
    errorMessage: str | None = None
    lastAttemptAt: str | None = None
    createdAt: str
    updatedAt: str


class MediaAsset(BaseModel):
    id: str
    mediaType: str
    originalSha256: str
    storageSha256: str
    url: str
    contentType: str | None = None
    filename: str | None = None
    originalSize: int = 0
    storedSize: int = 0
    status: MediaAssetStatus = "active"
    createdAt: str
    updatedAt: str


class MediaAssetRef(BaseModel):
    id: str
    assetId: str
    ownerUserId: str | None = None
    refType: str
    refId: str
    usage: str = "media"
    createdAt: str
    updatedAt: str


class SyncTask(BaseModel):
    id: str
    name: str
    status: SyncTaskStatus
    payload: dict = Field(default_factory=dict)
    result: dict | None = None
    errorMessage: str | None = None
    attempts: int = 0
    maxAttempts: int = 3
    nextRunAt: str | None = None
    lockedBy: str | None = None
    lockedAt: str | None = None
    createdAt: str
    updatedAt: str


class SyncTaskLog(BaseModel):
    id: str
    taskId: str
    event: str
    message: str
    payload: dict = Field(default_factory=dict)
    createdAt: str


class SkillRun(BaseModel):
    id: str
    skillId: str
    status: SkillRunStatus
    inputSnapshot: dict = Field(default_factory=dict)
    outputRef: str | None = None
    modelProvider: str | None = None
    errorMessage: str | None = None
    cost: float = 0
    startedAt: str
    endedAt: str | None = None


class AutomationDevice(BaseModel):
    id: str
    name: str = "Android 自动化设备"
    platform: Literal["android"] = "android"
    hidDeviceId: str | None = None
    status: AutomationDeviceStatus = "offline"
    activeWechatAccountId: str | None = None
    capabilities: list[str] = Field(default_factory=list)
    lastHeartbeatAt: str | None = None
    metadata: dict = Field(default_factory=dict)
    createdAt: str
    updatedAt: str


class AutomationTask(BaseModel):
    id: str
    functionId: str
    deviceId: str
    targetWechatAccountId: str | None = None
    payload: dict = Field(default_factory=dict)
    status: AutomationTaskStatus = "pending"
    result: dict | None = None
    errorMessage: str | None = None
    attempts: int = 0
    leaseToken: str | None = None
    leaseExpiresAt: str | None = None
    idempotencyKey: str | None = None
    startedAt: str | None = None
    finishedAt: str | None = None
    createdAt: str
    updatedAt: str


class AutomationBatchContent(BaseModel):
    batchNo: int = Field(ge=1, le=100)
    cardId: str | None = Field(default=None, max_length=120)
    text: str | None = Field(default=None, max_length=2000)
    enabled: bool = True
    updatedAt: str | None = None


class AutomationCardAsset(BaseModel):
    id: str
    cardId: str = Field(min_length=1, max_length=120)
    deepLink: str | None = Field(default=None, max_length=2000)
    cardTitle: str | None = Field(default=None, max_length=200)
    status: Literal["active", "inactive", "expired"] = "active"
    createdAt: str
    updatedAt: str


class AutomationGroupContentPlan(BaseModel):
    id: str
    groupCode: str = Field(min_length=1, max_length=40)
    remark: str | None = Field(default=None, max_length=500)
    status: Literal["active", "inactive"] = "active"
    batchContents: list[AutomationBatchContent] = Field(default_factory=list)
    createdAt: str
    updatedAt: str


class AutomationGroupCandidate(BaseModel):
    id: str
    deviceId: str
    wechatAccountId: str
    source: AutomationGroupSource = "xiaohongshu"
    groupQRCode: str | None = None
    groupName: str | None = None
    # One-way fingerprint only; never persist the member names used to derive it.
    groupIdentity: str | None = None
    # Scan-confirmed count of WeChat rows sharing this account/code/name route.
    # None means a legacy/manual candidate whose physical multiplicity is unknown.
    groupOccurrenceCount: int | None = Field(default=None, ge=1, le=10000)
    wechatAccountName: str | None = None
    savedAt: str
    joinStatus: AutomationJoinStatus = "unknown"
    canSend: bool | None = None
    remark: str | None = None
    groupCodes: list[str] = Field(default_factory=list)
    topic: str | None = None
    region: str | None = None
    allowedContentTypes: list[str] = Field(default_factory=list)
    batchContents: list[AutomationBatchContent] = Field(default_factory=list)
    dailySendLimit: int = Field(default=3, ge=0, le=50)
    membershipStatus: AutomationMembershipStatus = "unknown"
    lastActivityAt: str | None = None
    lastVerifiedAt: str | None = None
    lastSeenAt: str | None = None
    groupMemberCount: int | None = None
    groupMemberCountCheckedAt: str | None = None
    groupMemberCountSource: str | None = None
    idempotencyKey: str | None = None
    lastError: str | None = None
    createdAt: str
    updatedAt: str


class WecomArchiveCursor(BaseModel):
    id: str
    corpId: str
    seq: int = 0
    status: ArchiveCursorStatus = "idle"
    lastPayload: dict = Field(default_factory=dict)
    lastSyncedAt: str
    lockToken: str | None = None
    lockedAt: str | None = None
    lastError: str | None = None
    createdAt: str
    updatedAt: str


class WecomArchiveMessage(BaseModel):
    id: str
    corpId: str
    seq: int
    msgId: str | None = None
    action: str | None = None
    fromUser: str | None = None
    toList: list[str] = Field(default_factory=list)
    roomId: str | None = None
    msgTime: str | None = None
    msgType: str | None = None
    rawPayload: dict = Field(default_factory=dict)
    decryptedPayload: dict | None = None
    mediaRefs: list[dict] = Field(default_factory=list)
    generatedNoteId: str | None = None
    generatedCardId: str | None = None
    processedAt: str | None = None
    processError: str | None = None
    createdAt: str


class ResourceWallet(BaseModel):
    id: str
    ownerUserId: str
    balance: int = 0
    totalGranted: int = 0
    totalConsumed: int = 0
    status: Literal["active", "frozen"] = "active"
    createdAt: str
    updatedAt: str


class ResourcePointLedger(BaseModel):
    id: str
    ownerUserId: str
    walletId: str
    ledgerType: ResourceLedgerType
    actionType: str
    targetType: str | None = None
    targetId: str | None = None
    pointsDelta: int
    balanceAfter: int
    reason: str | None = None
    operatorId: str | None = None
    relatedUnlockId: str | None = None
    metadata: dict = Field(default_factory=dict)
    createdAt: str


class ResourceFreeQuota(BaseModel):
    id: str
    ownerUserId: str
    quotaType: str
    periodKey: str
    limitCount: int
    usedCount: int = 0
    createdAt: str
    updatedAt: str


class ResourceUnlockRecord(BaseModel):
    id: str
    ownerUserId: str
    actionType: str
    targetType: str
    targetId: str
    pointsCost: int = 0
    usedFreeQuota: bool = False
    quotaId: str | None = None
    ledgerId: str | None = None
    unlockedAt: str
    expiresAt: str | None = None
    createdAt: str
    updatedAt: str


class OpportunityLead(BaseModel):
    id: str
    title: str
    summary: str = ""
    city: str | None = None
    district: str | None = None
    industry: str | None = None
    demandType: str = "需求"
    content: str = ""
    tags: list[str] = Field(default_factory=list)
    contactStatus: OpportunityContactStatus = "pending_verify"
    trustStatus: OpportunityTrustStatus = "pending"
    status: OpportunityLeadStatus = "draft"
    priority: str | None = None
    publishedAt: str | None = None
    expiresAt: str | None = None
    # Explicitly marked operator test data may be permanently removed from
    # the PC cleanup tool. Formal business records remain archive-only.
    isTest: bool = False
    createdAt: str
    updatedAt: str


class OpportunityLeadSource(BaseModel):
    id: str
    leadId: str
    sourcePlatform: str | None = None
    sourceUrl: str | None = None
    sourceAuthor: str | None = None
    sourcePublishedAt: str | None = None
    sourceCapturedAt: str
    rawText: str = ""
    rawImages: list[str] = Field(default_factory=list)
    createdAt: str
    updatedAt: str


class OpportunityLeadContact(BaseModel):
    id: str
    leadId: str
    contactType: str
    contactValueEncrypted: str = ""
    contactMasked: str = ""
    verifyStatus: str = "pending"
    createdAt: str
    updatedAt: str


class OpportunityLeadMatch(BaseModel):
    id: str
    leadId: str
    userId: str
    matchScore: int = 0
    matchReasons: list[str] = Field(default_factory=list)
    status: OpportunityMatchStatus = "new"
    createdAt: str
    updatedAt: str


class OpportunityLeadSave(BaseModel):
    id: str
    leadId: str
    userId: str
    status: OpportunitySaveStatus = "saved"
    note: str | None = None
    reminderAt: str | None = None
    createdAt: str
    updatedAt: str


class OpportunityLeadFollowup(BaseModel):
    id: str
    leadId: str
    userId: str
    actionType: str
    note: str | None = None
    createdAt: str


class ResponsePackage(BaseModel):
    id: str
    ownerUserId: str
    leadId: str
    status: ResponsePackageStatus = "draft"
    title: str
    demandSummary: dict = Field(default_factory=dict)
    openingText: str = ""
    trackingUrl: str | None = None
    followupSuggestion: str | None = None
    costPoints: int = 0
    usedFreeQuota: bool = False
    createdAt: str
    updatedAt: str
    sentAt: str | None = None
    lastViewedAt: str | None = None


class ResponsePackageItem(BaseModel):
    id: str
    responsePackageId: str
    assetType: str
    assetId: str
    assetTitle: str
    assetSummary: str | None = None
    recommendReason: str
    sortOrder: int = 0
    createdAt: str


class ResponsePackageEvent(BaseModel):
    id: str
    responsePackageId: str
    eventType: str
    viewerId: str | None = None
    anonymousId: str | None = None
    metadata: dict = Field(default_factory=dict)
    createdAt: str


class OpportunitySubscription(BaseModel):
    id: str
    ownerUserId: str
    direction: str = "两边都看"
    lookingFor: str = ""
    providing: str = ""
    city: str = ""
    contactRequirement: str = "有电话"
    keywords: str = ""
    reminderCadence: str = "每天早上"
    status: OpportunitySubscriptionStatus = "active"
    createdAt: str
    updatedAt: str


class SupplyDemandCard(BaseModel):
    id: str
    ownerUserId: str
    cardType: SupplyDemandCardType = "supply"
    status: SupplyDemandCardStatus = "draft"
    title: str
    summary: str = ""
    city: str | None = None
    industry: str | None = None
    demandType: str = "合作"
    contactRequirement: str | None = None
    linkedNoteId: str | None = None
    linkedResourceType: str | None = None
    linkedResourceId: str | None = None
    tags: list[str] = Field(default_factory=list)
    # Contact values are kept behind the detail/unlock boundary.  Existing
    # cards may omit these fields and remain valid.
    contactSource: str = "none"
    contactType: str | None = None
    contactValueEncrypted: str = ""
    contactMasked: str = ""
    contactVerifyStatus: str = "self_declared"
    expiresAt: str | None = None
    reviewNote: str | None = None
    publishedAt: str | None = None
    reviewedAt: str | None = None
    # Keep destructive cleanup opt-in and limited to records intentionally
    # created as test data by an operator.
    isTest: bool = False
    createdAt: str
    updatedAt: str


class SupplyDemandApplication(BaseModel):
    id: str
    cardId: str
    applicantUserId: str
    ownerUserId: str
    status: SupplyDemandApplicationStatus = "pending"
    message: str = ""
    contactSnapshot: dict = Field(default_factory=dict)
    createdAt: str
    updatedAt: str


class OpportunityPushDigest(BaseModel):
    id: str
    ownerUserId: str
    subscriptionId: str | None = None
    title: str
    summary: str = ""
    status: OpportunityPushDigestStatus = "pending"
    recommendedLeadIds: list[str] = Field(default_factory=list)
    recommendedSupplyDemandCardIds: list[str] = Field(default_factory=list)
    createdAt: str
    updatedAt: str
    readAt: str | None = None


class MembershipOrder(BaseModel):
    id: str
    userId: str
    planCode: str = "sales_scrm_monthly"
    amountFen: int = 1990
    status: MembershipOrderStatus = "pending"
    paymentChannel: str = "test"
    paymentTransactionId: str | None = None
    referralRelationId: str | None = None
    paidAt: str | None = None
    refundedAt: str | None = None
    createdAt: str
    updatedAt: str


class MembershipEntitlement(BaseModel):
    id: str
    userId: str
    entitlementKey: str = "customer_intelligence"
    status: MembershipEntitlementStatus = "active"
    sourceOrderId: str
    startsAt: str
    expiresAt: str
    revokedAt: str | None = None
    createdAt: str
    updatedAt: str


class MutualPointAccount(BaseModel):
    id: str
    userId: str
    # The current physical table is kept for production compatibility, while
    # accountType lets future tools share the same points core without adding
    # another balance field or wallet table.
    accountType: str = "mutual_help"
    pointType: str = "base"
    balance: int = 0
    totalGranted: int = 0
    totalConsumed: int = 0
    createdAt: str
    updatedAt: str


class MutualPointLedger(BaseModel):
    id: str
    userId: str
    accountType: str = "mutual_help"
    pointType: str = "base"
    ledgerType: str
    pointsDelta: int
    balanceAfter: int
    reason: str
    relatedOrderId: str | None = None
    idempotencyKey: str | None = None
    sourceType: str | None = None
    sourceId: str | None = None
    metadata: dict = Field(default_factory=dict)
    createdAt: str


class MutualRechargeOrder(BaseModel):
    id: str
    userId: str
    points: int
    pointType: str = "reward"
    amountFen: int
    status: MutualRechargeOrderStatus = "pending"
    paymentChannel: str = "test"
    paymentTransactionId: str | None = None
    paidAt: str | None = None
    refundedAt: str | None = None
    createdAt: str
    updatedAt: str


class MutualActivityEvent(BaseModel):
    id: str
    eventType: MutualActivityEventType
    userId: str
    taskId: str
    taskKind: str = "ordinary"
    linkId: str = ""
    sessionId: str = ""
    metadata: dict = Field(default_factory=dict)
    idempotencyKey: str
    createdAt: str


class MutualHelpTask(BaseModel):
    """Server-authoritative task data shared by every logged-in device."""

    id: str
    ownerUserId: str
    taskKind: str = "ordinary"
    title: str
    category: str = "其他"
    description: str = ""
    contentBlocks: list[dict] = Field(default_factory=list)
    acceptanceCriteriaBlocks: list[dict] = Field(default_factory=list)
    taskLinks: list[dict] = Field(default_factory=list)
    shortLink: str = ""
    rewardPointType: str = "base"
    # once: each user can complete the task once; daily: once per Shanghai
    # calendar day while the task remains published and has quota.
    repeatPolicy: str = "once"
    woolPolicy: dict = Field(default_factory=dict)
    rewardPoints: int = 0
    executorReward: int = 0
    # Recharge-point tasks reserve the full budget when published. This keeps
    # a publisher from spending the same withdrawable points elsewhere while
    # submissions are still arriving.
    rewardBudgetReserved: int = 0
    rewardBudgetUsed: int = 0
    rewardBudgetReleased: int = 0
    remaining: int | None = None
    deadlineText: str = "长期开放"
    status: str = "published"
    woolAccessRecords: list[dict] = Field(default_factory=list)
    woolComments: list[dict] = Field(default_factory=list)
    woolCommentReports: list[dict] = Field(default_factory=list)
    woolTips: list[dict] = Field(default_factory=list)
    woolRefunds: list[dict] = Field(default_factory=list)
    # Formal tasks are never hard-deleted by the PC cleanup tool unless an
    # operator explicitly created them as test data.
    isTest: bool = False
    # Platform operators can promote a task without changing its lifecycle.
    isPinned: bool = False
    pinnedAt: str | None = None
    pinnedBy: str | None = None
    # Versioned server-generated image used by native WeChat sharing. History
    # is retained for the media cleanup worker and is never sent to clients.
    shareSnapshot: dict = Field(default_factory=dict)
    shareSnapshotHistory: list[dict] = Field(default_factory=list)
    createdAt: str
    updatedAt: str


class MutualHelpSubmission(BaseModel):
    id: str
    taskId: str
    executorUserId: str
    ownerUserId: str
    # The server's Asia/Shanghai calendar day for this participation.
    participationDay: str = ""
    status: str = "submitted"
    autoApproved: bool = False
    text: str = ""
    images: list[str] = Field(default_factory=list)
    submittedAt: str
    reviewDeadlineAt: str | None = None
    approvedAt: str | None = None
    completedAt: str | None = None
    rewardSettled: bool = False
    publisherCost: int = 0
    executorReward: int = 0
    publisherCostReserved: bool = False
    publisherBudgetReserved: bool = False
    publisherCostReservationReleased: bool = False
    publisherCostAllocations: list[dict] = Field(default_factory=list)
    rejectionReason: str = ""
    rejectedAt: str | None = None
    createdAt: str
    updatedAt: str


class MutualHelpConversation(BaseModel):
    """One private publisher/executor conversation for a mutual-help task."""

    id: str
    taskId: str
    ownerUserId: str
    executorUserId: str
    lastMessageAt: str | None = None
    lastMessagePreview: str = ""
    unreadByUser: dict[str, int] = Field(default_factory=dict)
    createdAt: str
    updatedAt: str


class MutualHelpChatMessage(BaseModel):
    id: str
    conversationId: str
    taskId: str
    senderUserId: str
    recipientUserId: str
    messageType: str = "text"
    text: str = ""
    imageUrl: str = ""
    miniProgram: dict = Field(default_factory=dict)
    idempotencyKey: str = ""
    createdAt: str


class NotificationPreference(BaseModel):
    id: str
    userId: str
    importantCustomerViewEnabled: bool = True
    ordinaryAnonymousViewEnabled: bool = True
    createdAt: str
    updatedAt: str


class WechatSubscriptionGrant(BaseModel):
    id: str
    userId: str
    templateId: str
    requestId: str = ""
    status: WechatSubscriptionGrantStatus = "available"
    source: str = "share"
    authorizedAt: str
    reservedAt: str | None = None
    consumedAt: str | None = None
    invalidAt: str | None = None
    createdAt: str
    updatedAt: str


class WechatSubscriptionDelivery(BaseModel):
    id: str
    ownerUserId: str
    grantId: str
    templateId: str
    notificationType: WechatSubscriptionNotificationType = "view"
    resourceType: Literal["card", "note", "showcase", "live_qr"]
    resourceId: str
    resourceTitle: str
    viewerType: Literal["important", "ordinary", "anonymous"]
    viewerLabel: str
    messageContent: str
    threadId: str | None = None
    messageId: str | None = None
    eventAt: str
    dedupeKey: str
    page: str
    data: dict = Field(default_factory=dict)
    status: WechatSubscriptionDeliveryStatus = "queued"
    attempts: int = 0
    lastError: str | None = None
    sentAt: str | None = None
    createdAt: str
    updatedAt: str


class ReferralRelation(BaseModel):
    id: str
    inviterUserId: str
    inviteeUserId: str
    source: str = "invite_code"
    createdAt: str
    updatedAt: str


class ReferralReward(BaseModel):
    id: str
    inviterUserId: str
    inviteeUserId: str
    sourceOrderId: str
    ratioBasisPoints: int = 5000
    amountFen: int
    reservedFen: int = 0
    withdrawnFen: int = 0
    status: ReferralRewardStatus = "pending"
    availableAt: str | None = None
    withdrawnAt: str | None = None
    revokedAt: str | None = None
    createdAt: str
    updatedAt: str


class ReferralWithdrawal(BaseModel):
    id: str
    userId: str
    amountFen: int
    feeFen: int = 0
    status: ReferralWithdrawalStatus = "pending"
    rewardIds: list[str] = Field(default_factory=list)
    rewardAllocations: dict[str, int] = Field(default_factory=dict)
    reviewedAt: str | None = None
    paidAt: str | None = None
    outBillNo: str | None = None
    transferBillNo: str | None = None
    transferState: str | None = None
    packageInfo: str | None = None
    failureReason: str | None = None
    settlementSource: str | None = None
    settlementNote: str | None = None
    createdAt: str
    updatedAt: str


class MutualPointWithdrawal(BaseModel):
    """A manual-review withdrawal from the cashable recharge-point ledger."""

    id: str
    userId: str
    pointType: str = "reward"
    points: int
    grossAmountFen: int
    feeRateBasisPoints: int = 2000
    feeFen: int = 0
    amountFen: int
    status: MutualPointWithdrawalStatus = "pending"
    reviewedAt: str | None = None
    paidAt: str | None = None
    outBillNo: str | None = None
    transferBillNo: str | None = None
    transferState: str | None = None
    packageInfo: str | None = None
    failureReason: str | None = None
    settlementSource: str | None = None
    settlementNote: str | None = None
    createdAt: str
    updatedAt: str


class SameStyleGeneration(BaseModel):
    id: str
    ownerUserId: str
    mode: Literal["reuse_content", "use_own_content"]
    sourceNoteId: str | None = None
    sourceShowcaseId: str | None = None
    sourceTemplateId: str | None = None
    generatedNoteId: str | None = None
    generatedShowcaseId: str | None = None
    referralRelationId: str | None = None
    idempotencyKey: str
    createdAt: str
    updatedAt: str


class LiveQrCode(BaseModel):
    id: str
    code: str
    ownerUserId: str | None = None
    name: str
    description: str | None = None
    groupAvatarUrl: str | None = None
    targetQrImageUrl: str | None = None
    targetQrImageUpdatedAt: str | None = None
    # The original upload remains the source of truth.  A source-style poster
    # is an optional derived asset that replaces only the QR in that upload.
    posterMode: Literal["plain", "source"] = "plain"
    posterImageUrl: str | None = None
    # Keep lightweight version metadata with the fixed entry.  Historical QR
    # binaries are intentionally not retained; only the current target image
    # is needed to keep the entry useful and media storage bounded.
    targetQrHistory: list[dict] = Field(default_factory=list)
    automationGroupCandidateId: str | None = None
    groupMemberCount: int | None = None
    groupMemberCountCheckedAt: str | None = None
    groupMemberCountSource: str | None = None
    targetUrl: str
    targetExpiresAt: str | None = None
    status: Literal["active", "paused"] = "active"
    version: int = 1
    scanCount: int = 0
    lastScannedAt: str | None = None
    targetUpdatedAt: str
    createdAt: str
    updatedAt: str


class GroupResource(BaseModel):
    id: str
    ownerUserId: str
    name: str
    cityMode: Literal["national", "city"] = "city"
    cityLabel: str = ""
    cityCode: str | None = None
    industry: str
    purpose: str
    tags: list[str] = Field(default_factory=list)
    memberRange: str | None = None
    activeLevel: str | None = None
    remark: str | None = None
    qrImageUrl: str
    status: Literal["active", "expired", "rejected", "deleted"] = "active"
    expiresAt: str
    createdAt: str
    updatedAt: str
    qrUpdatedAt: str
    views: int = 0
    confirmCount: int = 0
    rewardState: Literal["pending", "paid", "capped", "cancelled"] = "pending"
    rewardAmount: int = 0
    # `user` keeps the normal reward/penalty path.  Admin-created resources
    # still use the canonical public catalogue but must not credit or punish a
    # person merely because an operator entered the record.
    sourceType: Literal["user", "mobile_admin", "platform_admin"] = "user"
    createdByUserId: str | None = None
    createdByOperator: str | None = None
    # New group-resource submissions remain visible while they are under
    # review. These fields are defaulted so old production payloads continue
    # to load without a data migration.
    reviewStatus: Literal["reviewing", "approved", "rejected", "paused", "removed"] = "reviewing"
    qrVersion: int = 1
    complaintCount: int = 0
    lastComplaintAt: str | None = None
    rewardReleasedAt: str | None = None
    rewardRevokedAt: str | None = None
    penaltyDebt: int = 0
    reviewLogs: list[dict] = Field(default_factory=list)
    complaints: list[dict] = Field(default_factory=list)
    refundedViewLedgerIds: list[str] = Field(default_factory=list)
    # Formal group resources are archive/remove-only. This flag is the sole
    # opt-in for irreversible cleanup in the operations console.
    isTest: bool = False
    # Platform operators can promote an eligible resource without changing
    # review status, expiry, reward or complaint handling.
    isPinned: bool = False
    pinnedAt: str | None = None
    pinnedBy: str | None = None


class ContentSafetyRule(BaseModel):
    id: str
    term: str
    normalizedTerm: str
    termHash: str
    matchType: ContentSafetyRuleMatchType = "contains"
    category: str = "platform_custom"
    severity: ContentSafetyRuleSeverity = "medium"
    action: ContentSafetyRuleAction = "review"
    scopes: list[str] = Field(default_factory=list)
    enabled: bool = True
    version: int = 1
    source: Literal["manual", "import", "provider"] = "manual"
    expiresAt: str | None = None
    operatorName: str = "ops"
    reason: str = ""
    createdAt: str
    updatedAt: str


class ContentModerationAssessment(BaseModel):
    id: str
    targetType: str
    targetId: str
    ownerUserId: str | None = None
    contentRevision: str = ""
    contentFingerprint: str
    ruleVersion: str
    status: ContentModerationStatus = "allowed"
    decision: ContentModerationDecision = "allow"
    matchedRuleIds: list[str] = Field(default_factory=list)
    matchSummary: list[dict] = Field(default_factory=list)
    reviewedBy: str | None = None
    reviewedAt: str | None = None
    reviewNote: str | None = None
    createdAt: str
    updatedAt: str


class ContentModerationAuditLog(BaseModel):
    id: str
    eventType: str
    targetType: str | None = None
    targetId: str | None = None
    assessmentId: str | None = None
    ruleId: str | None = None
    operatorName: str = "system"
    details: dict = Field(default_factory=dict)
    createdAt: str


class AppState(BaseModel):
    users: list[User] = Field(default_factory=list)
    wecom_identity_bindings: list[WecomIdentityBinding] = Field(default_factory=list)
    wecom_bind_card_tokens: list[WecomBindCardToken] = Field(default_factory=list)
    wecom_bind_card_assets: list[WecomBindCardAsset] = Field(default_factory=list)
    import_batches: list[ImportBatch] = Field(default_factory=list)
    raw_messages: list[RawMessage] = Field(default_factory=list)
    cards: list[Card] = Field(default_factory=list)
    user_notes: list[UserNote] = Field(default_factory=list)
    showcase_pages: list[ShowcasePage] = Field(default_factory=list)
    view_events: list[ViewEvent] = Field(default_factory=list)
    showcase_events: list[ShowcaseEvent] = Field(default_factory=list)
    relay_entries: list[RelayEntry] = Field(default_factory=list)
    lead_reminders: list[LeadReminder] = Field(default_factory=list)
    customer_radar_summaries: list[CustomerRadarSummary] = Field(default_factory=list)
    customer_actions: list[CustomerAction] = Field(default_factory=list)
    message_threads: list[MessageThread] = Field(default_factory=list)
    message_records: list[MessageRecord] = Field(default_factory=list)
    categories: list[Category] = Field(default_factory=list)
    topics: list[Topic] = Field(default_factory=list)
    import_notifications: list[ImportNotification] = Field(default_factory=list)
    sync_cursors: list[SyncCursor] = Field(default_factory=list)
    media_retry_jobs: list[MediaRetryJob] = Field(default_factory=list)
    media_assets: list[MediaAsset] = Field(default_factory=list)
    media_asset_refs: list[MediaAssetRef] = Field(default_factory=list)
    sync_tasks: list[SyncTask] = Field(default_factory=list)
    sync_task_logs: list[SyncTaskLog] = Field(default_factory=list)
    skill_runs: list[SkillRun] = Field(default_factory=list)
    automation_devices: list[AutomationDevice] = Field(default_factory=list)
    automation_tasks: list[AutomationTask] = Field(default_factory=list)
    automation_group_candidates: list[AutomationGroupCandidate] = Field(default_factory=list)
    automation_card_assets: list[AutomationCardAsset] = Field(default_factory=list)
    automation_group_content_plans: list[AutomationGroupContentPlan] = Field(default_factory=list)
    wecom_archive_cursors: list[WecomArchiveCursor] = Field(default_factory=list)
    wecom_archive_messages: list[WecomArchiveMessage] = Field(default_factory=list)
    resource_wallets: list[ResourceWallet] = Field(default_factory=list)
    resource_point_ledgers: list[ResourcePointLedger] = Field(default_factory=list)
    resource_free_quotas: list[ResourceFreeQuota] = Field(default_factory=list)
    resource_unlock_records: list[ResourceUnlockRecord] = Field(default_factory=list)
    opportunity_leads: list[OpportunityLead] = Field(default_factory=list)
    opportunity_lead_sources: list[OpportunityLeadSource] = Field(default_factory=list)
    opportunity_lead_contacts: list[OpportunityLeadContact] = Field(default_factory=list)
    opportunity_lead_matches: list[OpportunityLeadMatch] = Field(default_factory=list)
    opportunity_lead_saves: list[OpportunityLeadSave] = Field(default_factory=list)
    opportunity_lead_followups: list[OpportunityLeadFollowup] = Field(default_factory=list)
    response_packages: list[ResponsePackage] = Field(default_factory=list)
    response_package_items: list[ResponsePackageItem] = Field(default_factory=list)
    response_package_events: list[ResponsePackageEvent] = Field(default_factory=list)
    opportunity_subscriptions: list[OpportunitySubscription] = Field(default_factory=list)
    supply_demand_cards: list[SupplyDemandCard] = Field(default_factory=list)
    supply_demand_applications: list[SupplyDemandApplication] = Field(default_factory=list)
    opportunity_push_digests: list[OpportunityPushDigest] = Field(default_factory=list)
    membership_orders: list[MembershipOrder] = Field(default_factory=list)
    membership_entitlements: list[MembershipEntitlement] = Field(default_factory=list)
    mutual_point_accounts: list[MutualPointAccount] = Field(default_factory=list)
    mutual_point_ledgers: list[MutualPointLedger] = Field(default_factory=list)
    mutual_recharge_orders: list[MutualRechargeOrder] = Field(default_factory=list)
    mutual_activity_events: list[MutualActivityEvent] = Field(default_factory=list)
    mutual_help_tasks: list[MutualHelpTask] = Field(default_factory=list)
    mutual_help_submissions: list[MutualHelpSubmission] = Field(default_factory=list)
    mutual_help_conversations: list[MutualHelpConversation] = Field(default_factory=list)
    mutual_help_chat_messages: list[MutualHelpChatMessage] = Field(default_factory=list)
    notification_preferences: list[NotificationPreference] = Field(default_factory=list)
    wechat_subscription_grants: list[WechatSubscriptionGrant] = Field(default_factory=list)
    wechat_subscription_deliveries: list[WechatSubscriptionDelivery] = Field(default_factory=list)
    referral_relations: list[ReferralRelation] = Field(default_factory=list)
    referral_rewards: list[ReferralReward] = Field(default_factory=list)
    referral_withdrawals: list[ReferralWithdrawal] = Field(default_factory=list)
    mutual_point_withdrawals: list[MutualPointWithdrawal] = Field(default_factory=list)
    same_style_generations: list[SameStyleGeneration] = Field(default_factory=list)
    live_qr_codes: list[LiveQrCode] = Field(default_factory=list)
    group_resources: list[GroupResource] = Field(default_factory=list)
    content_safety_rules: list[ContentSafetyRule] = Field(default_factory=list)
    content_moderation_assessments: list[ContentModerationAssessment] = Field(default_factory=list)
    content_moderation_audit_logs: list[ContentModerationAuditLog] = Field(default_factory=list)
