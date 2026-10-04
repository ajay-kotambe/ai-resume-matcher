import { useCallback, useState } from 'react'
import ResumeUploader from '../components/ResumeUploader'
import JobDescriptionInput from '../components/JobDescriptionInput'
import ProcessingOverlay from '../components/ProcessingOverlay'
import JobSummaryCard from '../components/JobSummaryCard'
import CandidateCard from '../components/CandidateCard'
import SummaryBar from '../components/SummaryBar'
import MatchFilters from '../components/MatchFilters'
import useMatchingPipeline from '../hooks/useMatchingPipeline'
import useApiHealth from '../hooks/useApiHealth'
import useCandidateSearch from '../hooks/useCandidateSearch'

export default function Dashboard() {
  const { isOnline } = useApiHealth({ pollIntervalMs: 30000 })

  const [files, setFiles] = useState([])
  const [rejected, setRejected] = useState([])
  const [jobDescription, setJobDescription] = useState('')
  const [useAi, setUseAi] = useState(false)
  const [formError, setFormError] = useState(null)

  const { analyze, reset, stages, activeStage, isProcessing, uploadPercent, result, error } =
    useMatchingPipeline()

  // Re-run the search hook against whichever job the latest analysis produced.
  const jobUid = result?.job?.job_uid ?? null
  const {
    candidates,
    filters,
    update,
    reset: resetFilters,
    hasActiveFilters,
    availableSkills,
    total,
    loading: searching,
  } = useCandidateSearch({ enabled: Boolean(result), jobUid })

  const handleFilesChange = useCallback((next, rejectedFiles) => {
    setFiles(next)
    if (rejectedFiles?.length) {
      setRejected(rejectedFiles)
    } else {
      setRejected([])
    }
  }, [])

  const validate = () => {
    if (files.length === 0) return 'Add at least one resume before running the analysis.'
    if (!jobDescription.trim()) return 'Paste the job description to match against.'
    if (jobDescription.trim().split(/\s+/).length < 15) {
      return 'The job description looks too short to extract requirements reliably.'
    }
    return null
  }

  const handleSubmit = async (event) => {
    event.preventDefault()
    const problem = validate()
    setFormError(problem)
    if (problem) return

    try {
      await analyze(files, jobDescription, useAi)
      setRejected([])
    } catch {
      /* error surfaced from the pipeline hook */
    }
  }

  const handleStartOver = () => {
    reset()
    setFiles([])
    setRejected([])
    setJobDescription('')
    setFormError(null)
  }

  return (
    <div className="space-y-8">
      <section className="animate-fade-in">
        <span className="badge bg-brand-50 text-brand-700">Phase 2 · Matching</span>
        <h1 className="mt-3 text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">
          AI Resume &amp; Job Matching
        </h1>
        <p className="mt-2 max-w-3xl text-sm leading-relaxed text-slate-600 sm:text-base">
          Upload resumes, paste a job description, and get a ranked shortlist with transparent,
          deterministic scores — plus an AI-written explanation for every candidate.
        </p>
      </section>

      {!isOnline && !isProcessing && (
        <div className="rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          The backend is not reachable. Start it with{' '}
          <code className="rounded bg-amber-100 px-1 py-0.5 font-mono text-[13px]">uvicorn app.main:app</code>{' '}
          on port 8000, then reload this page.
        </div>
      )}

      <form onSubmit={handleSubmit} className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_380px]">
        <div className="space-y-6">
          <section className="card">
            <h2 className="text-base font-semibold text-slate-900">1. Upload resumes</h2>
            <p className="mt-1 text-sm text-slate-600">
              PDF, TXT or MD. Text is extracted locally with PyMuPDF; nothing leaves your machine
              except the derived analysis.
            </p>
            <div className="mt-4">
              <ResumeUploader files={files} onChange={handleFilesChange} disabled={isProcessing} />
            </div>
            {rejected.length > 0 && (
              <p className="mt-2 text-sm text-amber-700">
                Skipped {rejected.length} unsupported file{rejected.length === 1 ? '' : 's'}:{' '}
                {rejected.join(', ')}
              </p>
            )}
          </section>

          <section className="card">
            <h2 className="text-base font-semibold text-slate-900">2. Paste the job description</h2>
            <p className="mt-1 text-sm text-slate-600">
              Required and preferred skills, minimum experience and education are extracted
              automatically.
            </p>
            <div className="mt-4">
              <JobDescriptionInput
                value={jobDescription}
                onChange={setJobDescription}
                disabled={isProcessing}
                error={formError}
              />
            </div>
          </section>
        </div>

        <aside className="lg:sticky lg:top-24 lg:self-start">
          <div className="card space-y-4">
            <h2 className="text-base font-semibold text-slate-900">3. Run the analysis</h2>
            <p className="text-sm text-slate-600">
              Scores are computed from your data. AI is only used to write the explanations and can
              never change a score.
            </p>

            <label className="flex items-start gap-2.5 rounded-lg bg-slate-50 px-3 py-2.5">
              <input
                type="checkbox"
                checked={useAi}
                onChange={(event) => setUseAi(event.target.checked)}
                disabled={isProcessing}
                className="mt-0.5 h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500"
              />
              <span className="text-sm text-slate-700">
                Use AI extraction &amp; explanations
                <span className="mt-0.5 block text-xs text-slate-500">
                  Requires an NVIDIA API key. Off means fully deterministic.
                </span>
              </span>
            </label>

            <button type="submit" disabled={isProcessing || !isOnline} className="btn-primary w-full">
              {isProcessing ? 'Analysing…' : 'Analyse & rank candidates'}
            </button>

            {files.length > 0 && (
              <p className="text-center text-xs text-slate-500">
                {files.length} resume{files.length === 1 ? '' : 's'} ready
              </p>
            )}

            {result && (
              <button type="button" onClick={handleStartOver} className="btn-ghost w-full">
                Start a new analysis
              </button>
            )}
          </div>
        </aside>
      </form>

      {error && (
        <div className="rounded-lg border border-rose-300 bg-rose-50 px-4 py-3">
          <p className="text-sm font-semibold text-rose-800">Analysis failed</p>
          <p className="mt-0.5 text-sm text-rose-700">{error.message}</p>
        </div>
      )}

      {result && (
        <div className="space-y-6">
          <JobSummaryCard job={result.job} />

          {result.errors?.length > 0 && (
            <div className="rounded-lg border border-amber-300 bg-amber-50 px-4 py-3">
              <p className="text-sm font-semibold text-amber-800">
                {result.errors.length} resume{result.errors.length === 1 ? '' : 's'} could not be
                processed
              </p>
              <ul className="mt-1 space-y-0.5 text-sm text-amber-700">
                {result.errors.map((item, index) => (
                  <li key={index}>
                    <span className="font-medium">{item.filename}</span>: {item.error}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <SummaryBar summary={result.summary} />

          <div className="grid gap-6 lg:grid-cols-[300px_minmax(0,1fr)]">
            <MatchFilters
              filters={filters}
              update={update}
              reset={resetFilters}
              hasActiveFilters={hasActiveFilters}
              availableSkills={availableSkills}
              total={total}
              loading={searching}
            />

            <div className="space-y-4">
              {candidates.length === 0 && !searching && (
                <div className="card text-center text-sm text-slate-500">
                  No candidates match the current filters.
                </div>
              )}
              {candidates.map((entry, index) => (
                <CandidateCard
                  key={entry.candidate?.candidate_uid ?? index}
                  entry={entry}
                  defaultOpenBreakdown={index === 0}
                />
              ))}
            </div>
          </div>
        </div>
      )}

      {isProcessing && (
        <ProcessingOverlay
          stages={stages}
          activeStage={activeStage}
          uploadPercent={uploadPercent}
          fileCount={files.length}
        />
      )}
    </div>
  )
}
