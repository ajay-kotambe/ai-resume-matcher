import { Link } from 'react-router-dom'
import ScoreRing from './ScoreRing'
import ScoreBreakdown from './ScoreBreakdown'
import { cn, EMPTY } from '../utils/cn'

function SkillChips({ skills, max = 6 }) {
  if (!skills?.length) return <span className="text-sm text-slate-400">No skills extracted</span>
  const shown = skills.slice(0, max)
  const rest = skills.length - shown.length

  return (
    <div className="flex flex-wrap gap-1.5">
      {shown.map((skill) => (
        <span
          key={skill}
          className="rounded-md bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-700 ring-1 ring-inset ring-slate-200"
        >
          {skill}
        </span>
      ))}
      {rest > 0 && (
        <span className="rounded-md px-2 py-0.5 text-xs font-medium text-slate-500">+{rest} more</span>
      )}
    </div>
  )
}

export default function CandidateCard({ entry, defaultOpenBreakdown = false }) {
  const { candidate, match, resume, rank, explanation } = entry
  const missingCount = match?.missing_skills?.length ?? 0
  const matchedCount = match?.matching_skills?.length ?? 0

  return (
    <article className="card transition-shadow hover:shadow-md">
      <div className="flex items-start gap-4">
        <div className="relative shrink-0">
          <ScoreRing score={match?.overall_score ?? 0} size={72} strokeWidth={7} />
          {rank > 0 && (
            <span className="absolute -left-1 -top-1 flex h-5 w-5 items-center justify-center rounded-full bg-slate-900 text-[10px] font-bold text-white">
              {rank}
            </span>
          )}
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div className="min-w-0">
              <h3 className="truncate text-base font-semibold text-slate-900">
                {candidate?.name || <span className="italic text-slate-400">Unnamed candidate</span>}
              </h3>
              <p className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs text-slate-500">
                {candidate?.email && <span className="truncate">{candidate.email}</span>}
                {candidate?.phone && <span>{candidate.phone}</span>}
                {candidate?.location && <span>{candidate.location}</span>}
              </p>
            </div>

            <Link
              to={`/candidates/${candidate?.candidate_uid}`}
              className="btn-ghost shrink-0 px-3 py-1.5 text-xs"
            >
              View profile
            </Link>
          </div>

          <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-2 text-xs sm:grid-cols-4">
            <div>
              <dt className="text-slate-400">Experience</dt>
              <dd className="font-medium tabular-nums text-slate-700">
                {candidate?.years_of_experience ? `${candidate.years_of_experience} yrs` : EMPTY}
              </dd>
            </div>
            <div>
              <dt className="text-slate-400">Skills matched</dt>
              <dd className="font-medium tabular-nums text-slate-700">
                {matchedCount}
                {missingCount > 0 && <span className="text-rose-500"> / {matchedCount + missingCount}</span>}
              </dd>
            </div>
            <div>
              <dt className="text-slate-400">Education</dt>
              <dd className="font-medium text-slate-700">
                {candidate?.education?.length
                  ? candidate.education[0]?.degree?.split('|')[0]?.trim() || 'Present'
                  : EMPTY}
              </dd>
            </div>
            <div>
              <dt className="text-slate-400">Source</dt>
              <dd className={cn('truncate font-medium text-slate-700')} title={resume?.original_filename}>
                {resume?.original_filename ?? EMPTY}
              </dd>
            </div>
          </dl>

          <div className="mt-3">
            <SkillChips skills={candidate?.skills} />
          </div>

          {explanation && (
            <p className="mt-3 border-l-2 border-brand-200 pl-3 text-sm leading-relaxed text-slate-600">
              {explanation}
            </p>
          )}

          <div className="mt-4 border-t border-slate-100 pt-3">
            <ScoreBreakdown match={match} weights={match?.weights} defaultOpen={defaultOpenBreakdown} />
          </div>
        </div>
      </div>
    </article>
  )
}
