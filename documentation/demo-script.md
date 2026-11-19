# PhotoTrace 2.0.0 demonstration script

This script uses only the synthetic fixtures in `samples/`. It does not use
private photographs or claim that any finding proves manipulation.

## Preparation

1. Install ExifTool and verify it with `exiftool -ver`.
2. Install backend dependencies:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   python -m pip install -r requirements.txt
   ```

3. Install frontend dependencies:

   ```bash
   npm --prefix frontend install
   ```

4. Start the API:

   ```bash
   .venv/bin/python -m uvicorn backend.main:app \
     --host 127.0.0.1 --port 8000
   ```

5. In a second terminal, start the frontend:

   ```bash
   npm --prefix frontend run dev
   ```

6. Open `http://localhost:5173`.

## Recommended presentation order

### 1. Dashboard

Explain that the application is local-first and that the dashboard summarizes
the current analysis status.

Expected result after analysis: the dashboard shows the metadata field count,
valid GPS status, and the number of findings.

### 2. Image Analysis

Upload `samples/demo_gps.jpg` and click **Run forensic analysis**.

Expected result:

- The synthetic image preview is shown.
- The file is identified as `demo_gps.jpg`.
- The report shows JPEG format, 960 × 640 dimensions, a SHA-256 hash, and valid
  GPS status.
- Processing completes through the local API.

### 3. Metadata Explorer

Open **Metadata Explorer** and leave sensitive metadata hidden for the initial
overview.

Expected result: ExifTool fields show the synthetic camera, software,
timestamps, dimensions, and GPS fields. The values are fixture data, not a
real camera record.

### 4. GPS & Location

Open **GPS & Location**.

Expected result:

- Latitude is `51.5`.
- Longitude is `-0.125`.
- The Leaflet map displays the extracted coordinate.
- The page states that the marker reflects metadata and is not inferred by
  visual geolocation.

The map provider may receive map-coordinate requests from the browser. The
image and metadata are not uploaded by PhotoTrace.

### 5. Integrity Analysis

Open **Integrity Analysis**.

Expected result:

- The SHA-256 digest is displayed.
- JPEG structure is complete.
- An SOF marker, dimensions, marker count, and thumbnail status are shown.

Explain that a hash identifies the analyzed file contents; it does not prove
the origin or authenticity of the image.

### 6. Advanced Forensic Analysis

Open **Advanced Forensic Analysis**.

Expected result:

- The timeline contains the synthetic capture and creation dates.
- Duplicate timestamps and missing fields may be reported.
- JPEG marker details and quantization-table observations are shown.
- Each finding includes limitations.

Emphasize that the findings are contextual indicators. They are not pixel-level
authentication, error-level analysis, or proof of editing.

### 7. Forensic Reports

Open **Forensic Reports** and select **Download report**.

Expected result:

- The JSON preview contains the same report version and file hash.
- The download uses a safe `demo_gps_report.json` filename.
- The report includes metadata, GPS state, integrity findings, advanced analysis,
  and method limitations.

Review the downloaded JSON locally and do not publish it without checking for
GPS, device, author, or other sensitive metadata.

## Optional comparison scenario

Repeat the workflow with `samples/demo_no_gps.jpg`.

Expected result: GPS status is `missing`, the map shows the no-coordinate state,
and the rest of the metadata and structural analysis remains available.

## Cleanup

Stop both local development processes after the demonstration. The API writes
uploads to temporary directories and removes them after each request.
