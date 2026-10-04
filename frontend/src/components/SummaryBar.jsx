import { cn, formatScore } from '../utils/cn'

function Stat({ label, value, suffix, tone = 'slate' }) {
  const tones = {
    slate: 'text-slate-900',
    brand: 'text-brand-700',
    emerald: 'text-emerald-700',
    amber: 'text-amber-700',
  }
  return (
    <div className="rounded-lg bg-slate-50 px-3 py-2.5">
      <p className="text-[11px] font-medium uppercase tracking-wide text-slate-500">{label}</p>
      <p className={cn('mt-0.5 text-lg font-bold tabular-nums', tones[tone])}>
        {value}
        {suffix && <span className="ml-0.5 text-xs font-medium text-slate-400">{suffix}</span>}
      </p>
    </div>
  )
}

/** Aggregate statistics for a ranked result set. */
export default function SummaryBar({ summary, className }) {
  if (!summary || !summary.total_candidates) return null

  return (
    <div className={cn('card', className)}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-sm font-semibold text-slate-900">Shortlist summary</h2>
        <span className="text-xs text-slate-500">
          {summary.total_candidates} candidate{summary.total_candidates === 1 ? '' : 's'} scored
        </span>
      </div>

      <div className="mt-3 grid grid-cols-2 gap-2.5 sm:grid-cols-3 lg:grid-cols-6">
        <Stat label="Top score" value={formatScore(summary.top_score)} suffix="%" tone="emerald" />
        <Stat label="Average" value={formatScore(summary.average_match)} suffix="%" tone="brand" />
        <Stat label="Median" value={formatScore(summary.median_score)} suffix="%" />
        <Stat label="Lowest" value={formatScore(summary.lowest_score)} suffix="%" />
        <Stat label="Above 70%" value={summary.above_70 ?? 0} tone="emerald" />
        <Stat label="Above 50%" value={summary.above_50 ?? 0} tone="amber" />
      </div>
    </div>
  )
}
