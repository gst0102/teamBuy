from __future__ import annotations

import json
from pathlib import Path

from app.services.wecom_message_normalizer import WecomMessageNormalizer


class WecomMockService:
    def __init__(self, mock_dir: Path):
        self.mock_dir = mock_dir
        self.normalizer = WecomMessageNormalizer()

    def load_fixture(self, fixture_name: str) -> list[dict]:
        filename = {
            "note": "wecom-note-messages.json",
            "link": "wecom-link-messages.json",
        }.get(fixture_name, "wecom-note-messages.json")
        return json.loads((self.mock_dir / filename).read_text(encoding="utf-8"))

    def sync_messages(self, external_user_id: str, conversation_id: str, fixture_name: str) -> list[dict]:
        messages = self.load_fixture(fixture_name)
        return self.normalizer.normalize_messages(messages, external_user_id, conversation_id)
