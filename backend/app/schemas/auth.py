from __future__ import annotations

from pydantic import BaseModel


class MockLoginRequest(BaseModel):
    nickname: str
    avatarUrl: str = "https://example.com/avatar-default.png"
    openid: str | None = None
    phone: str | None = None

