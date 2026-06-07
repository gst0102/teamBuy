from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

import psycopg
from psycopg.rows import dict_row

from app.core.database import normalize_database_url
from app.models.domain import AppState, Card, Category, ImportBatch, ImportNotification, RawMessage, RelayEntry, User, ViewEvent


class AppRepository(Protocol):
    def load(self) -> AppState:
        ...

    def save(self, state: AppState) -> None:
        ...

    def get_user(self, user_id: str) -> User | None:
        ...

    def get_user_by_openid(self, openid: str) -> User | None:
        ...

    def save_user(self, user: User) -> None:
        ...

    def list_import_batches(self, statuses: set[str] | None = None) -> list[ImportBatch]:
        ...

    def get_import_batch(self, import_id: str) -> ImportBatch | None:
        ...

    def save_import_batch(self, batch: ImportBatch) -> None:
        ...

    def save_raw_messages(self, messages: list[RawMessage]) -> None:
        ...

    def save_import_artifacts(
        self,
        batch: ImportBatch,
        raw_messages: list[RawMessage],
        card: Card,
        notification: ImportNotification,
    ) -> None:
        ...

    def get_card(self, card_id: str) -> Card | None:
        ...

    def list_cards(self, owner_user_id: str | None = None, keyword: str | None = None, category_id: str | None = None) -> list[Card]:
        ...

    def save_card(self, card: Card) -> None:
        ...

    def add_view_event(self, event: ViewEvent) -> None:
        ...

    def list_view_events_for_card(self, card_id: str) -> list[ViewEvent]:
        ...

    def add_relay_entry(self, relay: RelayEntry) -> None:
        ...

    def get_relay_entry(self, relay_id: str) -> RelayEntry | None:
        ...

    def save_relay_entry(self, relay: RelayEntry) -> None:
        ...

    def list_relay_entries_for_card(self, card_id: str, relay_status: str | None = "active") -> list[RelayEntry]:
        ...

    def save_import_notification(self, notification: ImportNotification) -> None:
        ...

    def list_import_notifications(self) -> list[ImportNotification]:
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

    def get_user(self, user_id: str) -> User | None:
        return next((item for item in self.load().users if item.id == user_id), None)

    def get_user_by_openid(self, openid: str) -> User | None:
        return next((item for item in self.load().users if item.openid == openid), None)

    def save_user(self, user: User) -> None:
        state = self.load()
        state.users = [item for item in state.users if item.id != user.id]
        state.users.append(user)
        self.save(state)

    def list_import_batches(self, statuses: set[str] | None = None) -> list[ImportBatch]:
        batches = self.load().import_batches
        return [item for item in batches if statuses is None or item.status in statuses]

    def get_import_batch(self, import_id: str) -> ImportBatch | None:
        return next((item for item in self.load().import_batches if item.id == import_id), None)

    def save_import_batch(self, batch: ImportBatch) -> None:
        state = self.load()
        state.import_batches = [item for item in state.import_batches if item.id != batch.id]
        state.import_batches.append(batch)
        self.save(state)

    def save_raw_messages(self, messages: list[RawMessage]) -> None:
        state = self.load()
        message_ids = {item.id for item in messages}
        state.raw_messages = [item for item in state.raw_messages if item.id not in message_ids]
        state.raw_messages.extend(messages)
        self.save(state)

    def save_import_artifacts(
        self,
        batch: ImportBatch,
        raw_messages: list[RawMessage],
        card: Card,
        notification: ImportNotification,
    ) -> None:
        state = self.load()
        state.import_batches = [item for item in state.import_batches if item.id != batch.id]
        state.import_batches.append(batch)
        message_ids = {item.id for item in raw_messages}
        state.raw_messages = [item for item in state.raw_messages if item.id not in message_ids]
        state.raw_messages.extend(raw_messages)
        state.cards = [item for item in state.cards if item.id != card.id]
        state.cards.append(card)
        state.import_notifications = [item for item in state.import_notifications if item.id != notification.id]
        state.import_notifications.append(notification)
        self.save(state)

    def get_card(self, card_id: str) -> Card | None:
        return next((item for item in self.load().cards if item.id == card_id), None)

    def list_cards(self, owner_user_id: str | None = None, keyword: str | None = None, category_id: str | None = None) -> list[Card]:
        cards = self.load().cards
        if owner_user_id:
            cards = [item for item in cards if item.ownerUserId == owner_user_id]
        if keyword:
            cards = [item for item in cards if keyword.lower() in item.title.lower()]
        if category_id:
            cards = [item for item in cards if category_id in item.categoryIds]
        return cards

    def save_card(self, card: Card) -> None:
        state = self.load()
        state.cards = [item for item in state.cards if item.id != card.id]
        state.cards.append(card)
        self.save(state)

    def add_view_event(self, event: ViewEvent) -> None:
        state = self.load()
        state.view_events.append(event)
        self.save(state)

    def list_view_events_for_card(self, card_id: str) -> list[ViewEvent]:
        return [item for item in self.load().view_events if item.cardId == card_id]

    def add_relay_entry(self, relay: RelayEntry) -> None:
        state = self.load()
        state.relay_entries.append(relay)
        self.save(state)

    def get_relay_entry(self, relay_id: str) -> RelayEntry | None:
        return next((item for item in self.load().relay_entries if item.id == relay_id), None)

    def save_relay_entry(self, relay: RelayEntry) -> None:
        state = self.load()
        state.relay_entries = [item for item in state.relay_entries if item.id != relay.id]
        state.relay_entries.append(relay)
        self.save(state)

    def list_relay_entries_for_card(self, card_id: str, relay_status: str | None = "active") -> list[RelayEntry]:
        relays = [item for item in self.load().relay_entries if item.cardId == card_id]
        if relay_status:
            relays = [item for item in relays if item.status == relay_status]
        return relays

    def save_import_notification(self, notification: ImportNotification) -> None:
        state = self.load()
        state.import_notifications = [item for item in state.import_notifications if item.id != notification.id]
        state.import_notifications.append(notification)
        self.save(state)

    def list_import_notifications(self) -> list[ImportNotification]:
        return self.load().import_notifications


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
    FIELD_COLUMNS = {
        "users": [
            ("openid", "text", "openid"),
            ("nickname", "text", "nickname"),
        ],
        "import_batches": [
            ("external_user_id", "text", "externalUserId"),
            ("conversation_id", "text", "conversationId"),
            ("claimed_by_user_id", "text", "claimedByUserId"),
            ("status", "text", "status"),
            ("title_candidate", "text", "titleCandidate"),
            ("source_type", "text", "sourceType"),
            ("generated_card_id", "text", "generatedCardId"),
            ("started_at", "timestamptz", "startedAt"),
            ("ended_at", "timestamptz", "endedAt"),
        ],
        "raw_messages": [
            ("import_batch_id", "text", "importBatchId"),
            ("external_user_id", "text", "externalUserId"),
            ("conversation_id", "text", "conversationId"),
            ("msg_type", "text", "msgType"),
            ("media_id", "text", "mediaId"),
            ("received_at", "timestamptz", "receivedAt"),
        ],
        "cards": [
            ("owner_user_id", "text", "ownerUserId"),
            ("import_batch_id", "text", "importBatchId"),
            ("source_card_id", "text", "sourceCardId"),
            ("status", "text", "status"),
            ("title", "text", "title"),
            ("published_at", "timestamptz", "publishedAt"),
        ],
        "view_events": [
            ("card_id", "text", "cardId"),
            ("viewer_user_id", "text", "viewerUserId"),
            ("view_type", "text", "viewType"),
            ("anonymous_id", "text", "anonymousId"),
            ("date_key", "date", "dateKey"),
            ("viewed_at", "timestamptz", "viewedAt"),
        ],
        "relay_entries": [
            ("card_id", "text", "cardId"),
            ("user_id", "text", "userId"),
            ("nickname", "text", "nickname"),
            ("status", "text", "status"),
            ("follow_up_status", "text", "followUpStatus"),
        ],
        "categories": [
            ("owner_user_id", "text", "ownerUserId"),
            ("name", "text", "name"),
        ],
        "import_notifications": [
            ("import_batch_id", "text", "importBatchId"),
            ("external_user_id", "text", "externalUserId"),
            ("conversation_id", "text", "conversationId"),
            ("status", "text", "status"),
            ("channel", "text", "channel"),
            ("sent_at", "timestamptz", "sentAt"),
        ],
    }
    INDEXES = {
        "import_batches": [
            ("idx_import_batches_status", "status"),
            ("idx_import_batches_conversation", "external_user_id, conversation_id, started_at"),
            ("idx_import_batches_claimed_by", "claimed_by_user_id"),
        ],
        "raw_messages": [
            ("idx_raw_messages_batch", "import_batch_id"),
            ("idx_raw_messages_conversation_time", "external_user_id, conversation_id, received_at"),
            ("idx_raw_messages_type", "msg_type"),
        ],
        "cards": [
            ("idx_cards_owner_status", "owner_user_id, status, updated_at"),
            ("idx_cards_import_batch", "import_batch_id"),
            ("idx_cards_source_card", "source_card_id"),
        ],
        "view_events": [
            ("idx_view_events_card_time", "card_id, viewed_at"),
            ("idx_view_events_card_date", "card_id, date_key"),
            ("idx_view_events_logged_viewer", "card_id, viewer_user_id"),
            ("idx_view_events_anonymous", "card_id, anonymous_id"),
        ],
        "relay_entries": [
            ("idx_relay_entries_card_status", "card_id, status, created_at"),
            ("idx_relay_entries_card_follow_up", "card_id, follow_up_status"),
            ("idx_relay_entries_user", "user_id"),
        ],
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
                        self._upsert_payload(conn, table_name, payload)

    def get_payload_by_id(self, table_name: str, item_id: str) -> dict | None:
        self._ensure_known_table(table_name)
        with psycopg.connect(self.database_url, row_factory=dict_row) as conn:
            row = conn.execute(f"select payload from {table_name} where id = %s", (item_id,)).fetchone()
        return row["payload"] if row else None

    def list_import_batches_by_status(self, batch_status: str) -> list[dict]:
        return self._list_payloads(
            "import_batches",
            "status = %s",
            (batch_status,),
            "started_at desc, id desc",
        )

    def get_user(self, user_id: str) -> User | None:
        payload = self.get_payload_by_id("users", user_id)
        return User.model_validate(payload) if payload else None

    def get_user_by_openid(self, openid: str) -> User | None:
        rows = self._list_payloads("users", "openid = %s", (openid,), "created_at desc, id desc")
        return User.model_validate(rows[0]) if rows else None

    def save_user(self, user: User) -> None:
        self._save_model("users", user)

    def list_import_batches(self, statuses: set[str] | None = None) -> list[ImportBatch]:
        if statuses:
            rows = self._list_payloads(
                "import_batches",
                "status = any(%s)",
                (list(statuses),),
                "started_at desc, id desc",
            )
        else:
            rows = self._list_payloads("import_batches", "true", (), "started_at desc, id desc")
        return [ImportBatch.model_validate(row) for row in rows]

    def get_import_batch(self, import_id: str) -> ImportBatch | None:
        payload = self.get_payload_by_id("import_batches", import_id)
        return ImportBatch.model_validate(payload) if payload else None

    def save_import_batch(self, batch: ImportBatch) -> None:
        self._save_model("import_batches", batch)

    def save_raw_messages(self, messages: list[RawMessage]) -> None:
        with psycopg.connect(self.database_url) as conn:
            with conn.transaction():
                for message in messages:
                    self._upsert_payload(conn, "raw_messages", message.model_dump(mode="json"))

    def save_import_artifacts(
        self,
        batch: ImportBatch,
        raw_messages: list[RawMessage],
        card: Card,
        notification: ImportNotification,
    ) -> None:
        with psycopg.connect(self.database_url) as conn:
            with conn.transaction():
                self._upsert_payload(conn, "import_batches", batch.model_dump(mode="json"))
                for message in raw_messages:
                    self._upsert_payload(conn, "raw_messages", message.model_dump(mode="json"))
                self._upsert_payload(conn, "cards", card.model_dump(mode="json"))
                self._upsert_payload(conn, "import_notifications", notification.model_dump(mode="json"))

    def list_raw_messages_for_batch(self, import_batch_id: str) -> list[dict]:
        return self._list_payloads(
            "raw_messages",
            "import_batch_id = %s",
            (import_batch_id,),
            "received_at asc, id asc",
        )

    def get_card(self, card_id: str) -> Card | None:
        payload = self.get_payload_by_id("cards", card_id)
        return Card.model_validate(payload) if payload else None

    def list_cards_by_owner(self, owner_user_id: str, card_status: str | None = None) -> list[dict]:
        if card_status:
            return self._list_payloads(
                "cards",
                "owner_user_id = %s and status = %s",
                (owner_user_id, card_status),
                "updated_at desc, id desc",
            )
        return self._list_payloads(
            "cards",
            "owner_user_id = %s",
            (owner_user_id,),
            "updated_at desc, id desc",
        )

    def list_cards(self, owner_user_id: str | None = None, keyword: str | None = None, category_id: str | None = None) -> list[Card]:
        where_parts = ["true"]
        params: list[str] = []
        if owner_user_id:
            where_parts.append("owner_user_id = %s")
            params.append(owner_user_id)
        if keyword:
            where_parts.append("title ilike %s")
            params.append(f"%{keyword}%")
        if category_id:
            where_parts.append("payload->'categoryIds' ? %s")
            params.append(category_id)
        rows = self._list_payloads("cards", " and ".join(where_parts), tuple(params), "updated_at desc, id desc")
        return [Card.model_validate(row) for row in rows]

    def save_card(self, card: Card) -> None:
        self._save_model("cards", card)

    def list_view_events_for_card(self, card_id: str) -> list[dict]:
        rows = self._list_payloads(
            "view_events",
            "card_id = %s",
            (card_id,),
            "viewed_at desc, id desc",
        )
        return [ViewEvent.model_validate(row) for row in rows]

    def add_view_event(self, event: ViewEvent) -> None:
        self._save_model("view_events", event)

    def list_relay_entries_for_card(self, card_id: str, relay_status: str = "active") -> list[dict]:
        rows = self._list_payloads(
            "relay_entries",
            "card_id = %s and status = %s",
            (card_id, relay_status),
            "created_at desc, id desc",
        )
        return [RelayEntry.model_validate(row) for row in rows]

    def add_relay_entry(self, relay: RelayEntry) -> None:
        self._save_model("relay_entries", relay)

    def get_relay_entry(self, relay_id: str) -> RelayEntry | None:
        payload = self.get_payload_by_id("relay_entries", relay_id)
        return RelayEntry.model_validate(payload) if payload else None

    def save_relay_entry(self, relay: RelayEntry) -> None:
        self._save_model("relay_entries", relay)

    def save_import_notification(self, notification: ImportNotification) -> None:
        self._save_model("import_notifications", notification)

    def list_import_notifications(self) -> list[ImportNotification]:
        rows = self._list_payloads("import_notifications", "true", (), "sent_at desc, id desc")
        return [ImportNotification.model_validate(row) for row in rows]

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
                    for column_name, column_type, _ in self.FIELD_COLUMNS.get(table_name, []):
                        conn.execute(f"alter table {table_name} add column if not exists {column_name} {column_type}")
                    for index_name, expression in self.INDEXES.get(table_name, []):
                        conn.execute(f"create index if not exists {index_name} on {table_name} ({expression})")

    def _upsert_payload(self, conn, table_name: str, payload: dict) -> None:
        field_columns = self.FIELD_COLUMNS.get(table_name, [])
        columns = ["id", "payload", "created_at", "updated_at", *[column[0] for column in field_columns]]
        placeholders = ["%s", "%s::jsonb", "coalesce(%s::timestamptz, now())", "coalesce(%s::timestamptz, now())"]
        placeholders.extend(["%s"] * len(field_columns))
        update_columns = [column for column in columns if column != "id"]
        update_sql = ", ".join([f"{column} = excluded.{column}" for column in update_columns])
        values = [
            payload["id"],
            json.dumps(payload, ensure_ascii=False),
            payload.get("createdAt") or payload.get("sentAt"),
            payload.get("updatedAt") or payload.get("sentAt"),
            *[payload.get(payload_key) for _, _, payload_key in field_columns],
        ]
        conn.execute(
            f"""
            insert into {table_name} ({", ".join(columns)})
            values ({", ".join(placeholders)})
            on conflict (id) do update set {update_sql}
            """,
            values,
        )

    def _save_model(self, table_name: str, item) -> None:
        self._ensure_known_table(table_name)
        with psycopg.connect(self.database_url) as conn:
            with conn.transaction():
                self._upsert_payload(conn, table_name, item.model_dump(mode="json"))

    def _list_payloads(self, table_name: str, where_sql: str, params: tuple, order_sql: str) -> list[dict]:
        self._ensure_known_table(table_name)
        with psycopg.connect(self.database_url, row_factory=dict_row) as conn:
            rows = conn.execute(
                f"select payload from {table_name} where {where_sql} order by {order_sql}",
                params,
            ).fetchall()
        return [row["payload"] for row in rows]

    def _ensure_known_table(self, table_name: str) -> None:
        if table_name not in self.TABLES.values():
            raise ValueError(f"Unknown repository table: {table_name}")


def build_repository(database_backend: str, database_url: str, data_file: Path) -> AppRepository:
    if database_backend == "postgres" and database_url:
        try:
            return PostgresRepository(database_url)
        except psycopg.Error:
            return JsonRepository(data_file)
    return JsonRepository(data_file)
