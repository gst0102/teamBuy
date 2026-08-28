from __future__ import annotations

import ctypes
import base64
import json
from pathlib import Path
from urllib.parse import quote

import httpx

from Crypto.Cipher import PKCS1_v1_5
from Crypto.PublicKey import RSA

from app.services.wecom_client import DownloadedMedia


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
        max_download_bytes: int = 50 * 1024 * 1024,
    ):
        self.corp_id = corp_id
        self.secret = secret
        self.private_key_path = private_key_path
        self.sdk_lib_path = sdk_lib_path
        self.proxy = proxy
        self.proxy_password = proxy_password
        self.timeout_seconds = timeout_seconds
        self.max_download_bytes = max(int(max_download_bytes), 1)

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

    def download_media(self, sdk_file_id: str) -> DownloadedMedia:
        missing = self.missing_fields()
        if missing:
            raise WecomArchiveClientError("会话内容存档 SDK 配置不完整: " + ", ".join(missing))
        sdk = _FinanceSdk(self.sdk_lib_path, self.corp_id, self.secret)
        try:
            content = sdk.get_media_data(
                sdk_file_id=sdk_file_id,
                proxy=self.proxy,
                proxy_password=self.proxy_password,
                timeout_seconds=self.timeout_seconds,
                max_bytes=self.max_download_bytes,
            )
        finally:
            sdk.close()
        return DownloadedMedia(content=content, content_type=None, filename=None)

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


class SharedWecomArchiveMediaClient:
    """Media-only adapter for messages delivered by wecom-archive-core."""

    def __init__(
        self,
        base_url: str,
        project_id: str,
        project_token: str,
        timeout_seconds: int = 30,
        max_download_bytes: int = 50 * 1024 * 1024,
    ):
        self.base_url = base_url.rstrip("/")
        self.project_id = project_id
        self.project_token = project_token
        self.timeout_seconds = timeout_seconds
        self.max_download_bytes = max(int(max_download_bytes), 1)

    def missing_fields(self) -> list[str]:
        missing: list[str] = []
        if not self.base_url:
            missing.append("WECOM_ARCHIVE_CORE_MEDIA_BASE_URL")
        if not self.project_id:
            missing.append("WECOM_ARCHIVE_CORE_PROJECT_ID")
        if not self.project_token:
            missing.append("WECOM_ARCHIVE_CORE_PROJECT_TOKEN")
        return missing

    def download_media(self, media_id: str) -> DownloadedMedia:
        if ":" not in media_id:
            raise WecomArchiveClientError("共享归档媒体 ID 缺少事件上下文")
        event_id, opaque_media_id = media_id.split(":", 1)
        missing = self.missing_fields()
        if missing:
            raise WecomArchiveClientError("共享归档媒体配置不完整: " + ", ".join(missing))
        url = (
            f"{self.base_url}/v1/projects/{quote(self.project_id, safe='')}"
            f"/media/{quote(event_id, safe='')}/{quote(opaque_media_id, safe='')}"
        )
        try:
            with httpx.stream(
                "GET",
                url,
                headers={"X-WeCom-Archive-Project-Token": self.project_token},
                timeout=max(self.timeout_seconds, 120),
            ) as response:
                response.raise_for_status()
                content_length = response.headers.get("content-length")
                try:
                    declared_length = int(content_length) if content_length else None
                except ValueError:
                    declared_length = None
                if declared_length and declared_length > self.max_download_bytes:
                    raise WecomArchiveClientError("共享归档媒体超过服务器允许的大小")
                content_type = response.headers.get("content-type")
                chunks: list[bytes] = []
                total = 0
                for chunk in response.iter_bytes():
                    total += len(chunk)
                    if total > self.max_download_bytes:
                        raise WecomArchiveClientError("共享归档媒体超过服务器允许的大小")
                    chunks.append(chunk)
                content = b"".join(chunks)
        except httpx.HTTPError as exc:
            raise WecomArchiveClientError("共享归档媒体读取失败") from exc
        return DownloadedMedia(
            content=content,
            content_type=content_type,
            filename=None,
        )


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
        self.lib.DecryptData.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_void_p]
        self.lib.DecryptData.restype = ctypes.c_int
        self.lib.GetMediaData.argtypes = [
            ctypes.c_void_p,
            ctypes.c_char_p,
            ctypes.c_char_p,
            ctypes.c_char_p,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_void_p,
        ]
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
                random_key.encode("utf-8"),
                encrypted_msg.encode("utf-8"),
                output,
            )
            if ret != 0:
                raise WecomArchiveClientError(f"Finance SDK DecryptData failed: {ret}")
            return self._slice_text(output)
        finally:
            self.lib.FreeSlice(output)

    def get_media_data(
        self,
        sdk_file_id: str,
        proxy: str,
        proxy_password: str,
        timeout_seconds: int,
        max_bytes: int = 50 * 1024 * 1024,
    ) -> bytes:
        index_buf = b""
        chunks: list[bytes] = []
        total_bytes = 0
        for _ in range(10000):
            media_data = self.lib.NewMediaData()
            try:
                ret = self.lib.GetMediaData(
                    self.sdk,
                    index_buf,
                    sdk_file_id.encode("utf-8"),
                    proxy.encode("utf-8"),
                    proxy_password.encode("utf-8"),
                    timeout_seconds,
                    media_data,
                )
                if ret != 0:
                    raise WecomArchiveClientError(f"Finance SDK GetMediaData failed: {ret}")
                data_len = self.lib.GetDataLen(media_data)
                if data_len > 0:
                    data_ptr = self.lib.GetData(media_data)
                    if data_ptr:
                        chunk = ctypes.string_at(data_ptr, data_len)
                        total_bytes += len(chunk)
                        if total_bytes > max_bytes:
                            raise WecomArchiveClientError("会话存档媒体超过服务器允许的大小")
                        chunks.append(chunk)
                if self.lib.IsMediaDataFinish(media_data):
                    return b"".join(chunks)
                index_len = self.lib.GetIndexLen(media_data)
                index_ptr = self.lib.GetOutIndexBuf(media_data)
                index_buf = ctypes.string_at(index_ptr, index_len) if index_ptr and index_len > 0 else b""
                if not index_buf:
                    raise WecomArchiveClientError("Finance SDK GetMediaData missing next index buffer")
            finally:
                self.lib.FreeMediaData(media_data)
        raise WecomArchiveClientError("Finance SDK GetMediaData exceeded max chunks")

    def _slice_text(self, value) -> str:
        content = self.lib.GetContentFromSlice(value)
        return content.decode("utf-8") if content else ""

    def close(self) -> None:
        if getattr(self, "sdk", None):
            self.lib.DestroySdk(self.sdk)
            self.sdk = None
