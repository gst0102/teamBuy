from __future__ import annotations

import re
from copy import deepcopy
from uuid import uuid4


PHONE_PATTERN = re.compile(r"1[3-9]\d{9}")


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:10]}"


def deep_copy(data):
    return deepcopy(data)


def mask_nickname(nickname: str) -> str:
    if len(nickname) <= 2:
        return nickname[0] + "*" if len(nickname) == 2 else nickname
    return nickname[:2] + "*" * (len(nickname) - 2)


def extract_phone(text: str) -> str | None:
    match = PHONE_PATTERN.search(text)
    return match.group(0) if match else None

