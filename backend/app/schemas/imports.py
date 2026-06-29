from __future__ import annotations

from pydantic import BaseModel


class ClaimImportRequest(BaseModel):
    userId: str


class ClaimImportTokenRequest(BaseModel):
    userId: str
    token: str


class MockImportRequest(BaseModel):
    externalUserId: str
    conversationId: str
    fixture: str = "note"
    eventType: str = "sync_msg"
