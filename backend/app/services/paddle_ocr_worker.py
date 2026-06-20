from __future__ import annotations

import contextlib
import json
import sys
from pathlib import Path


def main() -> int:
    image_path = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if not image_path or not image_path.exists():
        print(json.dumps({"configured": False, "text": "", "confidence": 0, "details": {"reason": "图片文件不存在"}}, ensure_ascii=False))
        return 0
    try:
        with contextlib.redirect_stdout(sys.stderr):
            from paddleocr import PaddleOCR  # type: ignore

            ocr = PaddleOCR(use_angle_cls=True, lang="ch", show_log=False)
            raw = ocr.ocr(str(image_path), cls=True)
    except Exception as exc:
        print(json.dumps({"configured": False, "text": "", "confidence": 0, "details": {"reason": str(exc)}}, ensure_ascii=False))
        return 0
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
    print(
        json.dumps(
            {
                "configured": True,
                "text": "\n".join(lines),
                "confidence": confidence,
                "details": {"lineCount": len(lines)},
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
