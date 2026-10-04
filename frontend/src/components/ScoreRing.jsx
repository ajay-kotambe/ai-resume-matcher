import { cn, formatScore } from '../utils/cn'

/** Score -> ring colour. Mirrors the backend's banding for quick scanning. */
function toneFor(score) {
  if (score >= 75) return { ring: 'stroke-emerald-500', text: 'text-emerald-700', label: 'Strong' }
  if (score >= 50) return { ring: 'stroke-amber-500', text: 'text-amber-700', label: 'Moderate' }
  if (score > 0) return { ring: 'stroke-rose-400', text: 'text-rose-600', label: 'Weak' }
  return { ring: 'stroke-slate-300', text: 'text-slate-500', label: 'Unscored' }
}

export default function ScoreRing({ score = 0, size = 64, strokeWidth = 6, showLabel = false, className }) {
  const radius = (size - strokeWidth) / 2
  const circumference = 2 * Math.PI * radius
  const clamped = Math.max(0, Math.min(100, Number(score) || 0))
  const offset = circumference - (clamped / 100) * circumference
  const tone = toneFor(clamped)

  return (
    <div className={cn('relative inline-flex shrink-0 items-center justify-center', className)}>
      <svg width={size} height={size} className="-rotate-90" aria-hidden="true">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          strokeWidth={strokeWidth}
          className="stroke-slate-200"
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          className={cn(tone.ring, 'transition-[stroke-dashoffset] duration-700 ease-out')}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className={cn('font-bold leading-none tabular-nums', tone.text)} style={{ fontSize: size * 0.28 }}>
          {formatScore(clamped)}
        </span>
        {showLabel && (
          <span className="mt-0.5 text-[9px] font-semibold uppercase tracking-wide text-slate-400">
            {tone.label}
          </span>
        )}
      </div>
      <span className="sr-only">Match score {formatScore(clamped)} out of 100, {tone.label}</span>
    </div>
  )
}
