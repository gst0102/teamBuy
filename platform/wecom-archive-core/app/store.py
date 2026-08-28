from __future__ import annotations

import contextlib
from collections.abc import Iterator
from datetime import datetime
from typing import Any

import psycopg
from psycopg.rows import dict_row


class CursorConflict(RuntimeError):
    pass


class PostgresStore:
    def __init__(self, database_url: str):
        self.database_url = database_url

    def _connect(self) -> psycopg.Connection:
        return psycopg.connect(self.database_url, row_factory=dict_row)

    def ensure_schema(self, schema_sql: str) -> None:
        with self._connect() as connection:
            connection.execute(schema_sql)

    @contextlib.contextmanager
    def advisory_lock(self, lock_name: str) -> Iterator[bool]:
        connection = self._connect()
        acquired = False
        try:
            row = connection.execute(
                "select pg_try_advisory_lock(hashtext(%s)) as acquired",
                (lock_name,),
            ).fetchone()
            acquired = bool(row and row["acquired"])
            yield acquired
            if acquired:
                connection.execute("select pg_advisory_unlock(hashtext(%s))", (lock_name,))
                connection.commit()
        finally:
            connection.close()

    def cursor(self, stream_key: str) -> int:
        with self._connect() as connection:
            row = connection.execute(
                "select next_seq from archive_core_cursors where stream_key = %s",
                (stream_key,),
            ).fetchone()
        return int(row["next_seq"]) if row else 0

    def ingest(
        self,
        *,
        stream_key: str,
        events: list[dict[str, Any]],
        sealed_payloads: dict[str, str],
        route_ids: dict[str, list[str]],
    ) -> dict[str, int]:
        inserted = 0
        duplicate = 0
        deliveries = 0
        with self._connect() as connection:
            for event in events:
                event_id = str(event["eventId"])
                result = connection.execute(
                    """
                    insert into archive_core_messages
                        (event_id, stream_key, seq, message_id_hash, room_id_hash,
                         message_type, message_time, sealed_payload)
                    values (%s, %s, %s, %s, %s, %s, %s, %s)
                    on conflict (event_id) do nothing
                    """,
                    (
                        event_id,
                        stream_key,
                        int(event["seq"]),
                        event.get("messageIdHash"),
                        event.get("roomIdHash"),
                        event.get("messageType"),
                        event.get("messageTime"),
                        sealed_payloads[event_id],
                    ),
                )
                if result.rowcount:
                    inserted += 1
                else:
                    duplicate += 1
                for project_id in route_ids.get(event_id, []):
                    result = connection.execute(
                        """
                        insert into archive_core_deliveries (event_id, project_id)
                        values (%s, %s)
                        on conflict (event_id, project_id) do nothing
                        """,
                        (event_id, project_id),
                    )
                    deliveries += int(result.rowcount or 0)
        return {"inserted": inserted, "duplicate": duplicate, "deliveries": deliveries}

    def advance_cursor(
        self,
        *,
        stream_key: str,
        expected_seq: int,
        next_seq: int,
        batch_count: int,
    ) -> None:
        with self._connect() as connection:
            result = connection.execute(
                """
                insert into archive_core_cursors
                    (stream_key, next_seq, last_batch_count, last_success_at, last_error)
                values (%s, %s, %s, now(), null)
                on conflict (stream_key) do update set
                    next_seq = excluded.next_seq,
                    last_batch_count = excluded.last_batch_count,
                    last_success_at = now(),
                    last_error = null,
                    updated_at = now()
                where archive_core_cursors.next_seq = %s
                """,
                (stream_key, next_seq, batch_count, expected_seq),
            )
            if result.rowcount != 1:
                raise CursorConflict("archive core cursor changed during ingestion")

    def mark_pull_failure(self, stream_key: str, error: str) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                insert into archive_core_cursors (stream_key, last_error)
                values (%s, %s)
                on conflict (stream_key) do update set
                    last_error = excluded.last_error,
                    updated_at = now()
                """,
                (stream_key, error[:500]),
            )

    def pending_deliveries(self, limit: int) -> list[dict[str, Any]]:
        with self._connect() as connection:
            return list(
                connection.execute(
                    """
                    select d.event_id, d.project_id, d.attempts, m.sealed_payload
                    from archive_core_deliveries d
                    join archive_core_messages m on m.event_id = d.event_id
                    where d.status = 'pending' and d.next_attempt_at <= now()
                    order by d.next_attempt_at asc, d.event_id asc
                    limit %s
                    """,
                    (limit,),
                ).fetchall()
            )

    def project_has_event(self, event_id: str, project_id: str) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                """
                select 1
                from archive_core_deliveries
                where event_id = %s and project_id = %s
                """,
                (event_id, project_id),
            ).fetchone()
        return bool(row)

    def messages_after(self, stream_key: str, after_seq: int, limit: int) -> list[dict[str, Any]]:
        with self._connect() as connection:
            return list(
                connection.execute(
                    """
                    select event_id, stream_key, seq, sealed_payload
                    from archive_core_messages
                    where stream_key = %s and seq > %s
                    order by seq asc
                    limit %s
                    """,
                    (stream_key, after_seq, limit),
                ).fetchall()
            )

    def add_delivery(self, event_id: str, project_id: str) -> bool:
        with self._connect() as connection:
            result = connection.execute(
                """
                insert into archive_core_deliveries (event_id, project_id)
                values (%s, %s)
                on conflict (event_id, project_id) do nothing
                """,
                (event_id, project_id),
            )
        return bool(result.rowcount)

    def reset_delivery(self, event_id: str, project_id: str) -> bool:
        with self._connect() as connection:
            result = connection.execute(
                """
                update archive_core_deliveries
                set status = 'pending', next_attempt_at = now(), delivered_at = null,
                    last_error = null, updated_at = now()
                where event_id = %s and project_id = %s
                """,
                (event_id, project_id),
            )
        return bool(result.rowcount)

    def mark_delivery_success(self, event_id: str, project_id: str) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                update archive_core_deliveries
                set status = 'delivered', attempts = attempts + 1,
                    delivered_at = now(), last_error = null, updated_at = now()
                where event_id = %s and project_id = %s
                """,
                (event_id, project_id),
            )

    def mark_delivery_failure(self, event_id: str, project_id: str, error: str, attempts: int) -> None:
        delay = min(300, 2 ** min(max(attempts, 0), 8))
        with self._connect() as connection:
            connection.execute(
                """
                update archive_core_deliveries
                set status = 'pending', attempts = attempts + 1,
                    next_attempt_at = now() + (%s * interval '1 second'),
                    last_error = %s, updated_at = now()
                where event_id = %s and project_id = %s
                """,
                (delay, error[:500], event_id, project_id),
            )

    def load_sealed_payload(self, event_id: str) -> str | None:
        with self._connect() as connection:
            row = connection.execute(
                "select sealed_payload from archive_core_messages where event_id = %s",
                (event_id,),
            ).fetchone()
        return str(row["sealed_payload"]) if row else None

    def cleanup_expired_messages(self, retention_hours: int, limit: int) -> int:
        """Delete only expired payloads whose project deliveries are complete.

        The delivery rows intentionally cascade with the message. The core is a
        short-lived encrypted relay, not the system of record; each project is
        responsible for durable business storage after acknowledging an event.
        """
        with self._connect() as connection:
            result = connection.execute(
                """
                delete from archive_core_messages
                where event_id in (
                    select candidate.event_id
                    from archive_core_messages candidate
                    where candidate.created_at < now() - (%s * interval '1 hour')
                      and not exists (
                          select 1
                          from archive_core_deliveries delivery
                          where delivery.event_id = candidate.event_id
                            and delivery.status <> 'delivered'
                      )
                    order by candidate.created_at asc
                    limit %s
                )
                """,
                (max(int(retention_hours), 1), max(int(limit), 1)),
            )
        return int(result.rowcount or 0)

    def request_wake(self, trigger: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "insert into archive_core_wakes (trigger) values (%s)",
                (trigger[:80],),
            )

    def has_wake(self) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                "select 1 from archive_core_wakes where consumed_at is null limit 1"
            ).fetchone()
        return bool(row)

    def consume_wakes(self) -> None:
        with self._connect() as connection:
            connection.execute(
                "update archive_core_wakes set consumed_at = now() where consumed_at is null"
            )

    def status(self, stream_key: str) -> dict[str, Any]:
        with self._connect() as connection:
            cursor = connection.execute(
                "select * from archive_core_cursors where stream_key = %s",
                (stream_key,),
            ).fetchone()
            counts = connection.execute(
                """
                select status, count(*)::int as count
                from archive_core_deliveries group by status
                """
            ).fetchall()
        return {
            "cursor": cursor or {"stream_key": stream_key, "next_seq": 0},
            "deliveries": {str(item["status"]): int(item["count"]) for item in counts},
        }
