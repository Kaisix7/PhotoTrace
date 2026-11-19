"""Structured forensic report creation and persistence."""

from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .gps import GPSInfo
from .integrity import Finding
from .metadata import get_tag


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_safe(value: Any) -> Any:
    """Keep unusual metadata values JSON-compatible without dropping them."""
    if isinstance(value, float) and not math.isfinite(value):
        return repr(value)
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _sanitize_metadata_paths(metadata: dict[str, Any]) -> dict[str, Any]:
    """Redact absolute local directories while retaining extracted field names."""
    sanitized: dict[str, Any] = {}
    for key, value in metadata.items():
        lowered = key.lower()
        if (
            "directory" in lowered
            or "sourcefile" in lowered
            or lowered in {"filepath", "path"}
        ):
            if isinstance(value, str) and ("/" in value or "\\" in value):
                sanitized[key] = value.replace("\\", "/").rsplit("/", 1)[-1] or "[directory redacted]"
            else:
                sanitized[key] = value
        else:
            sanitized[key] = _sanitize_unrecognized_string(value)
    return sanitized


def _sanitize_unrecognized_string(value: Any) -> Any:
    """Redact absolute Unix and Windows paths in nested metadata values."""
    if isinstance(value, str):
        if re.match(r"^(?:[A-Za-z]:[\\/]|\\\\|/)", value):
            return "[absolute path redacted]"
        if isinstance(value, str):
            return value
    if isinstance(value, dict):
        return {
            str(key): _sanitize_unrecognized_string(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_sanitize_unrecognized_string(item) for item in value]
    return value


def get_report_download(report: dict[str, Any]) -> tuple[str, str]:
    """Return a safe descriptive filename and exact JSON download payload."""
    original = str(report.get("original_filename", "image"))
    stem = Path(original).stem or "image"
    safe_stem = re.sub(r"[^A-Za-z0-9._-]+", "_", stem).strip("._") or "image"
    filename = f"{safe_stem}_report.json"
    payload = json.dumps(
        _json_safe(_sanitize_metadata_paths(report)),
        indent=2,
        ensure_ascii=False,
        sort_keys=False,
        allow_nan=False,
    )
    return filename, payload


def build_report(
    image_path: Path,
    metadata: dict[str, Any],
    gps: GPSInfo,
    findings: list[Finding],
    advanced: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a reproducible report while retaining every extracted tag."""
    severity_counts = {
        severity: sum(item.severity == severity for item in findings)
        for severity in ("Informational", "Warning", "Suspicious")
    }
    report = {
        "tool": "PhotoTrace",
        "version": "2.0.0",
        "analysis_timestamp": datetime.now(timezone.utc).isoformat(),
        "original_filename": image_path.name,
        "file": {
            "path": image_path.name,
            "size_bytes": image_path.stat().st_size,
            "sha256": _sha256(image_path),
            "format": get_tag(metadata, "FileType"),
            "mime_type": get_tag(metadata, "MIMEType"),
            "width": get_tag(metadata, "ImageWidth"),
            "height": get_tag(metadata, "ImageHeight"),
        },
        "metadata": _json_safe(_sanitize_metadata_paths(metadata)),
        "gps": gps.to_dict(),
        "integrity_findings": [item.to_dict() for item in findings],
        "advanced_analysis": _json_safe(
            advanced
            or {
                "timeline": {"events": [], "timezone_ambiguous": False},
                "image_structure": {},
                "findings": [],
                "method_limitations": [],
            }
        ),
        "summary": {
            "metadata_field_count": len(metadata),
            "finding_counts": severity_counts,
            "statement": "Findings are indicators for review and do not establish image manipulation.",
        },
    }
    return _json_safe(_sanitize_metadata_paths(report))


def save_report(report: dict[str, Any], reports_dir: Path) -> Path:
    """Save a report without overwriting an existing report."""
    reports_dir.mkdir(parents=True, exist_ok=True)
    stem = Path(str(report["original_filename"])).name
    base = Path(stem).stem or "image"
    counter = 0
    while True:
        suffix = "" if counter == 0 else f"_{counter}"
        report_path = reports_dir / f"{base}_report{suffix}.json"
        try:
            with report_path.open("x", encoding="utf-8") as file:
                json.dump(
                    _json_safe(_sanitize_metadata_paths(report)),
                    file,
                    indent=2,
                    ensure_ascii=False,
                    sort_keys=False,
                    allow_nan=False,
                )
                file.write("\n")
            return report_path
        except FileExistsError:
            counter += 1
