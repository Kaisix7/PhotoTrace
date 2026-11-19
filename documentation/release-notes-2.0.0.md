# PhotoTrace 2.0.0

## Overview

PhotoTrace 2.0.0 is a local-first image forensics workspace with a FastAPI
backend, a React/TypeScript interface, and a command-line entry point.

## Highlights

- Local image upload and validation with a 50 MB request limit
- ExifTool-backed EXIF, XMP, file, camera, lens, date, and software metadata
  extraction
- GPS coordinate validation, decimal conversion, and Leaflet map visualization
- SHA-256 file integrity hashing
- JPEG marker, frame-dimension, quantization-table, and thumbnail-signature
  inspection
- Metadata timeline construction and timestamp consistency indicators
- EXIF/XMP dimension and software consistency checks
- Structured JSON reports with safe filenames and sanitized absolute paths
- Dashboard, image analysis, metadata, GPS, integrity, advanced analysis, and
  report sections in the web interface
- Focused Python API/parser/report tests and frontend build/lint checks

## Scope and limitations

PhotoTrace reports explainable metadata and structural indicators. It does not
decode or authenticate pixels, perform visual geolocation, or independently
prove that an image is authentic, manipulated, or fraudulent.

The default commands are local-only. An internet-facing deployment would
require authentication, rate limiting, resource controls, and additional
production hardening.

## Verification performed locally

- `46` Python `unittest` cases passed with the project virtual environment.
- Frontend TypeScript/Vite production build passed.
- Oxlint passed.
- ExifTool `13.55` was available during verification.
- The complete UI workflow was exercised with synthetic fixtures.
