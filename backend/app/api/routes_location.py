from __future__ import annotations

import httpx
from fastapi import APIRouter, Query

from app.core.config import settings
from app.schemas.common import ApiResponse


router = APIRouter(prefix="/api/location", tags=["location"])


@router.get("/geocode", response_model=ApiResponse[dict])
def geocode_address(address: str = Query(..., min_length=2), region: str | None = Query(default=None)):
    clean_address = address.strip()
    if not settings.tencent_map_key:
        return ApiResponse(data={
            "configured": False,
            "found": False,
            "address": clean_address,
            "message": "TENCENT_MAP_KEY 未配置",
        })

    params = {
        "key": settings.tencent_map_key,
        "address": clean_address,
    }
    if region:
        params["region"] = region.strip()

    try:
        response = httpx.get(settings.tencent_map_geocoder_url, params=params, timeout=8)
        response.raise_for_status()
        payload = response.json()
    except Exception:
        return ApiResponse(data={
            "configured": True,
            "found": False,
            "address": clean_address,
            "message": "腾讯地图解析失败，请稍后重试或手动选择位置",
        })

    result = payload.get("result") or {}
    location = result.get("location") or {}
    latitude = location.get("lat")
    longitude = location.get("lng")
    if payload.get("status") != 0 or latitude is None or longitude is None:
        return ApiResponse(data={
            "configured": True,
            "found": False,
            "address": clean_address,
            "message": payload.get("message") or "未匹配到地图位置",
        })

    return ApiResponse(data={
        "configured": True,
        "found": True,
        "provider": "tencent-map",
        "name": result.get("title") or clean_address,
        "address": result.get("address") or clean_address,
        "latitude": latitude,
        "longitude": longitude,
        "level": result.get("level") or "",
        "reliability": result.get("reliability"),
    })
