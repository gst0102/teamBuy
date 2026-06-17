from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


IntentName = Literal["link_bookmark", "content_to_note", "note_to_comic_image", "showcase_builder", "billing", "help", "unknown"]
RouteSource = Literal["exact_command", "rule", "ai_fallback", "confirm_menu"]
SkillRunStatus = Literal["pending", "success", "failed", "needs_confirm"]


class ContentMediaPayload(BaseModel):
    type: str
    url: str | None = None
    mediaId: str | None = None
    title: str | None = None
    sourceRef: str | None = None


class ContentLinkPayload(BaseModel):
    url: str
    title: str | None = None
    description: str | None = None
    coverUrl: str | None = None


class ContentParticipantPayload(BaseModel):
    id: str | None = None
    name: str | None = None
    role: str | None = None


class ContentObjectPayload(BaseModel):
    sourceType: str
    title: str | None = None
    textBlocks: list[str] = Field(default_factory=list)
    media: list[ContentMediaPayload] = Field(default_factory=list)
    links: list[ContentLinkPayload] = Field(default_factory=list)
    participants: list[ContentParticipantPayload] = Field(default_factory=list)
    timestamps: list[str] = Field(default_factory=list)
    sourceRefs: list[str] = Field(default_factory=list)
    rawMessageIds: list[str] = Field(default_factory=list)


class SkillRouteRequest(BaseModel):
    text: str = ""
    content: ContentObjectPayload | None = None


class SkillCommandPayload(BaseModel):
    commandText: str
    aliases: list[str] = Field(default_factory=list)
    skillId: str
    intent: IntentName
    inputAdapter: str | None = None
    requiresPayment: bool = False
    enabled: bool = True


class IntentResultPayload(BaseModel):
    intent: IntentName
    skillId: str | None = None
    confidence: float = 0
    source: RouteSource
    needsConfirm: bool = False
    inputAdapter: str | None = None
    commandText: str | None = None
    message: str | None = None


class UserNoteDraftPayload(BaseModel):
    ownerUserId: str | None = None
    title: str
    summary: str
    body: str
    coverUrl: str | None = None
    media: list[ContentMediaPayload] = Field(default_factory=list)
    categoryIds: list[str] = Field(default_factory=list)
    phone: str | None = None
    locationText: str | None = None
    sourceRefs: list[str] = Field(default_factory=list)
    visibilityConfig: dict = Field(default_factory=dict)


class SkillRunPayload(BaseModel):
    id: str
    skillId: str
    status: SkillRunStatus
    inputSnapshot: dict
    outputRef: str | None = None
    modelProvider: str | None = None
    errorMessage: str | None = None
    cost: float = 0
    startedAt: str
    endedAt: str | None = None


class RunContentToNoteRequest(BaseModel):
    ownerUserId: str | None = None
    content: ContentObjectPayload


class RunContentToNoteResponse(BaseModel):
    intent: IntentResultPayload
    skillRun: SkillRunPayload
    noteDraft: UserNoteDraftPayload
