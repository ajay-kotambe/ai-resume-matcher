import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import ResumeUploader from '../components/ResumeUploader'
import useApiHealth from '../hooks/useApiHealth'
import { deleteResumes, listResumes, uploadResumes } from '../services/api'
import { cn, formatDate, formatRelativeTime, EMPTY } from '../utils/cn'

const STATUS_TONE = {
  extracted: 'bg-emerald-50 text-emerald-700 ring-emerald-600/20',
  analyzed: 'bg-brand-50 text-brand-700 ring-brand-600/20',
  failed: 'bg-rose-50 text-rose-700 ring-rose-600/20',
  pending: 'bg-amber-50 text-amber-800 ring-amber-600/20',
}

function ResumeRow({ entry }) {
  const { resume, candidate } = entry
  const tone = STATUS_TONE[resume.status] ?? STATUS_TONE.pending

  return (
    <tr className="align-top">
      <td className="px-4 py-3">
        <p className="font-medium text-slate-800">{resume.original_filename}</p>
        <p className="mt-0.5 text-xs text-slate-500">
          {resume.page_count ? `${resume.page_count} page${resume.page_count === 1 ? '' : 's'} · ` : ''}
          {resume.char_count.toLocaleString()} characters
        </p>
        {resume.error && <p className="mt-1 text-xs text-rose-600">{resume.error}</p>}
      </td>
      <td className="px-4 py-3">
        <span className={cn('rounded-md px-2 py-0.5 text-xs font-medium ring-1 ring-inset', tone)}>
          {resume.status}
        </span>
        {resume.extraction_method && (
          <p className="mt-1 text-xs text-slate-400">{resume.extraction_method}</p>
        )}
      </td>
      <td className="px-4 py-3">
        {candidate ? (
          <>
            <p className="font-medium text-slate-800">{candidate.name || EMPTY}</p>
            <p className="mt-0.5 text-xs text-slate-500">{candidate.email || EMPTY}</p>
            <p className="mt-1 line-clamp-2 text-xs text-slate-500">
              {candidate.skills?.slice(0, 6).join(', ') || 'No skills detected'}
              {candidate.skills?.length > 6 && ` +${candidate.skills.length - 6} more`}
            </p>
          </>
        ) : (
          <span className="text-sm text-slate-400">{EMPTY}</span>
        )}
      </td>
      <td className="px-4 py-3">
        {candidate?.candidate_uid ? (
          <Link to={`/candidates/${candidate.candidate_uid}`} className="btn-ghost px-3 py-1.5 text-xs">
            View
          </Link>
        ) : (
          <span className="text-xs text-slate-400">{EMPTY}</span>
        )}
      </td>
      <td className="whitespace-nowrap px-4 py-3 text-xs text-slate-500" title={formatDate(resume.created_at)}>
        {formatRelativeTime(resume.created_at)}
      </td>
    </tr>
  )
}

export default function Resumes() {
  const { isOnline } = useApiHealth({ pollIntervalMs: 30000 })
  const [files, setFiles] = useState([])
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState(null)
  const [notice, setNotice] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      setData(await listResumes())
      setError(null)
    } catch (err) {
      // An empty database legitimately 404s; show an empty table, not an error.
      if (err?.status === 404) {
        setData({ resumes: [], total: 0 })
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

  const handleUpload = async (event) => {
    event.preventDefault()
    if (!files.length) return
    setUploading(true)
    setNotice(null)
    try {
      const result = await uploadResumes(files)
      setNotice({
        message: result.message,
        tone: result.failed > 0 ? 'warn' : 'ok',
        errors: result.errors ?? [],
      })
      setFiles([])
      await load()
    } catch (err) {
      setError(err)
    } finally {
      setUploading(false)
    }
  }

  const handleDeleteAll = async () => {
    if (!window.confirm('Delete every stored resume, candidate and match result? This cannot be undone.')) {
      return
    }
    try {
      const result = await deleteResumes()
      setNotice({ message: result.message, tone: 'ok', errors: [] })
      await load()
    } catch (err) {
      setError(err)
    }
  }

  const resumes = data?.resumes ?? []

  return (
    <div className="space-y-6">
      <section className="animate-fade-in flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">Resumes</h1>
          <p className="mt-2 max-w-3xl text-sm leading-relaxed text-slate-600">
            Every uploaded resume and the candidate profile extracted from it. Run a matching
            analysis from the dashboard to score these candidates against a role.
          </p>
        </div>
        {resumes.length > 0 && (
          <button type="button" onClick={handleDeleteAll} className="btn-ghost text-rose-600 hover:bg-rose-50">
            Delete all
          </button>
        )}
      </section>

      <form onSubmit={handleUpload} className="card">
        <h2 className="text-base font-semibold text-slate-900">Upload resumes</h2>
        <div className="mt-4">
          <ResumeUploader files={files} onChange={setFiles} disabled={uploading || !isOnline} />
        </div>
        <button
          type="submit"
          disabled={uploading || files.length === 0 || !isOnline}
          className="btn-primary mt-4"
        >
          {uploading ? 'Uploading…' : `Upload ${files.length || ''} resume${files.length === 1 ? '' : 's'}`.trim()}
        </button>
      </form>

      {notice && (
        <div
          className={cn(
            'rounded-lg px-4 py-3 text-sm ring-1 ring-inset',
            notice.tone === 'warn'
              ? 'bg-amber-50 text-amber-800 ring-amber-600/20'
              : 'bg-emerald-50 text-emerald-800 ring-emerald-600/20',
          )}
        >
          <p className="font-medium">{notice.message}</p>
          {notice.errors?.length > 0 && (
            <ul className="mt-1 list-disc pl-5 text-[13px]">
              {notice.errors.map((item, index) => (
                <li key={index}>
                  {item.filename}: {item.error}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {error && (
        <div className="rounded-lg border border-rose-300 bg-rose-50 px-4 py-3">
          <p className="text-sm font-semibold text-rose-800">Request failed</p>
          <p className="mt-0.5 text-sm text-rose-700">{error.message}</p>
        </div>
      )}

      <section className="card overflow-hidden p-0">
        <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
          <h2 className="text-sm font-semibold text-slate-900">Stored resumes</h2>
          <span className="text-xs text-slate-500">
            {loading ? 'Loading…' : `${data?.total ?? 0} total`}
          </span>
        </div>

        {resumes.length === 0 && !loading ? (
          <p className="px-4 py-10 text-center text-sm text-slate-500">
            No resumes uploaded yet. Add files above to get started.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-100 text-left text-sm">
              <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-4 py-2.5 font-medium">File</th>
                  <th className="px-4 py-2.5 font-medium">Status</th>
                  <th className="px-4 py-2.5 font-medium">Extracted candidate</th>
                  <th className="px-4 py-2.5 font-medium">Profile</th>
                  <th className="px-4 py-2.5 font-medium">Uploaded</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {resumes.map((entry) => (
                  <ResumeRow key={entry.resume.resume_uid} entry={entry} />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  )
}
