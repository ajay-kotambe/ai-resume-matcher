import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import ScoreRing from '../components/ScoreRing'
import ScoreBreakdown from '../components/ScoreBreakdown'
import JobSummaryCard from '../components/JobSummaryCard'
import { getCandidate } from '../services/api'
import { SCORE_COMPONENTS, EDUCATION_LEVELS } from '../utils/scoring'
import { cn, formatDate, formatScore, EMPTY } from '../utils/cn'

function Detail({ label, value }) {
  return (
    <div>
      <dt className="text-xs font-medium uppercase tracking-wide text-slate-400">{label}</dt>
      <dd className="mt-0.5 text-sm text-slate-800">{value || EMPTY}</dd>
    </div>
  )
}

function Section({ title, items, empty }) {
  if (!items?.length) {
    return empty ? <p className="text-sm text-slate-400">{empty}</p> : null
  }
  return (
    <div>
      <h3 className="text-sm font-semibold text-slate-900">{title}</h3>
      <ul className="mt-2 space-y-1.5">
        {items.map((item, index) => (
          <li key={index} className="text-sm text-slate-700">
            {typeof item === 'string' ? item : JSON.stringify(item)}
          </li>
        ))}
      </ul>
    </div>
  )
}

export default function CandidateDetail() {
  const { candidateUid } = useParams()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [showText, setShowText] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      setData(await getCandidate(candidateUid))
      setError(null)
    } catch (err) {
      setError(err)
    } finally {
      setLoading(false)
    }
  }, [candidateUid])

  useEffect(() => {
    load()
  }, [load])

  if (loading) {
    return <div className="card text-center text-sm text-slate-500">Loading candidateâ€¦</div>
  }

  if (error) {
    return (
      <div className="card">
        <p className="text-sm font-semibold text-rose-800">
          {error.status === 404 ? 'Candidate not found' : 'Could not load candidate'}
        </p>
        <p className="mt-1 text-sm text-rose-700">{error.message}</p>
        <Link to="/matches" className="btn-ghost mt-4">
          Back to candidates
        </Link>
      </div>
    )
  }

  const { candidate, resume, match, explanation, explanation_method: method, job, resume_text: resumeText } = data

  return (
    <div className="space-y-6">
      <div>
        <Link to="/matches" className="text-sm font-medium text-brand-600 hover:text-brand-700">
          â† Back to candidates
        </Link>
      </div>

      <section className="card animate-fade-in">
        <div className="flex flex-wrap items-start gap-5">
          <ScoreRing score={match?.overall_score ?? 0} size={92} strokeWidth={8} showLabel />

          <div className="min-w-0 flex-1">
            <h1 className="text-2xl font-bold tracking-tight text-slate-900">
              {candidate?.name || <span className="italic text-slate-400">Unnamed candidate</span>}
            </h1>
            {candidate?.summary && (
              <p className="mt-2 max-w-3xl text-sm leading-relaxed text-slate-600">{candidate.summary}</p>
            )}

            <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-3 sm:grid-cols-4">
              <Detail label="Email" value={candidate?.email} />
              <Detail label="Phone" value={candidate?.phone} />
              <Detail label="Location" value={candidate?.location} />
              <Detail
                label="Experience"
                value={candidate?.years_of_experience ? `${candidate.years_of_experience} years` : ''}
              />
              <Detail
                label="Education level"
                value={EDUCATION_LEVELS[candidate?.education_level ?? 0]}
              />
              <Detail label="Source file" value={resume?.original_filename} />
              <Detail label="Pages" value={resume?.page_count ? String(resume.page_count) : ''} />
              <Detail label="Uploaded" value={formatDate(resume?.created_at)} />
            </dl>
          </div>
        </div>
      </section>

      {explanation && (
        <section className="card">
          <div className="flex items-center justify-between gap-3">
            <h2 className="text-sm font-semibold text-slate-900">Why this score</h2>
            <span
              className={cn(
                'rounded-md px-2 py-0.5 text-xs font-medium ring-1 ring-inset',
                method === 'ai'
                  ? 'bg-brand-50 text-brand-700 ring-brand-600/20'
                  : 'bg-slate-100 text-slate-600 ring-slate-300',
              )}
              title={
                method === 'ai'
                  ? 'Written by the language model; the score itself is deterministic.'
                  : 'Generated from a deterministic template.'
              }
            >
              {method === 'ai' ? 'AI explanation' : 'Template explanation'}
            </span>
          </div>
          <p className="mt-2 text-sm leading-relaxed text-slate-700">{explanation}</p>
        </section>
      )}

      {match && (
        <section className="card">
          <h2 className="text-sm font-semibold text-slate-900">Score breakdown</h2>
          <table className="mt-3 min-w-full text-left text-sm">
            <thead>
              <tr className="border-b border-slate-100 text-xs uppercase tracking-wide text-slate-400">
                <th className="pb-2 font-medium">Component</th>
                <th className="pb-2 text-right font-medium">Score</th>
                <th className="pb-2 text-right font-medium">Weight</th>
                <th className="pb-2 pl-4 font-medium">Contribution</th>
              </tr>
            </thead>
            <tbody>
              {SCORE_COMPONENTS.map((component) => {
                const value = match[component.key] ?? 0
                const weight = match.weights?.[component.key]
                return (
                  <tr key={component.key} className="border-b border-slate-50 last:border-0">
                    <td className="py-2.5 font-medium text-slate-700" title={component.hint}>
                      {component.label}
                    </td>
                    <td className="py-2.5 text-right tabular-nums text-slate-700">{formatScore(value)}</td>
                    <td className="py-2.5 text-right tabular-nums text-slate-400">
                      {weight !== undefined ? Number(weight).toFixed(2) : EMPTY}
                    </td>
                    <td className="py-2.5 pl-4">
                      <div className="h-1.5 w-full max-w-[180px] overflow-hidden rounded-full bg-slate-100">
                        <div
                          className={cn(
                            'h-full rounded-full',
                            value >= 75 ? 'bg-emerald-500' : value >= 50 ? 'bg-amber-500' : value > 0 ? 'bg-rose-400' : 'bg-slate-300',
                          )}
                          style={{ width: `${Math.max(0, Math.min(100, value))}%` }}
                        />
                      </div>
                    </td>
                  </tr>
                )
              })}
              <tr>
                <td className="pt-3 font-semibold text-slate-900">Overall</td>
                <td className="pt-3 text-right font-semibold tabular-nums text-slate-900">
                  {formatScore(match.overall_score)}
                </td>
                <td colSpan={2} />
              </tr>
            </tbody>
          </table>

          <div className="mt-4 border-t border-slate-100 pt-4">
            <ScoreBreakdown match={match} weights={match.weights} defaultOpen />
          </div>
        </section>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <section className="card space-y-5">
          <div>
            <h2 className="text-sm font-semibold text-slate-900">Skills</h2>
            {candidate?.skills?.length ? (
              <div className="mt-2 flex flex-wrap gap-1.5">
                {candidate.skills.map((skill) => (
                  <span
                    key={skill}
                    className={cn(
                      'rounded-md px-2 py-0.5 text-xs font-medium ring-1 ring-inset',
                      match?.matching_skills?.includes(skill)
                        ? 'bg-emerald-50 text-emerald-700 ring-emerald-600/20'
                        : 'bg-slate-100 text-slate-600 ring-slate-300',
                    )}
                    title={match?.matching_skills?.includes(skill) ? 'Required by the job' : undefined}
                  >
                    {skill}
                  </span>
                ))}
              </div>
            ) : (
              <p className="mt-2 text-sm text-slate-400">No skills extracted.</p>
            )}
          </div>

          <div>
            <h2 className="text-sm font-semibold text-slate-900">Education</h2>
            <ul className="mt-2 space-y-1.5">
              {(candidate?.education ?? []).map((item, index) => (
                <li key={index} className="text-sm text-slate-700">
                  {item.degree || item.detail || JSON.stringify(item)}
                </li>
              ))}
              {!candidate?.education?.length && <li className="text-sm text-slate-400">Not specified.</li>}
            </ul>
          </div>

          <Section title="Experience" items={candidate?.experience} empty="No experience entries extracted." />

          <Section title="Projects" items={candidate?.projects} />

          <Section
            title="Certifications"
            items={candidate?.certifications}
            empty="No certifications extracted."
          />
        </section>

        <div className="space-y-6">
          {job && <JobSummaryCard job={job} />}

          <section className="card">
            <h2 className="text-sm font-semibold text-slate-900">Source resume text</h2>
            <p className="mt-1 text-xs text-slate-500">
              Exactly what was extracted from {resume?.original_filename}
              {resume?.extraction_method ? ` via ${resume.extraction_method}` : ''}.
            </p>
            <div className="mt-3">
              <button type="button" onClick={() => setShowText((v) => !v)} className="btn-ghost px-3 py-1.5 text-xs">
                {showText ? 'Hide text' : 'Show extracted text'}
              </button>
              {showText && (
                <pre className="mt-3 max-h-[28rem] overflow-auto whitespace-pre-wrap rounded-lg bg-slate-50 p-3 font-mono text-[11px] leading-relaxed text-slate-600 ring-1 ring-inset ring-slate-200">
                  {resumeText || EMPTY}
                </pre>
              )}
            </div>
          </section>
        </div>
      </div>
    </div>
  )
}
