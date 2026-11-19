"""ExifTool-backed metadata extraction."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any


class MetadataExtractionError(RuntimeError):
    """Raised when ExifTool cannot produce a metadata result."""


def _exiftool_path() -> str:
    executable = shutil.which("exiftool")
    if not executable:
        raise MetadataExtractionError(
            "ExifTool is not installed or is not available on PATH."
        )
    return executable


def extract_metadata(image_path: Path) -> dict[str, Any]:
    """Extract all available metadata from an image using ExifTool."""
    command = [
        _exiftool_path(),
        "-json",
        "-n",
        "-G1",
        "-a",
        "-u",
        "-ee",
        str(image_path),
    ]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as error:
        raise MetadataExtractionError(
            f"Could not execute ExifTool: {error}"
        ) from error
    if result.returncode != 0:
        message = result.stderr.strip() or "ExifTool returned an error."
        raise MetadataExtractionError(message)
    if not result.stdout.strip():
        raise MetadataExtractionError("ExifTool returned no metadata.")
    try:
        records = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise MetadataExtractionError(
            "ExifTool returned invalid JSON."
        ) from error
    if not isinstance(records, list) or not records or not isinstance(records[0], dict):
        raise MetadataExtractionError("ExifTool returned an unexpected result.")
    metadata = records[0]
    if not any(key.endswith(":FileType") or key == "FileType" for key in metadata):
        raise MetadataExtractionError(
            "ExifTool could not identify the file as a supported image."
        )
    file_type = get_tag(metadata, "FileType")
    mime_type = get_tag(metadata, "MIMEType")
    if (
        isinstance(file_type, str)
        and file_type.upper() in {"TXT", "UNKNOWN", "FILE"}
    ) or (isinstance(mime_type, str) and not mime_type.startswith("image/")):
        raise MetadataExtractionError(
            "ExifTool identified the file as a non-image or unsupported format."
        )
    if len(records) > 1:
        metadata["_ExifToolAdditionalRecords"] = records[1:]
    return metadata


def get_tag(metadata: dict[str, Any], *names: str) -> Any:
    """Get a tag from grouped or ungrouped ExifTool output."""
    for name in names:
        if name in metadata:
            return metadata[name]
        suffix = f":{name}"
        for key, value in metadata.items():
            if key.endswith(suffix):
                return value
    return None
