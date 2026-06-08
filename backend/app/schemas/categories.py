from __future__ import annotations

from pydantic import BaseModel


class CategoryCreateRequest(BaseModel):
    ownerUserId: str
    name: str

