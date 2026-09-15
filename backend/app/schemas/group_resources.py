from __future__ import annotations

from pydantic import BaseModel, Field


class GroupResourceCreateRequest(BaseModel):
    ownerUserId: str = Field(min_length=1, max_length=160)
    name: str = Field(default="", max_length=80)
    cityMode: str = Field(default="city", max_length=20)
    cityLabel: str = Field(default="", max_length=80)
    cityCode: str | None = Field(default=None, max_length=32)
    industry: str = Field(min_length=1, max_length=40)
    purpose: str = Field(min_length=1, max_length=40)
    tags: list[str] = Field(default_factory=list, max_length=8)
    memberRange: str | None = Field(default=None, max_length=40)
    activeLevel: str | None = Field(default=None, max_length=20)
    remark: str | None = Field(default=None, max_length=240)
    qrImageUrl: str = Field(min_length=1, max_length=2000)
    expiresInDays: int = Field(default=7, ge=1, le=7)


class GroupResourceAdminCreateRequest(BaseModel):
    """Create payload shared by the authenticated mobile admin and PC ops.

    `ownerUserId` is intentionally absent.  Mobile identity comes from the
    signed session and PC identity comes from the admin token.
    """

    name: str = Field(default="", max_length=80)
    cityMode: str = Field(default="city", max_length=20)
    cityLabel: str = Field(default="", max_length=80)
    cityCode: str | None = Field(default=None, max_length=32)
    industry: str = Field(default="", max_length=40)
    purpose: str = Field(default="", max_length=40)
    tags: list[str] = Field(default_factory=list, max_length=8)
    memberRange: str | None = Field(default=None, max_length=40)
    activeLevel: str | None = Field(default=None, max_length=20)
    remark: str | None = Field(default=None, max_length=240)
    qrImageUrl: str | None = Field(default=None, max_length=2000)
    qrImageData: str | None = Field(default=None, max_length=14_000_000)
    expiresInDays: int = Field(default=7, ge=1, le=7)
    operatorName: str | None = Field(default=None, max_length=80)


class GroupResourceUpdateRequest(BaseModel):
    ownerUserId: str = Field(min_length=1, max_length=160)
    name: str | None = Field(default=None, max_length=80)
    cityMode: str | None = Field(default=None, max_length=20)
    cityLabel: str | None = Field(default=None, max_length=80)
    cityCode: str | None = Field(default=None, max_length=32)
    industry: str | None = Field(default=None, max_length=40)
    purpose: str | None = Field(default=None, max_length=40)
    tags: list[str] | None = Field(default=None, max_length=8)
    memberRange: str | None = Field(default=None, max_length=40)
    activeLevel: str | None = Field(default=None, max_length=20)
    remark: str | None = Field(default=None, max_length=240)
    qrImageUrl: str | None = Field(default=None, max_length=2000)
    expiresInDays: int | None = Field(default=None, ge=1, le=7)


class GroupResourceViewRequest(BaseModel):
    userId: str = Field(min_length=1, max_length=160)
