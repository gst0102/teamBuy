from __future__ import annotations

from io import BytesIO

from PIL import Image

from app.services.media_storage_service import MediaStorageService
from app.services.share_card_renderer import (
    NOTE_SHARE_CARD_STYLE_ID,
    NOTE_SHARE_CARD_RENDER_REVISION,
    UNIVERSAL_INFO_ARTWORK_PATH,
    ShareCardRenderer,
)


def _image_bytes(size=(320, 240), color=(70, 150, 220)) -> bytes:
    output = BytesIO()
    Image.new("RGB", size, color).save(output, format="PNG")
    return output.getvalue()


def _assert_share_card_size(content: bytes) -> None:
    with Image.open(BytesIO(content)) as image:
        assert image.format == "JPEG"
        assert image.size == (750, 600)


def test_renderer_builds_business_card_without_fetching_external_avatar(tmp_path):
    storage = MediaStorageService(storage_mode="local", storage_dir=tmp_path, public_url_prefix="/media")
    renderer = ShareCardRenderer()

    content = renderer.render_note(
        {
            "title": "Leo 的电子名片",
            "summary": "服装制造与供应链合作",
            "visibilityConfig": {
                "cardType": "business_card",
                "structuredData": {"name": "Leo", "role": "制造", "company": "服装工厂"},
            },
        },
        owner={"nickname": "Leo"},
        storage_service=storage,
    )

    _assert_share_card_size(content)


def test_business_card_contact_line_respects_market_privacy_boundary():
    renderer = ShareCardRenderer()
    structured = {"phone": "13800000000", "wechat": "leo_work"}
    owner = {"phone": "13900000000", "salesProfile": {"email": "leo@example.com"}}

    assert renderer._business_contact_line(structured, owner, {}) == "电话 13800000000 · 微信 leo_work"
    assert renderer._business_contact_line(
        structured,
        owner,
        {"businessOpportunity": {"enabled": True, "discoverable": True}},
    ) == "电话 138****0000 · 详情页查看"
    assert renderer._business_contact_line(
        structured,
        owner,
        {"businessOpportunity": {"enabled": True, "discoverable": True}},
        allow_full_contacts=True,
    ) == "电话 13800000000 · 微信 leo_work"


def test_renderer_builds_image_note_from_managed_media(tmp_path):
    storage = MediaStorageService(storage_mode="local", storage_dir=tmp_path, public_url_prefix="/media")
    image_url = storage.store_bytes("source", "image", _image_bytes(), "image/png")
    renderer = ShareCardRenderer()

    content = renderer.render_note(
        {
            "title": "图片资料",
            "summary": "点击查看完整资料",
            "visibilityConfig": {"cardType": "image_ocr", "structuredData": {}},
            "contentBlocks": [{"type": "image", "url": image_url}],
        },
        storage_service=storage,
    )

    _assert_share_card_size(content)


def test_renderer_uses_approved_universal_artwork_for_no_image_cards():
    renderer = ShareCardRenderer()

    assert UNIVERSAL_INFO_ARTWORK_PATH.is_file()
    artwork = renderer._load_universal_info_artwork()
    assert artwork.mode == "RGBA"
    assert artwork.width > 0 and artwork.height > 0


def test_renderer_builds_all_mutual_help_task_variants(tmp_path):
    storage = MediaStorageService(storage_mode="local", storage_dir=tmp_path, public_url_prefix="/media")
    renderer = ShareCardRenderer()

    for task_kind in ("miniapp", "ordinary", "wool"):
        content = renderer.render_mutual_task(
            {
                "taskKind": task_kind,
                "title": f"{task_kind}任务",
                "description": "按任务说明完成并提交记录",
                "executorReward": 4,
                "woolPolicy": {"unlockFeePoints": 2},
                "contentBlocks": [],
            },
            storage_service=storage,
        )
        _assert_share_card_size(content)


def test_mutual_task_share_ignores_unmanaged_content_image(tmp_path):
    storage = MediaStorageService(storage_mode="local", storage_dir=tmp_path, public_url_prefix="/media")
    renderer = ShareCardRenderer()

    content = renderer.render_mutual_task(
        {
            "taskKind": "ordinary",
            "title": "关注公众号即可",
            "description": "关注公众号截图即可",
            "executorReward": 4,
            "contentBlocks": [
                {"type": "image", "url": "https://mp.weixin.qq.com/s/example-image"},
            ],
            "acceptanceCriteriaBlocks": [],
        },
        storage_service=storage,
    )

    # An external/expired content image must not make the server snapshot
    # fail; the card falls back to its deliberate no-image visual.
    _assert_share_card_size(content)


def test_mutual_task_share_ignores_temporary_wxfile_acceptance_image(tmp_path):
    storage = MediaStorageService(storage_mode="local", storage_dir=tmp_path, public_url_prefix="/media")
    renderer = ShareCardRenderer()

    content = renderer.render_mutual_task(
        {
            "taskKind": "ordinary",
            "title": "关注公众号即可",
            "description": "关注公众号截图即可",
            "executorReward": 4,
            "contentBlocks": [],
            "acceptanceCriteriaBlocks": [
                {"type": "image", "url": "wxfile://tmp_pJNple.jpg"},
            ],
        },
        storage_service=storage,
    )

    # wxfile:// is a client-side temporary path, not a server-owned media
    # asset. It must fall back to the deliberate no-image task visual.
    _assert_share_card_size(content)


def test_mutual_task_share_ignores_missing_managed_content_image(tmp_path):
    storage = MediaStorageService(storage_mode="local", storage_dir=tmp_path, public_url_prefix="/media")
    renderer = ShareCardRenderer()

    content = renderer.render_mutual_task(
        {
            "taskKind": "ordinary",
            "title": "旧截图任务",
            "description": "按任务说明完成后提交",
            "executorReward": 4,
            "contentBlocks": [{"type": "image", "url": "/media/missing-task-image.jpg"}],
        },
        storage_service=storage,
    )

    _assert_share_card_size(content)


def test_renderer_uses_v8_layout_and_formats_typed_prices(tmp_path):
    storage = MediaStorageService(storage_mode="local", storage_dir=tmp_path, public_url_prefix="/media")
    renderer = ShareCardRenderer()

    assert NOTE_SHARE_CARD_STYLE_ID == "share_card_backend_v8"
    assert NOTE_SHARE_CARD_RENDER_REVISION == "business_card_layout_v4"
    assert renderer._note_price("property_listing", {"price": "1210", "listingMode": "rent"}) == "1210元/月"
    assert renderer._note_price(
        "product",
        {"variants": [{"name": "标准款", "priceFen": 12900, "stockStatus": "available"}]},
    ) == "¥129"

    content = renderer.render_note(
        {
            "title": "无图电商资料",
            "summary": "商品信息一页讲清",
            "visibilityConfig": {
                "cardType": "product",
                "structuredData": {
                    "variants": [{"name": "标准款", "priceFen": 12900, "stockStatus": "available"}],
                },
            },
            "contentBlocks": [],
        },
        storage_service=storage,
    )

    _assert_share_card_size(content)


def test_business_card_providing_text_is_limited_to_20_chars_with_ascii_ellipsis():
    renderer = ShareCardRenderer()

    clipped = renderer._clip("小微打工，企业资料整理、供应链对接、商务合作支持", 20, suffix="...")

    assert clipped == "小微打工，企业资料整理、供应链对接..."
    assert len(clipped) == 20
