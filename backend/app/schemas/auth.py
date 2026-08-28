from __future__ import annotations

from pydantic import BaseModel


class MockLoginRequest(BaseModel):
    nickname: str
    avatarUrl: str = ""
    openid: str | None = None
    wechat: str | None = None
    phone: str | None = None


class WechatLoginRequest(BaseModel):
    code: str
    nickname: str | None = None
    avatarUrl: str | None = None
    wechat: str | None = None
    phone: str | None = None


class UserProfileUpdateRequest(BaseModel):
    nickname: str | None = None
    avatarUrl: str | None = None
    wechat: str | None = None
    phone: str | None = None
    displayName: str | None = None
    jobTitle: str | None = None
    company: str | None = None
    city: str | None = None
    wechatQrUrl: str | None = None
    email: str | None = None
    website: str | None = None


class WecomBindIntentRequest(BaseModel):
    userId: str


class WecomBindCardRequest(BaseModel):
    token: str
    userId: str


class H5TicketRequest(BaseModel):
    userId: str
    entry: str = "resource-tools"
