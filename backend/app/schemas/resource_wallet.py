from __future__ import annotations

from pydantic import BaseModel, Field


class ResourceWalletConsumeRequest(BaseModel):
    ownerUserId: str
    actionType: str
    targetType: str
    targetId: str
    pointsCost: int = Field(default=0, ge=0)
    reason: str | None = None
    freeQuotaType: str | None = None
    freeQuotaLimit: int = Field(default=0, ge=0)
    periodKey: str | None = None
    metadata: dict = Field(default_factory=dict)


class ResourceWalletAdjustRequest(BaseModel):
    userId: str
    pointsDelta: int
    reason: str | None = None
    operatorId: str | None = None
