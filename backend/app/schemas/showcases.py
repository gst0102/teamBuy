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
    templateId: str = "classic_grid"
    shareTitle: str | None = None
    contactConfig: dict = Field(default_factory=dict)
    displayConfig: dict = Field(default_factory=dict)
    items: list[ShowcaseItemRequest] = Field(default_factory=list)


class ShowcaseStatusRequest(BaseModel):
    ownerUserId: str
