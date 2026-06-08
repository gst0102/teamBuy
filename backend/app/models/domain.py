from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


ImportStatus = Literal["pending", "success", "failed", "claimed"]
CardStatus = Literal["draft", "published", "archived"]
ViewType = Literal["logged_in", "anonymous"]
RelayStatus = Literal["active", "deleted"]
FollowUpStatus = Literal["pending", "followed"]
MessageType = Literal["text", "image", "link", "location", "video", "file", "unknown"]
SourceType = Literal["wechat_note", "miniapp_link", "mp_link", "web_link", "unknown"]


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
    createdAt: str
    updatedAt: str


class AppState(BaseModel):
    users: list[User] = Field(default_factory=list)
    import_batches: list[ImportBatch] = Field(default_factory=list)
    raw_messages: list[RawMessage] = Field(default_factory=list)
    cards: list[Card] = Field(default_factory=list)
    view_events: list[ViewEvent] = Field(default_factory=list)
    relay_entries: list[RelayEntry] = Field(default_factory=list)
    categories: list[Category] = Field(default_factory=list)
    import_notifications: list[ImportNotification] = Field(default_factory=list)
    sync_cursors: list[SyncCursor] = Field(default_factory=list)
