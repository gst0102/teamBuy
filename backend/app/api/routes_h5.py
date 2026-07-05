from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse


router = APIRouter(tags=["h5"])

H5_RESOURCE_TOOLS_INDEX = Path(__file__).resolve().parents[1] / "static" / "h5" / "resource-tools" / "index.html"


@router.get("/h5/resource-tools")
@router.get("/h5/resource-tools/")
@router.get("/api/h5/resource-tools")
@router.get("/api/h5/resource-tools/")
def resource_tools_h5():
    return FileResponse(H5_RESOURCE_TOOLS_INDEX)
