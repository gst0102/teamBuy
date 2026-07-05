from __future__ import annotations

from pydantic import BaseModel, Field


class OpportunityLeadSaveRequest(BaseModel):
    userId: str
    status: str = Field(default="saved")
    note: str | None = None
    reminderAt: str | None = None


class OpportunityLeadFollowupRequest(BaseModel):
    userId: str
    actionType: str = Field(default="note")
    note: str | None = None


class OpportunityContactUnlockRequest(BaseModel):
    userId: str


class OpportunitySubscriptionUpsertRequest(BaseModel):
    userId: str
    id: str | None = None
    direction: str = Field(default="两边都看")
    lookingFor: str = Field(default="")
    providing: str = Field(default="")
    city: str = Field(default="")
    contactRequirement: str = Field(default="有电话")
    keywords: str = Field(default="")
    reminderCadence: str = Field(default="每天早上")
    status: str = Field(default="active")


class SupplyDemandCardUpsertRequest(BaseModel):
    userId: str
    id: str | None = None
    cardType: str = Field(default="supply")
    title: str = Field(default="")
    summary: str = Field(default="")
    city: str | None = None
    industry: str | None = None
    demandType: str = Field(default="合作")
    contactRequirement: str | None = None
    linkedNoteId: str | None = None
    linkedResourceType: str | None = None
    linkedResourceId: str | None = None
    tags: list[str] = Field(default_factory=list)
    status: str = Field(default="draft")


class SupplyDemandApplicationCreateRequest(BaseModel):
    userId: str
    message: str | None = None


class SupplyDemandApplicationReviewRequest(BaseModel):
    userId: str
    status: str = Field(default="accepted")


class OpportunityPushDigestRequest(BaseModel):
    userId: str


class ResponsePackagePreviewRequest(BaseModel):
    userId: str
    selectedAssetIds: list[str] = Field(default_factory=list)


class ResponsePackageCreateRequest(BaseModel):
    userId: str
    selectedAssetIds: list[str] = Field(default_factory=list)


class ResponsePackageEventRequest(BaseModel):
    eventType: str = Field(default="view")
    viewerId: str | None = None
    anonymousId: str | None = None
    metadata: dict = Field(default_factory=dict)
