"""Focused PhotoTrace backend tests."""

from __future__ import annotations

import json
import hashlib
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from PIL import Image

from phototrace_app.gps import extract_gps, convert_coordinate
from phototrace_app.integrity import analyze_integrity
from phototrace_app.metadata import MetadataExtractionError, extract_metadata
from phototrace_app.reports import build_report, get_report_download, save_report
from phototrace_app.validation import ValidationError, validate_image
from phototrace_app.jpeg_structure import inspect_jpeg
from phototrace_app.timeline import build_metadata_timeline
from phototrace_app.advanced_analysis import analyze_advanced


def write_fixture(path: Path) -> None:
    """Write a valid minimal PNG fixture."""
    Image.new("RGBA", (1, 1), (255, 0, 0, 255)).save(path, format="PNG")


def write_synthetic_jpeg(
    path: Path,
    *,
    width: int = 32,
    height: int = 24,
    exif_thumbnail: bool = False,
    xmp: bool = False,
    truncated: bool = False,
) -> None:
    """Write a synthetic JPEG with controllable markers for structural tests."""
    data = bytearray(b"\xff\xd8")
    dqt_payload = bytes([0]) + bytes(range(1, 65))
    data += b"\xff\xdb" + (len(dqt_payload) + 2).to_bytes(2, "big") + dqt_payload
    sof_payload = bytes([8]) + height.to_bytes(2, "big") + width.to_bytes(2, "big") + bytes([1, 1, 0x11, 0])
    data += b"\xff\xc0" + (len(sof_payload) + 2).to_bytes(2, "big") + sof_payload
    if exif_thumbnail:
        ifd0_offset = 8
        ifd1_offset = 24
        thumbnail_offset = 54
        thumbnail_length = 10
        tiff = bytearray(b"II*\x00")
        tiff += ifd0_offset.to_bytes(4, "little")
        tiff += b"\x00\x00"
        tiff += ifd1_offset.to_bytes(4, "little")
        tiff += b"\x00" * 10
        tiff += b"\x02\x00"
        tiff += (0x0201).to_bytes(2, "little")
        tiff += (4).to_bytes(2, "little")
        tiff += (1).to_bytes(4, "little")
        tiff += thumbnail_offset.to_bytes(4, "little")
        tiff += (0x0202).to_bytes(2, "little")
        tiff += (4).to_bytes(2, "little")
        tiff += (1).to_bytes(4, "little")
        tiff += thumbnail_length.to_bytes(4, "little")
        tiff += b"\x00\x00\x00\x00"
        tiff += b"\xff\xd8\xff\xe0thumb\xff\xd9"
        exif_payload = b"Exif\x00\x00" + tiff
    else:
        exif_payload = b"Exif\x00\x00II*\x00"
    data += b"\xff\xe1" + (len(exif_payload) + 2).to_bytes(2, "big") + exif_payload
    if xmp:
        xmp_payload = b"http://ns.adobe.com/xap/1.0/\x00<x:xmpmeta/>"
        data += b"\xff\xe1" + (len(xmp_payload) + 2).to_bytes(2, "big") + xmp_payload
    data += b"\xff\xda\x00\x02"
    if not truncated:
        data += b"\xff\xd9"
    path.write_bytes(data)


class JPEGStructureTests(TestCase):
    def test_parses_markers_dimensions_and_quantization_table(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "structure.jpg"
            write_synthetic_jpeg(path)
            structure = inspect_jpeg(path)
            self.assertTrue(structure.is_jpeg)
            self.assertTrue(structure.complete)
            self.assertTrue(structure.has_end_marker)
            self.assertIn("DQT", structure.markers)
            self.assertIn("SOF0", structure.markers)
            self.assertEqual(structure.width, 32)
            self.assertEqual(structure.height, 24)
            self.assertEqual(structure.quantization_tables[0]["table_id"], 0)
            self.assertEqual(structure.quantization_tables[0]["value_count"], 64)

    def test_detects_exif_xmp_and_thumbnail(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "structured.jpg"
            write_synthetic_jpeg(path, exif_thumbnail=True, xmp=True)
            structure = inspect_jpeg(path)
            self.assertTrue(structure.exif_present)
            self.assertTrue(structure.xmp_present)
            self.assertTrue(structure.thumbnail_present)

    def test_rejects_malformed_and_truncated_jpegs(self) -> None:
        with TemporaryDirectory() as directory:
            invalid = Path(directory) / "invalid.jpg"
            invalid.write_bytes(b"not jpeg")
            structure = inspect_jpeg(invalid)
            self.assertFalse(structure.is_jpeg)
            truncated = Path(directory) / "truncated.jpg"
            write_synthetic_jpeg(truncated, truncated=True)
            structure = inspect_jpeg(truncated)
            self.assertTrue(structure.truncated)
            self.assertFalse(structure.has_end_marker)

    def test_handles_multiple_dqt_segments_and_16_bit_tables(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "dqt.jpg"
            data = bytearray(b"\xff\xd8")
            dqt8 = bytes([0]) + bytes(range(64))
            data += b"\xff\xdb" + (len(dqt8) + 2).to_bytes(2, "big") + dqt8
            dqt16_payload = bytes([0x10]) + bytes(
                value for pair in ((index * 256 + index) for index in range(64))
                for value in pair.to_bytes(2, "big")
            )
            data += b"\xff\xdb" + (len(dqt16_payload) + 2).to_bytes(2, "big") + dqt16_payload
            data += b"\xff\xd9"
            path.write_bytes(data)
            structure = inspect_jpeg(path)
            self.assertEqual(len(structure.quantization_tables), 2)
            self.assertEqual(structure.quantization_tables[0]["value_count"], 64)
            self.assertEqual(structure.quantization_tables[1]["precision_bits"], 16)
            self.assertEqual(structure.quantization_tables[1]["value_count"], 64)

    def test_rejects_invalid_segment_length_and_missing_markers(self) -> None:
        with TemporaryDirectory() as directory:
            invalid_length = Path(directory) / "invalid-length.jpg"
            invalid_length.write_bytes(b"\xff\xd8\xff\xdb\xff\xff\x00")
            structure = inspect_jpeg(invalid_length)
            self.assertTrue(structure.is_jpeg)
            self.assertTrue(structure.truncated)
            missing_soi = Path(directory) / "missing-soi.jpg"
            missing_soi.write_bytes(b"\xff\xd9")
            structure = inspect_jpeg(missing_soi)
            self.assertFalse(structure.is_jpeg)

    def test_repeated_sof_markers_are_recorded(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "repeated.jpg"
            sof_payload = bytes([8]) + (24).to_bytes(2, "big") + (32).to_bytes(2, "big") + bytes([1, 1, 0x11, 0])
            sof_segment = b"\xff\xc0" + (len(sof_payload) + 2).to_bytes(2, "big") + sof_payload
            path.write_bytes(b"\xff\xd8" + sof_segment + sof_segment + b"\xff\xd9")
            structure = inspect_jpeg(path)
            self.assertEqual(structure.duplicate_markers["SOF0"], 2)

    def test_trailing_bytes_after_eoi_are_recorded(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "trailing.jpg"
            path.write_bytes(b"\xff\xd8\xff\xd9TRAIL")
            structure = inspect_jpeg(path)
            self.assertTrue(structure.has_end_marker)
            self.assertEqual(structure.trailing_bytes, 5)


class TimelineAndAdvancedTests(TestCase):
    def test_builds_metadata_timeline_and_missing_fields(self) -> None:
        timeline = build_metadata_timeline({
            "EXIF:DateTimeOriginal": "2024:01:02 12:00:00",
            "EXIF:CreateDate": "2024:01:02 12:01:00",
        })
        self.assertEqual(timeline["missing_timestamp_fields"][0], "ModifyDate")
        self.assertGreaterEqual(len(timeline["events"]), 2)

    def test_detects_conflicting_timestamps(self) -> None:
        timeline = build_metadata_timeline({
            "EXIF:DateTimeOriginal": "2024:02:01 12:00:00",
            "EXIF:CreateDate": "2024:01:01 12:00:00",
            "EXIF:ModifyDate": "2024:01:15 12:00:00",
        })
        self.assertTrue(timeline["chronological_conflicts"])

    def test_timezone_ambiguity_is_reported(self) -> None:
        timeline = build_metadata_timeline({
            "EXIF:DateTimeOriginal": "2024:01:02 12:00:00+05:00",
            "EXIF:ModifyDate": "2024:01:02 12:30:00",
        })
        self.assertTrue(timeline["timezone_ambiguous"])

    def test_combines_gps_date_and_time_without_inventing_a_date(self) -> None:
        timeline = build_metadata_timeline({
            "EXIF:GPSDateStamp": "2024:01:02",
            "EXIF:GPSTimeStamp": [12, 30, 45],
        })
        gps_events = [
            event for event in timeline["events"]
            if event["field"] == "GPSDateTime"
        ]
        self.assertEqual(len(gps_events), 1)
        self.assertIn("2024-01-02", gps_events[0]["parsed_value"])
        self.assertIn("12:30:45", gps_events[0]["parsed_value"])

    def test_conflicting_exif_and_xmp_timestamps_are_reported(self) -> None:
        timeline = build_metadata_timeline({
            "EXIF:CreateDate": "2024:01:02 12:00:00",
            "XMP:CreateDate": "2024:01:03 12:00:00",
            "EXIF:ModifyDate": "2024:01:04 12:00:00",
            "XMP:ModifyDate": "2024:01:05 12:00:00",
        })
        conflicts = {
            tuple(conflict["fields"])
            for conflict in timeline["chronological_conflicts"]
        }
        self.assertIn(("CreateDate", "XMP:CreateDate"), conflicts)
        self.assertIn(("ModifyDate", "XMP:ModifyDate"), conflicts)

    def test_duplicate_timestamps_across_fields_are_reported(self) -> None:
        timeline = build_metadata_timeline({
            "EXIF:DateTimeOriginal": "2024:01:02 12:00:00",
            "EXIF:CreateDate": "2024:01:02 12:00:00",
        })
        self.assertTrue(timeline["duplicate_timestamp_fields"])

    def test_invalid_timestamp_remains_visible_in_timeline(self) -> None:
        timeline = build_metadata_timeline({
            "EXIF:DateTimeOriginal": "vendor-specific-value",
        })
        events = timeline["events"]
        self.assertEqual(events[0]["status"], "invalid")
        self.assertIsNone(events[0]["parsed_value"])

    def test_advanced_analysis_preserves_structure_and_limitations(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "advanced.jpg"
            write_synthetic_jpeg(path)
            report = analyze_advanced(
                path,
                {
                    "File:ImageWidth": 32,
                    "File:ImageHeight": 24,
                    "EXIF:ExifImageWidth": 33,
                    "EXIF:ExifImageHeight": 24,
                    "EXIF:DateTimeOriginal": "2024:01:02 12:00:00",
                },
            )
            titles = {finding["title"] for finding in report["findings"]}
            self.assertIn("EXIF and image dimensions conflict", titles)
            self.assertIn("image_structure", report)
            self.assertIn("timeline", report)
            self.assertTrue(report["method_limitations"])

    def test_advanced_report_serialization(self) -> None:
        with TemporaryDirectory() as directory:
            image = Path(directory) / "advanced.jpg"
            write_synthetic_jpeg(image)
            advanced = analyze_advanced(image, {"File:FileType": "JPEG"})
            report = build_report(
                image,
                {"File:FileType": "JPEG"},
                extract_gps({}),
                [],
                advanced,
            )
            report_path = save_report(report, Path(directory) / "reports")
            loaded = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(loaded["version"], "2.0.0")
            self.assertIn("advanced_analysis", loaded)


class ValidationTests(TestCase):
    def test_project_upload_limit_matches_backend_limit(self) -> None:
        from phototrace_app.validation import DEFAULT_MAX_FILE_SIZE

        self.assertEqual(DEFAULT_MAX_FILE_SIZE, 50 * 1024 * 1024)

    def test_upload_filename_is_sanitized_for_temporary_storage(self) -> None:
        app = Path(__file__).resolve().parents[1] / "backend" / "main.py"
        source = app.read_text(encoding="utf-8")
        self.assertIn("Path(filename).name", source)

    def test_validates_supported_nonempty_image(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "image.png"
            write_fixture(path)
            validated = validate_image(path)
            self.assertGreater(validated.size_bytes, 0)

    def test_rejects_unsupported_extension_and_oversized_file(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "image.txt"
            path.write_bytes(b"data")
            with self.assertRaises(ValidationError):
                validate_image(path)
            image = Path(directory) / "large.png"
            write_fixture(image)
            with self.assertRaises(ValidationError):
                validate_image(image, max_size_bytes=1)

    def test_rejects_corrupted_raster_content(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "corrupted.jpg"
            path.write_bytes(b"not-an-image")
            with self.assertRaises(ValidationError):
                validate_image(path)


class GPSTests(TestCase):
    def test_converts_dms_and_reference(self) -> None:
        self.assertAlmostEqual(convert_coordinate("51 30 0", "N"), 51.5)
        self.assertAlmostEqual(convert_coordinate("0 7 30", "W"), -0.125)

    def test_distinguishes_missing_and_invalid_gps(self) -> None:
        self.assertEqual(extract_gps({}).status, "missing")
        invalid = extract_gps({"GPS:GPSLatitude": 95, "GPS:GPSLongitude": 10})
        self.assertEqual(invalid.status, "invalid")

    def test_extracts_valid_gps(self) -> None:
        gps = extract_gps(
            {
                "GPS:GPSLatitude": 51.5,
                "GPS:GPSLongitude": -0.125,
                "GPS:GPSAltitude": 20,
            }
        )
        self.assertEqual(gps.status, "valid")
        self.assertEqual(gps.latitude, 51.5)

    def test_rejects_bad_dms_reference_and_nonfinite_values(self) -> None:
        self.assertEqual(
            extract_gps(
                {
                    "GPS:GPSLatitude": [51, 60, 0],
                    "GPS:GPSLongitude": 10,
                }
            ).status,
            "invalid",
        )
        self.assertEqual(
            extract_gps(
                {
                    "GPS:GPSLatitude": float("nan"),
                    "GPS:GPSLongitude": 10,
                }
            ).status,
            "invalid",
        )
        self.assertEqual(
            extract_gps(
                {
                    "GPS:GPSLatitude": 51,
                    "GPS:GPSLatitudeRef": "Q",
                    "GPS:GPSLongitude": 10,
                }
            ).status,
            "invalid",
        )


class MetadataTests(TestCase):
    def test_extracts_all_exiftool_fields(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "image.png"
            write_fixture(path)
            metadata = extract_metadata(path)
            self.assertIn("System:FileName", metadata)
            self.assertIn("File:FileType", metadata)

    @patch("phototrace_app.metadata.shutil.which", return_value=None)
    def test_reports_missing_exiftool(self, _: object) -> None:
        with self.assertRaises(MetadataExtractionError):
            extract_metadata(Path("image.jpg"))

    @patch("phototrace_app.metadata.subprocess.run")
    @patch("phototrace_app.metadata.shutil.which", return_value="/usr/bin/exiftool")
    def test_reports_exiftool_execution_failure(
        self, _: object, run: object
    ) -> None:
        run.return_value = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="bad image"
        )
        with self.assertRaisesRegex(MetadataExtractionError, "bad image"):
            extract_metadata(Path("image.jpg"))

    def test_rejects_non_image_content_with_supported_raw_extension(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "fake.cr2"
            path.write_bytes(b"not-a-camera-file")
            with self.assertRaisesRegex(MetadataExtractionError, "non-image"):
                extract_metadata(path)

    @patch("phototrace_app.metadata.subprocess.run")
    @patch("phototrace_app.metadata.shutil.which", return_value="/usr/bin/exiftool")
    def test_preserves_additional_exiftool_records(
        self, _: object, run: object
    ) -> None:
        run.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps(
                [
                    {"File:FileType": "JPEG", "File:MIMEType": "image/jpeg"},
                    {"Preview:Comment": "embedded record"},
                ]
            ),
            stderr="",
        )
        metadata = extract_metadata(Path("image.jpg"))
        self.assertEqual(
            metadata["_ExifToolAdditionalRecords"][0]["Preview:Comment"],
            "embedded record",
        )


class IntegrityAndReportTests(TestCase):
    def test_react_includes_advanced_forensic_section(self) -> None:
        app = Path(__file__).resolve().parents[1] / "frontend" / "src" / "App.tsx"
        source = app.read_text(encoding="utf-8")
        self.assertIn("Advanced Forensic Analysis", source)
        self.assertIn("TIMELINE", source.upper())
        self.assertIn("Image Structure", source)

    def test_react_report_download_uses_shared_export_helper(self) -> None:
        app = Path(__file__).resolve().parents[1] / "frontend" / "src" / "App.tsx"
        source = app.read_text(encoding="utf-8")
        self.assertIn("/api/reports/download", source)
        self.assertIn("downloadReport", source)
        self.assertIn("window.location.origin", source)

    def test_export_filename_and_payload_match_exact_report(self) -> None:
        report = {
            "tool": "PhotoTrace",
            "version": "1.2.0",
            "original_filename": "../../bad name:scan.jpg",
            "file": {"sha256": "abc123"},
            "gps": {"status": "missing"},
            "advanced_analysis": {"timeline": {"events": []}},
        }
        filename, payload = get_report_download(report)
        self.assertEqual(filename, "bad_name_scan_report.json")
        loaded = json.loads(payload)
        self.assertEqual(loaded["file"]["sha256"], "abc123")
        self.assertEqual(loaded["gps"]["status"], "missing")
        self.assertIn("advanced_analysis", loaded)

    def test_export_payload_safely_serializes_unusual_metadata(self) -> None:
        report = {
            "tool": "PhotoTrace",
            "original_filename": "image.jpg",
            "metadata": {
                "Float": float("inf"),
                "Absolute": "/private/var/tmp/image.jpg",
                "Nested": {"Windows": "C:\\Users\\forensics\\image.jpg"},
            },
        }
        filename, payload = get_report_download(report)
        loaded = json.loads(payload)
        self.assertEqual(filename, "image_report.json")
        self.assertEqual(loaded["metadata"]["Float"], "inf")
        self.assertEqual(
            loaded["metadata"]["Absolute"],
            "[absolute path redacted]",
        )
        self.assertEqual(
            loaded["metadata"]["Nested"]["Windows"],
            "[absolute path redacted]",
        )

    def test_saved_report_matches_exact_download_payload(self) -> None:
        with TemporaryDirectory() as directory:
            image = Path(directory) / "image.jpg"
            write_fixture(image)
            report = build_report(
                image,
                {"File:FileType": "JPEG", "SourceFile": "/private/var/tmp/image.jpg"},
                extract_gps({"GPS:GPSLatitude": 51.5, "GPS:GPSLongitude": -0.125}),
                [],
                {
                    "timeline": {"events": []},
                    "image_structure": {"format": "JPEG"},
                    "findings": [],
                    "method_limitations": [],
                },
            )
            report_path = save_report(report, Path(directory) / "reports")
            filename, payload = get_report_download(report)
            saved = json.loads(report_path.read_text(encoding="utf-8"))
            downloaded = json.loads(payload)
            self.assertEqual(filename, "image_report.json")
            self.assertEqual(downloaded, saved)
            self.assertEqual(downloaded["gps"]["status"], "valid")
            self.assertIn("advanced_analysis", downloaded)
            self.assertNotIn("/private/", json.dumps(downloaded))

    def test_timestamp_comparison_handles_valid_order_and_inconsistency(self) -> None:
        consistent = analyze_integrity(
            {
                "EXIF:DateTimeOriginal": "2024:01:02 12:00:00",
                "EXIF:CreateDate": "2024:01:02 12:01:00",
                "EXIF:ModifyDate": "2024:01:02 12:02:00",
            }
        )
        self.assertNotIn(
            "Timestamp ordering is inconsistent",
            {finding.title for finding in consistent},
        )
        inconsistent = analyze_integrity(
            {
                "EXIF:DateTimeOriginal": "2024:01:02 12:02:00",
                "EXIF:CreateDate": "2024:01:02 12:01:00",
                "EXIF:ModifyDate": "2024:01:02 12:03:00",
            }
        )
        self.assertIn(
            "Timestamp ordering is inconsistent",
            {finding.title for finding in inconsistent},
        )

    def test_timestamp_missing_invalid_and_timezone_cases_are_safe(self) -> None:
        missing = analyze_integrity({})
        self.assertIn("Some capture dates are unavailable", {item.title for item in missing})
        invalid = analyze_integrity({"EXIF:DateTimeOriginal": "not-a-date"})
        self.assertIn("Timestamp format is invalid", {item.title for item in invalid})
        mixed = analyze_integrity(
            {
                "EXIF:DateTimeOriginal": "2024:01:02 12:00:00+05:00",
                "EXIF:CreateDate": "2024:01:02 08:00:00",
            }
        )
        self.assertIn(
            "Timestamp timezone context is incomplete",
            {item.title for item in mixed},
        )
    def test_classifies_editor_and_timestamp_findings(self) -> None:
        findings = analyze_integrity(
            {
                "EXIF:DateTimeOriginal": "2024:01:02 12:00:00",
                "EXIF:ModifyDate": "2023:01:02 12:00:00",
                "EXIF:Software": "Adobe Photoshop",
            }
        )
        severities = {finding.severity for finding in findings}
        self.assertIn("Warning", severities)
        self.assertIn("Suspicious", severities)

    def test_writes_structured_json_report(self) -> None:
        with TemporaryDirectory() as directory:
            image = Path(directory) / "image.png"
            write_fixture(image)
            report = build_report(image, {"FileType": "PNG"}, extract_gps({}), [])
            report_path = save_report(report, Path(directory) / "reports")
            loaded = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(loaded["original_filename"], "image.png")
            self.assertIn("sha256", loaded["file"])

    def test_report_hash_and_non_overwriting_output(self) -> None:
        with TemporaryDirectory() as directory:
            image = Path(directory) / "image.png"
            write_fixture(image)
            report = build_report(
                image,
                {"FileType": "PNG", "Value": float("nan")},
                extract_gps({}),
                [],
            )
            reports = Path(directory) / "reports"
            first = save_report(report, reports)
            second = save_report(report, reports)
            self.assertNotEqual(first, second)
            self.assertEqual(
                report["file"]["sha256"],
                hashlib.sha256(image.read_bytes()).hexdigest(),
            )
            self.assertEqual(report["file"]["path"], "image.png")
            loaded = json.loads(first.read_text(encoding="utf-8"))
            self.assertEqual(loaded["metadata"]["Value"], "nan")

    def test_report_redacts_absolute_local_metadata_paths(self) -> None:
        with TemporaryDirectory() as directory:
            image = Path(directory) / "image.jpg"
            write_fixture(image)
            report = build_report(
                image,
                {
                    "File:FileType": "JPEG",
                    "SourceFile": "/private/var/tmp/image.jpg",
                    "System:Directory": "/private/var/tmp",
                    "Windows:SourceFile": "C:\\Users\\forensics\\image.jpg",
                },
                extract_gps({}),
                [],
            )
            self.assertEqual(report["metadata"]["SourceFile"], "image.jpg")
            self.assertEqual(report["metadata"]["System:Directory"], "tmp")
            self.assertEqual(report["metadata"]["Windows:SourceFile"], "image.jpg")
