from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.skills import ContentMediaPayload


class UserNoteUpdateRequest(BaseModel):
    ownerUserId: str
    title: str
    summary: str | None = None
    body: str
    coverUrl: str | None = None
    media: list[ContentMediaPayload] = Field(default_factory=list)
    categoryIds: list[str] = Field(default_factory=list)
    phone: str | None = None
    locationText: str | None = None
    visibilityConfig: dict = Field(default_factory=dict)


class ManualNoteDraftRequest(BaseModel):
    ownerUserId: str
    cardType: str
    inputMode: str
    rawText: str | None = None
    title: str | None = None


class PropertyBatchParseRequest(BaseModel):
    ownerUserId: str
    rawText: str


class PropertyBatchCandidatePayload(BaseModel):
    candidateId: str
    title: str
    community: str | None = None
    buildingRoom: str | None = None
    unitName: str | None = None
    layout: str | None = None
    price: str | None = None
    summary: str | None = None
    publicTags: list[str] = Field(default_factory=list)
    privateTags: list[str] = Field(default_factory=list)
    privateData: dict = Field(default_factory=dict)
    selected: bool = True


class PropertyBatchCreateRequest(BaseModel):
    ownerUserId: str
    rawText: str
    candidates: list[PropertyBatchCandidatePayload] = Field(default_factory=list)


class QuickNoteCaptureRequest(BaseModel):
    ownerUserId: str
    rawText: str
    title: str | None = None


class TopicCreateRequest(BaseModel):
    ownerUserId: str
    name: str
    description: str | None = None
    color: str | None = None


class TopicNoteRequest(BaseModel):
    ownerUserId: str


class NoteTypeConfirmRequest(BaseModel):
    ownerUserId: str
    cardType: str
    source: str | None = None


class CustomerActionSubmitRequest(BaseModel):
    viewerUserId: str | None = None
    anonymousId: str | None = None
    nickname: str | None = None
    avatarUrl: str | None = None
    payload: dict = Field(default_factory=dict)


class PropertySameCloneRequest(BaseModel):
    ownerUserId: str
    sourceType: str = "note"
    sourceId: str
    phone: str | None = None
    wechat: str | None = None
    upstreamContact: str | None = None
    ownerName: str | None = None
    avatarUrl: str | None = None
    publishShowcase: bool = False
