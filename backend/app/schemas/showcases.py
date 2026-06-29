from __future__ import annotations

from pydantic import BaseModel, Field


class ShowcaseItemRequest(BaseModel):
    noteId: str
    sortOrder: int = 0
    sectionTitle: str | None = None
    displayTitle: str | None = None
    visible: bool = True
    fieldConfig: dict = Field(default_factory=dict)


class ShowcasePageRequest(BaseModel):
    ownerUserId: str
    name: str
    description: str | None = None
    bannerUrl: str | None = None
    templateId: str = "featured_window"
    shareTitle: str | None = None
    contactConfig: dict = Field(default_factory=dict)
    displayConfig: dict = Field(default_factory=dict)
    items: list[ShowcaseItemRequest] = Field(default_factory=list)


class ShowcaseStatusRequest(BaseModel):
    ownerUserId: str


class ShowcaseEventRequest(BaseModel):
    eventType: str
    noteId: str | None = None
    shareId: str | None = None
    shareFromUserId: str | None = None
    scene: str | None = None
    referrer: str | None = None
    viewerUserId: str | None = None
    anonymousId: str | None = None
    nickname: str | None = None
    avatarUrl: str | None = None
    sessionId: str | None = None
    durationSeconds: int | None = None
    maxScrollPercent: int | None = None
    focusSections: list[str] = Field(default_factory=list)
