from __future__ import annotations

from pydantic import BaseModel


class ShareSnapshotRequest(BaseModel):
    ownerUserId: str
    sourceRevision: str
    fingerprint: str
    url: str
    styleId: str = "default"
    generatedAt: str | None = None


class ShareSnapshotPrepareRequest(BaseModel):
    """Client metadata for a server-rendered note snapshot.

    The server never uses client text or images as the render source. These
    values only identify the client template/version it is asking to cache.
    """

    ownerUserId: str
    sourceRevision: str
    fingerprint: str
    styleId: str
