# GitHub release preparation

This document is a local checklist for a future public repository release. No
Git or GitHub operation is performed by the project preparation process.

## Suggested repository description

> Local-first image forensics workspace for metadata, GPS, JPEG structure,
> integrity, timeline, and explainable forensic indicators.

## Suggested topics

`python`, `fastapi`, `react`, `typescript`, `vite`, `digital-forensics`,
`image-metadata`, `exif`, `jpeg`, `osint`, `privacy`, `leaflet`

## Suggested public contents

Review and include:

- `README.md`
- `requirements.txt`
- `backend/`
- `phototrace_app/`
- `phototrace.py`
- `frontend/src/`, `frontend/public/`, and frontend configuration files
- `frontend/package.json` and `frontend/package-lock.json`
- `tests/`
- approved synthetic fixtures in `samples/`
- approved screenshots in `documentation/screenshots/`
- `documentation/release-notes-2.0.0.md`

## Review before publishing

- Review `gps_report.json` because it contains GPS coordinates and raw metadata.
- Review `reports/train_report.json` separately; it is a protected project file
  and must not be modified, regenerated, or deleted as part of this work.
- Do not publish private photographs, raw camera files, personal locations,
  device serial numbers, author fields, or credentials.
- Keep `.venv/`, `frontend/node_modules/`, `frontend/dist/`, caches, coverage
  output, and local editor files excluded by `.gitignore`.
- Confirm that no local environment file, secret, token, or private path is
  added before the owner performs Git operations.

## License decision

No license file has been added. A public repository should have an explicit
license decision before publication:

- **MIT** is concise and permissive, suitable when broad reuse with minimal
  conditions is preferred.
- **Apache-2.0** is permissive and adds an explicit patent license and notice
  requirements.
- **GPL-3.0** requires derivative distributions to remain under GPL-compatible
  copyleft terms.
- **No license** means default copyright restrictions apply; others generally
  cannot legally reuse, modify, or distribute the code.

The repository owner should choose the license after considering intended reuse,
third-party dependencies, and any portfolio or educational goals.

## Release checklist

- [ ] Review the final source tree and sensitive JSON artifacts.
- [ ] Confirm the selected license and add it manually.
- [ ] Review the suggested description and topics.
- [ ] Run the documented tests, build, and lint commands.
- [ ] Review the version and release notes for `2.0.0`.
- [ ] Perform Git commit, remote publication, and release creation manually.
