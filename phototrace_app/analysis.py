"""PhotoTrace analysis orchestration."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .advanced_analysis import analyze_advanced
from .gps import extract_gps
from .integrity import analyze_integrity
from .metadata import extract_metadata
from .reports import build_report
from .validation import validate_image


def analyze_image(image_path: Path) -> dict[str, Any]:
    """Validate and analyze one local image."""
    validated = validate_image(image_path)
    metadata = extract_metadata(validated.path)
    gps = extract_gps(metadata)
    findings = analyze_integrity(metadata)
    advanced = analyze_advanced(validated.path, metadata)
    return build_report(validated.path, metadata, gps, findings, advanced)
