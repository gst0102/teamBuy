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
    nickname: str = "微信用户"
    avatarUrl: str = ""
    wechat: str | None = None
    phone: str | None = None


class UserProfileUpdateRequest(BaseModel):
    nickname: str | None = None
    avatarUrl: str | None = None
    wechat: str | None = None
    phone: str | None = None


class WecomBindIntentRequest(BaseModel):
    userId: str
