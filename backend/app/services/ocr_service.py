from __future__ import annotations

import shutil
import subprocess
import tempfile
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class OcrResult:
    text: str
    provider: str
    configured: bool
    confidence: float | None = None
    details: dict = field(default_factory=dict)


class OcrService:
    def __init__(
        self,
        provider: str = "auto",
        language: str = "chi_sim+eng",
        tesseract_bin: str = "tesseract",
        mock_text: str = "",
    ):
        self.provider = provider
        self.language = language
        self.tesseract_bin = tesseract_bin
        self.mock_text = mock_text

    def extract_text(self, content: bytes, filename: str | None = None) -> OcrResult:
        if self.provider == "mock":
            return OcrResult(
                text=self.mock_text.strip(),
                provider="mock",
                configured=True,
                confidence=1 if self.mock_text.strip() else 0,
                details={"filename": filename or "upload"},
            )
        if self.provider in {"auto", "paddle"}:
            paddle_result = self._try_paddle(content)
            if paddle_result.configured or self.provider == "paddle":
                return paddle_result
        if self.provider in {"auto", "tesseract"}:
            tesseract_result = self._try_tesseract(content, filename)
            if tesseract_result.configured or self.provider == "tesseract":
                return tesseract_result
        return OcrResult(
            text="",
            provider=self.provider,
            configured=False,
            confidence=0,
            details={"reason": "OCR 引擎未配置，可安装 PaddleOCR 或 Tesseract 后启用。"},
        )

    def _try_paddle(self, content: bytes) -> OcrResult:
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp.write(content)
            tmp_path = Path(tmp.name)
        try:
            completed = subprocess.run(
                [sys.executable, "-m", "app.services.paddle_ocr_worker", str(tmp_path)],
                check=False,
                capture_output=True,
                text=True,
                timeout=120,
            )
        except subprocess.TimeoutExpired:
            return OcrResult(text="", provider="paddle", configured=False, confidence=0, details={"reason": "paddleocr 执行超时"})
        except Exception as exc:
            return OcrResult(text="", provider="paddle", configured=False, confidence=0, details={"reason": str(exc)})
        finally:
            tmp_path.unlink(missing_ok=True)
        if completed.returncode != 0:
            reason = completed.stderr.strip() or completed.stdout.strip() or "paddleocr 子进程异常退出"
            return OcrResult(text="", provider="paddle", configured=False, confidence=0, details={"reason": reason[-1000:]})
        try:
            payload = json.loads(completed.stdout.strip() or "{}")
        except json.JSONDecodeError:
            return OcrResult(text="", provider="paddle", configured=False, confidence=0, details={"reason": "paddleocr 返回解析失败"})
        return OcrResult(
            text=str(payload.get("text") or ""),
            provider="paddle",
            configured=bool(payload.get("configured")),
            confidence=payload.get("confidence"),
            details=payload.get("details") if isinstance(payload.get("details"), dict) else {},
        )

    def _try_tesseract(self, content: bytes, filename: str | None) -> OcrResult:
        executable = shutil.which(self.tesseract_bin)
        if not executable:
            return OcrResult(text="", provider="tesseract", configured=False, confidence=0, details={"reason": "tesseract 命令不可用"})
        suffix = Path(filename or "upload.png").suffix or ".png"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(content)
            tmp_path = Path(tmp.name)
        try:
            completed = subprocess.run(
                [executable, str(tmp_path), "stdout", "-l", self.language, "--psm", "6"],
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
            )
        except Exception as exc:
            return OcrResult(text="", provider="tesseract", configured=True, confidence=0, details={"reason": str(exc)})
        finally:
            tmp_path.unlink(missing_ok=True)
        if completed.returncode != 0:
            return OcrResult(
                text="",
                provider="tesseract",
                configured=True,
                confidence=0,
                details={"reason": completed.stderr.strip() or "tesseract 执行失败"},
            )
        text = completed.stdout.strip()
        return OcrResult(text=text, provider="tesseract", configured=True, confidence=None, details={"lineCount": len([line for line in text.splitlines() if line.strip()])})
