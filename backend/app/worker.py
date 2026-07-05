from __future__ import annotations

import asyncio
import contextlib
import logging
import signal

from app.api.dependencies import (
    get_ocr_task_worker,
    get_wecom_archive_worker,
    register_background_task_handlers,
)


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main() -> None:
    register_background_task_handlers()
    stop_event = asyncio.Event()

    def _stop() -> None:
        stop_event.set()

    loop = asyncio.get_running_loop()
    with contextlib.suppress(NotImplementedError):
        loop.add_signal_handler(signal.SIGTERM, _stop)
        loop.add_signal_handler(signal.SIGINT, _stop)

    ocr_task_worker = get_ocr_task_worker()
    archive_worker = get_wecom_archive_worker()
    ocr_task_worker.start()
    archive_worker.start()
    logger.info("teamBuy background worker started")
    try:
        await stop_event.wait()
    finally:
        await ocr_task_worker.stop()
        await archive_worker.stop()
        logger.info("teamBuy background worker stopped")


if __name__ == "__main__":
    asyncio.run(main())
