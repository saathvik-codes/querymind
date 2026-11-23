export default function LogoMark({ size = 28 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" fill="none" className="logo-mark" aria-hidden>
      <circle cx="14.5" cy="14.5" r="9" stroke="var(--text)" strokeWidth="2.6" />
      <path d="M21 21l7 7" stroke="var(--accent)" strokeWidth="3.2" strokeLinecap="square" />
    </svg>
  )
}
