from __future__ import annotations

import re
from typing import Any

import httpx
from fastapi import APIRouter, Query

from app.core.config import settings
from app.schemas.common import ApiResponse


router = APIRouter(prefix="/api/enterprise-resources", tags=["enterprise-resources"])


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _short_name(name: str) -> str:
    clean = re.sub(r"[（）()]", "", name)
    clean = clean.replace("有限公司", "").replace("有限责任公司", "").replace("股份", "")
    clean = clean.replace("湖南", "").replace("长沙", "").replace("市", "")
    return clean[:4] or name[:4] or "企业"


def _pick(item: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in item and item[key] not in {None, ""}:
            return item[key]
    return ""


def _normalize_company(item: dict[str, Any], index: int = 0) -> dict[str, Any]:
    name = _clean_text(_pick(item, "name", "companyName", "entName"))
    credit_code = _clean_text(_pick(item, "creditCode", "credit_code", "regNumber", "orgNumber"))
    return {
        "id": _clean_text(_pick(item, "id", "gid", "companyId", "graphId")) or credit_code or f"tyc_{index}",
        "shortName": _clean_text(_pick(item, "alias", "shortName")) or _short_name(name),
        "name": name or "未命名企业",
        "status": _clean_text(_pick(item, "regStatus", "status", "regStatusCn")) or "未知",
        "legalPerson": _clean_text(_pick(item, "legalPersonName", "legalPerson", "legalPersonAlias")) or "未公开",
        "capital": _clean_text(_pick(item, "regCapital", "capital", "registeredCapital")) or "未公开",
        "foundedAt": _clean_text(_pick(item, "estiblishTime", "establishTime", "fromTime"))[:10] or "未公开",
        "industry": _clean_text(_pick(item, "industry", "industryAll", "category")) or "未公开",
        "city": _clean_text(_pick(item, "city", "base", "area")) or "未公开",
        "address": _clean_text(_pick(item, "regLocation", "address", "approvedTime")) or "未公开",
        "creditCode": credit_code or "未公开",
        "risk": _clean_text(_pick(item, "risk", "riskLevel")) or "建议继续查看司法风险和历史变更",
        "source": "tyc",
    }


def _extract_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    result = payload.get("result") or payload.get("data") or {}
    if isinstance(result, list):
        return result
    if not isinstance(result, dict):
        return []
    for key in ("items", "result", "list", "companyList", "data"):
        value = result.get(key)
        if isinstance(value, list):
            return value
    return []


def _markdown_cell(value: str) -> str:
    return re.sub(r"<[^>]+>", "", value).strip()


def _parse_markdown_companies(markdown: str) -> list[dict[str, Any]]:
    rows: list[list[str]] = []
    for line in markdown.splitlines():
        clean = line.strip()
        if not clean.startswith("|") or not clean.endswith("|"):
            continue
        cells = [_markdown_cell(cell) for cell in clean.strip("|").split("|")]
        if cells and all(re.fullmatch(r":?-{3,}:?", cell.replace(" ", "")) for cell in cells):
            continue
        rows.append(cells)
    if len(rows) < 2:
        return []
    header = rows[0]
    items: list[dict[str, Any]] = []
    for row in rows[1:]:
        values = {header[index]: row[index] for index in range(min(len(header), len(row)))}
        name = values.get("企业名称", "")
        if not name:
            continue
        items.append({
            "id": values.get("企业ID") or values.get("统一社会信用代码") or name,
            "shortName": _short_name(name),
            "name": name,
            "status": values.get("登记状态") or "未知",
            "legalPerson": values.get("法定代表人") or "未公开",
            "capital": values.get("注册资本") or "未公开",
            "foundedAt": (values.get("成立日期") or "未公开")[:10],
            "industry": values.get("企业类型") or "未公开",
            "city": "未公开",
            "address": "未公开",
            "creditCode": values.get("统一社会信用代码") or "未公开",
            "risk": "建议继续查看司法风险和历史变更",
            "source": "tyc-mcp",
        })
    return items


def _mcp_headers() -> dict[str, str]:
    return {
        "Authorization": settings.tyc_api_key,
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
    }


def _mcp_search_companies(keyword: str, page_size: int) -> list[dict[str, Any]]:
    headers = _mcp_headers()
    init_payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "teambuy", "version": "0.1.0"},
        },
    }
    with httpx.Client(timeout=20) as client:
        init_response = client.post(settings.tyc_mcp_url, headers=headers, json=init_payload)
        init_response.raise_for_status()
        session_id = init_response.headers.get("mcp-session-id") or init_response.headers.get("Mcp-Session-Id")
        if session_id:
            headers = {**headers, "mcp-session-id": session_id}
        client.post(settings.tyc_mcp_url, headers=headers, json={
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            "params": {},
        })
        response = client.post(settings.tyc_mcp_url, headers=headers, json={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "search_companies",
                "arguments": {
                    "query": keyword,
                    "page": 1,
                    "page_size": page_size,
                },
            },
        })
        response.raise_for_status()
        payload = response.json()
    if payload.get("error"):
        raise RuntimeError(payload["error"])
    content = ((payload.get("result") or {}).get("content") or [])
    markdown = "\n".join(item.get("text", "") for item in content if item.get("type") == "text")
    return _parse_markdown_companies(markdown)


@router.get("/search", response_model=ApiResponse[dict])
def search_enterprises(keyword: str = Query(..., min_length=1), page_size: int = Query(default=10, ge=1, le=20)):
    clean_keyword = keyword.strip()
    if not settings.tyc_api_key:
        return ApiResponse(data={
            "configured": False,
            "items": [],
            "message": "企业查询服务未配置",
        })

    try:
        items = _mcp_search_companies(clean_keyword, page_size)
    except Exception:
        return ApiResponse(data={
            "configured": True,
            "items": [],
            "message": "企业查询暂时不可用，请稍后再试",
        })
    return ApiResponse(data={
        "configured": True,
        "items": items,
        "message": "ok",
    })
