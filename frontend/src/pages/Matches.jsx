import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import MatchFilters from '../components/MatchFilters'
import CandidateCard from '../components/CandidateCard'
import SummaryBar from '../components/SummaryBar'
import JobSummaryCard from '../components/JobSummaryCard'
import useCandidateSearch from '../hooks/useCandidateSearch'
import { listJobs } from '../services/api'

/**
 * Browse previously scored candidates. Data comes from the backend's SQL
 * search/filter layer, so filters survive reloads and stay server-side.
 */
export default function Matches() {
  const {
    candidates,
    summary,
    filters,
    update,
    reset,
    hasActiveFilters,
    availableSkills,
    total,
    loading,
    error,
  } = useCandidateSearch({ enabled: true })

  const [job, setJob] = useState(null)

  // Show the most recent analysed role as context for the ranking.
  useEffect(() => {
    let active = true
    listJobs()
      .then((response) => {
        if (active && response?.job) setJob(response.job)
      })
      .catch(() => {
        /* job context is optional */
      })
    return () => {
      active = false
    }
  }, [candidates.length])

  return (
    <div className="space-y-6">
      <section className="animate-fade-in">
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">Ranked candidates</h1>
        <p className="mt-2 max-w-3xl text-sm leading-relaxed text-slate-600">
          Search and filter every candidate scored in the latest analysis. Filtering runs in SQL on
          the processed data, not on the frontend.
        </p>
      </section>

      {error && (
        <div className="rounded-lg border border-rose-300 bg-rose-50 px-4 py-3">
          <p className="text-sm font-semibold text-rose-800">Could not load candidates</p>
          <p className="mt-0.5 text-sm text-rose-700">{error.message}</p>
        </div>
      )}

      {candidates.length === 0 && !loading && !error && (
        <div className="card text-center">
          <p className="text-sm font-medium text-slate-700">No candidates have been scored yet.</p>
          <p className="mt-1 text-sm text-slate-500">
            Upload resumes and a job description from the dashboard to build a shortlist.
          </p>
          <Link to="/" className="btn-primary mt-4">
            Go to dashboard
          </Link>
        </div>
      )}

      {candidates.length > 0 && (
        <>
          <SummaryBar summary={summary} />

          {job && <JobSummaryCard job={job} />}

          <div className="grid gap-6 lg:grid-cols-[300px_minmax(0,1fr)]">
            <MatchFilters
              filters={filters}
              update={update}
              reset={reset}
              hasActiveFilters={hasActiveFilters}
              availableSkills={availableSkills}
              total={total}
              loading={loading}
            />

            <div className="space-y-4">
              {candidates.length === 0 ? (
                <div className="card text-center text-sm text-slate-500">
                  No candidates match the current filters.
                </div>
              ) : (
                candidates.map((entry, index) => (
                  <CandidateCard
                    key={entry.candidate?.candidate_uid ?? index}
                    entry={entry}
                    defaultOpenBreakdown={index === 0 && !hasActiveFilters}
                  />
                ))
              )}
            </div>
          </div>
        </>
      )}
    </div>
  )
}
