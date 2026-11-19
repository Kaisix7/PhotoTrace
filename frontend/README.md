# PhotoTrace frontend

This directory contains the React 19 and TypeScript frontend for PhotoTrace.
Vite provides the development server and production build. React-Leaflet
renders the map when an analyzed image contains valid GPS coordinates.

## Development

Install dependencies and start the frontend from the project root:

```bash
npm --prefix frontend install
npm --prefix frontend run dev
```

The Vite development server runs on `http://localhost:5173` and proxies API
requests to the local FastAPI backend at `http://localhost:8000`.

## Verification

```bash
npm --prefix frontend run build
npm --prefix frontend run lint
```

The production build is written to `frontend/dist/`. The backend serves that
directory automatically when it exists.
