"""Advanced metadata, timeline, and JPEG structure analysis."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .integrity import Finding
from .jpeg_structure import inspect_jpeg
from .metadata import get_tag
from .timeline import build_metadata_timeline


@dataclass(frozen=True)
class AdvancedFinding:
    """An advanced forensic indicator with explicit technical limitations."""

    severity: str
    title: str
    explanation: str
    evidence: dict[str, Any]
    limitations: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _advanced_finding(
    severity: str,
    title: str,
    explanation: str,
    evidence: dict[str, Any],
    limitations: str,
) -> AdvancedFinding:
    return AdvancedFinding(severity, title, explanation, evidence, limitations)


def analyze_advanced(image_path: Path, metadata: dict[str, Any]) -> dict[str, Any]:
    """Combine JPEG structure, timeline, and metadata consistency indicators."""
    structure = inspect_jpeg(image_path)
    timeline = build_metadata_timeline(metadata)
    findings: list[AdvancedFinding] = []

    if structure.is_jpeg and structure.truncated:
        findings.append(
            _advanced_finding(
                "Warning",
                "JPEG structure is incomplete",
                "The file lacks a complete marker sequence or end-of-image marker.",
                {
                    "complete": structure.complete,
                    "has_end_marker": structure.has_end_marker,
                    "marker_count": structure.marker_count,
                },
                "Truncation can result from interrupted transfer or editing; it does not prove which process occurred.",
            )
        )
    if structure.is_jpeg and not structure.sof_marker:
        findings.append(
            _advanced_finding(
                "Warning",
                "JPEG frame dimensions could not be observed",
                "No supported start-of-frame marker was found.",
                {"markers": structure.markers[:20]},
                "A marker parser limitation or damaged image may explain this observation.",
            )
        )
    repeated_sof_markers = {
        name: count
        for name, count in structure.duplicate_markers.items()
        if name.startswith("SOF")
    }
    if repeated_sof_markers:
        findings.append(
            _advanced_finding(
                "Warning",
                "Multiple JPEG frame markers are present",
                "The parser observed repeated start-of-frame markers.",
                {"duplicate_markers": repeated_sof_markers},
                "Repeated frame markers can indicate malformed concatenated or unusual JPEG data; pixel content was not examined.",
            )
        )
    if structure.trailing_bytes:
        findings.append(
            _advanced_finding(
                "Informational",
                "Bytes follow the JPEG end marker",
                "Data was observed after the EOI marker.",
                {"trailing_bytes": structure.trailing_bytes},
                "Trailing data can include concatenated images or metadata; it does not prove manipulation.",
            )
        )
    if structure.is_jpeg and len(structure.quantization_tables) == 0:
        findings.append(
            _advanced_finding(
                "Informational",
                "No JPEG quantization tables observed",
                "The JPEG parser did not find DQT segments.",
                {"markers": structure.markers[:20]},
                "This can occur in malformed files or unusual JPEG encodings.",
            )
        )

    exif_width = get_tag(metadata, "ExifImageWidth")
    exif_height = get_tag(metadata, "ExifImageHeight")
    file_width = get_tag(metadata, "ImageWidth")
    file_height = get_tag(metadata, "ImageHeight")
    dimension_pairs = [
        ("embedded EXIF", exif_width, exif_height),
        ("main image", file_width or structure.width, file_height or structure.height),
    ]
    for name, width, height in dimension_pairs:
        if width is not None and height is not None and (width <= 0 or height <= 0):
            findings.append(
                _advanced_finding(
                    "Warning",
                    "Invalid image dimensions",
                    f"The {name} dimensions are not positive.",
                    {"width": width, "height": height},
                    "Metadata may be malformed or from a nonstandard encoder.",
                )
            )
    if (
        exif_width is not None and exif_height is not None
        and file_width is not None and file_height is not None
        and (exif_width, exif_height) != (file_width, file_height)
    ):
        findings.append(
            _advanced_finding(
                "Warning",
                "EXIF and image dimensions conflict",
                "Embedded EXIF dimensions do not match the observed file dimensions.",
                {
                    "exif_width": exif_width,
                    "exif_height": exif_height,
                    "file_width": file_width,
                    "file_height": file_height,
                },
                "Dimensions may reflect a thumbnail or stale metadata; this is not proof of manipulation.",
            )
        )

    xmp_software = get_tag(metadata, "XMP:Software") or get_tag(metadata, "XMP:CreatorTool")
    exif_software = get_tag(metadata, "Software")
    if xmp_software and exif_software and str(xmp_software) != str(exif_software):
        findings.append(
            _advanced_finding(
                "Warning",
                "XMP and EXIF software metadata conflict",
                "The XMP creator tool and EXIF Software values identify different applications.",
                {"exif_software": exif_software, "xmp_software": xmp_software},
                "Export workflows and rewritten metadata commonly cause differing values.",
            )
        )
    if structure.exif_present and not structure.thumbnail_present:
        findings.append(
            _advanced_finding(
                "Informational",
                "EXIF metadata lacks a detected embedded thumbnail",
                "An EXIF APP1 segment was found, but no separate JPEG thumbnail signature was detected.",
                {"exif_present": True, "thumbnail_present": False},
                "Simple signature detection may miss thumbnails stored in TIFF offsets or unusual encodings.",
            )
        )

    thumbnail_width = get_tag(metadata, "ThumbnailImageWidth")
    thumbnail_height = get_tag(metadata, "ThumbnailImageHeight")
    if thumbnail_width is not None or thumbnail_height is not None:
        if (
            thumbnail_width is not None
            and thumbnail_height is not None
            and file_width is not None
            and file_height is not None
            and thumbnail_width == file_width
            and thumbnail_height == file_height
        ):
            findings.append(
                _advanced_finding(
                    "Informational",
                    "Embedded thumbnail matches main dimensions",
                    "The embedded thumbnail dimensions exactly match the main image dimensions.",
                    {
                        "thumbnail_width": thumbnail_width,
                        "thumbnail_height": thumbnail_height,
                        "main_width": file_width,
                        "main_height": file_height,
                    },
                    "Thumbnails can legitimately differ from conventions; dimension equality alone is weak evidence.",
                )
            )

    invalid_timeline_events = [
        event for event in timeline["events"]
        if event["status"] == "invalid"
    ]
    if invalid_timeline_events:
        findings.append(
            _advanced_finding(
                "Warning",
                "One or more metadata timestamps are invalid",
                "Timestamp values could not be normalized for timeline construction.",
                {"invalid_events": invalid_timeline_events},
                "Invalid values may reflect vendor-specific formats or damaged metadata.",
            )
        )
    if timeline["timezone_ambiguous"]:
        findings.append(
            _advanced_finding(
                "Warning",
                "Timeline timezone context is mixed or incomplete",
                "Some timestamp values include timezone information while others do not.",
                {"events": timeline["events"]},
                "Mixing timezone-aware and timezone-naive values can make chronological interpretation unreliable.",
            )
        )
    if timeline["duplicate_timestamp_fields"]:
        findings.append(
            _advanced_finding(
                "Informational",
                "Duplicate timestamps occur across metadata fields",
                "The same normalized timestamp is present in multiple metadata fields.",
                {"duplicates": timeline["duplicate_timestamp_fields"]},
                "Duplicate values can be legitimate metadata propagation and do not indicate manipulation.",
            )
        )
    if timeline["chronological_conflicts"]:
        findings.append(
            _advanced_finding(
                "Warning",
                "Metadata timestamps conflict",
                "Available capture, creation, and modification timestamps have contradictory ordering.",
                {"conflicts": timeline["chronological_conflicts"]},
                "Clock settings, timezone conversion, copy/export workflows, and metadata rewriting can explain conflicts.",
            )
        )
    missing_timeline_fields = timeline["missing_timestamp_fields"]
    if missing_timeline_fields:
        findings.append(
            _advanced_finding(
                "Informational",
                "Metadata timeline has missing timestamp fields",
                "One or more commonly available timestamp fields were not present.",
                {"missing_fields": missing_timeline_fields},
                "Missing timestamps are not evidence of manipulation.",
            )
        )

    return {
        "timeline": timeline,
        "image_structure": structure.to_dict(),
        "findings": [finding.to_dict() for finding in findings],
        "method_limitations": [
            "Marker parsing is structural and does not decode or authenticate pixels.",
            "Missing metadata is not evidence of manipulation.",
            "Quantization-table observations are contextual, not proof of editing.",
            "Thumbnail detection uses signatures and metadata indicators, not pixel comparison.",
        ],
    }
