"""Conservative JPEG structure and marker inspection."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


JPEG_MARKER_NAMES = {
    0xC0: "SOF0",
    0xC1: "SOF1",
    0xC2: "SOF2",
    0xC3: "SOF3",
    0xC4: "DHT",
    0xC5: "SOF5",
    0xC6: "SOF6",
    0xC7: "SOF7",
    0xC9: "SOF9",
    0xCA: "SOF10",
    0xCB: "SOF11",
    0xCC: "DAC",
    0xCD: "SOF13",
    0xCE: "SOF14",
    0xCF: "SOF15",
    0xDA: "SOS",
    0xDB: "DQT",
    0xDD: "DRI",
    0xE0: "APP0",
    0xE1: "APP1",
    0xE2: "APP2",
    0xED: "APP13",
    0xFE: "COM",
}


@dataclass(frozen=True)
class JPEGStructure:
    """Facts observed from JPEG markers, not a manipulation verdict."""

    format: str
    is_jpeg: bool
    complete: bool
    has_end_marker: bool
    truncated: bool
    marker_count: int
    markers: list[str]
    marker_offsets: dict[str, list[int]]
    sof_marker: str | None
    width: int | None
    height: int | None
    precision: int | None
    quantization_tables: list[dict[str, Any]]
    thumbnail_present: bool
    thumbnail_valid: bool
    thumbnail_offset: int | None
    thumbnail_length: int | None
    duplicate_markers: dict[str, int]
    trailing_bytes: int
    exif_present: bool
    xmp_present: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def inspect_jpeg(image_path: Path) -> JPEGStructure:
    """Parse JPEG markers and quantization-table metadata without decoding pixels."""
    data = image_path.read_bytes()
    if len(data) < 2 or data[:2] != b"\xff\xd8":
        return JPEGStructure(
            format="Not JPEG", is_jpeg=False, complete=False, has_end_marker=False,
            truncated=False, marker_count=0, markers=[], marker_offsets={},
            sof_marker=None, width=None, height=None, precision=None,
            quantization_tables=[], thumbnail_present=False, exif_present=False,
            xmp_present=False, thumbnail_valid=False, thumbnail_offset=None,
            thumbnail_length=None, duplicate_markers={}, trailing_bytes=0,
        )

    markers: list[str] = []
    offsets: dict[str, list[int]] = {}
    quantization_tables: list[dict[str, Any]] = []
    sof_marker: str | None = None
    width: int | None = None
    height: int | None = None
    precision: int | None = None
    exif_present = False
    xmp_present = False
    thumbnail_present = False
    position = 2
    complete = True
    has_end_marker = False
    duplicate_markers: dict[str, int] = {}
    trailing_bytes = 0

    while position < len(data):
        if data[position] != 0xFF:
            position += 1
            continue
        while position < len(data) and data[position] == 0xFF:
            position += 1
        if position >= len(data):
            complete = False
            break
        marker = data[position]
        position += 1
        if marker == 0x00:
            continue
        if marker == 0xD9:
            has_end_marker = True
            name = "EOI"
            markers.append(name)
            offsets.setdefault(name, []).append(position - 2)
            marker_offset_count = len(offsets[name])
            if marker_offset_count > 1:
                duplicate_markers[name] = marker_offset_count
            trailing_bytes = max(0, len(data) - position)
            break
        if marker in (0x01, 0xD0, 0xD1, 0xD2, 0xD3, 0xD4, 0xD5, 0xD6, 0xD7):
            name = f"{marker:02X}"
            markers.append(name)
            offsets.setdefault(name, []).append(position - 2)
            continue
        if position + 2 > len(data):
            complete = False
            break
        length = int.from_bytes(data[position:position + 2], "big")
        if length < 2 or position + length > len(data):
            complete = False
            break
        payload_start = position + 2
        payload_end = position + length
        name = JPEG_MARKER_NAMES.get(marker, f"FF{marker:02X}")
        markers.append(name)
        offsets.setdefault(name, []).append(position - 2)
        marker_offset_count = len(offsets[name])
        if marker_offset_count > 1:
            duplicate_markers[name] = marker_offset_count

        if marker in range(0xC0, 0xD0) and marker not in (0xC4, 0xC8, 0xCC):
            if payload_end - payload_start >= 6:
                precision = data[payload_start]
                height = int.from_bytes(data[payload_start + 1:payload_start + 3], "big")
                width = int.from_bytes(data[payload_start + 3:payload_start + 5], "big")
                component_count = data[payload_start + 5]
                if precision not in (8, 12, 16) or width == 0 or height == 0 or component_count == 0:
                    complete = False
                elif payload_end - payload_start < 6 + component_count * 3:
                    complete = False
                sof_marker = name
        elif marker == 0xDB:
            payload = data[payload_start:payload_end]
            cursor = 0
            while cursor < len(payload):
                if cursor >= len(payload):
                    break
                table_info = payload[cursor]
                table_precision = table_info >> 4
                table_id = table_info & 0x0F
                if table_precision not in (0, 1) or table_id > 3:
                    complete = False
                cursor += 1
                value_count = 64 * (2 if table_precision == 1 else 1)
                if cursor + value_count > len(payload):
                    complete = False
                    break
                values = list(payload[cursor:cursor + value_count])
                checksum_values = (
                    [int.from_bytes(values[index:index + 2], "big")
                     for index in range(0, len(values), 2)]
                    if table_precision == 1
                    else values
                )
                quantization_tables.append({
                    "table_id": table_id,
                    "precision_bits": 16 if table_precision == 1 else 8,
                    "value_count": 64,
                    "unique_values": len(set(checksum_values)),
                    "checksum": sum(
                        (index + 1) * value
                        for index, value in enumerate(checksum_values)
                    ),
                })
                cursor += value_count
        elif marker == 0xE1:
            payload = data[payload_start:payload_end]
            if payload.startswith(b"Exif\x00\x00"):
                exif_present = True
            if b"http://ns.adobe.com/xap/1.0/" in payload:
                xmp_present = True
        elif marker == 0xE0:
            payload = data[payload_start:payload_end]
            if payload.startswith(b"JFIF\x00"):
                pass
        position = payload_end

    thumbnail_valid = False
    thumbnail_offset: int | None = None
    thumbnail_length: int | None = None
    if exif_present:
        thumbnail_info = _detect_thumbnail(data)
        thumbnail_present = thumbnail_info["present"]
        thumbnail_valid = thumbnail_info["valid"]
        thumbnail_offset = thumbnail_info["offset"]
        thumbnail_length = thumbnail_info["length"]
    truncated = not complete or not has_end_marker
    return JPEGStructure(
        format="JPEG", is_jpeg=True, complete=complete, has_end_marker=has_end_marker,
        truncated=truncated, marker_count=len(markers), markers=markers,
        marker_offsets=offsets, sof_marker=sof_marker, width=width, height=height,
        precision=precision, quantization_tables=quantization_tables,
        thumbnail_present=thumbnail_present, exif_present=exif_present,
        xmp_present=xmp_present, thumbnail_valid=thumbnail_valid,
        thumbnail_offset=thumbnail_offset, thumbnail_length=thumbnail_length,
        duplicate_markers=duplicate_markers,
        trailing_bytes=trailing_bytes,
    )


def _detect_thumbnail(data: bytes) -> dict[str, Any]:
    """Validate an EXIF IFD1 thumbnail offset and length where possible."""
    position = 2
    while position < len(data):
        if data[position] != 0xFF:
            position += 1
            continue
        while position < len(data) and data[position] == 0xFF:
            position += 1
        if position >= len(data):
            break
        marker = data[position]
        position += 1
        if marker in (0x00, 0xD9):
            break
        if position + 2 > len(data):
            break
        length = int.from_bytes(data[position:position + 2], "big")
        if length < 2 or position + length > len(data):
            break
        payload_start = position + 2
        payload_end = position + length
        payload = data[payload_start:payload_end]
        position = payload_end
        if marker != 0xE1 or not payload.startswith(b"Exif\x00\x00"):
            continue

        tiff = payload[6:]
        if len(tiff) < 8:
            continue
        byte_order = tiff[:2]
        if byte_order == b"II":
            endian = "little"
        elif byte_order == b"MM":
            endian = "big"
        else:
            continue
        if tiff[2:4] != (b"\x2a\x00" if endian == "little" else b"\x00\x2a"):
            continue
        ifd0_offset = int.from_bytes(tiff[4:8], endian)
        ifd_offsets = [ifd0_offset]
        visited: set[int] = set()
        for ifd_offset in ifd_offsets:
            if ifd_offset in visited or ifd_offset + 2 > len(tiff):
                continue
            visited.add(ifd_offset)
            entry_count = int.from_bytes(tiff[ifd_offset:ifd_offset + 2], endian)
            entry_table_end = ifd_offset + 2 + entry_count * 12
            if entry_table_end + 4 > len(tiff):
                continue
            thumbnail_offset_value: int | None = None
            thumbnail_length_value: int | None = None
            for index in range(entry_count):
                entry = ifd_offset + 2 + index * 12
                tag = int.from_bytes(tiff[entry:entry + 2], endian)
                field_type = int.from_bytes(tiff[entry + 2:entry + 4], endian)
                component_count = int.from_bytes(tiff[entry + 4:entry + 8], endian)
                value_offset = int.from_bytes(tiff[entry + 8:entry + 12], endian)
                if tag == 0x0201:
                    if field_type == 4:
                        thumbnail_offset_value = value_offset
                elif tag == 0x0202:
                    if field_type in (3, 4):
                        thumbnail_length_value = (
                            (value_offset & 0xFFFF)
                            if field_type == 3 and component_count == 1
                            else value_offset if component_count == 1 else None
                        )
            next_ifd = int.from_bytes(tiff[entry_table_end:entry_table_end + 4], endian)
            if next_ifd:
                ifd_offsets.append(next_ifd)
            if thumbnail_offset_value is not None and thumbnail_length_value is not None:
                absolute_offset = payload_start + 6 + thumbnail_offset_value
                absolute_end = absolute_offset + thumbnail_length_value
                present = 0 <= absolute_offset < len(data)
                valid = (
                    present
                    and absolute_end <= len(data)
                    and data[absolute_offset:absolute_offset + 2] == b"\xff\xd8"
                    and data[max(absolute_offset, absolute_end - 2):absolute_end] == b"\xff\xd9"
                )
                return {
                    "present": present,
                    "valid": valid,
                    "offset": absolute_offset if present else None,
                    "length": thumbnail_length_value,
                }
    return {"present": False, "valid": False, "offset": None, "length": None}
