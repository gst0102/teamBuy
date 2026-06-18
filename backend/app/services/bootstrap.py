from __future__ import annotations

import json
from pathlib import Path

from app.models.domain import AppState
from app.services.repository import JsonRepository


MOCK_FILES = {
    "users": "users.json",
    "import_batches": "import-batches.json",
    "raw_messages": "raw-messages.json",
    "cards": "cards.json",
    "view_events": "view-events.json",
    "relay_entries": "relays.json",
    "customer_actions": "customer-actions.json",
    "categories": "categories.json",
    "import_notifications": "import-notifications.json",
}


def seed_runtime_state(repo: JsonRepository, mock_dir: Path) -> None:
    state = repo.load()
    if any(
        [
            state.users,
            state.import_batches,
            state.raw_messages,
            state.cards,
            state.view_events,
            state.relay_entries,
            state.categories,
        ]
    ):
        return

    payload: dict[str, list] = {}
    for key, filename in MOCK_FILES.items():
        file_path = mock_dir / filename
        payload[key] = json.loads(file_path.read_text(encoding="utf-8"))
    repo.save(AppState.model_validate(payload))
