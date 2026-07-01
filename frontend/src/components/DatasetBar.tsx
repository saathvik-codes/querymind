import { useEffect, useRef, useState } from 'react'
import type { DatasetInfo } from '../types'

function DatabaseIcon({ size = 13 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <ellipse cx="12" cy="5" rx="8" ry="3" />
      <path d="M4 5v14c0 1.66 3.58 3 8 3s8-1.34 8-3V5M4 12c0 1.66 3.58 3 8 3s8-1.34 8-3" />
    </svg>
  )
}

export default function DatasetBar({
  datasets,
  activeDatasetId,
  onSelect,
  onUpload,
}: {
  datasets: DatasetInfo[]
  activeDatasetId: string
  onSelect: (id: string) => void
  onUpload: (file: File) => Promise<void>
}) {
  const fileInputRef = useRef<HTMLInputElement>(null)
  const menuRef = useRef<HTMLDivElement>(null)
  const [menuOpen, setMenuOpen] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const active = datasets.find((d) => d.dataset_id === activeDatasetId) ?? datasets[0]

  useEffect(() => {
    if (!menuOpen) return
    function onClickOutside(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) setMenuOpen(false)
    }
    document.addEventListener('mousedown', onClickOutside)
    return () => document.removeEventListener('mousedown', onClickOutside)
  }, [menuOpen])

  async function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file) return
    setUploading(true)
    setError(null)
    try {
      await onUpload(file)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed')
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="dataset-bar">
      <div className="dataset-select-wrap" ref={menuRef}>
        <button className="dataset-select-trigger" onClick={() => setMenuOpen((o) => !o)}>
          <DatabaseIcon />
          <span className="dataset-select-label">
            {active ? `${active.name} · ${active.row_count.toLocaleString()} rows` : 'Select dataset'}
          </span>
          <svg
            width="10"
            height="10"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.5"
            style={{ transform: menuOpen ? 'rotate(180deg)' : 'none', transition: 'transform .15s', flexShrink: 0 }}
          >
            <path d="M6 9l6 6 6-6" />
          </svg>
        </button>

        {menuOpen && (
          <div className="dataset-menu">
            {datasets.map((ds) => (
              <button
                key={ds.dataset_id}
                className={`dataset-menu-item ${ds.dataset_id === activeDatasetId ? 'active' : ''}`}
                onClick={() => {
                  onSelect(ds.dataset_id)
                  setMenuOpen(false)
                }}
              >
                <div className="dataset-menu-item-text">
                  <div className="dataset-menu-item-name">{ds.name}</div>
                  <div className="dataset-menu-item-rows">{ds.row_count.toLocaleString()} rows</div>
                </div>
                {ds.dataset_id === activeDatasetId && (
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                    <path d="M20 6L9 17l-5-5" />
                  </svg>
                )}
              </button>
            ))}
          </div>
        )}
      </div>

      <button className="upload-btn" onClick={() => fileInputRef.current?.click()} disabled={uploading}>
        {uploading ? (
          <span className="spinner spinner-dark" />
        ) : (
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M12 16V4M12 4l-4 4M12 4l4 4M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3" />
          </svg>
        )}
        {uploading ? 'Uploading…' : 'Upload CSV'}
      </button>
      <input ref={fileInputRef} type="file" accept=".csv" hidden onChange={handleFileChange} />

      {error && <div className="upload-error">{error}</div>}
    </div>
  )
}
