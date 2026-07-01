import type { ModeKey, PaletteKey, ThemeState } from '../types'

const PALETTES: { key: PaletteKey; color: string; label: string }[] = [
  { key: 'indigo', color: '#6366f1', label: 'Indigo' },
  { key: 'emerald', color: '#10b981', label: 'Emerald' },
  { key: 'violet', color: '#a855f7', label: 'Violet' },
  { key: 'amber', color: '#f59e0b', label: 'Amber' },
  { key: 'rose', color: '#f43f5e', label: 'Rose' },
]

export default function ThemeSwitcher({
  theme,
  onChange,
}: {
  theme: ThemeState
  onChange: (theme: ThemeState) => void
}) {
  const setMode = (mode: ModeKey) => onChange({ ...theme, mode })
  const setPalette = (palette: PaletteKey) => onChange({ ...theme, palette })

  return (
    <div className="theme-switcher">
      <div className="theme-palettes">
        {PALETTES.map((p) => (
          <button
            key={p.key}
            className={`palette-dot ${theme.palette === p.key ? 'active' : ''}`}
            style={{ background: p.color }}
            title={p.label}
            aria-label={`${p.label} palette`}
            onClick={() => setPalette(p.key)}
          />
        ))}
      </div>
      <button className="mode-toggle" onClick={() => setMode(theme.mode === 'dark' ? 'light' : 'dark')}>
        {theme.mode === 'dark' ? (
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="5" />
            <path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" />
          </svg>
        ) : (
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
          </svg>
        )}
      </button>
    </div>
  )
}
