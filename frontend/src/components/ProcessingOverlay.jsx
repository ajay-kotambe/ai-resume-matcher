import { cn } from '../utils/cn'

const STATUS = {
  done: { ring: 'bg-emerald-500', text: 'text-emerald-700', label: 'Complete' },
  active: { ring: 'bg-brand-500 animate-pulse', text: 'text-brand-700', label: 'In progress' },
  pending: { ring: 'bg-slate-300', text: 'text-slate-400', label: 'Waiting' },
}

/** Full-screen progress indicator for the analysis pipeline. */
export default function ProcessingOverlay({ stages, activeStage, uploadPercent, fileCount = 0 }) {
  const isDone = activeStage === 'done'

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4 backdrop-blur-sm"
      role="status"
      aria-live="polite"
    >
      <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl">
        <div className="flex items-center gap-3">
          {isDone ? (
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-emerald-100">
              <svg className="h-6 w-6 text-emerald-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
                <path strokeLinecap="round" strokeLinejoin="round" d="m5 13 4 4L19 7" />
              </svg>
            </span>
          ) : (
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-brand-100">
              <svg className="h-5 w-5 animate-spin text-brand-600" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
              </svg>
            </span>
          )}
          <div>
            <h2 className="text-base font-semibold text-slate-900">
              {isDone ? 'Analysis complete' : 'Analysing candidates'}
            </h2>
            <p className="text-sm text-slate-500">
              {isDone
                ? 'Ranking and explanations are ready.'
                : `Processing ${fileCount || 'your'} resume${fileCount === 1 ? '' : 's'}. Large batches can take a minute.`}
            </p>
          </div>
        </div>

        {!isDone && (
          <div className="mt-5">
            <div className="flex items-center justify-between text-xs text-slate-500">
              <span>Uploading</span>
              <span className="tabular-nums">{uploadPercent}%</span>
            </div>
            <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-slate-100">
              <div
                className="h-full rounded-full bg-brand-500 transition-all duration-300"
                style={{ width: `${Math.min(100, uploadPercent)}%` }}
              />
            </div>
          </div>
        )}

        <ol className="mt-5 space-y-2.5">
          {stages.map((stage) => {
            const status = STATUS[stage.status] ?? STATUS.pending
            return (
              <li key={stage.key} className="flex items-center gap-3">
                <span className={cn('h-2.5 w-2.5 shrink-0 rounded-full', status.ring)} />
                <span className={cn('flex-1 text-sm', status.text)}>{stage.label}</span>
                <span className="text-xs text-slate-400">{status.label}</span>
              </li>
            )
          })}
        </ol>
      </div>
    </div>
  )
}
