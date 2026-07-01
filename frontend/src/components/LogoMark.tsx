export default function LogoMark({ size = 28 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" fill="none" className="logo-mark">
      <rect x="1" y="1" width="30" height="30" rx="9" fill="url(#qm-grad)" />
      <path
        className="logo-spark"
        d="M16 8.5l1.9 5.6 5.6 1.9-5.6 1.9-1.9 5.6-1.9-5.6-5.6-1.9 5.6-1.9L16 8.5z"
        fill="#fff"
        fillOpacity="0.96"
      />
      <defs>
        <linearGradient id="qm-grad" x1="0" y1="0" x2="32" y2="32" gradientUnits="userSpaceOnUse">
          <stop offset="0%" style={{ stopColor: 'var(--accent)' }} />
          <stop offset="100%" style={{ stopColor: 'var(--accent-strong)' }} />
        </linearGradient>
      </defs>
    </svg>
  )
}
