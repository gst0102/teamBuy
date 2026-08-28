from __future__ import annotations

from io import BytesIO

from PIL import Image

from app.services.media_processing_service import MediaProcessingService


def make_image_bytes(size=(2400, 1600), color=(40, 120, 220)) -> bytes:
    image = Image.new("RGB", size, color)
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def test_image_upload_is_resized_and_converted_to_webp():
    service = MediaProcessingService(image_max_edge=800, image_quality=80)
    original = make_image_bytes()

    processed = service.process_upload("image", original, "image/png", "cover.png")

    assert processed.content_type == "image/webp"
    assert processed.filename == "cover.webp"
    assert processed.original_size == len(original)
    assert processed.stored_size == len(processed.content)
    assert processed.compressed is True

    with Image.open(BytesIO(processed.content)) as image:
        assert max(image.size) <= 800


def test_invalid_image_upload_falls_back_without_blocking():
    service = MediaProcessingService()

    processed = service.process_upload("image", b"not-an-image", "image/png", "broken.png")

    assert processed.content == b"not-an-image"
    assert processed.content_type == "image/webp"
    assert processed.compressed is False


def test_share_image_is_always_exported_as_jpeg():
    service = MediaProcessingService(image_max_edge=800, image_quality=80)
    original = make_image_bytes(size=(1200, 900))

    processed = service.process_share_image(original, "share-card.png")

    assert processed.content_type == "image/jpeg"
    assert processed.filename == "share-card.jpg"
    assert processed.original_size == len(original)
    assert processed.stored_size == len(processed.content)

    with Image.open(BytesIO(processed.content)) as image:
        assert image.format == "JPEG"
        assert image.size == (800, 600)


def test_invalid_share_image_is_rejected():
    service = MediaProcessingService()

    try:
        service.process_share_image(b"not-an-image", "broken.webp")
    except ValueError as exc:
        assert str(exc) == "分享图必须是有效的图片"
    else:
        raise AssertionError("invalid share image should be rejected")
