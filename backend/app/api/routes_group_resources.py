from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.api.dependencies import get_app_service
from app.schemas.common import ApiResponse
from app.schemas.group_resources import GroupResourceAdminCreateRequest, GroupResourceCreateRequest, GroupResourceUpdateRequest, GroupResourceViewRequest
from app.schemas.ops_admin import GroupResourceComplaintRequest
from app.services.app_service import AppService


router = APIRouter(prefix="/api/group-resources", tags=["group-resources"])


def _group_user_id(request: Request, fallback: str | None = None) -> str | None:
    if getattr(request.app.state, "production_auth_enabled", False):
        return str(getattr(request.state, "authenticated_user_id", "") or "").strip() or None
    return str(fallback or "").strip() or None


@router.get("", response_model=ApiResponse[dict | list[dict]])
def list_group_resources(
    keyword: str | None = Query(default=None),
    cityCode: str | None = Query(default=None),
    cityLabel: str | None = Query(default=None),
    industry: str | None = Query(default=None),
    purpose: str | None = Query(default=None),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=50),
    service: AppService = Depends(get_app_service),
):
    result = service.list_group_resources(
        keyword=keyword,
        city_code=cityCode,
        city_label=cityLabel,
        industry=industry,
        purpose=purpose,
        cursor=cursor,
        limit=limit,
    )
    # Keep the old no-query response shape for existing callers; paginated
    # clients pass cursor=0 and receive the envelope with hasMore/nextCursor.
    return ApiResponse(data=result if cursor is not None else result["items"])


@router.get("/mine", response_model=ApiResponse[list[dict]])
def list_my_group_resources(
    request: Request,
    ownerUserId: str = Query(...),
    service: AppService = Depends(get_app_service),
):
    user_id = _group_user_id(request, ownerUserId)
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录后查看我的群资源")
    return ApiResponse(data=service.list_my_group_resources(user_id))


@router.get("/publish-quota", response_model=ApiResponse[dict])
def get_group_resource_publish_quota(
    request: Request,
    ownerUserId: str = Query(...),
    service: AppService = Depends(get_app_service),
):
    user_id = _group_user_id(request, ownerUserId)
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录后查看发布额度")
    return ApiResponse(data=service.get_group_resource_publish_quota(user_id))


@router.get("/admin-status", response_model=ApiResponse[dict])
def get_group_resource_admin_status(
    request: Request,
    userId: str | None = Query(default=None),
    service: AppService = Depends(get_app_service),
):
    user_id = _group_user_id(request, userId)
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录后检查管理员权限")
    return ApiResponse(data=service.group_resource_admin_status(user_id))


@router.post("/admin", response_model=ApiResponse[dict])
def create_admin_group_resource(
    request: Request,
    payload: GroupResourceAdminCreateRequest,
    userId: str | None = Query(default=None),
    service: AppService = Depends(get_app_service),
):
    user_id = _group_user_id(request, userId)
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录后新增群资源")
    values = payload.model_dump(exclude_none=True)
    values["operatorName"] = values.get("operatorName") or ""
    return ApiResponse(data=service.create_group_resource_as_admin(values, operator_user_id=user_id), message="管理员群资源已提交审核")


@router.post("", response_model=ApiResponse[dict])
def create_group_resource(
    request: Request,
    payload: GroupResourceCreateRequest,
    service: AppService = Depends(get_app_service),
):
    user_id = _group_user_id(request, payload.ownerUserId)
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录后发布群资源")
    values = payload.model_dump()
    values["ownerUserId"] = user_id
    return ApiResponse(data=service.create_group_resource(values), message="群资源已发布")


@router.patch("/{resource_id}", response_model=ApiResponse[dict])
def update_group_resource(
    resource_id: str,
    request: Request,
    payload: GroupResourceUpdateRequest,
    service: AppService = Depends(get_app_service),
):
    user_id = _group_user_id(request, payload.ownerUserId)
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录后修改群资源")
    values = payload.model_dump(exclude_none=True)
    values["ownerUserId"] = user_id
    return ApiResponse(data=service.update_group_resource(resource_id, values), message="群资源已更新")


@router.delete("/{resource_id}", response_model=ApiResponse[dict])
def delete_group_resource(
    resource_id: str,
    request: Request,
    ownerUserId: str = Query(...),
    service: AppService = Depends(get_app_service),
):
    user_id = _group_user_id(request, ownerUserId)
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录后删除群资源")
    return ApiResponse(data=service.delete_group_resource(resource_id, user_id), message="群资源已删除")


@router.post("/{resource_id}/view", response_model=ApiResponse[dict])
def view_group_resource(
    resource_id: str,
    request: Request,
    payload: GroupResourceViewRequest,
    service: AppService = Depends(get_app_service),
):
    user_id = _group_user_id(request, payload.userId)
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录后查看群二维码")
    return ApiResponse(data=service.view_group_resource(resource_id, user_id))


@router.post("/{resource_id}/complaints", response_model=ApiResponse[dict])
def file_group_resource_complaint(
    resource_id: str,
    request: Request,
    payload: GroupResourceComplaintRequest,
    service: AppService = Depends(get_app_service),
):
    user_id = _group_user_id(request, payload.userId)
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录后举报群资源")
    return ApiResponse(data=service.file_group_resource_complaint(resource_id, user_id, payload.reason))
