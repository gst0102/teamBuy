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
    runId: str | None = Field(default=None, max_length=256)
    leaseSeconds: int = Field(default=120, ge=30, le=900)
    functionIds: list[str] = Field(default_factory=list, max_length=16)


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
    # SHA-256 fingerprint of locally observed member-name identity; raw names
    # are never sent to or persisted by the PC service.
    groupIdentity: str | None = Field(default=None, min_length=64, max_length=64)
    groupOccurrenceCount: int | None = Field(default=None, ge=1, le=10000)
    wechatAccountName: str | None = Field(default=None, max_length=120)
    savedAt: str | None = None
    joinStatus: Literal["pending", "success", "failed", "unknown"] = "unknown"
    canSend: bool | None = None
    remark: str | None = Field(default=None, max_length=1000)
    lastSeenAt: str | None = None
    idempotencyKey: str | None = Field(default=None, max_length=256)
    lastError: str | None = Field(default=None, max_length=2000)
    groupMemberCount: int | None = Field(default=None, ge=0, le=10000)


class AutomationNativeGroupScanRequest(BaseModel):
    deviceId: str = Field(min_length=1, max_length=128)
    wechatAccountId: str = Field(min_length=1, max_length=128)
    wechatAccountName: str | None = Field(default=None, max_length=120)
    scanId: str = Field(min_length=1, max_length=256)
    scanMode: Literal["full", "incremental", "targeted"] = "full"
    coverage: Literal["partial", "complete"] = "partial"
    contactsScanStopReason: str = Field(default="", max_length=80)
    chatListScanStopReason: str = Field(default="", max_length=80)
    contactsGroupCount: int = Field(default=0, ge=0, le=10000)
    chatListGroupCount: int = Field(default=0, ge=0, le=10000)
    groupNames: list[str] = Field(default_factory=list, max_length=10000)
    # occurrenceCount collapses equal account/code/name rows into one route
    # while preserving how many native WeChat result rows the phone observed.
    groupMappings: list[dict] = Field(default_factory=list, max_length=10000)
    deleteMissing: bool = False


class AutomationGroupScanConfigRequest(BaseModel):
    """PC-managed native-WeChat code prefixes and queueing safety switch."""

    searchPrefixes: list[str] = Field(min_length=1, max_length=12)
    scanOnly: bool = False


class AutomationRunCompletionRequest(BaseModel):
    """Safe, non-secret completion summary sent by an AScript device."""

    deviceId: str = Field(min_length=1, max_length=128)
    runId: str = Field(min_length=1, max_length=128)
    # Devices may finish their UI workflow but lack enough evidence to claim
    # delivery; preserve that honest terminal state in the queued report.
    status: Literal["success", "degraded", "failed", "unverified"]
    batchNo: int | None = Field(default=None, ge=1, le=100)
    groupCodes: list[str] = Field(default_factory=list, max_length=100)
    scanConfig: dict = Field(default_factory=dict)
    accounts: list[dict] = Field(default_factory=list, max_length=16)
    scanSummary: dict = Field(default_factory=dict)
    queueSummary: dict = Field(default_factory=dict)
    forwardSummary: dict = Field(default_factory=dict)


class AutomationLiveQrMemberCountRequest(BaseModel):
    deviceId: str = Field(min_length=1, max_length=128)
    candidateId: str = Field(min_length=1, max_length=128)
    liveQrCodeId: str = Field(min_length=1, max_length=128)
    wechatAccountId: str = Field(min_length=1, max_length=128)
    groupName: str = Field(min_length=1, max_length=200)
    groupMemberCount: int = Field(ge=0, le=10000)
    checkedAt: str | None = Field(default=None, max_length=80)


class AutomationBatchContentRequest(BaseModel):
    batchNo: int = Field(ge=1, le=100)
    cardId: str | None = Field(default=None, max_length=120)
    text: str | None = Field(default=None, max_length=2000)
    enabled: bool = True


class AutomationBatchContentBulkReplaceRequest(BaseModel):
    oldCardId: str | None = Field(default=None, max_length=120)
    newCardId: str | None = Field(default=None, max_length=120)
    oldText: str | None = Field(default=None, max_length=2000)
    newText: str | None = Field(default=None, max_length=2000)


class AutomationCardAssetUpsertRequest(BaseModel):
    cardId: str = Field(min_length=1, max_length=120)
    deepLink: str | None = Field(default=None, max_length=2000)
    cardTitle: str | None = Field(default=None, max_length=200)
    status: Literal["active", "inactive", "expired"] = "active"


class AutomationGroupContentPlanUpsertRequest(BaseModel):
    groupCode: str = Field(min_length=1, max_length=40)
    remark: str | None = Field(default=None, max_length=500)
    status: Literal["active", "inactive"] = "active"
    batchContents: list[AutomationBatchContentRequest] = Field(default_factory=list, max_length=100)


class AutomationGroupContentPlanBulkReplaceRequest(BaseModel):
    groupCode: str | None = Field(default=None, max_length=40)
    oldCardId: str | None = Field(default=None, max_length=120)
    newCardId: str | None = Field(default=None, max_length=120)
    oldText: str | None = Field(default=None, max_length=2000)
    newText: str | None = Field(default=None, max_length=2000)


class AutomationGroupBatchTaskRequest(BaseModel):
    """Expand one PC group-code batch into bounded per-group tasks."""

    groupCode: str = Field(min_length=1, max_length=40)
    batchNo: int = Field(ge=1, le=100)
    deviceId: str = Field(min_length=1, max_length=128)
    wechatAccountId: str | None = Field(default=None, max_length=128)
    maxTargets: int = Field(default=50, ge=1, le=50)


class AutomationDeviceBatchRunRequest(BaseModel):
    """Create one grouped task per account and group code for a phone run."""

    deviceId: str = Field(min_length=1, max_length=128)
    batchNo: int = Field(ge=1, le=100)
    wechatAccountIds: list[str] = Field(default_factory=list, max_length=16)
    groupCodes: list[str] = Field(default_factory=list, max_length=100)
    maxTargets: int = Field(default=1000, ge=1, le=1000)
    runId: str | None = Field(default=None, max_length=128)


class AutomationGroupCandidateReviewRequest(BaseModel):
    canSend: bool | None = None
    remark: str | None = Field(default=None, max_length=1000)
    groupCodes: list[str] | None = Field(default=None, max_length=20)
    wechatAccountName: str | None = Field(default=None, max_length=120)
    topic: str | None = Field(default=None, max_length=80)
    region: str | None = Field(default=None, max_length=80)
    allowedContentTypes: list[str] | None = Field(default=None, max_length=8)
    batchContents: list[AutomationBatchContentRequest] | None = Field(default=None, max_length=100)
    dailySendLimit: int | None = Field(default=None, ge=0, le=50)
    membershipStatus: Literal["unknown", "active", "removed"] | None = None
    lastActivityAt: str | None = Field(default=None, max_length=64)
    lastVerifiedAt: str | None = Field(default=None, max_length=64)
