from __future__ import annotations

from fastapi import HTTPException, UploadFile


async def read_upload_with_limit(
    file: UploadFile,
    max_bytes: int,
    too_large_detail: str,
) -> bytes:
    """Read at most one byte beyond the configured limit.

    Starlette may spool an upload to disk, but it does not make an unbounded
    ``read()`` safe for the application.  Keeping the limit at the API edge
    prevents oversized media from reaching image/PDF/video decoders.
    """
    limit = max(int(max_bytes), 1)
    content = await file.read(limit + 1)
    if len(content) > limit:
        raise HTTPException(status_code=413, detail=too_large_detail)
    if not content:
        raise HTTPException(status_code=400, detail="上传文件不能为空")
    return content
