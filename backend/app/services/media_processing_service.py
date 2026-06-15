from __future__ import annotations

from io import BytesIO
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from PIL import Image


@dataclass(slots=True)
class ProcessedMedia:
    content: bytes
    content_type: str | None
    filename: str | None
    original_size: int
    stored_size: int
    compressed: bool


class MediaProcessingService:
    def __init__(
        self,
        image_max_edge: int = 1600,
        image_quality: int = 82,
        video_max_width: int = 1280,
        video_crf: int = 28,
        ffmpeg_bin: str = "ffmpeg",
    ):
        self.image_max_edge = image_max_edge
        self.image_quality = image_quality
        self.video_max_width = video_max_width
        self.video_crf = video_crf
        self.ffmpeg_bin = ffmpeg_bin

    def process_upload(
        self,
        media_type: str,
        content: bytes,
        content_type: str | None = None,
        filename: str | None = None,
    ) -> ProcessedMedia:
        if media_type == "image":
            return self.process_image(content, filename)
        if media_type == "video":
            return self.process_video(content, filename)
        return ProcessedMedia(content, content_type, filename, len(content), len(content), False)

    def process_image(self, content: bytes, filename: str | None = None) -> ProcessedMedia:
        try:
            image = Image.open(BytesIO(content))
            image.load()
            image.thumbnail((self.image_max_edge, self.image_max_edge))
            if image.mode not in {"RGB", "RGBA"}:
                image = image.convert("RGBA" if "A" in image.getbands() else "RGB")
            output = BytesIO()
            image.save(output, format="WEBP", quality=self.image_quality, method=6)
            processed = output.getvalue()
            if not processed:
                raise ValueError("image processing produced empty output")
            return ProcessedMedia(
                content=processed,
                content_type="image/webp",
                filename=_replace_extension(filename, "webp"),
                original_size=len(content),
                stored_size=len(processed),
                compressed=len(processed) < len(content) or filename != _replace_extension(filename, "webp"),
            )
        except Exception:
            return ProcessedMedia(content, "image/webp", filename, len(content), len(content), False)

    def process_video(self, content: bytes, filename: str | None = None) -> ProcessedMedia:
        input_suffix = _suffix_from_filename(filename) or ".mp4"
        with tempfile.NamedTemporaryFile(suffix=input_suffix, delete=False) as input_file:
            input_file.write(content)
            input_path = Path(input_file.name)
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as output_file:
            output_path = Path(output_file.name)
        try:
            command = [
                self.ffmpeg_bin,
                "-y",
                "-i",
                str(input_path),
                "-vf",
                f"scale='min({self.video_max_width},iw)':-2",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                str(self.video_crf),
                "-c:a",
                "aac",
                "-b:a",
                "96k",
                "-movflags",
                "+faststart",
                str(output_path),
            ]
            subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
            processed = output_path.read_bytes()
            if not processed:
                raise ValueError("ffmpeg produced empty output")
            return ProcessedMedia(
                content=processed,
                content_type="video/mp4",
                filename=_replace_extension(filename, "mp4"),
                original_size=len(content),
                stored_size=len(processed),
                compressed=len(processed) < len(content) or filename != _replace_extension(filename, "mp4"),
            )
        except Exception:
            return ProcessedMedia(content, "video/mp4", filename, len(content), len(content), False)
        finally:
            input_path.unlink(missing_ok=True)
            output_path.unlink(missing_ok=True)
def _replace_extension(filename: str | None, extension: str) -> str:
    stem = Path(filename or "upload").stem or "upload"
    return f"{stem}.{extension}"


def _suffix_from_filename(filename: str | None) -> str:
    suffix = Path(filename or "").suffix.lower()
    return suffix if suffix else ""
