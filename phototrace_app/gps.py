"""GPS extraction, conversion, and validation."""

from __future__ import annotations

import re
import math
from dataclasses import asdict, dataclass
from typing import Any

from .metadata import get_tag


class GPSExtractionError(ValueError):
    """Raised when GPS values are present but cannot be validated."""


@dataclass(frozen=True)
class GPSInfo:
    """Validated GPS state for an analyzed image."""

    status: str
    latitude: float | None = None
    longitude: float | None = None
    altitude: float | None = None
    maps_url: str | None = None
    message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def convert_coordinate(value: Any, reference: str | None = None) -> float:
    """Convert decimal or degree-minute-second input to decimal degrees."""
    if isinstance(value, (int, float)):
        decimal = float(value)
    elif isinstance(value, (list, tuple)) and len(value) == 3:
        degrees, minutes, seconds = (float(item) for item in value)
        if not 0 <= minutes < 60 or not 0 <= seconds < 60:
            raise GPSExtractionError(f"Invalid DMS coordinate value: {value!r}")
        decimal = degrees + minutes / 60 + seconds / 3600
    else:
        text = str(value).strip()
        try:
            decimal = float(text)
        except ValueError:
            numbers = [
                float(item)
                for item in re.findall(r"-?\d+(?:\.\d+)?", text)
            ]
            if len(numbers) != 3:
                raise GPSExtractionError(f"Invalid coordinate value: {value!r}")
            if not 0 <= numbers[1] < 60 or not 0 <= numbers[2] < 60:
                raise GPSExtractionError(f"Invalid DMS coordinate value: {value!r}")
            decimal = numbers[0] + numbers[1] / 60 + numbers[2] / 3600
            if "-" in text.split()[0]:
                decimal = -abs(decimal)
    direction = (reference or "").strip().upper()
    if direction in {"S", "W"}:
        decimal = -abs(decimal)
    elif direction in {"N", "E"}:
        decimal = abs(decimal)
    elif reference is not None and direction:
        raise GPSExtractionError(f"Invalid coordinate reference: {reference!r}")
    if not math.isfinite(decimal) or not -180 <= decimal <= 180:
        raise GPSExtractionError(f"Coordinate is outside valid bounds: {value!r}")
    return decimal


def extract_gps(metadata: dict[str, Any]) -> GPSInfo:
    """Return missing, invalid, or valid GPS state without inventing coordinates."""
    latitude_value = get_tag(metadata, "GPSLatitude")
    longitude_value = get_tag(metadata, "GPSLongitude")
    if latitude_value is None and longitude_value is None:
        return GPSInfo(status="missing", message="No GPS coordinates were found.")
    if latitude_value is None or longitude_value is None:
        return GPSInfo(
            status="invalid",
            message="GPS metadata is incomplete; both coordinates are required.",
        )
    try:
        latitude = convert_coordinate(
            latitude_value, get_tag(metadata, "GPSLatitudeRef")
        )
        longitude = convert_coordinate(
            longitude_value, get_tag(metadata, "GPSLongitudeRef")
        )
        if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
            raise GPSExtractionError("GPS coordinates are outside valid bounds.")
    except (GPSExtractionError, TypeError, ValueError) as error:
        return GPSInfo(status="invalid", message=str(error))
    altitude = get_tag(metadata, "GPSAltitude")
    return GPSInfo(
        status="valid",
        latitude=latitude,
        longitude=longitude,
        altitude=float(altitude) if isinstance(altitude, (int, float)) else None,
        maps_url=f"https://www.google.com/maps?q={latitude},{longitude}",
    )
