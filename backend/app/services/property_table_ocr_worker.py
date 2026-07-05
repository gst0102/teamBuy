from __future__ import annotations

import contextlib
import json
import sys
from pathlib import Path


def _clusters(indices, gap: int = 6) -> list[int]:
    result: list[int] = []
    group: list[int] = []
    for value in indices:
        value = int(value)
        if not group or value - group[-1] <= gap:
            group.append(value)
            continue
        result.append(int(sum(group) / len(group)))
        group = [value]
    if group:
        result.append(int(sum(group) / len(group)))
    return result


def _detect_table(image):
    import cv2
    import numpy as np

    height, width = image.shape[:2]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    binary = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, 31, 8)
    horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(width // 18, 35), 1))
    vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(height // 35, 25)))
    horizontal = cv2.morphologyEx(binary, cv2.MORPH_OPEN, horizontal_kernel)
    vertical = cv2.morphologyEx(binary, cv2.MORPH_OPEN, vertical_kernel)
    horizontal_scores = horizontal.sum(axis=1)
    vertical_scores = vertical.sum(axis=0)
    horizontal_threshold = max(255 * width * 0.12, float(horizontal_scores.max()) * 0.35)
    vertical_threshold = max(255 * height * 0.10, float(vertical_scores.max()) * 0.35)
    horizontal_lines = _clusters(np.where(horizontal_scores > horizontal_threshold)[0], gap=8)
    vertical_lines = _clusters(np.where(vertical_scores > vertical_threshold)[0], gap=8)
    row_bounds = []
    for top, bottom in zip(horizontal_lines, horizontal_lines[1:]):
        if bottom - top >= 14:
            row_bounds.append((top, bottom))
    table_like = len(vertical_lines) >= 4 and len(row_bounds) >= 8
    return {
        "tableLike": table_like,
        "width": width,
        "height": height,
        "horizontalLines": horizontal_lines,
        "verticalLines": vertical_lines,
        "rowBounds": row_bounds,
    }


def _ocr_rows(image, row_bounds):
    import cv2
    from paddleocr import PaddleOCR  # type: ignore

    with contextlib.redirect_stdout(sys.stderr):
        ocr = PaddleOCR(use_angle_cls=True, lang="ch", show_log=False)
    rows: list[str] = []
    confidences: list[float] = []
    height, width = image.shape[:2]
    for top, bottom in row_bounds:
        top = max(top - 2, 0)
        bottom = min(bottom + 2, height)
        if bottom - top < 14:
            continue
        crop = image[top:bottom, 0:width]
        crop = cv2.resize(crop, None, fx=4, fy=4, interpolation=cv2.INTER_CUBIC)
        raw = ocr.ocr(crop, cls=True)
        cells = []
        for page in raw or []:
            for item in page or []:
                if not isinstance(item, (list, tuple)) or len(item) < 2:
                    continue
                value = item[1]
                if not isinstance(value, (list, tuple)) or not value:
                    continue
                text = str(value[0] or "").strip()
                if not text:
                    continue
                try:
                    x = min(float(point[0]) for point in item[0])
                except Exception:
                    x = len(cells)
                cells.append((x, text))
                if len(value) > 1:
                    with contextlib.suppress(TypeError, ValueError):
                        confidences.append(float(value[1]))
        row_text = " ".join(text for _, text in sorted(cells, key=lambda cell: cell[0])).strip()
        if row_text:
            rows.append(row_text)
    confidence = sum(confidences) / len(confidences) if confidences else None
    return rows, confidence


def main() -> int:
    image_path = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    detect_only = "--detect-only" in sys.argv
    if not image_path or not image_path.exists():
        print(json.dumps({"configured": False, "tableLike": False, "text": "", "details": {"reason": "图片文件不存在"}}, ensure_ascii=False))
        return 0
    try:
        import cv2

        image = cv2.imread(str(image_path))
        if image is None:
            raise ValueError("图片读取失败")
        detected = _detect_table(image)
        if detect_only:
            print(json.dumps({"configured": True, **detected}, ensure_ascii=False))
            return 0
        if not detected["tableLike"]:
            print(json.dumps({"configured": True, "text": "", "confidence": 0, "details": detected}, ensure_ascii=False))
            return 0
        rows, confidence = _ocr_rows(image, detected["rowBounds"])
    except Exception as exc:
        print(json.dumps({"configured": False, "text": "", "confidence": 0, "details": {"reason": str(exc)}}, ensure_ascii=False))
        return 0
    print(
        json.dumps(
            {
                "configured": True,
                "text": "\n".join(rows),
                "confidence": confidence,
                "details": {
                    **{key: value for key, value in detected.items() if key != "rowBounds"},
                    "rowCount": len(detected["rowBounds"]),
                    "lineCount": len(rows),
                    "mode": "property-table-row-ocr",
                },
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
