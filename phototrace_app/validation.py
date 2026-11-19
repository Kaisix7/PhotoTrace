"""Input-file validation for PhotoTrace."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

SUPPORTED_EXTENSIONS = {
    ".avif",
    ".bmp",
    ".cr2",
    ".cr3",
    ".dng",
    ".gif",
    ".heic",
    ".heif",
    ".jpeg",
    ".jpg",
    ".nef",
    ".orf",
    ".png",
    ".raf",
    ".raw",
    ".tif",
    ".tiff",
    ".webp",
}
RASTER_EXTENSIONS = {
    ".avif",
    ".bmp",
    ".gif",
    ".heic",
    ".heif",
    ".jpeg",
    ".jpg",
    ".png",
    ".tif",
    ".tiff",
    ".webp",
}
DEFAULT_MAX_FILE_SIZE = 50 * 1024 * 1024


class ValidationError(ValueError):
    """Raised when an input image does not meet validation requirements."""


@dataclass(frozen=True)
class ValidatedFile:
    """A validated local image path and its basic file facts."""

    path: Path
    size_bytes: int


def validate_image(
    image_path: Path,
    max_size_bytes: int = DEFAULT_MAX_FILE_SIZE,
) -> ValidatedFile:
    """Validate path, size, and a known image extension."""
    path = image_path.expanduser().resolve()
    if not path.is_file():
        raise ValidationError(f"Image file not found: {path}")
    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise ValidationError(
            f"Unsupported image format: {path.suffix or 'no extension'}."
        )
    size = path.stat().st_size
    if size == 0:
        raise ValidationError("The image file is empty.")
    if size > max_size_bytes:
        limit_mb = max_size_bytes / (1024 * 1024)
        raise ValidationError(f"The image exceeds the {limit_mb:g} MB size limit.")
    if path.suffix.lower() in RASTER_EXTENSIONS:
        try:
            from PIL import Image, UnidentifiedImageError

            with Image.open(path) as image:
                image.verify()
        except (ImportError, UnidentifiedImageError, OSError, SyntaxError) as error:
            raise ValidationError(
                f"The file is not a readable {path.suffix.lower()} image."
            ) from error
    return ValidatedFile(path=path, size_bytes=size)
