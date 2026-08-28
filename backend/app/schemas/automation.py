from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class AutomationDeviceHeartbeatRequest(BaseModel):
    deviceId: str = Field(min_length=1, max_length=128)
    name: str = Field(default="Android 自动化设备", max_length=120)
    hidDeviceId: str | None = Field(default=None, max_length=128)
    status: Literal["offline", "ready", "busy", "paused", "degraded"] = "ready"
    activeWechatAccountId: str | None = Field(default=None, max_length=128)
    capabilities: list[str] = Field(default_factory=list, max_length=32)
    metadata: dict = Field(default_factory=dict)


class AutomationTaskCreateRequest(BaseModel):
    functionId: str = Field(min_length=1, max_length=128)
    deviceId: str = Field(min_length=1, max_length=128)
    targetWechatAccountId: str | None = Field(default=None, max_length=128)
    payload: dict = Field(default_factory=dict)
    idempotencyKey: str | None = Field(default=None, max_length=256)


class AutomationMarketingCardTaskRequest(BaseModel):
    candidateId: str = Field(min_length=1, max_length=128)
    noteId: str = Field(min_length=1, max_length=128)
    deviceId: str = Field(min_length=1, max_length=128)
    idempotencyKey: str | None = Field(default=None, max_length=256)


class AutomationMarketingCardRouteRequest(BaseModel):
    topic: str = Field(min_length=1, max_length=80)
    region: str = Field(default="", max_length=80)
    contentType: str = Field(min_length=1, max_length=80)


class AutomationTaskClaimRequest(BaseModel):
    deviceId: str = Field(min_length=1, max_length=128)
    activeWechatAccountId: str | None = Field(default=None, max_length=128)
    leaseSeconds: int = Field(default=120, ge=30, le=900)


class AutomationTaskCompleteRequest(BaseModel):
    deviceId: str = Field(min_length=1, max_length=128)
    leaseToken: str = Field(min_length=1, max_length=128)
    activeWechatAccountId: str | None = Field(default=None, max_length=128)
    result: dict = Field(default_factory=dict)


class AutomationTaskFailRequest(BaseModel):
    deviceId: str = Field(min_length=1, max_length=128)
    leaseToken: str = Field(min_length=1, max_length=128)
    activeWechatAccountId: str | None = Field(default=None, max_length=128)
    errorMessage: str = Field(min_length=1, max_length=2000)
    result: dict = Field(default_factory=dict)


class AutomationGroupCandidateUpsertRequest(BaseModel):
    id: str | None = Field(default=None, max_length=128)
    deviceId: str = Field(min_length=1, max_length=128)
    wechatAccountId: str = Field(min_length=1, max_length=128)
    source: Literal["xiaohongshu", "wechat_native"] = "xiaohongshu"
    groupQRCode: str | None = Field(default=None, max_length=2000)
    groupName: str | None = Field(default=None, max_length=200)
    wechatAccountName: str | None = Field(default=None, max_length=120)
    savedAt: str | None = None
    joinStatus: Literal["pending", "success", "failed", "unknown"] = "unknown"
    canSend: bool | None = None
    remark: str | None = Field(default=None, max_length=1000)
    lastSeenAt: str | None = None
    idempotencyKey: str | None = Field(default=None, max_length=256)
    lastError: str | None = Field(default=None, max_length=2000)


class AutomationGroupCandidateReviewRequest(BaseModel):
    canSend: bool | None = None
    remark: str | None = Field(default=None, max_length=1000)
    wechatAccountName: str | None = Field(default=None, max_length=120)
    topic: str | None = Field(default=None, max_length=80)
    region: str | None = Field(default=None, max_length=80)
    allowedContentTypes: list[str] | None = Field(default=None, max_length=8)
    membershipStatus: Literal["unknown", "active", "removed"] | None = None
    lastActivityAt: str | None = Field(default=None, max_length=64)
    lastVerifiedAt: str | None = Field(default=None, max_length=64)
