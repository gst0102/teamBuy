from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from app.services.time_utils import now_iso


@dataclass
class SyncTaskSnapshot:
    id: str
    name: str
    status: str
    createdAt: str
    updatedAt: str
    result: dict[str, Any] | None = None
    errorMessage: str | None = None

    def model_dump(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status,
            "createdAt": self.createdAt,
            "updatedAt": self.updatedAt,
            "result": self.result,
            "errorMessage": self.errorMessage,
        }


class InMemorySyncTaskQueue:
    def __init__(self):
        self.tasks: dict[str, SyncTaskSnapshot] = {}

    def enqueue(self, name: str, task_factory: Callable[[], Awaitable[dict[str, Any]]]) -> SyncTaskSnapshot:
        now = now_iso()
        task = SyncTaskSnapshot(
            id=f"sync_task_{uuid4().hex}",
            name=name,
            status="queued",
            createdAt=now,
            updatedAt=now,
        )
        self.tasks[task.id] = task
        asyncio.create_task(self._run(task.id, task_factory))
        return task

    def list_recent(self) -> list[SyncTaskSnapshot]:
        return sorted(self.tasks.values(), key=lambda item: item.createdAt, reverse=True)

    async def _run(self, task_id: str, task_factory: Callable[[], Awaitable[dict[str, Any]]]) -> None:
        task = self.tasks[task_id]
        task.status = "running"
        task.updatedAt = now_iso()
        try:
            task.result = await task_factory()
            task.status = "success" if task.result.get("syncStatus") != "running" else "skipped"
            task.errorMessage = None
        except Exception as exc:
            task.status = "failed"
            task.errorMessage = str(exc)
        task.updatedAt = now_iso()
