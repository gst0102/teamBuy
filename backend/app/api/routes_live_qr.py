from __future__ import annotations

from io import BytesIO
import html
from pathlib import Path
import secrets
from urllib.parse import quote, urlparse
from datetime import timedelta
import math

import qrcode
from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, Response

from app.api.dependencies import get_app_service
from app.api.upload_utils import read_upload_with_limit
from app.core.config import settings
from app.models.domain import LiveQrCode
from app.schemas.common import ApiResponse
from app.schemas.ops_admin import LiveQrCodeCreateRequest, LiveQrCodeUpdateRequest, LiveQrStyleUpdateRequest
from app.services.app_service import AppService
from app.services.helpers import new_id
from app.services.media_storage_service import MediaStorageService
from app.services.time_utils import SHANGHAI, now_iso, parse_iso


router = APIRouter(tags=["live-qr"])
LIVE_QR_INDEX_FILE = Path(__file__).resolve().parents[1] / "static" / "live-qr" / "index.html"
LIVE_QR_CODE_PATTERN = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-")
LIVE_QR_EXPIRY_FILTERS = {"all", "expired", "1d", "2d", "3d"}
LIVE_QR_DECODE_MAX_BYTES = 10 * 1024 * 1024
LIVE_QR_AVATAR_MAX_BYTES = 5 * 1024 * 1024
LIVE_QR_TARGET_QR_MAX_BYTES = 10 * 1024 * 1024
LIVE_QR_MEMBER_FILTERS = {"all", "warning", "replace", "unknown"}
LIVE_QR_MEMBER_WARNING_THRESHOLD = 180
LIVE_QR_MEMBER_REPLACE_THRESHOLD = 200
LIVE_QR_POSTER_MODES = {"plain", "source"}
LIVE_QR_POSTER_MAX_PIXELS = 30_000_000


def _verify_admin_token(provided_token: str | None) -> None:
    if not settings.admin_token:
        raise HTTPException(status_code=403, detail="WECOM_ADMIN_TOKEN is not configured")
    if provided_token != settings.admin_token:
        raise HTTPException(status_code=403, detail="admin token verification failed")


def _validate_target_url(value: str) -> str:
    target = str(value or "").strip()
    parsed = urlparse(target)
    if len(target) > 2000 or parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise HTTPException(status_code=400, detail="目标链接必须是完整的 http 或 https 地址")
    if parsed.username or parsed.password:
        raise HTTPException(status_code=400, detail="目标链接不能包含账号或密码")
    return target


def _validate_name(value: str) -> str:
    name = str(value or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="活码名称不能为空")
    return name


def _normalize_expiry(value: str, *, now: str) -> str:
    raw = str(value or "").strip()
    try:
        expiry = parse_iso(raw)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="目标二维码有效期必须是有效日期时间") from exc
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=SHANGHAI)
    expiry = expiry.astimezone(SHANGHAI)
    if expiry <= parse_iso(now):
        raise HTTPException(status_code=400, detail="目标二维码有效期必须晚于当前时间")
    return expiry.isoformat()

def _default_expiry(now: str) -> str:
    return (parse_iso(now) + timedelta(days=7)).isoformat()

def _expiry_meta(value: str | None) -> dict:
    if not value:
        return {"targetExpiryState": "unknown", "targetExpiresInDays": None}
    try:
        expiry = parse_iso(value)
        current = parse_iso(now_iso())
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=SHANGHAI)
        if current.tzinfo is None:
            current = current.replace(tzinfo=SHANGHAI)
        remaining_seconds = (expiry - current).total_seconds()
    except (TypeError, ValueError):
        return {"targetExpiryState": "unknown", "targetExpiresInDays": None}
    if remaining_seconds <= 0:
        return {
            "targetExpiryState": "expired",
            "targetExpiresInDays": 0,
            "targetExpiresAtText": expiry.strftime("%Y-%m-%d"),
        }
    days = max(1, math.ceil(remaining_seconds / 86400))
    return {
        "targetExpiryState": "expiring_soon" if days <= 1 else "active",
        "targetExpiresInDays": days,
        "targetExpiresAtText": expiry.strftime("%Y-%m-%d"),
    }


def _expiry_filter_match(item: dict, expiry_filter: str) -> bool:
    if expiry_filter == "all":
        return True
    if expiry_filter == "expired":
        return item.get("targetExpiryState") == "expired"
    return item.get("targetExpiryState") != "expired" and item.get("targetExpiresInDays") == int(expiry_filter[0])


def _expiry_summary(items: list[dict]) -> dict[str, int]:
    summary = {"expired": 0, "1d": 0, "2d": 0, "3d": 0}
    for item in items:
        if item.get("targetExpiryState") == "expired":
            summary["expired"] += 1
            continue
        days = item.get("targetExpiresInDays")
        if days in {1, 2, 3}:
            summary[f"{days}d"] += 1
    return summary


def _member_count_meta(item: dict | LiveQrCode) -> dict:
    count = item.get("groupMemberCount") if isinstance(item, dict) else item.groupMemberCount
    checked_at = item.get("groupMemberCountCheckedAt") if isinstance(item, dict) else item.groupMemberCountCheckedAt
    source = item.get("groupMemberCountSource") if isinstance(item, dict) else item.groupMemberCountSource
    if count is None or source != "wechat_group_info":
        state = "unknown"
    elif count >= LIVE_QR_MEMBER_REPLACE_THRESHOLD:
        state = "replace"
    elif count >= LIVE_QR_MEMBER_WARNING_THRESHOLD:
        state = "warning"
    else:
        state = "normal"
    return {
        "groupMemberCountState": state,
        "groupMemberCountCheckedAt": checked_at,
    }


def _member_filter_match(item: dict, member_filter: str) -> bool:
    if member_filter == "all":
        return True
    return item.get("groupMemberCountState") == member_filter


def _member_count_summary(items: list[dict]) -> dict[str, int]:
    summary = {"normal": 0, "warning": 0, "replace": 0, "unknown": 0}
    for item in items:
        if item.get("status") != "active":
            continue
        state = item.get("groupMemberCountState") or "unknown"
        summary[state] = summary.get(state, 0) + 1
    return summary


def _decode_qr_target_url(content: bytes) -> str:
    decoded_values: list[str] = []
    try:
        import zxingcpp
        from PIL import Image

        with Image.open(BytesIO(content)) as image:
            decoded_values.extend(
                str(barcode.text).strip()
                for barcode in zxingcpp.read_barcodes(image)
                if str(barcode.text).strip()
            )
    except ImportError:
        pass
    except (OSError, ValueError, RuntimeError):
        pass

    try:
        import cv2
        import numpy as np
    except ImportError as exc:
        raise HTTPException(status_code=503, detail="二维码解析组件暂不可用，请手动粘贴链接") from exc

    image = cv2.imdecode(np.frombuffer(content, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise HTTPException(status_code=400, detail="无法读取图片，请上传清晰的二维码图片")

    detector = cv2.QRCodeDetector()
    decoded, _, _ = detector.detectAndDecode(image)
    if decoded:
        decoded_values.append(decoded)
    if not decoded_values and hasattr(detector, "detectAndDecodeMulti"):
        try:
            detected, decoded_info, _, _ = detector.detectAndDecodeMulti(image)
            if detected:
                decoded_values.extend(value for value in decoded_info if value)
        except cv2.error:
            pass
    target = next((str(value).strip() for value in decoded_values if str(value).strip()), "")
    if not target:
        raise HTTPException(status_code=400, detail="没有识别到二维码，请上传包含清晰群二维码的图片")
    try:
        return _validate_target_url(target)
    except HTTPException as exc:
        raise HTTPException(
            status_code=400,
            detail="二维码已识别，但内容不是完整的 http 或 https 链接，请手动粘贴可长期访问的链接",
        ) from exc


def _validate_code(code: str) -> str:
    value = str(code or "").strip()
    if not value or len(value) > 64 or any(char not in LIVE_QR_CODE_PATTERN for char in value):
        raise HTTPException(status_code=404, detail="活码不存在")
    return value


def _public_base_url(request: Request) -> str:
    configured = str(settings.public_base_url or "").strip().rstrip("/")
    return configured or str(request.base_url).rstrip("/")


def _public_url(request: Request, code: str) -> str:
    return f"{_public_base_url(request)}/live-qr/{quote(code, safe='')}"


def _public_asset_url(request: Request, value: str | None) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    parsed = urlparse(raw)
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        return raw
    return f"{_public_base_url(request)}{raw if raw.startswith('/') else '/' + raw}"


def _payload(request: Request, item: LiveQrCode) -> dict:
    code = quote(item.code, safe="")
    poster_mode = item.posterMode if item.posterMode in LIVE_QR_POSTER_MODES else "plain"
    payload = {
        **item.model_dump(mode="json"),
        "publicUrl": _public_url(request, item.code),
        "qrImageUrl": (
            item.posterImageUrl
            if poster_mode == "source" and item.posterImageUrl
            else f"/live-qr/{code}.png?v={item.version}"
        ),
        "targetQrImageUrl": item.targetQrImageUrl,
        "posterMode": poster_mode,
        **_expiry_meta(item.targetExpiresAt),
        **_member_count_meta(item),
    }
    history = []
    for entry in reversed(item.targetQrHistory or []):
        row = dict(entry)
        row.setdefault("updatedAtText", str(row.get("targetUpdatedAt") or row.get("updatedAt") or "")[:10])
        row.setdefault("expiresAtText", str(row.get("targetExpiresAt") or "")[:10])
        history.append(row)
    payload["history"] = history
    payload["reminderConfigured"] = bool(
        settings.wechat_miniapp_live_qr_subscribe_template_id
        and settings.wechat_miniapp_live_qr_subscribe_field_keys()
    )
    return payload


def _new_code(service: AppService) -> str:
    for _ in range(8):
        candidate = f"qr_{secrets.token_urlsafe(8).replace('-', '').replace('_', '').lower()}"
        if not service.repo.get_live_qr_code_by_code(candidate):
            return candidate
    raise HTTPException(status_code=503, detail="暂时无法生成新的活码，请稍后重试")


def _user_live_qr_items(service: AppService, owner_user_id: str) -> list[LiveQrCode]:
    if not service.repo.get_user(owner_user_id):
        raise HTTPException(status_code=404, detail="用户不存在")
    return [item for item in service.repo.list_live_qr_codes() if item.ownerUserId == owner_user_id]


def _user_media_storage(service: AppService) -> MediaStorageService:
    storage = service.media_storage_service
    if storage.storage_mode == "mock":
        return MediaStorageService(
            storage_mode="local",
            storage_dir=settings.media_storage_dir,
            public_url_prefix=settings.media_public_url_prefix,
            public_base_url=settings.public_base_url,
        )
    return storage


def _normalize_poster_mode(value: str | None) -> str:
    mode = str(value or "plain").strip().lower()
    if mode not in LIVE_QR_POSTER_MODES:
        raise HTTPException(status_code=400, detail="投放样式只支持纯二维码或保留原图样式")
    return mode


def _remove_media_ref(service: AppService, url: str | None, ref_type: str, ref_id: str) -> None:
    if not url:
        return
    asset = service.repo.get_media_asset_by_url(url)
    if asset:
        service.repo.delete_media_asset_refs(asset.id, ref_type=ref_type, ref_id=ref_id, usage="current")


def _qr_points(content: bytes):
    try:
        import cv2
        import numpy as np
    except ImportError as exc:
        raise HTTPException(status_code=503, detail="二维码图片处理组件暂不可用，请稍后重试") from exc

    image = cv2.imdecode(np.frombuffer(content, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        return None
    detector = cv2.QRCodeDetector()
    try:
        _, points, _ = detector.detectAndDecode(image)
    except cv2.error:
        points = None
    if points is None and hasattr(detector, "detectAndDecodeMulti"):
        try:
            detected, _, points, _ = detector.detectAndDecodeMulti(image)
            if not detected:
                points = None
        except cv2.error:
            points = None
    if points is None:
        try:
            detected, points = detector.detect(image)
            if not detected:
                points = None
        except cv2.error:
            points = None
    if points is None:
        return None
    values = np.asarray(points, dtype=float)
    if values.ndim >= 3:
        values = values[0]
    values = values.reshape(-1, 2)
    return values if len(values) >= 4 else None


def _build_live_qr_poster(content: bytes, fixed_url: str) -> bytes:
    try:
        from PIL import Image, ImageDraw
    except ImportError as exc:
        raise HTTPException(status_code=503, detail="图片处理组件暂不可用，请稍后重试") from exc

    try:
        source = Image.open(BytesIO(content))
        source.load()
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="无法读取原图，请重新上传清晰的二维码图片") from exc
    if source.width * source.height > LIVE_QR_POSTER_MAX_PIXELS:
        raise HTTPException(status_code=413, detail="原图尺寸过大，请压缩后重新上传")
    points = _qr_points(content)
    if points is None:
        raise HTTPException(status_code=400, detail="无法定位原图中的二维码，请上传二维码清晰且无遮挡的图片")

    poster = source.convert("RGBA")
    left_point = float(points[:, 0].min())
    right_point = float(points[:, 0].max())
    top_point = float(points[:, 1].min())
    bottom_point = float(points[:, 1].max())
    detected_side = max(right_point - left_point, bottom_point - top_point)
    side = min(
        max(int(round(detected_side * 1.16)), int(detected_side) + 16),
        poster.width,
        poster.height,
    )
    center_x = (left_point + right_point) / 2
    center_y = (top_point + bottom_point) / 2
    left = max(0, min(poster.width - side, int(round(center_x - side / 2))))
    top = max(0, min(poster.height - side, int(round(center_y - side / 2))))

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(fixed_url)
    qr.make(fit=True)
    replacement = qr.make_image(fill_color="#20221f", back_color="#ffffff").convert("RGBA")
    replacement = replacement.resize((side, side), Image.Resampling.LANCZOS)
    ImageDraw.Draw(poster).rectangle((left, top, left + side, top + side), fill="#ffffff")
    poster.paste(replacement, (left, top))
    output = BytesIO()
    poster.save(output, format="PNG", optimize=True)
    return output.getvalue()


def _store_live_qr_poster(
    service: AppService,
    content: bytes,
    owner_user_id: str | None,
    resource_id: str,
    fixed_url: str,
) -> str:
    poster_content = _build_live_qr_poster(content, fixed_url)
    return service.process_and_store_media(
        media_id=new_id("live_qr_poster"),
        media_type="image",
        content=poster_content,
        content_type="image/png",
        filename="live-qr-poster.png",
        owner_user_id=owner_user_id,
        ref_type="live_qr_poster",
        ref_id=resource_id,
        usage="current",
        preserve_source_format=True,
        storage_service=_user_media_storage(service) if owner_user_id else None,
    )


async def _store_user_target_qr(
    service: AppService,
    file: UploadFile,
    owner_user_id: str,
    resource_id: str,
) -> tuple[str, str, bytes]:
    if file.content_type and file.content_type not in {"image/png", "image/jpeg", "image/webp"}:
        raise HTTPException(status_code=400, detail="群二维码仅支持 PNG、JPEG 或 WebP 图片")
    content = await read_upload_with_limit(
        file,
        LIVE_QR_TARGET_QR_MAX_BYTES,
        "群二维码图片不能超过10MB",
    )
    target_url = _decode_qr_target_url(content)
    image_url = service.process_and_store_media(
        media_id=new_id("live_qr_target"),
        media_type="image",
        content=content,
        content_type=file.content_type,
        filename=file.filename,
        owner_user_id=owner_user_id,
        ref_type="live_qr_target",
        ref_id=resource_id,
        usage="current",
        preserve_source_format=True,
        storage_service=_user_media_storage(service),
    )
    return target_url, image_url, content


@router.get("/api/live-qr-codes", response_model=ApiResponse[list[dict]])
def list_user_live_qr_codes(
    request: Request,
    ownerUserId: str = Query(...),
    service: AppService = Depends(get_app_service),
):
    return ApiResponse(data=[_payload(request, item) for item in _user_live_qr_items(service, ownerUserId)])


@router.post("/api/live-qr-codes", response_model=ApiResponse[dict])
async def create_user_live_qr_code(
    request: Request,
    ownerUserId: str = Form(...),
    styleMode: str = Form(default="plain"),
    file: UploadFile = File(...),
    service: AppService = Depends(get_app_service),
):
    items = _user_live_qr_items(service, ownerUserId)
    item_id = new_id("live_qr")
    poster_mode = _normalize_poster_mode(styleMode)
    target_url, image_url, content = await _store_user_target_qr(service, file, ownerUserId, item_id)
    now = now_iso()
    code = _new_code(service)
    try:
        service._enforce_content_safety(
            "live_qr",
            item_id,
            {"name": f"微信群活码 {len(items) + 1}", "targetUrl": target_url},
            owner_user_id=ownerUserId,
            content_revision=now,
            for_publish=True,
        )
    except Exception:
        _remove_media_ref(service, image_url, "live_qr_target", item_id)
        raise
    poster_url = None
    if poster_mode == "source":
        try:
            poster_url = _store_live_qr_poster(service, content, ownerUserId, item_id, _public_url(request, code))
        except Exception:
            _remove_media_ref(service, image_url, "live_qr_target", item_id)
            raise
    item = LiveQrCode(
        id=item_id,
        code=code,
        ownerUserId=ownerUserId,
        name=f"微信群活码 {len(items) + 1}",
        targetQrImageUrl=image_url,
        targetQrImageUpdatedAt=now,
        posterMode=poster_mode,
        posterImageUrl=poster_url,
        targetUrl=target_url,
        targetExpiresAt=_default_expiry(now),
        targetUpdatedAt=now,
        createdAt=now,
        updatedAt=now,
    )
    service.repo.save_live_qr_code(item)
    return ApiResponse(message="活码已生成", data=_payload(request, item))


@router.post("/api/live-qr-codes/{qr_id}/target-qr", response_model=ApiResponse[dict])
async def update_user_live_qr_target(
    qr_id: str,
    request: Request,
    ownerUserId: str = Form(...),
    file: UploadFile = File(...),
    service: AppService = Depends(get_app_service),
):
    current = service.repo.get_live_qr_code(qr_id)
    if not current:
        raise HTTPException(status_code=404, detail="活码不存在")
    if current.ownerUserId != ownerUserId:
        raise HTTPException(status_code=403, detail="无权修改该活码")
    target_url, image_url, content = await _store_user_target_qr(service, file, ownerUserId, current.id)
    now = now_iso()
    try:
        service._enforce_content_safety(
            "live_qr",
            current.id,
            {"name": current.name, "targetUrl": target_url},
            owner_user_id=ownerUserId,
            content_revision=now,
            for_publish=True,
        )
    except Exception:
        _remove_media_ref(service, image_url, "live_qr_target", current.id)
        raise
    poster_url = current.posterImageUrl
    if current.posterMode == "source":
        try:
            poster_url = _store_live_qr_poster(service, content, ownerUserId, current.id, _public_url(request, current.code))
        except Exception:
            _remove_media_ref(service, image_url, "live_qr_target", current.id)
            raise
    if current.targetQrImageUrl and current.targetQrImageUrl != image_url:
        _remove_media_ref(service, current.targetQrImageUrl, "live_qr_target", current.id)
    if current.posterImageUrl and current.posterImageUrl != poster_url:
        _remove_media_ref(service, current.posterImageUrl, "live_qr_poster", current.id)
    updated = current.model_copy(update={
        "targetQrImageUrl": image_url,
        "targetQrImageUpdatedAt": now,
        "posterImageUrl": poster_url,
        "targetUrl": target_url,
        "targetExpiresAt": _default_expiry(now),
        "targetUpdatedAt": now,
        "targetQrHistory": [
            *(current.targetQrHistory or []),
            {
                "version": int(current.version or 1),
                "targetUpdatedAt": current.targetUpdatedAt,
                "targetExpiresAt": current.targetExpiresAt,
            },
        ][-20:],
        "version": int(current.version or 1) + 1,
        "updatedAt": now,
    })
    service.repo.save_live_qr_code(updated)
    return ApiResponse(message="二维码已更新，固定入口保持不变", data=_payload(request, updated))


@router.patch("/api/live-qr-codes/{qr_id}/style", response_model=ApiResponse[dict])
def update_user_live_qr_style(
    qr_id: str,
    payload: LiveQrStyleUpdateRequest,
    request: Request,
    service: AppService = Depends(get_app_service),
):
    current = service.repo.get_live_qr_code(qr_id)
    if not current:
        raise HTTPException(status_code=404, detail="活码不存在")
    if current.ownerUserId != payload.ownerUserId:
        raise HTTPException(status_code=403, detail="无权修改该活码")
    mode = _normalize_poster_mode(payload.styleMode)
    poster_url = current.posterImageUrl if mode == "source" else None
    if mode == "source" and not poster_url:
        if not current.targetQrImageUrl:
            raise HTTPException(status_code=400, detail="请先上传微信群二维码")
        content = _user_media_storage(service).read_bytes(current.targetQrImageUrl)
        if not content:
            raise HTTPException(status_code=400, detail="原二维码图片暂无法读取，请重新上传二维码")
        poster_url = _store_live_qr_poster(
            service,
            content,
            payload.ownerUserId,
            current.id,
            _public_url(request, current.code),
        )
    if current.posterImageUrl and current.posterImageUrl != poster_url:
        _remove_media_ref(service, current.posterImageUrl, "live_qr_poster", current.id)
    updated = current.model_copy(update={
        "posterMode": mode,
        "posterImageUrl": poster_url,
        "updatedAt": now_iso(),
    })
    service.repo.save_live_qr_code(updated)
    return ApiResponse(message="投放样式已更新", data=_payload(request, updated))


@router.delete("/api/live-qr-codes/{qr_id}", response_model=ApiResponse[dict])
def delete_user_live_qr_code(
    qr_id: str,
    ownerUserId: str = Query(...),
    service: AppService = Depends(get_app_service),
):
    current = service.repo.get_live_qr_code(qr_id)
    if not current:
        raise HTTPException(status_code=404, detail="活码不存在")
    if current.ownerUserId != ownerUserId:
        raise HTTPException(status_code=403, detail="无权删除该活码")
    if current.targetQrImageUrl:
        _remove_media_ref(service, current.targetQrImageUrl, "live_qr_target", current.id)
    if current.posterImageUrl:
        _remove_media_ref(service, current.posterImageUrl, "live_qr_poster", current.id)
    if not service.repo.delete_live_qr_code(current.id):
        raise HTTPException(status_code=404, detail="活码不存在")
    return ApiResponse(message="活码已删除", data={"id": current.id})


@router.get("/ops/live-qr")
@router.get("/ops/live-qr/")
def live_qr_console_page():
    return FileResponse(
        LIVE_QR_INDEX_FILE,
        headers={"Cache-Control": "no-store, max-age=0"},
    )


@router.post("/api/ops-admin/live-qr-decode", response_model=ApiResponse[dict])
async def decode_live_qr_image(
    file: UploadFile = File(...),
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
):
    _verify_admin_token(x_admin_token)
    content = await read_upload_with_limit(
        file,
        LIVE_QR_DECODE_MAX_BYTES,
        "二维码图片不能超过10MB",
    )
    target_url = _decode_qr_target_url(content)
    return ApiResponse(message="二维码链接已识别", data={"targetUrl": target_url})


@router.post("/api/ops-admin/live-qr-codes/{qr_id}/avatar", response_model=ApiResponse[dict])
async def upload_live_qr_avatar(
    qr_id: str,
    request: Request,
    file: UploadFile = File(...),
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    service: AppService = Depends(get_app_service),
):
    _verify_admin_token(x_admin_token)
    current = service.repo.get_live_qr_code(qr_id)
    if not current:
        raise HTTPException(status_code=404, detail="活码不存在")
    if file.content_type and file.content_type not in {"image/png", "image/jpeg", "image/webp"}:
        raise HTTPException(status_code=400, detail="群头像仅支持 PNG、JPEG 或 WebP 图片")
    content = await read_upload_with_limit(
        file,
        LIVE_QR_AVATAR_MAX_BYTES,
        "群头像图片不能超过5MB",
    )
    avatar_url = service.process_and_store_media(
        media_id=new_id("live_qr_avatar"),
        media_type="image",
        content=content,
        content_type=file.content_type,
        filename=file.filename,
        ref_type="live_qr_avatar",
        ref_id=current.id,
        usage="current",
    )
    if current.groupAvatarUrl and current.groupAvatarUrl != avatar_url:
        previous_asset = service.repo.get_media_asset_by_url(current.groupAvatarUrl)
        if previous_asset:
            service.repo.delete_media_asset_refs(
                previous_asset.id,
                ref_type="live_qr_avatar",
                ref_id=current.id,
                usage="current",
            )
    updated = current.model_copy(update={"groupAvatarUrl": avatar_url, "updatedAt": now_iso()})
    service.repo.save_live_qr_code(updated)
    return ApiResponse(message="真实群头像已更新", data=_payload(request, updated))


@router.post("/api/ops-admin/live-qr-codes/{qr_id}/target-qr", response_model=ApiResponse[dict])
async def upload_live_qr_target_qr(
    qr_id: str,
    request: Request,
    file: UploadFile = File(...),
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    service: AppService = Depends(get_app_service),
):
    """Store the current inner QR and reset its lifetime to seven days.

    Decoding validates the upload and keeps the target URL for diagnostics and
    compatibility. Visitors never follow that URL directly: the stable outer
    code renders this stored image for a second WeChat scan.
    """
    _verify_admin_token(x_admin_token)
    current = service.repo.get_live_qr_code(qr_id)
    if not current:
        raise HTTPException(status_code=404, detail="活码不存在")
    if file.content_type and file.content_type not in {"image/png", "image/jpeg", "image/webp"}:
        raise HTTPException(status_code=400, detail="群二维码仅支持 PNG、JPEG 或 WebP 图片")
    content = await read_upload_with_limit(
        file,
        LIVE_QR_TARGET_QR_MAX_BYTES,
        "群二维码图片不能超过10MB",
    )
    target_url = _decode_qr_target_url(content)
    image_url = service.process_and_store_media(
        media_id=new_id("live_qr_target"),
        media_type="image",
        content=content,
        content_type=file.content_type,
        filename=file.filename,
        ref_type="live_qr_target",
        ref_id=current.id,
        usage="current",
        preserve_source_format=True,
    )
    poster_url = current.posterImageUrl
    if current.posterMode == "source":
        try:
            poster_url = _store_live_qr_poster(
                service,
                content,
                None,
                current.id,
                _public_url(request, current.code),
            )
        except Exception:
            _remove_media_ref(service, image_url, "live_qr_target", current.id)
            raise
    if current.targetQrImageUrl and current.targetQrImageUrl != image_url:
        _remove_media_ref(service, current.targetQrImageUrl, "live_qr_target", current.id)
    if current.posterImageUrl and current.posterImageUrl != poster_url:
        _remove_media_ref(service, current.posterImageUrl, "live_qr_poster", current.id)
    now = now_iso()
    updated = current.model_copy(
        update={
            "targetQrImageUrl": image_url,
            "targetQrImageUpdatedAt": now,
            "posterImageUrl": poster_url,
            "targetUrl": target_url,
            "targetExpiresAt": _default_expiry(now),
            "targetUpdatedAt": now,
            "targetQrHistory": [
                *(current.targetQrHistory or []),
                {
                    "version": int(current.version or 1),
                    "targetUpdatedAt": current.targetUpdatedAt,
                    "targetExpiresAt": current.targetExpiresAt,
                },
            ][-20:],
            "version": int(current.version or 1) + 1,
            "updatedAt": now,
        }
    )
    service.repo.save_live_qr_code(updated)
    return ApiResponse(
        message="群二维码已保存，有效期已自动设置为7天",
        data={**_payload(request, updated), "decodedTargetUrl": target_url},
    )


@router.get("/api/ops-admin/live-qr-codes", response_model=ApiResponse[dict | list[dict]])
def list_live_qr_codes(
    request: Request,
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    page: int | None = Query(default=None, ge=1),
    page_size: int = Query(default=10, ge=1, le=50, alias="pageSize"),
    expiry_filter: str = Query(default="all", alias="expiryFilter"),
    member_filter: str = Query(default="all", alias="memberFilter"),
    service: AppService = Depends(get_app_service),
):
    _verify_admin_token(x_admin_token)
    if expiry_filter not in LIVE_QR_EXPIRY_FILTERS:
        raise HTTPException(status_code=400, detail="目标有效期筛选条件不受支持")
    if member_filter not in LIVE_QR_MEMBER_FILTERS:
        raise HTTPException(status_code=400, detail="群人数筛选条件不受支持")
    all_items = [_payload(request, item) for item in service.repo.list_live_qr_codes()]
    items = [
        item for item in all_items
        if _expiry_filter_match(item, expiry_filter) and _member_filter_match(item, member_filter)
    ]
    if page is None:
        return ApiResponse(data=items)
    total = len(items)
    total_pages = max(1, math.ceil(total / page_size))
    current_page = min(page, total_pages)
    start = (current_page - 1) * page_size
    return ApiResponse(data={
        "items": items[start:start + page_size],
        "page": current_page,
        "pageSize": page_size,
        "total": total,
        "totalPages": total_pages,
        "expiryFilter": expiry_filter,
        "expirySummary": _expiry_summary(all_items),
        "memberFilter": member_filter,
        "memberSummary": _member_count_summary(all_items),
        "serverDate": now_iso()[:10],
    })


@router.post("/api/ops-admin/live-qr-codes", response_model=ApiResponse[dict])
def create_live_qr_code(
    payload: LiveQrCodeCreateRequest,
    request: Request,
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    service: AppService = Depends(get_app_service),
):
    _verify_admin_token(x_admin_token)
    name = _validate_name(payload.name)
    target_url = _validate_target_url(payload.targetUrl)
    now = now_iso()
    target_expires_at = _normalize_expiry(payload.targetExpiresAt, now=now) if payload.targetExpiresAt else _default_expiry(now)
    item = LiveQrCode(
        id=new_id("live_qr"),
        code=_new_code(service),
        name=name,
        description=str(payload.description or "").strip() or None,
        automationGroupCandidateId=payload.automationGroupCandidateId,
        groupMemberCount=payload.groupMemberCount,
        groupMemberCountCheckedAt=now if payload.groupMemberCount is not None else None,
        groupMemberCountSource="manual" if payload.groupMemberCount is not None else None,
        targetUrl=target_url,
        targetExpiresAt=target_expires_at,
        targetUpdatedAt=now,
        createdAt=now,
        updatedAt=now,
    )
    service._enforce_content_safety(
        "live_qr",
        item.id,
        {"name": item.name, "description": item.description, "targetUrl": item.targetUrl},
        owner_user_id=item.ownerUserId,
        content_revision=item.updatedAt,
        for_publish=True,
    )
    service.repo.save_live_qr_code(item)
    return ApiResponse(message="活码已创建", data=_payload(request, item))


@router.patch("/api/ops-admin/live-qr-codes/{qr_id}", response_model=ApiResponse[dict])
def update_live_qr_code(
    qr_id: str,
    payload: LiveQrCodeUpdateRequest,
    request: Request,
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    service: AppService = Depends(get_app_service),
):
    _verify_admin_token(x_admin_token)
    current = service.repo.get_live_qr_code(qr_id)
    if not current:
        raise HTTPException(status_code=404, detail="活码不存在")
    updates: dict = {}
    if payload.name is not None:
        updates["name"] = _validate_name(payload.name)
    target_changed = False
    if payload.targetUrl is not None:
        target_url = _validate_target_url(payload.targetUrl)
        if target_url != current.targetUrl:
            target_changed = True
            updates["targetUrl"] = target_url
            updates["targetUpdatedAt"] = now_iso()
            updates["version"] = int(current.version or 1) + 1
    if payload.targetExpiresAt is not None:
        updates["targetExpiresAt"] = _normalize_expiry(payload.targetExpiresAt, now=now_iso())
    elif target_changed:
        updates["targetExpiresAt"] = _default_expiry(now_iso())
    if payload.description is not None:
        updates["description"] = str(payload.description).strip() or None
    if payload.groupMemberCount is not None:
        updates["groupMemberCount"] = payload.groupMemberCount
        updates["groupMemberCountCheckedAt"] = now_iso()
        updates["groupMemberCountSource"] = "manual"
    if payload.automationGroupCandidateId is not None:
        updates["automationGroupCandidateId"] = payload.automationGroupCandidateId.strip() or None
    if payload.status is not None:
        status = str(payload.status).strip().lower()
        if status not in {"active", "paused"}:
            raise HTTPException(status_code=400, detail="活码状态只支持 active 或 paused")
        updates["status"] = status
    updates["updatedAt"] = now_iso()
    updated = current.model_copy(update=updates)
    service._enforce_content_safety(
        "live_qr",
        updated.id,
        {"name": updated.name, "description": updated.description, "targetUrl": updated.targetUrl},
        owner_user_id=updated.ownerUserId,
        content_revision=updated.updatedAt,
        for_publish=True,
    )
    service.repo.save_live_qr_code(updated)
    return ApiResponse(message="活码已更新", data=_payload(request, updated))


@router.delete("/api/ops-admin/live-qr-codes/{qr_id}", response_model=ApiResponse[dict])
def delete_live_qr_code(
    qr_id: str,
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    service: AppService = Depends(get_app_service),
):
    _verify_admin_token(x_admin_token)
    current = service.repo.get_live_qr_code(qr_id)
    if not current:
        raise HTTPException(status_code=404, detail="活码不存在")
    if current.groupAvatarUrl:
        asset = service.repo.get_media_asset_by_url(current.groupAvatarUrl)
        if asset:
            service.repo.delete_media_asset_refs(
                asset.id,
                ref_type="live_qr_avatar",
                ref_id=current.id,
                usage="current",
            )
    if current.targetQrImageUrl:
        asset = service.repo.get_media_asset_by_url(current.targetQrImageUrl)
        if asset:
            service.repo.delete_media_asset_refs(
                asset.id,
                ref_type="live_qr_target",
                ref_id=current.id,
                usage="current",
            )
    if not service.repo.delete_live_qr_code(current.id):
        raise HTTPException(status_code=404, detail="活码不存在")
    return ApiResponse(message="活码已删除", data={"id": current.id, "code": current.code})


@router.get("/live-qr/{code}.png", include_in_schema=False)
def live_qr_image(code: str, request: Request, service: AppService = Depends(get_app_service)):
    value = _validate_code(code)
    item = service.repo.get_live_qr_code_by_code(value)
    if not item:
        raise HTTPException(status_code=404, detail="活码不存在")
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(_public_url(request, item.code))
    qr.make(fit=True)
    image = qr.make_image(fill_color="#20221f", back_color="#ffffff")
    output = BytesIO()
    image.save(output, format="PNG")
    return Response(
        content=output.getvalue(),
        media_type="image/png",
        headers={
            "Cache-Control": "public, max-age=31536000, immutable",
            "Content-Disposition": f'inline; filename="{item.code}.png"',
        },
    )


@router.get("/live-qr/{code}", include_in_schema=False)
def resolve_live_qr(code: str, request: Request, service: AppService = Depends(get_app_service)):
    value = _validate_code(code)
    current = service.repo.get_live_qr_code_by_code(value)
    if not current:
        return HTMLResponse(
            "<!doctype html><meta charset='utf-8'><title>入口暂不可用</title>"
            "<h1>这个入口暂时不可用</h1><p>请联系发布者获取最新入口。</p>",
            status_code=410,
            headers={"Cache-Control": "no-store, max-age=0"},
        )
    try:
        service._enforce_content_safety(
            "live_qr",
            current.id,
            {"name": current.name, "description": current.description, "targetUrl": current.targetUrl},
            owner_user_id=current.ownerUserId,
            content_revision=current.targetUpdatedAt or current.updatedAt,
            for_publish=True,
            persist=False,
        )
    except HTTPException:
        return HTMLResponse(
            "<!doctype html><meta charset='utf-8'><title>入口暂不可用</title>"
            "<h1>这个入口暂时不可用</h1><p>请联系发布者获取最新入口。</p>",
            status_code=410,
            headers={"Cache-Control": "no-store, max-age=0"},
        )
    message = ""
    if current.status == "paused":
        message = "入口暂时不可用：这个入口已暂停使用"
    elif current.targetExpiresAt:
        try:
            if parse_iso(current.targetExpiresAt) <= parse_iso(now_iso()):
                message = "入口暂时不可用：当前群二维码已过期，请联系发布者更新"
        except (TypeError, ValueError):
            pass
    if message:
        return HTMLResponse(
            f"<!doctype html><meta charset='utf-8'><title>入口暂不可用</title><h1>{message}</h1>",
            status_code=410,
            headers={"Cache-Control": "no-store, max-age=0"},
        )
    item = service.repo.record_live_qr_scan(value, now_iso())
    if not item:
        return HTMLResponse(
            "<!doctype html><meta charset='utf-8'><title>入口暂不可用</title>"
            "<h1>这个入口暂时不可用</h1><p>请联系发布者获取最新入口。</p>",
            status_code=410,
            headers={"Cache-Control": "no-store, max-age=0"},
        )
    target_qr_url = _public_asset_url(request, item.targetQrImageUrl)
    if target_qr_url:
        body = f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">
<meta name="robots" content="noindex,nofollow"><title>二维码</title>
<style>
*{{box-sizing:border-box}} html,body{{margin:0;min-height:100%;background:#fff}}
body{{display:flex;align-items:center;justify-content:center;padding:12px}}
.target-qr{{display:block;width:100%;height:auto;max-width:100vw;max-height:calc(100vh - 24px);object-fit:contain}}
</style></head><body><img class="target-qr" src="{html.escape(target_qr_url, quote=True)}" alt="群二维码"></body></html>"""
    else:
        body = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">
<meta name="robots" content="noindex,nofollow"><title>二维码</title>
<style>
*{box-sizing:border-box} html,body{margin:0;min-height:100%;background:#fff}
body{display:flex;align-items:center;justify-content:center;padding:24px;font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif}
.qr-empty{color:#8b8d85;text-align:center;font-size:16px}
</style></head><body><div class="qr-empty">当前群二维码暂未上传</div></body></html>"""
    return HTMLResponse(
        body,
        status_code=200,
        headers={"Cache-Control": "no-store, max-age=0"},
    )
