import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import JobDescriptionInput from '../components/JobDescriptionInput'
import JobSummaryCard from '../components/JobSummaryCard'
import useApiHealth from '../hooks/useApiHealth'
import { analyzeJobDescription, listJobs } from '../services/api'
import { formatDate } from '../utils/cn'

export default function Jobs() {
  const { isOnline } = useApiHealth({ pollIntervalMs: 30000 })
  const [jobDescription, setJobDescription] = useState('')
  const [useAi, setUseAi] = useState(false)
  const [job, setJob] = useState(null)
  const [analysing, setAnalysing] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [formError, setFormError] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const response = await listJobs()
      setJob(response?.job ?? null)
      setError(null)
    } catch (err) {
      // 404 simply means nothing has been analysed yet.
      if (err?.status === 404) {
        setJob(null)
        setError(null)
      } else {
        setError(err)
      }
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const handleSubmit = async (event) => {
    event.preventDefault()
    const words = jobDescription.trim().split(/\s+/).filter(Boolean).length
    if (!jobDescription.trim()) {
      setFormError('Paste a job description to analyse.')
      return
    }
    if (words < 15) {
      setFormError('The job description looks too short to extract requirements reliably.')
      return
    }
    setFormError(null)
    setAnalysing(true)
    try {
      const response = await analyzeJobDescription(jobDescription, useAi)
      setJob(response.job)
      setError(null)
    } catch (err) {
      setError(err)
    } finally {
      setAnalysing(false)
    }
  }

  return (
    <div className="space-y-6">
      <section className="animate-fade-in">
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">Job descriptions</h1>
        <p className="mt-2 max-w-3xl text-sm leading-relaxed text-slate-600">
          Analyse a role on its own to inspect exactly which requirements the system extracts. The
          original text is always stored verbatim, so nothing is lost in translation.
        </p>
      </section>

      <form onSubmit={handleSubmit} className="card">
        <h2 className="text-base font-semibold text-slate-900">Analyse a job description</h2>
        <div className="mt-4">
          <JobDescriptionInput
            value={jobDescription}
            onChange={setJobDescription}
            disabled={analysing}
            error={formError}
          />
        </div>

        <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
          <label className="flex items-start gap-2.5 rounded-lg bg-slate-50 px-3 py-2.5">
            <input
              type="checkbox"
              checked={useAi}
              onChange={(event) => setUseAi(event.target.checked)}
              disabled={analysing}
              className="mt-0.5 h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500"
            />
            <span className="text-sm text-slate-700">
              Use AI extraction
              <span className="mt-0.5 block text-xs text-slate-500">
                Off means fully deterministic parsing.
              </span>
            </span>
          </label>

          <button type="submit" disabled={analysing || !isOnline} className="btn-primary">
            {analysing ? 'Analysing…' : 'Analyse requirements'}
          </button>
        </div>
      </form>

      {error && (
        <div className="rounded-lg border border-rose-300 bg-rose-50 px-4 py-3">
          <p className="text-sm font-semibold text-rose-800">Analysis failed</p>
          <p className="mt-0.5 text-sm text-rose-700">{error.message}</p>
        </div>
      )}

      {loading ? (
        <div className="card text-center text-sm text-slate-500">Loading stored roles…</div>
      ) : job ? (
        <>
          <JobSummaryCard job={job} />
          <div className="card flex flex-wrap items-center justify-between gap-3">
            <p className="text-xs text-slate-500">
              Analysed {formatDate(job.created_at)} · job id <code className="font-mono">{job.job_uid}</code>
            </p>
            <Link to="/matches" className="btn-primary">
              View ranked candidates
            </Link>
          </div>
        </>
      ) : (
        <div className="card text-center">
          <p className="text-sm font-medium text-slate-700">
            No job description has been analysed yet.
          </p>
          <p className="mt-1 text-sm text-slate-500">
            Paste a role above, or use the sample, to see the extracted requirements.
          </p>
        </div>
      )}
    </div>
  )
}
