from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

import psycopg
from psycopg.rows import dict_row

from app.core.database import normalize_database_url
from app.models.domain import AppState


class AppRepository(Protocol):
    def load(self) -> AppState:
        ...

    def save(self, state: AppState) -> None:
        ...


class JsonRepository:
    def __init__(self, data_file: Path):
        self.data_file = data_file
        self.data_file.parent.mkdir(parents=True, exist_ok=True)
        if not self.data_file.exists():
            self.save(AppState())

    def load(self) -> AppState:
        payload = json.loads(self.data_file.read_text(encoding="utf-8"))
        return AppState.model_validate(payload)

    def save(self, state: AppState) -> None:
        self.data_file.write_text(
            state.model_dump_json(indent=2),
            encoding="utf-8",
        )


class PostgresRepository:
    TABLES = {
        "users": "users",
        "import_batches": "import_batches",
        "raw_messages": "raw_messages",
        "cards": "cards",
        "view_events": "view_events",
        "relay_entries": "relay_entries",
        "categories": "categories",
        "import_notifications": "import_notifications",
    }

    def __init__(self, database_url: str):
        self.database_url = normalize_database_url(database_url)
        self.init_schema()

    def load(self) -> AppState:
        payload: dict[str, list[dict]] = {}
        with psycopg.connect(self.database_url, row_factory=dict_row) as conn:
            for state_key, table_name in self.TABLES.items():
                rows = conn.execute(f"select payload from {table_name} order by created_at, id").fetchall()
                payload[state_key] = [row["payload"] for row in rows]
        return AppState.model_validate(payload)

    def save(self, state: AppState) -> None:
        with psycopg.connect(self.database_url) as conn:
            with conn.transaction():
                for state_key, table_name in self.TABLES.items():
                    items = getattr(state, state_key)
                    conn.execute(f"delete from {table_name}")
                    for item in items:
                        payload = item.model_dump(mode="json")
                        conn.execute(
                            f"""
                            insert into {table_name} (id, payload, created_at, updated_at)
                            values (%s, %s::jsonb, coalesce(%s::timestamptz, now()), coalesce(%s::timestamptz, now()))
                            on conflict (id) do update set
                                payload = excluded.payload,
                                updated_at = excluded.updated_at
                            """,
                            (
                                payload["id"],
                                json.dumps(payload, ensure_ascii=False),
                                payload.get("createdAt") or payload.get("sentAt"),
                                payload.get("updatedAt") or payload.get("sentAt"),
                            ),
                        )

    def init_schema(self) -> None:
        with psycopg.connect(self.database_url) as conn:
            with conn.transaction():
                for table_name in self.TABLES.values():
                    conn.execute(
                        f"""
                        create table if not exists {table_name} (
                            id text primary key,
                            payload jsonb not null,
                            created_at timestamptz not null default now(),
                            updated_at timestamptz not null default now()
                        )
                        """
                    )
                    conn.execute(
                        f"create index if not exists idx_{table_name}_payload_gin on {table_name} using gin (payload)"
                    )


def build_repository(database_backend: str, database_url: str, data_file: Path) -> AppRepository:
    if database_backend == "postgres" and database_url:
        try:
            return PostgresRepository(database_url)
        except psycopg.Error:
            return JsonRepository(data_file)
    return JsonRepository(data_file)
