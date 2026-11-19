# PhotoTrace 2.0

PhotoTrace is a standalone, local-first digital forensics application for
inspecting image metadata, GPS information, JPEG structure, timestamp timelines,
and metadata integrity indicators.

The application uses a React and TypeScript frontend, a FastAPI Python backend,
and ExifTool for metadata extraction. Images and metadata remain on the local
machine.

## Features

- JPEG, PNG, TIFF, WebP, BMP, GIF, HEIC/HEIF, and supported RAW extensions
- Full available ExifTool metadata retained in JSON reports
- Camera, lens, date, software, file, and image properties
- Validated GPS coordinates with decimal-degree conversion
- Missing GPS data distinguished from invalid or incomplete GPS data
- Conservative informational, warning, and suspicious findings
- Structured JSON forensic reports with SHA-256 file hashes
- CLI and custom web interface
- Leaflet map for valid GPS coordinates
- Advanced JPEG marker and quantization-table structure inspection
- Metadata timeline construction and timestamp conflict checks
- EXIF, XMP, dimensions, software, and thumbnail consistency indicators
- Advanced findings with evidence and explicit detection limitations

Metadata findings are indicators for review. Missing metadata or timestamp
inconsistencies do not prove that an image was manipulated or is fraudulent.

## Advanced forensic methodology

The advanced analysis performs local structural inspection only. It parses JPEG
markers and DQT segments, observes start-of-frame dimensions and embedded
EXIF/XMP indicators, and constructs a timeline from available metadata.
Quantization-table values, timestamp conflicts, and thumbnail/dimension
comparisons are reported as forensic indicators. They are not pixel-analysis
proof, error-level-analysis claims, or authenticity determinations.

Example findings include incomplete JPEG structure, conflicting EXIF/image
dimensions, mixed or incomplete timestamp timezone context, contradictory
capture/creation/modification ordering, and EXIF/XMP software disagreement.
Each advanced finding includes severity, technical evidence, an explanation,
and the limitations of that detection.

## Architecture

```text
frontend/       React 19, TypeScript, Vite, Leaflet
backend/        FastAPI API and temporary upload handling
phototrace_app/ Existing forensic analysis modules
tests/          Backend, API, parser, report, and export tests
```

The backend reuses `phototrace_app` for validation, ExifTool extraction, GPS
analysis, JPEG structure inspection, timelines, integrity findings, and reports.

## Installation

Install ExifTool using your operating system package manager.

For an isolated setup, create a virtual environment in the project directory:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Verify ExifTool is available:

```bash
exiftool -ver
```

## CLI usage

```bash
python3 phototrace.py /path/to/image.jpg
python3 phototrace.py /path/to/image.jpg --reports-dir reports
```

The JSON report is saved in `reports/` by default.

## Web application usage

Install backend dependencies and start FastAPI:

```bash
.venv/bin/python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

The production frontend build is served automatically at
`http://127.0.0.1:8000` when `frontend/dist/` exists.

For frontend development:

```bash
cd frontend
npm install
npm run dev
```

The development interface is available at `http://localhost:5173` and calls the
API at `http://localhost:8000` by default.

Upload an image through the sidebar interface. The application provides
Dashboard, Image Analysis, Metadata Explorer, GPS & Location, Integrity
Analysis, Advanced Forensic Analysis, and Forensic Reports sections. Sensitive
metadata fields are hidden by default.

## Testing

Run the focused test suite with:

```bash
python3 -m unittest discover -s tests -v
npm --prefix frontend run build
```

## API

- `GET /api/health`
- `POST /api/analyze`
- `POST /api/reports`
- `POST /api/reports/download`

Uploaded files are written to a temporary directory, validated, analyzed, and
removed automatically. They are not sent to external analysis services.

Reports use safe `<image_name>_report.json` filenames and redact absolute Unix
and Windows metadata paths. Repeated saved reports do not overwrite earlier files.

## Limitations

- ExifTool-supported formats are limited by the installed ExifTool version and
  the conservative extension validation list.
- GPS analysis reports extracted coordinates only; it does not infer a location.
- Integrity checks are heuristic indicators and are not an authenticity verdict.
- Interactive map tiles may be loaded by the browser from the configured map
  provider. The provider may receive displayed map coordinates; image files and
  metadata are not uploaded by PhotoTrace.
- Leaflet tile providers may receive browser map-coordinate requests when a
  valid GPS location is displayed. Image files and metadata are not uploaded.
- Browser download completion is platform-dependent; report JSON and download
  payload parity are verified in backend tests.