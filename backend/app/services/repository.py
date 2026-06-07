from __future__ import annotations

import json
from pathlib import Path

from app.models.domain import AppState


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

