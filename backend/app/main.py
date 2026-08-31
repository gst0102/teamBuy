from __future__ import annotations

from contextlib import asynccontextmanager
import json
import logging
import mimetypes
import re

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes_auth import router as auth_router
from app.api.routes_automation import router as automation_router
from app.api.routes_cards import router as cards_router
from app.api.routes_dashboard import router as dashboard_router
from app.api.routes_enterprise_resources import router as enterprise_resources_router
from app.api.routes_h5 import router as h5_router
from app.api.routes_imports import router as imports_router
from app.api.routes_live_qr import router as live_qr_router
from app.api.routes_location import router as location_router
from app.api.routes_messages import router as messages_router
from app.api.routes_notes import router as notes_router
from app.api.routes_ocr import router as ocr_router
from app.api.routes_opportunities import packages_router, push_router, router as opportunities_router, subscriptions_router, supply_demand_router
from app.api.routes_ops_admin import router as ops_admin_router
from app.api.routes_orders import router as orders_router
from app.api.routes_robot import router as robot_router
from app.api.routes_resource_wallet import router as resource_wallet_router
from app.api.routes_showcases import router as showcases_router
from app.api.routes_skills import router as skills_router
from app.api.routes_scrm import router as scrm_router
from app.api.routes_wecom import recover_persisted_sync_tasks, router as wecom_router
from app.api.dependencies import close_ops_console_store, close_repository, get_ocr_task_worker, get_wecom_archive_worker, register_background_task_handlers
from app.core.config import settings
from app.core.database import DatabaseConfigError, check_postgres_connection, validate_database_settings
from app.services.session_token import verify_user_session

mimetypes.add_type("image/webp", ".webp")

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    register_background_task_handlers()
    archive_worker = get_wecom_archive_worker()
    ocr_task_worker = get_ocr_task_worker()
    if settings.background_tasks_in_api:
        await recover_persisted_sync_tasks()
        archive_worker.start()
        ocr_task_worker.start()
    try:
        yield
    finally:
        await ocr_task_worker.stop()
        await archive_worker.stop()
        close_ops_console_store()
        close_repository()


app = FastAPI(title="teamBuy MVP API", version="0.1.0", lifespan=lifespan)


_IDENTITY_FIELDS = {
    "ownerUserId",
    "userId",
    "requesterUserId",
    "operatorUserId",
    "inviteeUserId",
}
_PUBLIC_API_EXACT = {
    "/api/auth/mock-login",
    "/api/auth/wechat-login",
    "/api/auth/h5-session",
    "/api/location/geocode",
}
_PUBLIC_API_PREFIXES = (
    "/api/notes/public/",
    "/api/showcases/public/",
    "/api/robot/",
    "/api/automation/",
    "/api/ops-admin/",
    "/api/ops/",
)
_PUBLIC_API_CALLBACKS = {
    "/api/wecom/kf/teamBuy/callback",
    "/api/wecom/archive/callback",
    "/api/wecom/archive/core-events",
    "/api/scrm/wechat-pay/notify",
    "/api/scrm/wechat-transfer/notify",
}
_PUBLIC_API_SUFFIXES = (
    "/view",
    "/events",
    "/customer-actions/config",
    "/customer-actions/lead-contact",
    "/customer-actions/appointment",
    "/customer-actions/order-intent",
    "/customer-actions/relay-intent",
)
_PROFILE_PATH = re.compile(r"^/api/auth/users/([^/]+)/profile$")


def _is_public_api(path: str) -> bool:
    if path in _PUBLIC_API_EXACT or path in _PUBLIC_API_CALLBACKS or path.startswith(_PUBLIC_API_PREFIXES):
        return True
    if path.startswith("/api/cards/") and (path.endswith("/view") or path.endswith("/stats")):
        return True
    if path.startswith("/api/notes/") and any(path.endswith(suffix) for suffix in _PUBLIC_API_SUFFIXES):
        return True
    if path.startswith("/api/showcases/") and path.endswith("/events"):
        return True
    return False


def _assert_identity(user_id: str, candidate: object) -> None:
    value = str(candidate or "").strip()
    if value and value != user_id:
        raise ValueError("request user does not match the authenticated account")


@app.middleware("http")
async def enforce_production_api_identity(request: Request, call_next):
    enabled = str(settings.app_env or "").lower() == "production"
    app.state.production_auth_enabled = enabled
    path = request.url.path
    authenticated_user_id = None
    if enabled and path.startswith("/api/") and request.headers.get("authorization"):
        try:
            session = verify_user_session(request.headers.get("authorization"))
        except Exception as exc:
            status = getattr(exc, "status_code", 401)
            detail = getattr(exc, "detail", "登录状态无效，请重新登录")
            return JSONResponse(status_code=status, content={"success": False, "message": detail, "data": None})
        authenticated_user_id = str(session.get("userId") or "").strip() or None
        request.state.authenticated_user_id = authenticated_user_id

    if not enabled or not path.startswith("/api/") or _is_public_api(path):
        return await call_next(request)

    try:
        user_id = authenticated_user_id
        if not user_id:
            raise ValueError("missing authenticated user")
    except Exception:
        return JSONResponse(status_code=401, content={"success": False, "message": "登录状态无效，请重新登录", "data": None})
    request.state.authenticated_user_id = user_id

    try:
        for key, value in request.query_params.multi_items():
            if key in _IDENTITY_FIELDS:
                _assert_identity(user_id, value)

        profile_match = _PROFILE_PATH.match(path)
        if profile_match:
            _assert_identity(user_id, profile_match.group(1))

        content_type = (request.headers.get("content-type") or "").lower()
        body = await request.body()
        if body and "application/json" in content_type:
            try:
                payload = json.loads(body.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                payload = None
            if isinstance(payload, dict):
                for key in _IDENTITY_FIELDS:
                    if key in payload:
                        _assert_identity(user_id, payload.get(key))
        elif body and "multipart/form-data" in content_type and b"ownerUserId" in body:
            match = re.search(rb'name="ownerUserId"\r?\n\r?\n([^\r\n-]+)', body)
            if match:
                _assert_identity(user_id, match.group(1).decode("utf-8", errors="ignore"))
    except ValueError:
        return JSONResponse(status_code=403, content={"success": False, "message": "只能访问自己的账号数据", "data": None})

    return await call_next(request)


@app.middleware("http")
async def add_cache_headers(request: Request, call_next):
    response = await call_next(request)
    path = request.url.path
    client_build = str(request.headers.get("x-teambuy-client-build") or "").strip()
    if client_build:
        response.headers["X-TeamBuy-Client-Build"] = client_build
        if path.startswith("/api/scrm/"):
            logger.info("scrm request client_build=%s path=%s status=%s", client_build, path, response.status_code)
    if path.startswith("/api/") or path.startswith("/health"):
        # API payloads may contain account-scoped content and customer data.
        # Keep browser/proxy caches from serving it across sessions.
        response.headers["Cache-Control"] = "no-store, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Vary"] = "Authorization"
    elif path.startswith(f"{settings.media_public_url_prefix.rstrip('/')}/"):
        # Media URLs are versioned/stable assets; the API never changes the
        # bytes behind an existing URL in place.
        response.headers.setdefault("Cache-Control", "public, max-age=31536000, immutable")
    return response

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(automation_router)
app.include_router(h5_router)
app.include_router(imports_router)
app.include_router(live_qr_router)
app.include_router(cards_router)
app.include_router(dashboard_router)
app.include_router(enterprise_resources_router)
app.include_router(wecom_router)
app.include_router(skills_router)
app.include_router(notes_router)
app.include_router(ocr_router)
app.include_router(opportunities_router)
app.include_router(packages_router)
app.include_router(subscriptions_router)
app.include_router(supply_demand_router)
app.include_router(push_router)
app.include_router(ops_admin_router)
app.include_router(orders_router)
app.include_router(robot_router)
app.include_router(showcases_router)
app.include_router(messages_router)
app.include_router(location_router)
app.include_router(resource_wallet_router)
app.include_router(scrm_router)

settings.media_storage_dir.mkdir(parents=True, exist_ok=True)
app.mount(
    settings.media_public_url_prefix,
    StaticFiles(directory=settings.media_storage_dir),
    name="media",
)


@app.get("/health")
def healthcheck():
    return {
        "status": "ok",
        "database": validate_database_settings(settings),
    }


@app.get("/health/db")
def database_healthcheck():
    try:
        return check_postgres_connection(settings)
    except DatabaseConfigError as exc:
        return {"backend": settings.database_backend, "connected": False, "message": str(exc)}
