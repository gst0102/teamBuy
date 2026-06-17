from __future__ import annotations

import ctypes
import base64
import json
from pathlib import Path

from Crypto.Cipher import PKCS1_v1_5
from Crypto.PublicKey import RSA


class WecomArchiveClientError(RuntimeError):
    pass


class WecomArchiveClient:
    def __init__(
        self,
        corp_id: str,
        secret: str,
        private_key_path: Path | None,
        sdk_lib_path: Path | None,
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

    def is_configured(self) -> bool:
        return bool(
            self.corp_id
            and self.secret
            and self.private_key_path
            and self.private_key_path.exists()
            and self.sdk_lib_path
            and self.sdk_lib_path.exists()
        )

    def missing_fields(self) -> list[str]:
        missing: list[str] = []
        if not self.corp_id:
            missing.append("WECOM_CORP_ID")
        if not self.secret:
            missing.append("WECOM_ARCHIVE_SECRET")
        if not self.private_key_path:
            missing.append("WECOM_ARCHIVE_PRIVATE_KEY_PATH")
        elif not self.private_key_path.exists():
            missing.append("WECOM_ARCHIVE_PRIVATE_KEY_PATH(file not found)")
        if not self.sdk_lib_path:
            missing.append("WECOM_ARCHIVE_SDK_LIB_PATH")
        elif not self.sdk_lib_path.exists():
            missing.append("WECOM_ARCHIVE_SDK_LIB_PATH(file not found)")
        return missing

    def pull_and_decrypt(self, seq: int, limit: int) -> dict:
        missing = self.missing_fields()
        if missing:
            raise WecomArchiveClientError("会话内容存档 SDK 配置不完整: " + ", ".join(missing))
        sdk = _FinanceSdk(self.sdk_lib_path, self.corp_id, self.secret)
        try:
            raw_response = sdk.get_chat_data(
                seq=seq,
                limit=limit,
                proxy=self.proxy,
                proxy_password=self.proxy_password,
                timeout_seconds=self.timeout_seconds,
            )
            payload = json.loads(raw_response)
            if int(payload.get("errcode", 0)) != 0:
                raise WecomArchiveClientError(f"GetChatData failed: {payload}")
            messages = []
            for item in payload.get("chatdata") or []:
                messages.append(self._decrypt_item(sdk, item))
            return {
                "errcode": payload.get("errcode", 0),
                "errmsg": payload.get("errmsg", "ok"),
                "rawCount": len(payload.get("chatdata") or []),
                "messages": messages,
            }
        finally:
            sdk.close()

    def _decrypt_item(self, sdk: "_FinanceSdk", item: dict) -> dict:
        encrypt_random_key = item.get("encrypt_random_key") or item.get("encryptRandomKey")
        encrypt_chat_msg = item.get("encrypt_chat_msg") or item.get("encryptChatMsg")
        if not encrypt_random_key or not encrypt_chat_msg:
            raise WecomArchiveClientError("chatdata 缺少 encrypt_random_key 或 encrypt_chat_msg")
        random_key = self._decrypt_random_key(encrypt_random_key)
        decrypted_text = sdk.decrypt_data(random_key, encrypt_chat_msg)
        try:
            decrypted_payload = json.loads(decrypted_text)
        except json.JSONDecodeError as exc:
            raise WecomArchiveClientError(f"DecryptData returned invalid JSON: {exc}") from exc
        return {
            **item,
            "decryptedPayload": decrypted_payload,
            "msgid": decrypted_payload.get("msgid") or item.get("msgid"),
            "action": decrypted_payload.get("action") or item.get("action"),
            "from": decrypted_payload.get("from"),
            "tolist": decrypted_payload.get("tolist") or [],
            "roomid": decrypted_payload.get("roomid"),
            "msgtime": decrypted_payload.get("msgtime"),
            "msgtype": decrypted_payload.get("msgtype"),
        }

    def _decrypt_random_key(self, encrypted_key: str) -> str:
        key_text = self.private_key_path.read_text(encoding="utf-8")
        private_key = RSA.import_key(key_text)
        cipher = PKCS1_v1_5.new(private_key)
        decrypted = cipher.decrypt(base64.b64decode(encrypted_key), None)
        if decrypted is None:
            raise WecomArchiveClientError("encrypt_random_key 解密失败")
        return decrypted.decode("utf-8")


class _FinanceSdk:
    def __init__(self, lib_path: Path, corp_id: str, secret: str):
        self.lib = ctypes.cdll.LoadLibrary(str(lib_path))
        self._bind()
        self.sdk = self.lib.NewSdk()
        ret = self.lib.Init(self.sdk, corp_id.encode("utf-8"), secret.encode("utf-8"))
        if ret != 0:
            self.close()
            raise WecomArchiveClientError(f"Finance SDK Init failed: {ret}")

    def _bind(self) -> None:
        self.lib.NewSdk.restype = ctypes.c_void_p
        self.lib.DestroySdk.argtypes = [ctypes.c_void_p]
        self.lib.Init.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p]
        self.lib.Init.restype = ctypes.c_int
        self.lib.NewSlice.restype = ctypes.c_void_p
        self.lib.FreeSlice.argtypes = [ctypes.c_void_p]
        self.lib.GetContentFromSlice.argtypes = [ctypes.c_void_p]
        self.lib.GetContentFromSlice.restype = ctypes.c_char_p
        self.lib.GetChatData.argtypes = [
            ctypes.c_void_p,
            ctypes.c_ulonglong,
            ctypes.c_uint,
            ctypes.c_char_p,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_void_p,
        ]
        self.lib.GetChatData.restype = ctypes.c_int
        self.lib.DecryptData.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_void_p]
        self.lib.DecryptData.restype = ctypes.c_int

    def get_chat_data(self, seq: int, limit: int, proxy: str, proxy_password: str, timeout_seconds: int) -> str:
        output = self.lib.NewSlice()
        try:
            ret = self.lib.GetChatData(
                self.sdk,
                seq,
                limit,
                proxy.encode("utf-8"),
                proxy_password.encode("utf-8"),
                timeout_seconds,
                output,
            )
            if ret != 0:
                raise WecomArchiveClientError(f"Finance SDK GetChatData failed: {ret}")
            return self._slice_text(output)
        finally:
            self.lib.FreeSlice(output)

    def decrypt_data(self, random_key: str, encrypted_msg: str) -> str:
        output = self.lib.NewSlice()
        try:
            ret = self.lib.DecryptData(
                self.sdk,
                random_key.encode("utf-8"),
                encrypted_msg.encode("utf-8"),
                output,
            )
            if ret != 0:
                raise WecomArchiveClientError(f"Finance SDK DecryptData failed: {ret}")
            return self._slice_text(output)
        finally:
            self.lib.FreeSlice(output)

    def _slice_text(self, value) -> str:
        content = self.lib.GetContentFromSlice(value)
        return content.decode("utf-8") if content else ""

    def close(self) -> None:
        if getattr(self, "sdk", None):
            self.lib.DestroySdk(self.sdk)
            self.sdk = None
