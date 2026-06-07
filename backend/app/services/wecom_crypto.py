from __future__ import annotations

import base64
import hashlib
import struct

from Crypto.Cipher import AES


class WecomCryptoError(ValueError):
    pass


def build_signature(token: str, timestamp: str, nonce: str, encrypted: str) -> str:
    parts = [token, timestamp, nonce, encrypted]
    parts.sort()
    return hashlib.sha1("".join(parts).encode("utf-8")).hexdigest()


def verify_signature(token: str, timestamp: str, nonce: str, encrypted: str, signature: str) -> bool:
    return build_signature(token, timestamp, nonce, encrypted) == signature


def decrypt_aes_message(encoding_aes_key: str, encrypted: str, corp_id: str | None = None) -> str:
    if len(encoding_aes_key) != 43:
        raise WecomCryptoError("EncodingAESKey 必须是 43 位")
    aes_key = base64.b64decode(f"{encoding_aes_key}=")
    cipher = AES.new(aes_key, AES.MODE_CBC, aes_key[:16])
    decrypted = cipher.decrypt(base64.b64decode(encrypted))
    plaintext = _strip_pkcs7_padding(decrypted)
    msg_len = struct.unpack(">I", plaintext[16:20])[0]
    message = plaintext[20 : 20 + msg_len].decode("utf-8")
    received_corp_id = plaintext[20 + msg_len :].decode("utf-8")
    if corp_id and received_corp_id != corp_id:
        raise WecomCryptoError("CorpID 校验失败")
    return message


def _strip_pkcs7_padding(payload: bytes) -> bytes:
    pad = payload[-1]
    if pad < 1 or pad > 32:
        raise WecomCryptoError("AES padding 非法")
    return payload[:-pad]

