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
