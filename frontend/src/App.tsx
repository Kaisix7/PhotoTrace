import { useRef, useState, type ChangeEvent, type DragEvent, type ReactNode } from 'react'
import { MapContainer, Marker, TileLayer } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'
import L from 'leaflet'
import './App.css'

type Section =
  | 'Dashboard'
  | 'Image Analysis'
  | 'Metadata Explorer'
  | 'GPS & Location'
  | 'Integrity Analysis'
  | 'Advanced Forensic Analysis'
  | 'Forensic Reports'

type Finding = {
  severity: 'Informational' | 'Warning' | 'Suspicious'
  title: string
  explanation: string
  evidence: Record<string, unknown>
  limitations?: string
}

type Report = {
  tool: string
  version: string
  analysis_timestamp: string
  original_filename: string
  file: Record<string, unknown>
  metadata: Record<string, unknown>
  gps: {
    status: 'missing' | 'invalid' | 'valid'
    latitude: number | null
    longitude: number | null
    altitude: number | null
    maps_url: string | null
    message: string | null
  }
  integrity_findings: Finding[]
  advanced_analysis: {
    timeline: {
      events: Array<Record<string, unknown>>
      timezone_ambiguous: boolean
      missing_timestamp_fields: string[]
      chronological_conflicts: Array<Record<string, unknown>>
      duplicate_timestamp_fields: Array<Record<string, unknown>>
    }
    image_structure: Record<string, unknown>
    findings: Finding[]
    method_limitations: string[]
  }
  summary: {
    metadata_field_count: number
    finding_counts: Record<string, number>
    statement: string
  }
}

const sections: Section[] = [
  'Dashboard',
  'Image Analysis',
  'Metadata Explorer',
  'GPS & Location',
  'Integrity Analysis',
  'Advanced Forensic Analysis',
  'Forensic Reports',
]

const markerIcon = L.divIcon({
  className: 'phototrace-marker',
  html: '<span></span>',
  iconSize: [28, 28],
  iconAnchor: [14, 14],
})

function Icon({ name }: { name: Section | 'Upload' | 'Shield' | 'Report' }) {
  const paths: Record<string, ReactNode> = {
    Dashboard: <><rect x="3" y="3" width="7" height="7" rx="2"/><rect x="14" y="3" width="7" height="7" rx="2"/><rect x="3" y="14" width="7" height="7" rx="2"/><rect x="14" y="14" width="7" height="7" rx="2"/></>,
    'Image Analysis': <><rect x="3" y="4" width="18" height="16" rx="3"/><circle cx="8.5" cy="9" r="1.5"/><path d="M21 15l-5-5L5 20"/></>,
    'Metadata Explorer': <><path d="M4 5h16M4 12h16M4 19h16"/><circle cx="8" cy="5" r="1"/><circle cx="16" cy="12" r="1"/><circle cx="10" cy="19" r="1"/></>,
    'GPS & Location': <><path d="M20 10c0 5-8 11-8 11S4 15 4 10a8 8 0 1116 0z"/><circle cx="12" cy="10" r="2.5"/></>,
    'Integrity Analysis': <><path d="M12 3l7 3v5c0 5-3 8-7 10-4-2-7-5-7-10V6l7-3z"/><path d="M9 12l2 2 4-4"/></>,
    'Advanced Forensic Analysis': <><path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/><path d="M2 10l8-6 6 9 6-5"/></>,
    'Forensic Reports': <><path d="M6 3h9l4 4v14H6z"/><path d="M15 3v5h5M9 13h7M9 17h7"/></>,
    Upload: <><path d="M12 16V4M7 9l5-5 5 5"/><path d="M5 20h14"/></>,
  }
  return <svg viewBox="0 0 24 24" aria-hidden="true">{paths[name]}</svg>
}

function GlassPanel({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <section className={`glass-panel ${className}`}>{children}</section>
}

function FindingList({ findings }: { findings: Finding[] }) {
  if (!findings.length) {
    return <div className="empty-state">No forensic findings were triggered.</div>
  }
  return (
    <div className="finding-list">
      {findings.map((finding, index) => (
        <article className={`finding severity-${finding.severity.toLowerCase()}`} key={`${finding.title}-${index}`}>
          <div className="finding-heading">
            <span className="severity-dot" />
            <div>
              <span className="finding-severity">{finding.severity}</span>
              <h3>{finding.title}</h3>
            </div>
          </div>
          <p>{finding.explanation}</p>
          <div className="evidence-grid">
            {Object.entries(finding.evidence).map(([key, value]) => (
              <div key={key}><span>{key.replaceAll('_', ' ')}</span><strong>{typeof value === 'object' ? JSON.stringify(value) : String(value)}</strong></div>
            ))}
          </div>
          {finding.limitations && <small>Limitations: {finding.limitations}</small>}
        </article>
      ))}
    </div>
  )
}

function App() {
  const [active, setActive] = useState<Section>('Dashboard')
  const [report, setReport] = useState<Report | null>(null)
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [dragging, setDragging] = useState(false)
  const [showSensitive, setShowSensitive] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const apiBase =
    (import.meta.env.VITE_API_URL as string | undefined)
    || (window.location.port === '5173'
      ? 'http://localhost:8000'
      : window.location.origin)

  const selectFile = (selected: File) => {
    setFile(selected)
    setError('')
    setReport(null)
    if (preview) URL.revokeObjectURL(preview)
    setPreview(URL.createObjectURL(selected))
  }

  const onFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    const selected = event.target.files?.[0]
    if (selected) selectFile(selected)
  }

  const onDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault()
    setDragging(false)
    const selected = event.dataTransfer.files?.[0]
    if (selected) selectFile(selected)
  }

  const analyze = async () => {
    if (!file) return
    setLoading(true)
    setError('')
    try {
      const form = new FormData()
      form.append('file', file)
      const response = await fetch(`${apiBase}/api/analyze`, { method: 'POST', body: form })
      const data = await response.json()
      if (!response.ok) throw new Error(data.detail || 'The image could not be analyzed.')
      setReport(data)
      setActive('Dashboard')
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'The image could not be analyzed.')
    } finally {
      setLoading(false)
    }
  }

  const downloadReport = async () => {
    if (!file) return
    const form = new FormData()
    form.append('file', file)
    const response = await fetch(`${apiBase}/api/reports/download`, { method: 'POST', body: form })
    if (!response.ok) {
      setError('The report could not be downloaded.')
      return
    }
    const blob = await response.blob()
    const disposition = response.headers.get('Content-Disposition') || ''
    const match = disposition.match(/filename="([^"]+)"/)
    const link = document.createElement('a')
    link.href = URL.createObjectURL(blob)
    link.download = match?.[1] || `${file.name.replace(/\.[^.]+$/, '')}_report.json`
    link.click()
    URL.revokeObjectURL(link.href)
  }

  const gps = report?.gps
  const advanced = report?.advanced_analysis
  const metadataEntries = report ? Object.entries(report.metadata).filter(([key]) => {
    if (showSensitive) return true
    const lowered = key.toLowerCase()
    return !['serial', 'owner', 'credit', 'copyright'].some((token) => lowered.includes(token))
  }) : []

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <button className="brand" onClick={() => setActive('Dashboard')} aria-label="Open dashboard">
          <span className="brand-mark">PT</span>
          <span><strong>PhotoTrace</strong><small>Digital Forensics</small></span>
        </button>
        <nav>
          {sections.map((section) => (
            <button key={section} className={active === section ? 'nav-item active' : 'nav-item'} onClick={() => setActive(section)}>
              <Icon name={section} /><span>{section}</span>
            </button>
          ))}
        </nav>
        <div className="sidebar-footer"><span>Version</span><strong>2.0.0</strong></div>
      </aside>

      <main className="main-content">
        <header className="topbar">
          <div><span className="eyebrow">FORENSIC WORKSPACE</span><h1>{active}</h1></div>
          <div className="privacy-badge"><span />Local processing</div>
        </header>

        {active === 'Dashboard' && (
          <div className="page-grid">
            <GlassPanel className="welcome-panel">
              <div>
                <span className="eyebrow">PHOTO FORENSICS</span>
                <h2>Examine the evidence behind the image.</h2>
                <p>Upload an image for local metadata, GPS, timeline, and structural analysis.</p>
              </div>
              <button className="primary-button" onClick={() => setActive('Image Analysis')}>Begin analysis <span>→</span></button>
            </GlassPanel>
            <GlassPanel className="status-panel">
              <div className="panel-label">ANALYSIS STATUS</div>
              {report ? (
                <>
                  <div className="status-ring"><span>{report.summary.metadata_field_count}</span><small>metadata fields</small></div>
                  <div className="status-row"><span>GPS</span><strong className={`gps-${gps?.status}`}>{gps?.status}</strong></div>
                  <div className="status-row"><span>Findings</span><strong>{report.integrity_findings.length + (advanced?.findings.length || 0)}</strong></div>
                </>
              ) : (
                <div className="empty-state">No image analyzed yet</div>
              )}
            </GlassPanel>
            <GlassPanel className="overview-panel">
              <div className="panel-heading"><div><span className="eyebrow">OVERVIEW</span><h2>Forensic modules</h2></div></div>
              <div className="module-grid">
                {[
                  ['Metadata', 'EXIF, XMP and file properties'],
                  ['Location', 'Validated GPS coordinates'],
                  ['Integrity', 'JPEG structure and SHA-256'],
                  ['Timeline', 'Capture and modification dates'],
                ].map(([title, copy]) => (
                  <button key={title} onClick={() => setActive(title === 'Location' ? 'GPS & Location' : title === 'Integrity' ? 'Integrity Analysis' : title === 'Timeline' ? 'Advanced Forensic Analysis' : 'Metadata Explorer')}>
                    <span className="module-icon"><Icon name={title === 'Location' ? 'GPS & Location' : title === 'Integrity' ? 'Integrity Analysis' : title === 'Timeline' ? 'Advanced Forensic Analysis' : 'Metadata Explorer'} /></span>
                    <span><strong>{title}</strong><small>{copy}</small></span>
                  </button>
                ))}
              </div>
            </GlassPanel>
          </div>
        )}

        {active === 'Image Analysis' && (
          <div className="analysis-layout">
            <GlassPanel className="upload-panel">
              <div
                className={dragging ? 'drop-zone dragging' : 'drop-zone'}
                onDragEnter={() => setDragging(true)}
                onDragLeave={() => setDragging(false)}
                onDragOver={(event) => event.preventDefault()}
                onDrop={onDrop}
                onClick={() => inputRef.current?.click()}
                role="button"
                tabIndex={0}
              >
                <input ref={inputRef} type="file" accept=".jpg,.jpeg,.png,.tif,.tiff,.webp,.bmp,.gif,.avif,.cr2,.cr3,.dng,.nef,.orf,.raf,.raw,.heic,.heif" onChange={onFileChange} />
                {preview ? <img src={preview} alt="Selected image preview" /> : <span className="upload-icon"><Icon name="Upload" /></span>}
                <div><strong>{file ? file.name : 'Drop an image here'}</strong><small>{file ? `${(file.size / 1024).toFixed(1)} KB` : 'JPEG, PNG, TIFF, RAW and supported formats · 50 MB maximum'}</small></div>
              </div>
              {error && <div className="error-banner">{error}</div>}
              <button className="primary-button full" onClick={analyze} disabled={!file || loading}>{loading ? 'Analyzing locally…' : 'Run forensic analysis'}</button>
            </GlassPanel>
            {report && <GlassPanel className="analysis-result">
              <div className="panel-heading"><div><span className="eyebrow">ANALYSIS COMPLETE</span><h2>{report.original_filename}</h2></div><span className="verified-label">Processed locally</span></div>
              <div className="result-grid">
                <div><span>SHA-256</span><code>{String(report.file.sha256)}</code></div>
                <div><span>Format</span><strong>{String(report.file.format)}</strong></div>
                <div><span>Dimensions</span><strong>{String(report.file.width)} × {String(report.file.height)}</strong></div>
                <div><span>GPS</span><strong className={`gps-${gps?.status}`}>{gps?.status}</strong></div>
              </div>
            </GlassPanel>}
          </div>
        )}

        {active === 'Metadata Explorer' && (
          <GlassPanel>
            <div className="panel-heading"><div><span className="eyebrow">EXTRACTED TAGS</span><h2>Metadata Explorer</h2></div><label className="toggle"><input type="checkbox" checked={showSensitive} onChange={(event) => setShowSensitive(event.target.checked)} /><span />Sensitive metadata</label></div>
            {!report ? <div className="empty-state">Analyze an image to inspect metadata.</div> : <div className="metadata-grid">{metadataEntries.map(([key, value]) => <div className="metadata-row" key={key}><span>{key}</span><code>{typeof value === 'object' ? JSON.stringify(value) : String(value)}</code></div>)}</div>}
          </GlassPanel>
        )}

        {active === 'GPS & Location' && (
          <GlassPanel className="map-panel">
            <div className="panel-heading"><div><span className="eyebrow">GEOGRAPHIC DATA</span><h2>GPS & Location</h2></div></div>
            {!report ? <div className="empty-state">Analyze an image to inspect GPS metadata.</div> : gps?.status === 'valid' ? (
              <>
                <div className="coordinate-row"><div><span>Latitude</span><strong>{gps.latitude}</strong></div><div><span>Longitude</span><strong>{gps.longitude}</strong></div><div><span>Altitude</span><strong>{gps.altitude ?? 'Not available'}</strong></div></div>
                <MapContainer key={`${gps.latitude}-${gps.longitude}`} center={[gps.latitude!, gps.longitude!]} zoom={12} scrollWheelZoom>
                  <TileLayer attribution="&copy; OpenStreetMap contributors" url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
                  <Marker position={[gps.latitude!, gps.longitude!]} icon={markerIcon} />
                </MapContainer>
                <p className="map-note">Marker placement reflects extracted coordinates only. Location is not inferred.</p>
              </>
            ) : <div className="empty-map"><span>NO VALID COORDINATES</span><p>{gps?.message || 'GPS metadata is unavailable.'}</p></div>}
          </GlassPanel>
        )}

        {active === 'Integrity Analysis' && (
          <div className="integrity-layout">
            <GlassPanel><span className="eyebrow">FILE INTEGRITY</span><h2>SHA-256</h2>{report ? <code className="hash-value">{String(report.file.sha256)}</code> : <div className="empty-state">No image analyzed.</div>}</GlassPanel>
            <GlassPanel><span className="eyebrow">JPEG STRUCTURE</span><h2>Structural Analysis</h2>{!advanced ? <div className="empty-state">No structure data available.</div> : <div className="structure-grid">{Object.entries(advanced.image_structure).filter(([, value]) => typeof value !== 'object').slice(0, 12).map(([key, value]) => <div key={key}><span>{key.replaceAll('_', ' ')}</span><strong>{String(value)}</strong></div>)}</div>}</GlassPanel>
          </div>
        )}

        {active === 'Advanced Forensic Analysis' && (
          <div className="advanced-layout">
            <GlassPanel><div className="panel-heading"><div><span className="eyebrow">FORENSIC INDICATORS</span><h2>Advanced Findings</h2></div></div>{advanced ? <FindingList findings={advanced.findings} /> : <div className="empty-state">Analyze an image for advanced findings.</div>}</GlassPanel>
            <GlassPanel><span className="eyebrow">METADATA TIMELINE</span><h2>Timeline</h2>{advanced?.timeline.events.length ? <div className="timeline">{advanced.timeline.events.map((event, index) => <div key={index}><span>{String(event.source)}</span><strong>{String(event.raw_value)}</strong><small>{String(event.status)}</small></div>)}</div> : <div className="empty-state">No timestamps available.</div>}</GlassPanel>
            <GlassPanel><span className="eyebrow">JPEG STRUCTURE</span><h2>Image Structure</h2>{advanced?.image_structure && Object.keys(advanced.image_structure).length ? <pre className="report-code">{JSON.stringify(advanced.image_structure, null, 2)}</pre> : <div className="empty-state">No image structure available.</div>}</GlassPanel>
            <GlassPanel><span className="eyebrow">DETECTION LIMITATIONS</span><h2>Methodology</h2>{advanced?.method_limitations.map((limit) => <p className="limitation" key={limit}>{limit}</p>) || <div className="empty-state">No limitations loaded.</div>}</GlassPanel>
          </div>
        )}

        {active === 'Forensic Reports' && (
          <GlassPanel>
            <div className="panel-heading"><div><span className="eyebrow">FORENSIC EXPORT</span><h2>JSON Report</h2></div>{report && file && <button className="primary-button" onClick={downloadReport}>Download report</button>}</div>
            {!report ? <div className="empty-state">Analyze an image to generate a forensic report.</div> : <><div className="report-summary"><div><span>Original filename</span><strong>{report.original_filename}</strong></div><div><span>Analysis timestamp</span><strong>{report.analysis_timestamp}</strong></div><div><span>Report version</span><strong>{report.version}</strong></div></div><pre className="report-code">{JSON.stringify(report, null, 2)}</pre></>}
          </GlassPanel>
        )}
      </main>
    </div>
  )
}

export default App
