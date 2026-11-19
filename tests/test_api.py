"""FastAPI integration tests."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from fastapi.testclient import TestClient
from PIL import Image

from backend.main import app


client = TestClient(app)


def write_jpeg(path: Path, *, gps: bool = False) -> None:
    """Write a synthetic JPEG fixture."""
    Image.new("RGB", (32, 24), "navy").save(path, format="JPEG", quality=90)
    if gps:
        subprocess.run(
            [
                "exiftool",
                "-overwrite_original",
                "-GPSLatitude=51.5",
                "-GPSLatitudeRef=N",
                "-GPSLongitude=-0.125",
                "-GPSLongitudeRef=W",
                str(path),
            ],
            check=True,
            capture_output=True,
        )


class APIIntegrationTests(TestCase):
    """Test the HTTP migration surface."""

    def test_health_endpoint(self) -> None:
        response = client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    def test_analyze_valid_jpeg(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "valid.jpg"
            write_jpeg(path)
            response = client.post(
                "/api/analyze",
                files={"file": ("valid.jpg", path.read_bytes(), "image/jpeg")},
            )
        self.assertEqual(response.status_code, 200)
        report = response.json()
        self.assertEqual(report["original_filename"], "valid.jpg")
        self.assertIn(report["gps"]["status"], {"missing", "invalid", "valid"})
        self.assertIn("advanced_analysis", report)
        self.assertTrue(report["file"]["sha256"])

    def test_analyze_valid_gps(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "gps.jpg"
            write_jpeg(path, gps=True)
            response = client.post(
                "/api/analyze",
                files={"file": ("gps.jpg", path.read_bytes(), "image/jpeg")},
            )
        self.assertEqual(response.status_code, 200)
        gps = response.json()["gps"]
        self.assertEqual(gps["status"], "valid")
        self.assertEqual(gps["latitude"], 51.5)
        self.assertEqual(gps["longitude"], -0.125)

    def test_reject_corrupted_and_unsupported_files(self) -> None:
        corrupted = client.post(
            "/api/analyze",
            files={"file": ("corrupted.jpg", b"not jpeg", "image/jpeg")},
        )
        unsupported = client.post(
            "/api/analyze",
            files={"file": ("document.txt", b"text", "text/plain")},
        )
        self.assertEqual(corrupted.status_code, 400)
        self.assertEqual(unsupported.status_code, 400)

    def test_download_returns_valid_json_and_hash(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "download.jpg"
            write_jpeg(path)
            original_hash = hashlib.sha256(path.read_bytes()).hexdigest()
            response = client.post(
                "/api/reports/download",
                files={"file": ("download.jpg", path.read_bytes(), "image/jpeg")},
            )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            response.headers["content-disposition"].endswith(
                'filename="download_report.json"'
            )
        )
        self.assertTrue(
            response.headers["content-type"].startswith("application/json")
        )
        report = json.loads(response.text)
        self.assertEqual(report["file"]["sha256"], original_hash)
        self.assertNotIn("/private/", response.text)
