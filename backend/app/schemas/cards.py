from __future__ import annotations

from pydantic import BaseModel, Field


class RelayConfigPayload(BaseModel):
    enabled: bool = True
    requirePhone: bool = False
    requireAddress: bool = False


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
    relayConfig: RelayConfigPayload = Field(default_factory=RelayConfigPayload)


class PublishCardRequest(BaseModel):
    userId: str


class DuplicateCardRequest(BaseModel):
    userId: str


class RecordViewRequest(BaseModel):
    viewerUserId: str | None = None
    anonymousId: str | None = None
    nickname: str | None = None
    avatarUrl: str | None = None


class CreateRelayRequest(BaseModel):
    userId: str
    nickname: str
    avatarUrl: str = "https://example.com/avatar-default.png"
    phone: str | None = None
    address: str | None = None


class FollowUpRelayRequest(BaseModel):
    operatorUserId: str

