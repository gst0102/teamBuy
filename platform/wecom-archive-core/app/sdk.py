from __future__ import annotations

import base64
import ctypes
import json
from dataclasses import dataclass
from pathlib import Path

from Crypto.Cipher import PKCS1_v1_5
from Crypto.PublicKey import RSA


class FinanceSdkError(RuntimeError):
    pass


@dataclass(frozen=True)
class DownloadedMedia:
    content: bytes
    content_type: str | None = None
    filename: str | None = None


class FinanceSdkClient:
    def __init__(
        self,
        corp_id: str,
        secret: str,
        private_key_path: Path,
        sdk_lib_path: Path,
        proxy: str = "",
        proxy_password: str = "",
        timeout_seconds: int = 30,
    ):
        self.corp_id = corp_id
        self.secret = secret
        self.private_key_path = private_key_path
        self.sdk_lib_path = sdk_lib_path
        self.proxy = proxy
        self.proxy_password = proxy_password
        self.timeout_seconds = timeout_seconds

    def pull_and_decrypt(self, seq: int, limit: int) -> list[dict]:
        sdk = _FinanceSdk(self.sdk_lib_path, self.corp_id, self.secret)
        try:
            payload = json.loads(sdk.get_chat_data(seq, limit, self.proxy, self.proxy_password, self.timeout_seconds))
            if int(payload.get("errcode", 0)) != 0:
                raise FinanceSdkError(f"GetChatData failed: {payload.get('errcode')}")
            return [self._decrypt_item(sdk, item) for item in payload.get("chatdata") or []]
        finally:
            sdk.close()

    def download_media(self, sdk_file_id: str) -> DownloadedMedia:
        sdk = _FinanceSdk(self.sdk_lib_path, self.corp_id, self.secret)
        try:
            return DownloadedMedia(content=sdk.get_media_data(sdk_file_id, self.proxy, self.proxy_password, self.timeout_seconds))
        finally:
            sdk.close()

    def _decrypt_item(self, sdk: "_FinanceSdk", item: dict) -> dict:
        encrypted_key = item.get("encrypt_random_key") or item.get("encryptRandomKey")
        encrypted_message = item.get("encrypt_chat_msg") or item.get("encryptChatMsg")
        if not encrypted_key or not encrypted_message:
            raise FinanceSdkError("chatdata is missing encrypted fields")
        key_text = self.private_key_path.read_text(encoding="utf-8")
        private_key = RSA.import_key(key_text)
        random_key = PKCS1_v1_5.new(private_key).decrypt(base64.b64decode(encrypted_key), None)
        if random_key is None:
            raise FinanceSdkError("archive random key decryption failed")
        decrypted = json.loads(sdk.decrypt_data(random_key.decode("utf-8"), encrypted_message))
        return {
            **item,
            "decryptedPayload": decrypted,
            "msgid": decrypted.get("msgid") or item.get("msgid"),
            "action": decrypted.get("action") or item.get("action"),
            "from": decrypted.get("from"),
            "tolist": decrypted.get("tolist") or [],
            "roomid": decrypted.get("roomid"),
            "msgtime": decrypted.get("msgtime"),
            "msgtype": decrypted.get("msgtype"),
        }


class _FinanceSdk:
    def __init__(self, lib_path: Path, corp_id: str, secret: str):
        self.lib = ctypes.cdll.LoadLibrary(str(lib_path))
        self._bind()
        self.sdk = self.lib.NewSdk()
        result = self.lib.Init(self.sdk, corp_id.encode(), secret.encode())
        if result != 0:
            self.close()
            raise FinanceSdkError(f"Finance SDK Init failed: {result}")

    def _bind(self) -> None:
        self.lib.NewSdk.restype = ctypes.c_void_p
        self.lib.DestroySdk.argtypes = [ctypes.c_void_p]
        self.lib.Init.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p]
        self.lib.Init.restype = ctypes.c_int
        self.lib.NewSlice.restype = ctypes.c_void_p
        self.lib.FreeSlice.argtypes = [ctypes.c_void_p]
        self.lib.GetContentFromSlice.argtypes = [ctypes.c_void_p]
        self.lib.GetContentFromSlice.restype = ctypes.c_char_p
        self.lib.GetChatData.argtypes = [ctypes.c_void_p, ctypes.c_ulonglong, ctypes.c_uint, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int, ctypes.c_void_p]
        self.lib.GetChatData.restype = ctypes.c_int
        self.lib.DecryptData.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_void_p]
        self.lib.DecryptData.restype = ctypes.c_int
        self.lib.GetMediaData.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int, ctypes.c_void_p]
        self.lib.GetMediaData.restype = ctypes.c_int
        self.lib.NewMediaData.restype = ctypes.c_void_p
        self.lib.FreeMediaData.argtypes = [ctypes.c_void_p]
        self.lib.GetOutIndexBuf.argtypes = [ctypes.c_void_p]
        self.lib.GetOutIndexBuf.restype = ctypes.c_void_p
        self.lib.GetData.argtypes = [ctypes.c_void_p]
        self.lib.GetData.restype = ctypes.c_void_p
        self.lib.GetIndexLen.argtypes = [ctypes.c_void_p]
        self.lib.GetIndexLen.restype = ctypes.c_int
        self.lib.GetDataLen.argtypes = [ctypes.c_void_p]
        self.lib.GetDataLen.restype = ctypes.c_int
        self.lib.IsMediaDataFinish.argtypes = [ctypes.c_void_p]
        self.lib.IsMediaDataFinish.restype = ctypes.c_int

    def get_chat_data(self, seq: int, limit: int, proxy: str, proxy_password: str, timeout_seconds: int) -> str:
        output = self.lib.NewSlice()
        try:
            result = self.lib.GetChatData(self.sdk, seq, limit, proxy.encode(), proxy_password.encode(), timeout_seconds, output)
            if result != 0:
                raise FinanceSdkError(f"Finance SDK GetChatData failed: {result}")
            return self._slice_text(output)
        finally:
            self.lib.FreeSlice(output)

    def decrypt_data(self, random_key: str, encrypted_message: str) -> str:
        output = self.lib.NewSlice()
        try:
            result = self.lib.DecryptData(random_key.encode(), encrypted_message.encode(), output)
            if result != 0:
                raise FinanceSdkError(f"Finance SDK DecryptData failed: {result}")
            return self._slice_text(output)
        finally:
            self.lib.FreeSlice(output)

    def get_media_data(self, sdk_file_id: str, proxy: str, proxy_password: str, timeout_seconds: int) -> bytes:
        index_buf = b""
        chunks: list[bytes] = []
        for _ in range(10000):
            media_data = self.lib.NewMediaData()
            try:
                result = self.lib.GetMediaData(self.sdk, index_buf, sdk_file_id.encode(), proxy.encode(), proxy_password.encode(), timeout_seconds, media_data)
                if result != 0:
                    raise FinanceSdkError(f"Finance SDK GetMediaData failed: {result}")
                data_len = self.lib.GetDataLen(media_data)
                data_ptr = self.lib.GetData(media_data)
                if data_ptr and data_len > 0:
                    chunks.append(ctypes.string_at(data_ptr, data_len))
                if self.lib.IsMediaDataFinish(media_data):
                    return b"".join(chunks)
                index_len = self.lib.GetIndexLen(media_data)
                index_ptr = self.lib.GetOutIndexBuf(media_data)
                index_buf = ctypes.string_at(index_ptr, index_len) if index_ptr and index_len > 0 else b""
                if not index_buf:
                    raise FinanceSdkError("Finance SDK GetMediaData returned no next index")
            finally:
                self.lib.FreeMediaData(media_data)
        raise FinanceSdkError("Finance SDK GetMediaData exceeded max chunks")

    def _slice_text(self, value) -> str:
        content = self.lib.GetContentFromSlice(value)
        return content.decode("utf-8") if content else ""

    def close(self) -> None:
        if getattr(self, "sdk", None):
            self.lib.DestroySdk(self.sdk)
            self.sdk = None
