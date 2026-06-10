from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


ImportStatus = Literal["pending", "success", "failed", "claimed"]
CardStatus = Literal["draft", "published", "archived"]
ViewType = Literal["logged_in", "anonymous"]
RelayStatus = Literal["active", "deleted"]
FollowUpStatus = Literal["pending", "followed"]
LeadReminderStatus = Literal["pending", "contacted"]
MessageType = Literal["text", "image", "link", "location", "video", "file", "unknown"]
SourceType = Literal["wechat_note", "miniapp_link", "mp_link", "web_link", "unknown"]
SyncStatus = Literal["idle", "running", "success", "failed"]
MediaRetryStatus = Literal["pending", "success", "failed"]
SyncTaskStatus = Literal["queued", "running", "success", "failed", "retrying", "skipped"]


class User(BaseModel):
    id: str
    openid: str
    unionid: str | None = None
    nickname: str
    avatarUrl: str
    phone: str | None = None
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


class ViewEvent(BaseModel):
    id: str
    cardId: str
    viewerUserId: str | None = None
    viewType: ViewType
    anonymousId: str | None = None
    nickname: str | None = None
    avatarUrl: str | None = None
    viewedAt: str
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
    viewCount: int = 0
    lastViewedAt: str | None = None
    contactedAt: str | None = None
    nextFollowUpAt: str | None = None
    followUpLogs: list[LeadFollowUpLog] = Field(default_factory=list)
    createdAt: str
    updatedAt: str


class Category(BaseModel):
    id: str
    ownerUserId: str
    name: str
    sortOrder: int
    createdAt: str


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


class AppState(BaseModel):
    users: list[User] = Field(default_factory=list)
    import_batches: list[ImportBatch] = Field(default_factory=list)
    raw_messages: list[RawMessage] = Field(default_factory=list)
    cards: list[Card] = Field(default_factory=list)
    view_events: list[ViewEvent] = Field(default_factory=list)
    relay_entries: list[RelayEntry] = Field(default_factory=list)
    lead_reminders: list[LeadReminder] = Field(default_factory=list)
    categories: list[Category] = Field(default_factory=list)
    import_notifications: list[ImportNotification] = Field(default_factory=list)
    sync_cursors: list[SyncCursor] = Field(default_factory=list)
    media_retry_jobs: list[MediaRetryJob] = Field(default_factory=list)
    sync_tasks: list[SyncTask] = Field(default_factory=list)
    sync_task_logs: list[SyncTaskLog] = Field(default_factory=list)
