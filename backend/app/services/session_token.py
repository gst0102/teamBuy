"""Signed mini-program session tokens.

The mini-program API historically trusted user ids supplied in query strings and
JSON bodies.  A short, signed token gives the API a server-verifiable identity
without putting an openid or a secret in the client code.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from datetime import datetime, timezone

from fastapi import HTTPException

from app.core.config import settings


DEFAULT_SESSION_TTL_SECONDS = 30 * 24 * 60 * 60


def _secret() -> bytes:
    return (settings.h5_auth_secret or "teamBuy-h5-dev-secret").encode("utf-8")


def _encode(payload: dict) -> str:
    body = base64.urlsafe_b64encode(
        json.dumps(payload, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
    ).decode("ascii").rstrip("=")
    signature = hmac.new(_secret(), body.encode("ascii"), hashlib.sha256).hexdigest()
    return f"{body}.{signature}"


def _decode_body(body: str) -> dict:
    padded = f"{body}{'=' * (-len(body) % 4)}"
    try:
        value = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8"))
    except Exception as exc:  # pragma: no cover - the caller receives the same 401 for all malformed tokens
        raise HTTPException(status_code=401, detail="登录状态无效，请重新登录") from exc
    return value if isinstance(value, dict) else {}


def issue_user_session(user_id: str) -> dict:
    now = int(time.time())
    ttl = max(300, int(getattr(settings, "user_session_ttl_seconds", DEFAULT_SESSION_TTL_SECONDS)))
    payload = {"userId": str(user_id), "iat": now, "exp": now + ttl}
    return {
        "authToken": _encode(payload),
        "authTokenExpiresAt": datetime.fromtimestamp(payload["exp"], tz=timezone.utc).isoformat(),
    }


def verify_user_session(token: str | None) -> dict:
    raw = str(token or "").strip()
    if raw.lower().startswith("bearer "):
        raw = raw[7:].strip()
    if "." not in raw:
        raise HTTPException(status_code=401, detail="登录状态无效，请重新登录")
    body, signature = raw.rsplit(".", 1)
    expected = hmac.new(_secret(), body.encode("ascii"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        raise HTTPException(status_code=401, detail="登录状态无效，请重新登录")
    payload = _decode_body(body)
    user_id = str(payload.get("userId") or "").strip()
    if not user_id or int(payload.get("exp") or 0) <= int(time.time()):
        raise HTTPException(status_code=401, detail="登录状态已过期，请重新登录")
    return payload
