from __future__ import annotations

import asyncio
from pathlib import Path

from app.config import Settings
from app.engine import ArchiveCoreEngine
from app.sdk import FinanceSdkClient
from app.store import PostgresStore


async def run_loop(settings: Settings) -> None:
    store = PostgresStore(settings.database_url)
    store.ensure_schema((Path(__file__).resolve().parents[1] / "schema.sql").read_text(encoding="utf-8"))
    engine = ArchiveCoreEngine(
        settings,
        store,
        FinanceSdkClient(
            settings.corp_id,
            settings.archive_secret,
            settings.private_key_path,
            settings.sdk_lib_path,
            settings.proxy,
            settings.proxy_password,
            settings.sdk_timeout_seconds,
        ),
    )
    while True:
        with store.advisory_lock("wecom-archive-core-ingest") as acquired:
            if acquired:
                try:
                    await asyncio.to_thread(engine.ingest_once)
                except Exception as exc:
                    store.mark_pull_failure(engine.stream_key, str(exc))
                await engine.deliver_once()
                await asyncio.to_thread(engine.cleanup_expired)
        if store.has_wake():
            store.consume_wakes()
            continue
        await asyncio.sleep(settings.poll_interval_seconds)


async def main() -> None:
    settings = Settings.from_env()
    missing = settings.missing_fields()
    if missing:
        raise RuntimeError("WeCom archive core configuration incomplete: " + ", ".join(missing))
    await run_loop(settings)


if __name__ == "__main__":
    asyncio.run(main())
