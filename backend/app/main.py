from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes_auth import router as auth_router
from app.api.routes_cards import router as cards_router
from app.api.routes_imports import router as imports_router
from app.api.routes_notes import router as notes_router
from app.api.routes_skills import router as skills_router
from app.api.routes_wecom import recover_persisted_sync_tasks, router as wecom_router
from app.core.config import settings
from app.core.database import DatabaseConfigError, check_postgres_connection, validate_database_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    await recover_persisted_sync_tasks()
    yield


app = FastAPI(title="teamBuy MVP API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(imports_router)
app.include_router(cards_router)
app.include_router(wecom_router)
app.include_router(skills_router)
app.include_router(notes_router)

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
