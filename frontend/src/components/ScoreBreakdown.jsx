import { useState } from 'react'
import { SCORE_COMPONENTS as COMPONENTS } from '../utils/scoring'
import { cn, formatScore } from '../utils/cn'

function SkillGroup({ title, skills, tone }) {
  if (!skills?.length) return null
  return (
    <div>
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
        {title} <span className="tabular-nums text-slate-400">({skills.length})</span>
      </p>
      <div className="mt-1.5 flex flex-wrap gap-1.5">
        {skills.map((skill) => (
          <span
            key={skill}
            className={cn(
              'rounded-md px-2 py-0.5 text-xs font-medium',
              tone === 'good' && 'bg-emerald-50 text-emerald-700 ring-1 ring-inset ring-emerald-600/20',
              tone === 'warn' && 'bg-amber-50 text-amber-800 ring-1 ring-inset ring-amber-600/20',
              tone === 'bad' && 'bg-rose-50 text-rose-700 ring-1 ring-inset ring-rose-600/20',
              tone === 'neutral' && 'bg-slate-100 text-slate-600 ring-1 ring-inset ring-slate-300',
            )}
          >
            {skill}
          </span>
        ))}
      </div>
    </div>
  )
}

export default function ScoreBreakdown({ match, weights = {}, defaultOpen = false }) {
  const [open, setOpen] = useState(defaultOpen)
  if (!match) return null

  const groups = [
    { title: 'Matched skills', skills: match.matching_skills, tone: 'good' },
    { title: 'Partially matched', skills: match.partial_skills, tone: 'warn' },
    { title: 'Missing skills', skills: match.missing_skills, tone: 'bad' },
    { title: 'Additional skills', skills: match.extra_skills, tone: 'neutral' },
  ].filter((group) => group.skills?.length)

  return (
    <div className="space-y-4">
      <div>
        <button
          type="button"
          onClick={() => setOpen((value) => !value)}
          aria-expanded={open}
          className="flex w-full items-center justify-between text-xs font-semibold uppercase tracking-wide text-slate-500 hover:text-slate-700"
        >
          <span>How this score was calculated</span>
          <svg
            className={cn('h-4 w-4 transition-transform', open && 'rotate-180')}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth="2"
            aria-hidden="true"
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="m19 9-7 7-7-7" />
          </svg>
        </button>

        {open && (
          <ul className="mt-3 space-y-2.5">
            {COMPONENTS.map((component) => {
              const value = match[component.key] ?? 0
              const weight = weights[component.key]
              return (
                <li key={component.key} title={component.hint}>
                  <div className="flex items-baseline justify-between gap-2 text-xs">
                    <span className="font-medium text-slate-700">{component.label}</span>
                    <span className="tabular-nums text-slate-500">
                      {formatScore(value)}
                      {weight !== undefined && (
                        <span className="ml-1 text-slate-400">
                          (w {Number(weight).toFixed(2)})
                        </span>
                      )}
                    </span>
                  </div>
                  <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-slate-100">
                    <div
                      className={cn(
                        'h-full rounded-full transition-all duration-500',
                        value >= 75 && 'bg-emerald-500',
                        value >= 50 && value < 75 && 'bg-amber-500',
                        value > 0 && value < 50 && 'bg-rose-400',
                        value <= 0 && 'bg-slate-300',
                      )}
                      style={{ width: `${Math.max(0, Math.min(100, value))}%` }}
                    />
                  </div>
                </li>
              )
            })}
          </ul>
        )}
      </div>

      {groups.length > 0 && (
        <div className="space-y-3 border-t border-slate-100 pt-4">
          {groups.map((group) => (
            <SkillGroup key={group.title} {...group} />
          ))}
        </div>
      )}
    </div>
  )
}
