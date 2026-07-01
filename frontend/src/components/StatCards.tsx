import type { Row } from '../types'

function prettifyLabel(key: string): string {
  return key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
}

function formatValue(value: unknown): string {
  if (typeof value !== 'number') return String(value ?? '')
  const abs = Math.abs(value)
  if (!Number.isInteger(value)) return value.toLocaleString(undefined, { maximumFractionDigits: 2 })
  if (abs >= 1_000_000) return (value / 1_000_000).toLocaleString(undefined, { maximumFractionDigits: 2 }) + 'M'
  if (abs >= 10_000) return (value / 1_000).toLocaleString(undefined, { maximumFractionDigits: 1 }) + 'K'
  return value.toLocaleString()
}

export default function StatCards({ fields, row }: { fields: string[]; row: Row }) {
  return (
    <div className="stat-grid">
      {fields.map((key) => (
        <div className="stat-card" key={key}>
          <div className="stat-value">{formatValue(row[key])}</div>
          <div className="stat-label">{prettifyLabel(key)}</div>
        </div>
      ))}
    </div>
  )
}
