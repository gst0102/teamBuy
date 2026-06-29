from __future__ import annotations

from pydantic import BaseModel, Field


class RelayConfigPayload(BaseModel):
    enabled: bool = True
    requirePhone: bool = False
    requireAddress: bool = False


class CardMediaPayload(BaseModel):
    type: str
    url: str
    sortOrder: int = 1


class CardUpdateRequest(BaseModel):
    ownerUserId: str
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
    media: list[CardMediaPayload] = Field(default_factory=list)
    relayConfig: RelayConfigPayload = Field(default_factory=RelayConfigPayload)


class CardCreateRequest(BaseModel):
    ownerUserId: str
    title: str
    coverUrl: str | None = None
    detailText: str = ""
    projectName: str | None = None
    locationText: str | None = None
    phone: str | None = None
    relayNotice: str | None = None
    sourceUrl: str | None = None
    enabledFields: list[str] = Field(default_factory=list)
    categoryIds: list[str] = Field(default_factory=list)
    media: list[CardMediaPayload] = Field(default_factory=list)
    relayConfig: RelayConfigPayload = Field(default_factory=RelayConfigPayload)


class PublishCardRequest(BaseModel):
    userId: str


class DuplicateCardRequest(BaseModel):
    userId: str


class RecordViewRequest(BaseModel):
    eventType: str | None = None
    viewerUserId: str | None = None
    anonymousId: str | None = None
    nickname: str | None = None
    avatarUrl: str | None = None
    shareId: str | None = None
    shareFromUserId: str | None = None
    scene: str | None = None
    referrer: str | None = None
    sessionId: str | None = None
    durationSeconds: int | None = None
    maxScrollPercent: int | None = None
    focusSections: list[str] = Field(default_factory=list)


class CreateRelayRequest(BaseModel):
    userId: str
    nickname: str
    avatarUrl: str = ""
    phone: str | None = None
    address: str | None = None


class FollowUpRelayRequest(BaseModel):
    operatorUserId: str


class LeadReminderUpsertRequest(BaseModel):
    ownerUserId: str
    cardId: str
    viewerUserId: str
    nickname: str
    avatarUrl: str | None = None
    status: str = "pending"
    note: str | None = None
    viewCount: int = 0
    lastViewedAt: str | None = None
    nextFollowUpAt: str | None = None


class LeadReminderUpdateRequest(BaseModel):
    ownerUserId: str
    status: str | None = None
    note: str | None = None
    customerPhone: str | None = None
    customerWechat: str | None = None
    budgetText: str | None = None
    intentLevel: str | None = None
    customerTags: list[str] | None = None
    conclusionReason: str | None = None
    nextFollowUpAt: str | None = None
    logContent: str | None = None
