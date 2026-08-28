from __future__ import annotations

import base64
import binascii
import hashlib
import xml.etree.ElementTree as ET

from Crypto.Cipher import AES


class ArchiveCryptoError(ValueError):
    pass


def verify_signature(token: str, timestamp: str, nonce: str, encrypted: str, signature: str) -> bool:
    expected = hashlib.sha1("".join(sorted((token, timestamp, nonce, encrypted))).encode()).hexdigest()
    return bool(signature) and expected == signature


def decrypt_callback_message(aes_key: str, encrypted: str, corp_id: str) -> str:
    try:
        key = base64.b64decode(aes_key + "=", validate=False)
        cipher = AES.new(key, AES.MODE_CBC, key[:16])
        padded = cipher.decrypt(base64.b64decode(encrypted))
    except (ValueError, TypeError, binascii.Error) as exc:
        raise ArchiveCryptoError("invalid archive callback encryption") from exc
    if not padded:
        raise ArchiveCryptoError("empty archive callback payload")
    padding = padded[-1]
    if padding < 1 or padding > 32 or padded[-padding:] != bytes([padding]) * padding:
        raise ArchiveCryptoError("invalid archive callback padding")
    body = padded[:-padding]
    if len(body) < 20:
        raise ArchiveCryptoError("archive callback payload is too short")
    length = int.from_bytes(body[16:20], "big")
    message = body[20 : 20 + length]
    received_corp_id = body[20 + length :].decode("utf-8")
    if received_corp_id and received_corp_id != corp_id:
        raise ArchiveCryptoError("archive callback corp id mismatch")
    return message.decode("utf-8")


def encrypted_xml_value(body: bytes) -> str:
    try:
        root = ET.fromstring(body)
        value = root.findtext("Encrypt") or root.findtext("encrypt")
    except ET.ParseError as exc:
        raise ArchiveCryptoError("invalid archive callback XML") from exc
    if not value:
        raise ArchiveCryptoError("archive callback XML has no Encrypt field")
    return value.strip()
