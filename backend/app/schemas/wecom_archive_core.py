from __future__ import annotations

from pydantic import BaseModel, Field


class SharedArchiveMessage(BaseModel):
    seq: int = Field(ge=1)
    msgId: str | None = None
    action: str | None = None
    fromUser: str | None = None
    toList: list[str] = Field(default_factory=list)
    roomId: str | None = None
    msgTime: int | str | None = None
    msgType: str | None = None
    decryptedPayload: dict = Field(default_factory=dict)
    mediaRefs: list[dict] = Field(default_factory=list)


class SharedArchiveEvent(BaseModel):
    schemaVersion: int = Field(ge=1)
    eventId: str = Field(min_length=8, max_length=180)
    streamKey: str = Field(min_length=8, max_length=100)
    seq: int = Field(ge=1)
    message: SharedArchiveMessage
