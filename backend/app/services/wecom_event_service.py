from __future__ import annotations

import json
import xml.etree.ElementTree as ET

from app.core.config import Settings
from app.services.wecom_crypto import WecomCryptoError, decrypt_aes_message, verify_signature


def parse_callback_body(
    raw_body: bytes,
    content_type: str,
    settings: Settings,
    query: dict[str, str | None],
    token: str | None = None,
    encoding_aes_key: str | None = None,
) -> dict:
    text = raw_body.decode("utf-8") if raw_body else ""
    if "application/json" in content_type:
        return json.loads(text or "{}")

    if not text.strip():
        return {}

    xml_payload = _xml_to_dict(text)
    encrypted = xml_payload.get("Encrypt")
    if encrypted:
        callback_token = token or settings.wecom_callback_token
        callback_aes_key = encoding_aes_key or settings.wecom_encoding_aes_key
        signature = query.get("msg_signature") or ""
        timestamp = query.get("timestamp") or ""
        nonce = query.get("nonce") or ""
        if not verify_signature(callback_token, timestamp, nonce, encrypted, signature):
            raise WecomCryptoError("企业微信回调签名验证失败")
        decrypted_xml = decrypt_aes_message(callback_aes_key, encrypted, settings.wecom_corp_id)
        return _xml_to_dict(decrypted_xml)
    return xml_payload


def _xml_to_dict(xml_text: str) -> dict:
    root = ET.fromstring(xml_text)
    payload: dict[str, str] = {}
    for child in root:
        payload[child.tag] = child.text or ""
    return payload
