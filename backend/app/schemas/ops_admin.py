from __future__ import annotations

from pydantic import BaseModel, Field


class GroupUploadPreviewRequest(BaseModel):
    rawText: str = Field(default="")


class GroupUploadCreateRequest(BaseModel):
    rawText: str = Field(default="")
    batchName: str | None = None
    operatorName: str | None = None


class SingleGroupResourceCreateRequest(BaseModel):
    name: str = Field(default="")
    cityMode: str = Field(default="city")
    cityLabel: str = Field(default="")
    region: list[str] = Field(default_factory=list)
    groupType: str = Field(default="房源")
    purposes: list[str] = Field(default_factory=list)
    memberRange: str = Field(default="")
    activeLevel: str = Field(default="")
    expiresInDays: int = 5
    remark: str | None = None
    customTags: list[str] = Field(default_factory=list)
    qrImageData: str | None = None
    operatorName: str | None = None


class WecomGroupJoinWayCreateRequest(BaseModel):
    remark: str = Field(default="资料助手资源群")
    chatIdList: list[str] = Field(default_factory=list)
    roomBaseName: str = Field(default="资料助手资源群")
    roomBaseId: int = 1
    autoCreateRoom: int = 1
    state: str = Field(default="teambuy_resource_group")
    operatorName: str | None = None
    dryRun: bool = True


class GroupBotChannelUpsertRequest(BaseModel):
    groupId: str = Field(default="")
    groupName: str = Field(default="")
    webhook: str = Field(default="")
    groupType: str = Field(default="资源群")
    audience: str = Field(default="")
    cityLabel: str = Field(default="")
    dailyTemplate: str = Field(default="midday")
    sendWindow: str = Field(default="")
    ownerName: str | None = None
    remark: str | None = None
    enabled: bool = True


class FeedbackTicketCreateRequest(BaseModel):
    type: str = Field(default="bug")
    userId: str | None = None
    userNickname: str | None = None
    contact: str | None = None
    content: str = Field(default="")


class FeedbackTicketUpdateRequest(BaseModel):
    status: str | None = None
    replyText: str | None = None
    rewardNote: str | None = None
    operatorName: str | None = None
