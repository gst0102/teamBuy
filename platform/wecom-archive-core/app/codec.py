from __future__ import annotations

import base64
import hashlib
import hmac
import json
from typing import Any

from Crypto.Cipher import AES


class SealedPayload:
    def __init__(self, key: bytes):
        self.key = key

    def seal(self, value: dict[str, Any]) -> str:
        cipher = AES.new(self.key, AES.MODE_GCM)
        ciphertext, tag = cipher.encrypt_and_digest(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode())
        return base64.urlsafe_b64encode(cipher.nonce + tag + ciphertext).decode()

    def open(self, value: str) -> dict[str, Any]:
        raw = base64.urlsafe_b64decode(value.encode())
        nonce, tag, ciphertext = raw[:16], raw[16:32], raw[32:]
        return json.loads(AES.new(self.key, AES.MODE_GCM, nonce=nonce).decrypt_and_verify(ciphertext, tag))


def digest(value: object) -> str:
    return hashlib.sha256(str(value or "").encode()).hexdigest()[:24]


def media_token(key: bytes, event_id: str, path: str, sdk_file_id: str) -> str:
    return "media_" + hmac.new(key, f"{event_id}:{path}:{sdk_file_id}".encode(), hashlib.sha256).hexdigest()[:32]
