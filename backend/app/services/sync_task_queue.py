from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import timedelta
from typing import Any
from uuid import uuid4

from app.models.domain import SyncTask, SyncTaskLog
from app.services.repository import AppRepository
from app.services.time_utils import now_iso, parse_iso


TaskHandler = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


class SyncTaskQueue:
    def __init__(
        self,
        repo: AppRepository,
        worker_id: str | None = None,
        retry_delay_seconds: int = 30,
        lock_timeout_seconds: int = 600,
    ):
        self.repo = repo
        self.worker_id = worker_id or f"worker_{uuid4().hex}"
        self.retry_delay_seconds = retry_delay_seconds
        self.lock_timeout_seconds = lock_timeout_seconds
        self.handlers: dict[str, TaskHandler] = {}
        self._scheduled_task_ids: set[str] = set()

    def register(self, name: str, handler: TaskHandler) -> None:
        self.handlers[name] = handler

    def enqueue(self, name: str, payload: dict[str, Any] | None = None, max_attempts: int = 3) -> SyncTask:
        now = now_iso()
        task = SyncTask(
            id=f"sync_task_{uuid4().hex}",
            name=name,
            status="queued",
            payload=payload or {},
            attempts=0,
            maxAttempts=max_attempts,
            nextRunAt=now,
            createdAt=now,
            updatedAt=now,
        )
        self.repo.save_sync_task(task)
        self._log(task.id, "queued", f"Task {name} queued", {"payload": task.payload})
        self._schedule(task.id)
        return task

    def list_recent(self, limit: int = 50) -> list[SyncTask]:
        return self.repo.list_sync_tasks(limit=limit)

    def list_logs(self, task_id: str | None = None, limit: int = 100) -> list[SyncTaskLog]:
        return self.repo.list_sync_task_logs(task_id, limit)

    def start_pending(self) -> int:
        scheduled = 0
        for task in self.repo.list_sync_tasks({"queued", "retrying", "running"}, limit=100):
            if self._is_ready(task):
                self._schedule(task.id)
                scheduled += 1
            elif task.status in {"queued", "retrying"} and task.nextRunAt:
                delay = max(1, int((parse_iso(task.nextRunAt) - parse_iso(now_iso())).total_seconds()))
                asyncio.create_task(self._schedule_after_delay(task.id, delay))
                scheduled += 1
        return scheduled

    def _schedule(self, task_id: str) -> None:
        if task_id in self._scheduled_task_ids:
            return
        self._scheduled_task_ids.add(task_id)
        asyncio.create_task(self._run(task_id))

    async def _run(self, task_id: str) -> None:
        try:
            stale_before = (parse_iso(now_iso()) - timedelta(seconds=self.lock_timeout_seconds)).isoformat()
            claimed = self.repo.claim_sync_task(task_id, self.worker_id, now_iso(), stale_before)
            if not claimed:
                return
            self._log(claimed.id, "running", f"Task {claimed.name} claimed", {"workerId": self.worker_id})
            handler = self.handlers.get(claimed.name)
            if not handler:
                self._mark_failed(claimed, f"No handler registered for task {claimed.name}", retry=False)
                return
            try:
                result = await handler(claimed.payload)
            except Exception as exc:
                self._mark_failed(claimed, str(exc), retry=True)
                return
            status = "success" if result.get("syncStatus") != "running" else "skipped"
            now = now_iso()
            claimed.status = status
            claimed.result = result
            claimed.errorMessage = None
            claimed.lockedBy = None
            claimed.lockedAt = None
            claimed.updatedAt = now
            self.repo.update_sync_task(claimed)
            self._log(claimed.id, status, f"Task {claimed.name} finished with {status}", {"result": result})
        finally:
            self._scheduled_task_ids.discard(task_id)

    def _mark_failed(self, task: SyncTask, error_message: str, retry: bool) -> None:
        now = now_iso()
        task.attempts += 1
        task.errorMessage = error_message
        task.lockedBy = None
        task.lockedAt = None
        task.updatedAt = now
        can_retry = retry and task.attempts < task.maxAttempts
        if can_retry:
            task.status = "retrying"
            task.nextRunAt = (parse_iso(now) + timedelta(seconds=self.retry_delay_seconds)).isoformat()
        else:
            task.status = "failed"
            task.nextRunAt = None
        self.repo.update_sync_task(task)
        self._log(
            task.id,
            task.status,
            error_message,
            {"attempts": task.attempts, "maxAttempts": task.maxAttempts, "nextRunAt": task.nextRunAt},
        )
        if can_retry:
            asyncio.create_task(self._schedule_after_delay(task.id, self.retry_delay_seconds))

    async def _schedule_after_delay(self, task_id: str, delay_seconds: int) -> None:
        await asyncio.sleep(delay_seconds)
        self._schedule(task_id)

    def _is_ready(self, task: SyncTask) -> bool:
        if task.status == "running":
            if not task.lockedAt:
                return True
            stale_before = parse_iso(now_iso()) - timedelta(seconds=self.lock_timeout_seconds)
            return parse_iso(task.lockedAt) <= stale_before
        if not task.nextRunAt:
            return True
        return parse_iso(task.nextRunAt) <= parse_iso(now_iso())

    def _log(self, task_id: str, event: str, message: str, payload: dict[str, Any] | None = None) -> None:
        now = now_iso()
        self.repo.add_sync_task_log(
            SyncTaskLog(
                id=f"sync_task_log_{uuid4().hex}",
                taskId=task_id,
                event=event,
                message=message,
                payload=payload or {},
                createdAt=now,
            )
        )
