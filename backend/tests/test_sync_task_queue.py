from __future__ import annotations

import asyncio
from pathlib import Path

from app.services.repository import JsonRepository
from app.services.sync_task_queue import SyncTaskQueue


def test_sync_task_queue_persists_task_and_logs_success(tmp_path: Path):
    async def run():
        repo = JsonRepository(tmp_path / "state.json")
        queue = SyncTaskQueue(repo, retry_delay_seconds=1)

        async def handler(payload):
            return {"syncStatus": "success", "value": payload["value"]}

        queue.register("demo", handler)
        task = queue.enqueue("demo", {"value": 42})
        await asyncio.sleep(0.05)

        saved = repo.list_sync_tasks()[0]
        logs = repo.list_sync_task_logs(task.id)
        assert saved.id == task.id
        assert saved.status == "success"
        assert saved.result == {"syncStatus": "success", "value": 42}
        assert {item.event for item in logs} >= {"queued", "running", "success"}

    asyncio.run(run())


def test_sync_task_queue_retries_failed_task(tmp_path: Path):
    async def run():
        repo = JsonRepository(tmp_path / "state.json")
        queue = SyncTaskQueue(repo, retry_delay_seconds=1)

        async def handler(payload):
            raise RuntimeError("temporary sync failure")

        queue.register("demo", handler)
        queue.enqueue("demo", {}, max_attempts=2)
        await asyncio.sleep(0.05)

        saved = repo.list_sync_tasks()[0]
        assert saved.status == "retrying"
        assert saved.attempts == 1
        assert saved.nextRunAt is not None

    asyncio.run(run())


def test_sync_task_queue_fails_without_registered_handler(tmp_path: Path):
    async def run():
        repo = JsonRepository(tmp_path / "state.json")
        queue = SyncTaskQueue(repo)

        queue.enqueue("missing-handler", {}, max_attempts=1)
        await asyncio.sleep(0.05)

        saved = repo.list_sync_tasks()[0]
        assert saved.status == "failed"
        assert "No handler registered" in (saved.errorMessage or "")

    asyncio.run(run())
