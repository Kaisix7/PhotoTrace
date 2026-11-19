"""FastAPI application for local PhotoTrace analysis."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from phototrace_app.analysis import analyze_image
from phototrace_app.metadata import MetadataExtractionError
from phototrace_app.reports import get_report_download
from phototrace_app.validation import DEFAULT_MAX_FILE_SIZE, ValidationError


app = FastAPI(
    title="PhotoTrace API",
    version="2.0.0",
    description="Local digital image forensics API.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    """Return local API health."""
    return {"status": "ok", "tool": "PhotoTrace", "version": "2.0.0"}


def _safe_filename(filename: str) -> str:
    """Return the basename of an uploaded filename."""
    return Path(filename).name


@app.post("/api/analyze")
async def analyze_upload(file: UploadFile = File(...)) -> dict[str, Any]:
    """Validate, analyze, and return one uploaded image report."""
    filename = _safe_filename(file.filename or "image")
    if not filename:
        raise HTTPException(status_code=400, detail="A filename is required.")

    with tempfile.TemporaryDirectory(prefix="phototrace-api-") as directory:
        image_path = Path(directory) / filename
        size = 0
        try:
            with image_path.open("wb") as output:
                while True:
                    chunk = await file.read(1024 * 1024)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > DEFAULT_MAX_FILE_SIZE:
                        raise HTTPException(
                            status_code=413,
                            detail="The image exceeds the 50 MB size limit.",
                        )
                    output.write(chunk)
        finally:
            await file.close()

        try:
            report = analyze_image(image_path)
        except (ValidationError, MetadataExtractionError, OSError, ValueError) as error:
            raise HTTPException(
                status_code=400,
                detail=str(error),
            ) from error
        return JSONResponse(content=report)


@app.post("/api/reports")
async def generate_report(file: UploadFile = File(...)) -> dict[str, Any]:
    """Generate the same report payload returned by analysis."""
    return await analyze_upload(file)


@app.post("/api/reports/download")
async def download_report(file: UploadFile = File(...)) -> Response:
    """Download a forensic JSON report directly."""
    filename = _safe_filename(file.filename or "image")
    with tempfile.TemporaryDirectory(prefix="phototrace-api-") as directory:
        image_path = Path(directory) / filename
        size = 0
        try:
            with image_path.open("wb") as output:
                while True:
                    chunk = await file.read(1024 * 1024)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > DEFAULT_MAX_FILE_SIZE:
                        raise HTTPException(status_code=413, detail="The image exceeds the 50 MB size limit.")
                    output.write(chunk)
        finally:
            await file.close()
        try:
            report = analyze_image(image_path)
        except (ValidationError, MetadataExtractionError, OSError, ValueError) as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        download_filename, payload = get_report_download(report)
        return Response(
            content=payload,
            media_type="application/json",
            headers={
                "Content-Disposition": f'attachment; filename="{download_filename}"',
            },
        )


frontend_dist = Path(__file__).resolve().parents[1] / "frontend" / "dist"
if frontend_dist.is_dir():
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
