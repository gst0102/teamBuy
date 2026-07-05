from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

from app.services.ocr_service import OcrResult


class PropertyTableOcrService:
    def looks_like_property_table_image(self, content: bytes) -> bool:
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp.write(content)
            tmp_path = Path(tmp.name)
        try:
            completed = subprocess.run(
                [sys.executable, "-m", "app.services.property_table_ocr_worker", str(tmp_path), "--detect-only"],
                check=False,
                capture_output=True,
                text=True,
                timeout=20,
            )
        except Exception:
            return False
        finally:
            tmp_path.unlink(missing_ok=True)
        if completed.returncode != 0:
            return False
        try:
            payload = json.loads(completed.stdout.strip() or "{}")
        except json.JSONDecodeError:
            return False
        return bool(payload.get("tableLike"))

    def extract_text(self, content: bytes, filename: str | None = None) -> OcrResult:
        with tempfile.NamedTemporaryFile(suffix=Path(filename or "table.png").suffix or ".png", delete=False) as tmp:
            tmp.write(content)
            tmp_path = Path(tmp.name)
        try:
            completed = subprocess.run(
                [sys.executable, "-m", "app.services.property_table_ocr_worker", str(tmp_path)],
                check=False,
                capture_output=True,
                text=True,
                timeout=240,
            )
        except subprocess.TimeoutExpired:
            return OcrResult(text="", provider="paddle-table", configured=True, confidence=0, details={"reason": "表格 OCR 执行超时"})
        except Exception as exc:
            return OcrResult(text="", provider="paddle-table", configured=False, confidence=0, details={"reason": str(exc)})
        finally:
            tmp_path.unlink(missing_ok=True)
        if completed.returncode != 0:
            reason = completed.stderr.strip() or completed.stdout.strip() or "表格 OCR 子进程异常退出"
            return OcrResult(text="", provider="paddle-table", configured=False, confidence=0, details={"reason": reason[-1000:]})
        try:
            payload = json.loads(completed.stdout.strip() or "{}")
        except json.JSONDecodeError:
            return OcrResult(text="", provider="paddle-table", configured=False, confidence=0, details={"reason": "表格 OCR 返回解析失败"})
        return OcrResult(
            text=str(payload.get("text") or ""),
            provider="paddle-table",
            configured=bool(payload.get("configured")),
            confidence=payload.get("confidence"),
            details=payload.get("details") if isinstance(payload.get("details"), dict) else {},
        )
