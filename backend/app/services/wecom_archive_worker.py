from __future__ import annotations

import asyncio
import contextlib
import logging

from app.services.app_service import AppService
from app.services.wecom_archive_client import WecomArchiveClient


logger = logging.getLogger(__name__)


class WecomArchiveWorker:
    def __init__(
        self,
        service: AppService,
        archive_client: WecomArchiveClient,
        *,
        enabled: bool,
        interval_seconds: int,
        pull_limit: int,
    ):
        self.service = service
        self.archive_client = archive_client
        self.enabled = enabled
        self.interval_seconds = max(interval_seconds, 10)
        self.pull_limit = pull_limit
        self._task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()

    def start(self) -> None:
        if not self.enabled:
            logger.info("wecom archive worker disabled")
            return
        if self._task and not self._task.done():
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run(), name="wecom-archive-worker")
        logger.info("wecom archive worker started")

    async def stop(self) -> None:
        if not self._task:
            return
        self._stop_event.set()
        self._task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self._task
        self._task = None
        logger.info("wecom archive worker stopped")

    async def run_once(self) -> dict:
        pull_result = await asyncio.to_thread(
            self.service.pull_wecom_archive_messages,
            self.archive_client,
            self.pull_limit,
        )
        process_result = await asyncio.to_thread(self.service.process_wecom_archive_messages, self.pull_limit)
        return {"pull": pull_result, "process": process_result}

    async def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                result = await self.run_once()
                logger.info("wecom archive worker tick: %s", result)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("wecom archive worker tick failed")
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=self.interval_seconds)
            except TimeoutError:
                continue
