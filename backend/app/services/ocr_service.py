from __future__ import annotations

import shutil
import subprocess
import tempfile
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
        try:
            from paddleocr import PaddleOCR  # type: ignore
        except Exception:
            return OcrResult(text="", provider="paddle", configured=False, confidence=0, details={"reason": "paddleocr 未安装"})
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp.write(content)
            tmp_path = Path(tmp.name)
        try:
            ocr = PaddleOCR(use_angle_cls=True, lang="ch", show_log=False)
            raw = ocr.ocr(str(tmp_path), cls=True)
        except Exception as exc:
            return OcrResult(text="", provider="paddle", configured=False, confidence=0, details={"reason": str(exc)})
        finally:
            tmp_path.unlink(missing_ok=True)
        lines: list[str] = []
        confidences: list[float] = []
        for page in raw or []:
            for item in page or []:
                if not isinstance(item, (list, tuple)) or len(item) < 2:
                    continue
                value = item[1]
                if isinstance(value, (list, tuple)) and value:
                    text = str(value[0] or "").strip()
                    if text:
                        lines.append(text)
                    if len(value) > 1:
                        try:
                            confidences.append(float(value[1]))
                        except (TypeError, ValueError):
                            pass
        confidence = sum(confidences) / len(confidences) if confidences else None
        return OcrResult(text="\n".join(lines), provider="paddle", configured=True, confidence=confidence, details={"lineCount": len(lines)})

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
