export function BrandMark({ size = 18 }: { size?: number }) {
  return (
    <div className="brand-mark">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" width={size} height={size}
        strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 2L4 6v6c0 5 3.5 9 8 10 4.5-1 8-5 8-10V6l-8-4z" />
        <path d="M9 12l2 2 4-4" />
      </svg>
    </div>
  )
}
