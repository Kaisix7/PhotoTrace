"""Metadata timeline construction and timezone-safe comparison."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

from .metadata import get_tag


@dataclass(frozen=True)
class TimelineEvent:
    """One normalized metadata event."""

    source: str
    field: str
    raw_value: Any
    parsed_value: str | None
    timezone_present: bool
    status: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def parse_metadata_date(value: Any) -> tuple[datetime | None, bool]:
    """Parse an EXIF or ISO date while preserving timezone presence."""
    if isinstance(value, (list, tuple)) and len(value) >= 3:
        return None, False
    if not isinstance(value, str):
        return None, False
    text = value.strip()
    if len(text) >= 19 and text[4] == ":" and text[7] == ":":
        text = f"{text[:4]}-{text[5:7]}-{text[8:]}"
    try:
        parsed = datetime.fromisoformat(text)
        return parsed, parsed.tzinfo is not None
    except ValueError:
        return None, False


def build_metadata_timeline(metadata: dict[str, Any]) -> dict[str, Any]:
    """Build a structured timeline from available metadata timestamps."""
    fields = (
        ("DateTimeOriginal", "Capture"),
        ("CreateDate", "Creation"),
        ("ModifyDate", "Modification"),
        ("GPSDateStamp", "GPS date"),
        ("GPSTimeStamp", "GPS time"),
        ("FileModifyDate", "File modification"),
        ("DateTime", "General timestamp"),
        ("XMP:CreateDate", "XMP creation"),
        ("XMP:ModifyDate", "XMP modification"),
        ("XMP:MetadataDate", "XMP metadata"),
        ("XMP:DateCreated", "XMP capture"),
    )
    events: list[TimelineEvent] = []
    gps_date = get_tag(metadata, "GPSDateStamp")
    gps_time = get_tag(metadata, "GPSTimeStamp")
    gps_time_string: str | None = None
    if isinstance(gps_time, (list, tuple)) and len(gps_time) >= 3:
        try:
            def gps_component(value: Any, *, seconds: bool = False) -> str:
                number = float(value)
                if number.is_integer():
                    return f"{int(number):02d}"
                if seconds:
                    return f"{number:.6f}".rstrip("0").rstrip(".")
                return f"{number:g}"

            gps_time_string = (
                f"{gps_component(gps_time[0])}:"
                f"{gps_component(gps_time[1])}:"
                f"{gps_component(gps_time[2], seconds=True)}"
            )
        except (TypeError, ValueError, OverflowError):
            gps_time_string = None
    elif isinstance(gps_time, str):
        gps_time_string = gps_time

    if gps_date is not None and gps_time_string is not None:
        gps_date_text = str(gps_date).strip()
        if len(gps_date_text) >= 10 and gps_date_text[4] == ":":
            gps_date_text = (
                f"{gps_date_text[:4]}-{gps_date_text[5:7]}-{gps_date_text[8:10]}"
            )
        combined = f"{gps_date_text} {gps_time_string}"
        parsed, timezone_present = parse_metadata_date(combined)
        events.append(
            TimelineEvent(
                source="GPS",
                field="GPSDateTime",
                raw_value={"GPSDateStamp": gps_date, "GPSTimeStamp": gps_time},
                parsed_value=parsed.isoformat() if parsed else None,
                timezone_present=timezone_present,
                status="parsed" if parsed else "invalid",
            )
        )

    for field, source in fields:
        if field in ("GPSDateStamp", "GPSTimeStamp"):
            continue
        value = get_tag(metadata, field)
        if value is None:
            continue
        parsed, timezone_present = parse_metadata_date(value)
        events.append(
            TimelineEvent(
                source=source,
                field=field,
                raw_value=value,
                parsed_value=parsed.isoformat() if parsed else None,
                timezone_present=timezone_present,
                status="parsed" if parsed else "invalid",
            )
        )

    software = get_tag(metadata, "Software")
    if software is not None:
        events.append(
            TimelineEvent(
                source="Software",
                field="Software",
                raw_value=software,
                parsed_value=None,
                timezone_present=False,
                status="metadata indicator",
            )
        )

    aware = [event for event in events if event.timezone_present]
    naive = [
        event for event in events
        if event.status == "parsed" and not event.timezone_present
    ]
    parsed_events = [
        event for event in events
        if event.status == "parsed" and event.parsed_value is not None
    ]
    invalid_events = [
        event for event in events
        if event.status == "invalid"
    ]
    other_events = [
        event for event in events
        if event.status not in ("parsed", "invalid")
    ]
    if parsed_events and not (aware and naive):
        dated_events = sorted(
            parsed_events,
            key=lambda event: datetime.fromisoformat(event.parsed_value or ""),
        )
    else:
        dated_events = parsed_events
    chronological = dated_events + invalid_events + other_events

    return {
        "events": [event.to_dict() for event in chronological],
        "timezone_ambiguous": bool(aware and naive),
        "gps_timestamp_available": gps_date is not None or gps_time is not None,
        "software_available": software is not None,
        "missing_timestamp_fields": [
            field
            for field, _source in fields
            if get_tag(metadata, field) is None
        ],
        "chronological_conflicts": _find_chronological_conflicts(parsed_events),
        "duplicate_timestamp_fields": _find_duplicate_timestamp_fields(parsed_events),
    }


def _find_duplicate_timestamp_fields(events: list[TimelineEvent]) -> list[dict[str, Any]]:
    """Report timestamp values repeated across multiple metadata fields."""
    groups: dict[str, list[str]] = {}
    for event in events:
        if event.status == "parsed" and event.parsed_value:
            groups.setdefault(event.parsed_value, []).append(event.field)
    return [
        {"parsed_value": value, "fields": sorted(set(fields))}
        for value, fields in groups.items()
        if len(set(fields)) > 1
    ]


def _find_chronological_conflicts(events: list[TimelineEvent]) -> list[dict[str, Any]]:
    """Find contradictory original, creation, and modification ordering."""
    if not events:
        return []
    parsed = {
        event.field: datetime.fromisoformat(event.parsed_value or "")
        for event in events
        if event.status == "parsed" and event.parsed_value
    }
    timezone_modes = {
        event.timezone_present
        for event in events
        if event.status == "parsed"
    }
    if len(timezone_modes) > 1:
        return []
    conflicts: list[dict[str, Any]] = []
    original = parsed.get("DateTimeOriginal")
    created = parsed.get("CreateDate")
    modified = parsed.get("ModifyDate")
    if original and modified and original > modified:
        conflicts.append({
            "fields": ["DateTimeOriginal", "ModifyDate"],
            "explanation": "Capture date occurs after modification date.",
        })
    if created and modified and created > modified:
        conflicts.append({
            "fields": ["CreateDate", "ModifyDate"],
            "explanation": "Creation date occurs after modification date.",
        })
    if original and created and original > created:
        conflicts.append({
            "fields": ["DateTimeOriginal", "CreateDate"],
            "explanation": "Capture date occurs after creation date.",
        })
    exif_created = created
    xmp_created = parsed.get("XMP:CreateDate") or parsed.get("XMP:DateCreated")
    xmp_modified = parsed.get("XMP:ModifyDate") or parsed.get("XMP:MetadataDate")
    if exif_created and xmp_created and exif_created != xmp_created:
        conflicts.append({
            "fields": ["CreateDate", "XMP:CreateDate"],
            "explanation": "EXIF and XMP creation timestamps differ.",
        })
    exif_modified = modified
    if exif_modified and xmp_modified and exif_modified != xmp_modified:
        conflicts.append({
            "fields": ["ModifyDate", "XMP:ModifyDate"],
            "explanation": "EXIF and XMP modification timestamps differ.",
        })
    if original and parsed.get("XMP:DateCreated"):
        xmp_original = parsed["XMP:DateCreated"]
        if original != xmp_original:
            conflicts.append({
                "fields": ["DateTimeOriginal", "XMP:DateCreated"],
                "explanation": "EXIF capture and XMP capture timestamps differ.",
            })
    return conflicts
