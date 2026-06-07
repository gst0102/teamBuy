from __future__ import annotations

import json
from pathlib import Path


class WecomMockService:
    def __init__(self, mock_dir: Path):
        self.mock_dir = mock_dir

    def load_fixture(self, fixture_name: str) -> list[dict]:
        filename = {
            "note": "wecom-note-messages.json",
            "link": "wecom-link-messages.json",
        }.get(fixture_name, "wecom-note-messages.json")
        return json.loads((self.mock_dir / filename).read_text(encoding="utf-8"))

    def sync_messages(self, external_user_id: str, conversation_id: str, fixture_name: str) -> list[dict]:
        messages = self.load_fixture(fixture_name)
        normalized: list[dict] = []
        for item in messages:
            normalized.append(
                {
                    **item,
                    "externalUserId": external_user_id,
                    "conversationId": conversation_id,
                }
            )
        return normalized

