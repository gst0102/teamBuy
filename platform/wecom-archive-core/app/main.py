from __future__ import annotations

import asyncio
import contextlib
import secrets
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse, Response

from app.config import Settings
from app.crypto import ArchiveCryptoError, decrypt_callback_message, encrypted_xml_value, verify_signature
from app.engine import ArchiveCoreEngine
from app.sdk import FinanceSdkClient
from app.store import PostgresStore


def build_app(settings: Settings | None = None) -> FastAPI:
    runtime = settings or Settings.from_env()
    store = PostgresStore(runtime.database_url)
    if runtime.database_url:
        store.ensure_schema((Path(__file__).resolve().parents[1] / "schema.sql").read_text(encoding="utf-8"))
    client = FinanceSdkClient(
        runtime.corp_id,
        runtime.archive_secret,
        runtime.private_key_path,
        runtime.sdk_lib_path,
        runtime.proxy,
        runtime.proxy_password,
        runtime.sdk_timeout_seconds,
    )
    engine = ArchiveCoreEngine(runtime, store, client)
    stop_event = asyncio.Event()
    worker_task: asyncio.Task | None = None

    async def worker_loop() -> None:
        while not stop_event.is_set():
            try:
                if runtime.enabled and runtime.worker_enabled:
                    with store.advisory_lock("wecom-archive-core-ingest") as acquired:
                        if acquired:
                            try:
                                await asyncio.to_thread(engine.ingest_once)
                            except Exception as exc:
                                store.mark_pull_failure(engine.stream_key, str(exc))
                            await engine.deliver_once()
                            await asyncio.to_thread(engine.cleanup_expired)
            except asyncio.CancelledError:
                raise
            except Exception:
                # The next tick retries. Do not write payloads or credentials to logs.
                pass
            if store.has_wake():
                store.consume_wakes()
                continue
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=runtime.poll_interval_seconds)
            except TimeoutError:
                continue

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        nonlocal worker_task
        missing = runtime.missing_fields() if runtime.enabled and runtime.worker_enabled else []
        if missing:
            raise RuntimeError("WeCom archive core configuration incomplete: " + ", ".join(missing))
        if runtime.worker_enabled:
            worker_task = asyncio.create_task(worker_loop(), name="wecom-archive-core-worker")
        try:
            yield
        finally:
            stop_event.set()
            if worker_task:
                worker_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await worker_task

    app = FastAPI(title="WeCom Archive Core", lifespan=lifespan)

    def require_admin(value: str | None) -> None:
        configured = runtime.admin_token
        if not configured or not value or not secrets.compare_digest(value, configured):
            raise HTTPException(status_code=401, detail="Invalid archive core admin token")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/wecom/archive/callback", response_class=PlainTextResponse)
    async def verify_callback(
        msg_signature: str = Query(default=""),
        timestamp: str = Query(default=""),
        nonce: str = Query(default=""),
        echostr: str = Query(default=""),
    ) -> PlainTextResponse:
        if not runtime.callback_token or not runtime.encoding_aes_key:
            raise HTTPException(status_code=503, detail="Archive callback is not configured")
        if not verify_signature(runtime.callback_token, timestamp, nonce, echostr, msg_signature):
            raise HTTPException(status_code=403, detail="Invalid archive callback signature")
        try:
            echo = decrypt_callback_message(runtime.encoding_aes_key, echostr, runtime.corp_id)
        except ArchiveCryptoError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return PlainTextResponse(echo)

    @app.post("/wecom/archive/callback", response_class=PlainTextResponse)
    async def receive_callback(
        request: Request,
        msg_signature: str = Query(default=""),
        timestamp: str = Query(default=""),
        nonce: str = Query(default=""),
    ) -> PlainTextResponse:
        encrypted = encrypted_xml_value(await request.body())
        if not verify_signature(runtime.callback_token, timestamp, nonce, encrypted, msg_signature):
            raise HTTPException(status_code=403, detail="Invalid archive callback signature")
        try:
            decrypt_callback_message(runtime.encoding_aes_key, encrypted, runtime.corp_id)
        except ArchiveCryptoError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        store.request_wake("wecom_callback")
        return PlainTextResponse("success")

    @app.get("/v1/admin/status")
    async def admin_status(x_archive_admin_token: str | None = Header(default=None, alias="X-Archive-Admin-Token")):
        require_admin(x_archive_admin_token)
        return {"enabled": runtime.enabled, "workerEnabled": runtime.worker_enabled, **engine.project_status()}

    @app.get("/v1/projects/{project_id}/media/{event_id}/{media_id}")
    async def project_media(
        project_id: str,
        event_id: str,
        media_id: str,
        x_project_token: str | None = Header(default=None, alias="X-WeCom-Archive-Project-Token"),
    ) -> Response:
        route = next((item for item in runtime.projects if item.project_id == project_id and item.enabled), None)
        if route is None or not x_project_token or not secrets.compare_digest(route.token, x_project_token):
            raise HTTPException(status_code=401, detail="Invalid project token")
        if not store.project_has_event(event_id, project_id):
            raise HTTPException(status_code=404, detail="Media not found")
        try:
            content = await asyncio.to_thread(engine.media_bytes, event_id, media_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Media not found") from exc
        return Response(content=content, media_type="application/octet-stream", headers={"Cache-Control": "private, max-age=300"})

    @app.post("/v1/admin/run-once")
    async def admin_run_once(x_archive_admin_token: str | None = Header(default=None, alias="X-Archive-Admin-Token")):
        require_admin(x_archive_admin_token)
        with store.advisory_lock("wecom-archive-core-ingest") as acquired:
            if not acquired:
                raise HTTPException(status_code=409, detail="Archive core worker is busy")
            try:
                pull = await asyncio.to_thread(engine.ingest_once)
            except Exception as exc:
                store.mark_pull_failure(engine.stream_key, str(exc))
                raise HTTPException(status_code=502, detail="Archive core pull failed") from exc
            delivery = await engine.deliver_once()
            cleaned = await asyncio.to_thread(engine.cleanup_expired)
        return {"pull": pull, "delivery": delivery, "cleaned": cleaned}

    @app.post("/v1/admin/replay/{project_id}")
    async def admin_replay_project(
        project_id: str,
        after_seq: int = Query(default=0, ge=0, alias="afterSeq"),
        limit: int = Query(default=1000, ge=1, le=10000),
        x_archive_admin_token: str | None = Header(default=None, alias="X-Archive-Admin-Token"),
    ):
        require_admin(x_archive_admin_token)
        try:
            return await asyncio.to_thread(engine.replay_project, project_id, after_seq, limit)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Project route is not configured") from exc

    @app.post("/v1/admin/redeliver/{project_id}/{event_id}")
    async def admin_redeliver_event(
        project_id: str,
        event_id: str,
        x_archive_admin_token: str | None = Header(default=None, alias="X-Archive-Admin-Token"),
    ):
        require_admin(x_archive_admin_token)
        with store.advisory_lock("wecom-archive-core-ingest") as acquired:
            if not acquired:
                raise HTTPException(status_code=409, detail="Archive core worker is busy")
            try:
                return await engine.redeliver_event(project_id, event_id)
            except KeyError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc

    return app


app = build_app()
