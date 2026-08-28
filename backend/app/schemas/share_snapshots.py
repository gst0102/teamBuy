from __future__ import annotations

from pydantic import BaseModel


class ShareSnapshotRequest(BaseModel):
    ownerUserId: str
    sourceRevision: str
    fingerprint: str
    url: str
    styleId: str = "default"
    generatedAt: str | None = None
