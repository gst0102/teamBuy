from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


ImportStatus = Literal["pending", "success", "failed", "claimed"]
CardStatus = Literal["draft", "published", "archived"]
UserNoteStatus = Literal["draft", "active", "deleted"]
ViewType = Literal["logged_in", "anonymous", "share"]
RelayStatus = Literal["active", "deleted"]
FollowUpStatus = Literal["pending", "followed"]
LeadReminderStatus = Literal["pending", "contacted", "invalid", "paused", "completed"]
MessageType = Literal["text", "image", "link", "location", "video", "file", "weapp", "unknown"]
SourceType = Literal["wechat_note", "miniapp_link", "mp_link", "web_link", "unknown"]
SyncStatus = Literal["idle", "running", "success", "failed"]
MediaRetryStatus = Literal["pending", "success", "failed"]
SyncTaskStatus = Literal["queued", "running", "success", "failed", "retrying", "skipped"]
SkillRunStatus = Literal["pending", "success", "failed", "needs_confirm"]
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


class User(BaseModel):
    id: str
    openid: str
    unionid: str | None = None
    nickname: str
    avatarUrl: str
    wechat: str | None = None
    phone: str | None = None
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
    title: str
    summary: str
    body: str
    coverUrl: str | None = None
    media: list[dict] = Field(default_factory=list)
    categoryIds: list[str] = Field(default_factory=list)
    phone: str | None = None
    locationText: str | None = None
    sourceRefs: list[str] = Field(default_factory=list)
    visibilityConfig: dict = Field(default_factory=dict)
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
    templateId: str = "featured_window"
    shareTitle: str | None = None
    contactConfig: dict = Field(default_factory=dict)
    displayConfig: dict = Field(default_factory=dict)
    items: list[ShowcaseItem] = Field(default_factory=list)
    publicSnapshot: dict = Field(default_factory=dict)
    snapshotVersion: int = 0
    snapshotCreatedAt: str | None = None
    publishedAt: str | None = None
    createdAt: str
    updatedAt: str


class ViewEvent(BaseModel):
    id: str
    cardId: str
    viewerUserId: str | None = None
    viewType: ViewType
    anonymousId: str | None = None
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


class LeadReminder(BaseModel):
    id: str
    ownerUserId: str
    cardId: str
    viewerUserId: str
    nickname: str
    avatarUrl: str | None = None
    status: LeadReminderStatus
    note: str | None = None
    customerPhone: str | None = None
    customerWechat: str | None = None
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
    createdAt: str
    updatedAt: str


class CustomerAction(BaseModel):
    id: str
    ownerUserId: str
    noteId: str
    sourceCardId: str | None = None
    viewerUserId: str | None = None
    anonymousId: str | None = None
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
    reviewNote: str | None = None
    publishedAt: str | None = None
    reviewedAt: str | None = None
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


class AppState(BaseModel):
    users: list[User] = Field(default_factory=list)
    wecom_identity_bindings: list[WecomIdentityBinding] = Field(default_factory=list)
    import_batches: list[ImportBatch] = Field(default_factory=list)
    raw_messages: list[RawMessage] = Field(default_factory=list)
    cards: list[Card] = Field(default_factory=list)
    user_notes: list[UserNote] = Field(default_factory=list)
    showcase_pages: list[ShowcasePage] = Field(default_factory=list)
    view_events: list[ViewEvent] = Field(default_factory=list)
    showcase_events: list[ShowcaseEvent] = Field(default_factory=list)
    relay_entries: list[RelayEntry] = Field(default_factory=list)
    lead_reminders: list[LeadReminder] = Field(default_factory=list)
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
