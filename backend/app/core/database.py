from __future__ import annotations

import psycopg

from app.core.config import Settings


class DatabaseConfigError(ValueError):
    pass


def validate_database_settings(settings: Settings) -> dict:
    missing = settings.missing_database_fields()
    return {
        "backend": settings.database_backend,
        "configured": not missing,
        "missing": missing,
    }


def check_postgres_connection(settings: Settings) -> dict:
    if settings.database_backend != "postgres":
        return {"backend": settings.database_backend, "connected": False, "message": "PostgreSQL 未启用"}
    if not settings.database_url:
        raise DatabaseConfigError("缺少 DATABASE_URL")

    with psycopg.connect(settings.database_url, connect_timeout=5) as conn:
        with conn.cursor() as cur:
            cur.execute("select 1")
            value = cur.fetchone()[0]
    return {"backend": "postgres", "connected": value == 1, "message": "PostgreSQL 连接成功"}
