"""Conservative metadata integrity findings."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

from .metadata import get_tag


@dataclass(frozen=True)
class Finding:
    """A factual or analytical metadata finding."""

    severity: str
    title: str
    explanation: str
    evidence: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _parse_date(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    if len(normalized) >= 19 and normalized[4] == ":" and normalized[7] == ":":
        normalized = f"{normalized[:4]}-{normalized[5:7]}-{normalized[8:]}"
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def analyze_integrity(metadata: dict[str, Any]) -> list[Finding]:
    """Create explainable findings without declaring an image manipulated."""
    findings: list[Finding] = []
    date_values = {
        "original": get_tag(metadata, "DateTimeOriginal"),
        "created": get_tag(metadata, "CreateDate"),
        "modified": get_tag(metadata, "ModifyDate"),
    }
    missing = [name for name, value in date_values.items() if value is None]
    if missing:
        findings.append(
            Finding(
                "Informational",
                "Some capture dates are unavailable",
                "Missing metadata can result from camera settings, export tools, or privacy processing; it does not prove manipulation.",
                {"missing_fields": missing},
            )
        )
    parsed_dates = {
        name: parsed
        for name, value in date_values.items()
        if (parsed := _parse_date(value)) is not None
    }
    invalid = [
        name
        for name, value in date_values.items()
        if value is not None and name not in parsed_dates
    ]
    if invalid:
        findings.append(
            Finding(
                "Warning",
                "Timestamp format is invalid",
                "One or more timestamp fields could not be parsed. The affected values were not used for chronological comparison.",
                {"invalid_fields": invalid, "timestamps": date_values},
            )
        )
    aware_values = [value for value in parsed_dates.values() if value.tzinfo]
    naive_values = [value for value in parsed_dates.values() if not value.tzinfo]
    if aware_values and naive_values:
        findings.append(
            Finding(
                "Warning",
                "Timestamp timezone context is incomplete",
                "Some timestamps include timezone information while others do not, so chronological comparison may be ambiguous.",
                {"timestamps": date_values},
            )
        )
    ordered_dates = list(parsed_dates.values())
    if len(ordered_dates) >= 2 and not (aware_values and naive_values) and any(
        later < earlier for earlier, later in zip(ordered_dates, ordered_dates[1:])
    ):
        findings.append(
            Finding(
                "Warning",
                "Timestamp ordering is inconsistent",
                "The available timestamp values do not follow chronological order. This may reflect timezone, export, or editing behavior and requires context.",
                {"timestamps": date_values},
            )
        )
    software = get_tag(metadata, "Software")
    if isinstance(software, str) and any(
        marker in software.lower()
        for marker in ("photoshop", "lightroom", "gimp", "snapseed", "adobe")
    ):
        findings.append(
            Finding(
                "Suspicious",
                "Editing software is identified",
                "The Software tag names an editor or image-processing application. This is an indicator for review, not proof that image content was manipulated.",
                {"software": software},
            )
        )
    if not findings:
        findings.append(
            Finding(
                "Informational",
                "No notable metadata inconsistencies detected",
                "The available metadata did not trigger the configured checks. This is not a guarantee of authenticity.",
                {},
            )
        )
    return findings
