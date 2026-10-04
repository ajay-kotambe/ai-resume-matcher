import { useState } from 'react'
import { EMPTY } from '../utils/cn'

function Chips({ title, items, tone = 'brand' }) {
  if (!items?.length) return null
  const tones = {
    brand: 'bg-brand-50 text-brand-700 ring-brand-600/20',
    emerald: 'bg-emerald-50 text-emerald-700 ring-emerald-600/20',
    slate: 'bg-slate-100 text-slate-600 ring-slate-300',
  }
  return (
    <div>
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
        {title} <span className="tabular-nums text-slate-400">({items.length})</span>
      </p>
      <div className="mt-1.5 flex flex-wrap gap-1.5">
        {items.map((item) => (
          <span key={item} className={`rounded-md px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${tones[tone]}`}>
            {item}
          </span>
        ))}
      </div>
    </div>
  )
}

/** Collapsible view of the parsed job requirements. */
export default function JobSummaryCard({ job, className }) {
  const [showRaw, setShowRaw] = useState(false)
  if (!job) return null

  return (
    <div className={`card ${className ?? ''}`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs font-semibold uppercase tracking-wide text-brand-600">Analysed role</p>
          <h2 className="mt-0.5 text-lg font-bold text-slate-900">
            {job.job_title || <span className="italic text-slate-400">Untitled role</span>}
          </h2>
          <p className="mt-0.5 text-sm text-slate-500">
            {[job.company, job.location].filter(Boolean).join(' · ') || EMPTY}
          </p>
        </div>

        <div className="text-right text-xs text-slate-500">
          {job.minimum_experience && (
            <p className="font-medium text-slate-700">{job.minimum_experience}</p>
          )}
          <p className="mt-0.5">
            via {job.extraction_method || 'auto'}
          </p>
        </div>
      </div>

      <div className="mt-4 space-y-4 border-t border-slate-100 pt-4">
        <Chips title="Required skills" items={job.required_skills} tone="brand" />
        <Chips title="Preferred skills" items={job.preferred_skills} tone="emerald" />

        {job.education_requirements?.length > 0 && (
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Education</p>
            <ul className="mt-1.5 space-y-1">
              {job.education_requirements.map((item) => (
                <li key={item} className="flex gap-2 text-sm text-slate-700">
                  <span aria-hidden="true" className="text-slate-400">•</span>
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {job.responsibilities?.length > 0 && (
          <details className="group">
            <summary className="cursor-pointer list-none text-xs font-semibold uppercase tracking-wide text-slate-500 hover:text-slate-700">
              Responsibilities ({job.responsibilities.length})
            </summary>
            <ol className="mt-2 list-decimal space-y-1 pl-5">
              {job.responsibilities.map((item) => (
                <li key={item} className="text-sm text-slate-700">
                  {item}
                </li>
              ))}
            </ol>
          </details>
        )}

        {job.warning && (
          <p className="rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-800 ring-1 ring-inset ring-amber-600/20">
            {job.warning}
          </p>
        )}

        <div>
          <button
            type="button"
            onClick={() => setShowRaw((value) => !value)}
            className="text-xs font-medium text-slate-500 hover:text-slate-700"
          >
            {showRaw ? 'Hide' : 'Show'} original job description
          </button>
          {showRaw && (
            <pre className="mt-2 max-h-72 overflow-auto whitespace-pre-wrap rounded-lg bg-slate-50 p-3 font-mono text-[11px] leading-relaxed text-slate-600 ring-1 ring-inset ring-slate-200">
              {job.raw_text}
            </pre>
          )}
        </div>
      </div>
    </div>
  )
}
