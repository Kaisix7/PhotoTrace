# PhotoTrace portfolio materials

## Project motivation

Images can contain useful technical evidence beyond their visible pixels:
camera metadata, timestamps, GPS coordinates, software markers, file hashes,
and structural encoding details. PhotoTrace provides a local workspace for
reviewing those signals without sending the image to an external analysis
service.

The project is designed for learning, demonstrations, portfolio review, and
preliminary evidence inspection. It deliberately presents findings as
indicators rather than authenticity verdicts.

## Technical implementation

PhotoTrace uses a FastAPI backend to receive multipart uploads, apply a 50 MB
streaming limit, validate image inputs, and coordinate the analysis pipeline.
Python modules use Pillow for raster validation and ExifTool for grouped
metadata extraction.

The forensic pipeline calculates a SHA-256 digest, derives GPS state, evaluates
metadata integrity indicators, parses JPEG markers and quantization-table
segments, builds a metadata timeline, and serializes a structured JSON report.

The React and TypeScript frontend is built with Vite. It keeps the selected
report in the browser session, provides separate analysis sections, hides
selected sensitive fields by default, renders valid GPS coordinates with
React-Leaflet, and downloads reports through the backend.

## Engineering decisions

- **Local-first processing:** temporary upload directories reduce persistent
  image storage and make the default workflow suitable for private local
  analysis.
- **Explainable findings:** each finding includes severity, evidence, an
  explanation, and limitations instead of an opaque authenticity score.
- **Conservative validation:** a supported extension is required; raster
  content is verified with Pillow; ExifTool remains the source of available
  metadata.
- **Safe report handling:** generated filenames are constrained, absolute
  metadata paths are sanitized, and saved reports do not overwrite earlier
  reports.
- **Separate UI modules:** dashboard, metadata, GPS, integrity, advanced
  analysis, and report views let users inspect one evidence category at a time.

## Forensic capabilities and practical value

PhotoTrace can surface missing or inconsistent timestamps, mixed timezone
context, EXIF/XMP dimension or software disagreements, incomplete JPEG
structure, trailing bytes, quantization-table observations, and thumbnail
signatures. These signals can help a reviewer decide what to investigate next
and preserve a reproducible report of the observed file.

The application does not decode or authenticate pixels, perform visual
geolocation, compare image content against a reference, or prove that a file is
authentic or manipulated.

## Security and privacy

The default server examples bind to loopback. Uploads are stored in temporary
directories and removed after analysis. The API does not use shell execution
for ExifTool, and upload filenames are reduced to safe basenames before
temporary storage.

Reports intentionally retain available metadata for forensic review. That
metadata may include GPS coordinates, serial numbers, author fields, and other
personal information. Reports must be reviewed before sharing. A public,
multi-user deployment would additionally require authentication, rate
limiting, resource controls, and production security hardening.

## Testing and validation

The current local verification completed:

- 46 Python `unittest` cases with the project virtual environment
- frontend TypeScript/Vite production build
- frontend Oxlint
- ExifTool availability check (`13.55` during verification)
- end-to-end browser walkthrough using synthetic GPS and no-GPS fixtures

These checks validate the current local state; they are not a claim of
independent forensic certification or exhaustive security testing.

## Limitations and future improvements

Current limitations include dependency on installed ExifTool format support,
metadata reliability, local-only security assumptions, map-provider requests
for displayed coordinates, and the absence of pixel-level authenticity
analysis.

Possible future work includes configurable resource limits, optional local
redaction profiles, more format-specific structural parsers, reference-image
comparison, stronger deployment hardening, and expanded cross-platform
integration tests.

## Short GitHub repository description

Local-first image forensics workspace for metadata, GPS, JPEG structure,
integrity, timeline, and explainable forensic indicators.

## Portfolio project description

PhotoTrace is a local-first digital forensics application I built to examine
the technical evidence embedded in image files. It combines a FastAPI/Python
analysis backend with a React/TypeScript interface, ExifTool metadata
extraction, Pillow validation, GPS visualization, SHA-256 integrity hashing,
JPEG structural inspection, timestamp timelines, and structured JSON reports.
The system emphasizes explainable findings and explicit limitations rather than
claiming to determine image authenticity automatically.

## Technical CV summary

Built PhotoTrace 2.0, a FastAPI and React/TypeScript image-forensics workspace
with ExifTool/Pillow processing, GPS and JPEG structural analysis, SHA-256
reporting, timeline consistency checks, local temporary-file handling, and
automated Python/frontend validation.

## LinkedIn announcement — English

I built PhotoTrace 2.0, a local-first image forensics workspace for examining
EXIF/XMP metadata, GPS coordinates, SHA-256 integrity, JPEG structure, and
metadata timelines. It combines a FastAPI/Python backend with a React and
TypeScript interface, explainable findings, and structured JSON reports.

The project is intentionally conservative: its results are forensic indicators
for review, not proof that an image is authentic or manipulated. I also added
safe synthetic fixtures, reproducible documentation, and local UI walkthrough
screenshots.

## LinkedIn announcement — Russian translation

Я разработала PhotoTrace 2.0 — локальное приложение для предварительного
форензик-анализа изображений. Оно анализирует EXIF/XMP-метаданные, GPS-
координаты, SHA-256, структуру JPEG и временную шкалу метаданных. Проект
объединяет backend на FastAPI/Python, интерфейс на React и TypeScript,
объяснимые findings и структурированные JSON-отчёты.

Проект намеренно не делает категоричных выводов: результаты являются
индикаторами для дальнейшего анализа, а не доказательством подлинности или
редактирования изображения. Также подготовлены безопасные synthetic fixtures,
воспроизводимая документация и screenshots локального интерфейса.
