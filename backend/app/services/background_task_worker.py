from __future__ import annotations

import asyncio
import contextlib
import logging

from app.services.sync_task_queue import SyncTaskQueue


logger = logging.getLogger(__name__)


class BackgroundTaskWorker:
    def __init__(
        self,
        queue: SyncTaskQueue,
        *,
        enabled: bool,
        interval_seconds: int = 5,
        task_names: set[str] | None = None,
        max_running: int | None = None,
    ):
        self.queue = queue
        self.enabled = enabled
        self.interval_seconds = max(interval_seconds, 1)
        self.task_names = task_names
        self.max_running = max_running
        self._task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()

    def start(self) -> None:
        if not self.enabled:
            logger.info("background task worker disabled")
            return
        if self._task and not self._task.done():
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run(), name="background-task-worker")
        logger.info("background task worker started")

    async def stop(self) -> None:
        if not self._task:
            return
        self._stop_event.set()
        self._task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self._task
        self._task = None
        logger.info("background task worker stopped")

    async def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                scheduled = self.queue.start_pending(
                    names=self.task_names,
                    max_to_schedule=1 if self.max_running else None,
                    max_running=self.max_running,
                )
                if scheduled:
                    logger.info("background task worker scheduled %s task(s)", scheduled)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("background task worker tick failed")
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=self.interval_seconds)
            except TimeoutError:
                continue
