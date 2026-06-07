from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from zoneinfo import ZoneInfoNotFoundError


try:
    SHANGHAI = ZoneInfo("Asia/Shanghai")
except ZoneInfoNotFoundError:
    SHANGHAI = timezone(timedelta(hours=8), name="Asia/Shanghai")


def now_iso() -> str:
    return datetime.now(tz=SHANGHAI).isoformat()


def utc_now() -> datetime:
    return datetime.now(tz=timezone.utc)


def parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value)


def date_key(value: str) -> str:
    return parse_iso(value).astimezone(SHANGHAI).date().isoformat()
