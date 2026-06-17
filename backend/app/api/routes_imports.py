from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.dependencies import get_app_service
from app.schemas.common import ApiResponse
from app.schemas.imports import ClaimImportRequest
from app.services.app_service import AppService


router = APIRouter(prefix="/api/imports", tags=["imports"])


@router.get("/pending", response_model=ApiResponse[list[dict]])
def list_pending_imports(service: AppService = Depends(get_app_service)):
    return ApiResponse(data=service.list_pending_imports())


@router.post("/{import_id}/claim", response_model=ApiResponse[dict])
def claim_import(import_id: str, payload: ClaimImportRequest, service: AppService = Depends(get_app_service)):
    result = service.claim_import(import_id, payload.userId)
    return ApiResponse(
        data={
            "importBatch": result["importBatch"].model_dump(),
            "card": result["card"].model_dump(),
            "note": result["note"].model_dump() if result.get("note") else None,
            "identityBinding": result["identityBinding"].model_dump() if result.get("identityBinding") else None,
        }
    )
