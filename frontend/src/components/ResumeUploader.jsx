import { useCallback, useRef, useState } from 'react'
import { cn } from '../utils/cn'

const ACCEPTED = ['.pdf', '.txt', '.md']
const MAX_FILES = 25

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`
  return `${(bytes / 1024 / 1024).toFixed(2)} MB`
}

export default function ResumeUploader({ files, onChange, disabled = false }) {
  const inputRef = useRef(null)
  const [dragging, setDragging] = useState(false)

  const addFiles = useCallback(
    (incoming) => {
      const list = Array.from(incoming || [])
      if (!list.length) return

      const accepted = []
      const rejected = []
      list.forEach((file) => {
        const ext = `.${file.name.split('.').pop()?.toLowerCase()}`
        if (ACCEPTED.includes(ext)) accepted.push(file)
        else rejected.push(`${file.name} (unsupported type)`)
      })

      const merged = [...files]
      accepted.forEach((file) => {
        // Skip exact duplicates within the current selection.
        const duplicate = merged.some(
          (existing) =>
            existing.name === file.name &&
            existing.size === file.size &&
            existing.lastModified === file.lastModified,
        )
        if (!duplicate && merged.length < MAX_FILES) merged.push(file)
      })

      onChange(merged, rejected)
    },
    [files, onChange],
  )

  const removeAt = (index) => {
    const next = files.filter((_, i) => i !== index)
    onChange(next, [])
  }

  const handleDrop = (event) => {
    event.preventDefault()
    setDragging(false)
    if (disabled) return
    addFiles(event.dataTransfer.files)
  }

  const totalBytes = files.reduce((sum, file) => sum + file.size, 0)

  return (
    <div className="space-y-3">
      <div
        onDragOver={(e) => {
          e.preventDefault()
          if (!disabled) setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        className={cn(
          'rounded-xl border-2 border-dashed px-6 py-8 text-center transition-colors',
          dragging ? 'border-brand-500 bg-brand-50' : 'border-slate-300 bg-white hover:border-slate-400',
          disabled && 'pointer-events-none opacity-60',
        )}
      >
        <svg
          className="mx-auto h-9 w-9 text-slate-400"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth="1.5"
          aria-hidden="true"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M12 16.5V4.5m0 0L7.5 9M12 4.5 16.5 9M4.5 16.5v1.8A2.2 2.2 0 0 0 6.7 20.5h10.6a2.2 2.2 0 0 0 2.2-2.2v-1.8"
          />
        </svg>
        <p className="mt-3 text-sm font-medium text-slate-900">
          Drag &amp; drop resumes here
        </p>
        <p className="mt-1 text-xs text-slate-500">PDF, TXT or MD · up to {MAX_FILES} files</p>
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          disabled={disabled}
          className="btn-ghost mt-4"
        >
          Browse files
        </button>
        <input
          ref={inputRef}
          type="file"
          multiple
          accept={ACCEPTED.join(',')}
          className="hidden"
          onChange={(e) => {
            addFiles(e.target.files)
            e.target.value = ''
          }}
        />
      </div>

      {files.length > 0 && (
        <div className="rounded-lg border border-slate-200 bg-white">
          <div className="flex items-center justify-between border-b border-slate-100 px-3 py-2">
            <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              {files.length} file{files.length === 1 ? '' : 's'} selected
            </span>
            <button
              type="button"
              onClick={() => onChange([], [])}
              disabled={disabled}
              className="text-xs font-medium text-rose-600 hover:text-rose-700 disabled:opacity-50"
            >
              Clear all
            </button>
          </div>
          <ul className="max-h-56 divide-y divide-slate-100 overflow-y-auto">
            {files.map((file, index) => (
              <li key={`${file.name}-${file.lastModified}-${index}`} className="flex items-center justify-between gap-3 px-3 py-2">
                <div className="flex min-w-0 items-center gap-2.5">
                  <span className="shrink-0 rounded bg-rose-50 px-1.5 py-0.5 text-[10px] font-bold uppercase text-rose-700">
                    {file.name.split('.').pop()}
                  </span>
                  <span className="truncate text-sm text-slate-700" title={file.name}>
                    {file.name}
                  </span>
                  <span className="shrink-0 text-xs text-slate-400">{formatSize(file.size)}</span>
                </div>
                <button
                  type="button"
                  onClick={() => removeAt(index)}
                  disabled={disabled}
                  aria-label={`Remove ${file.name}`}
                  className="shrink-0 rounded p-1 text-slate-400 transition-colors hover:bg-rose-50 hover:text-rose-600 disabled:opacity-50"
                >
                  <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M6 18 18 6M6 6l12 12" />
                  </svg>
                </button>
              </li>
            ))}
          </ul>
          <div className="border-t border-slate-100 px-3 py-2 text-xs text-slate-500">
            Total {formatSize(totalBytes)}
          </div>
        </div>
      )}
    </div>
  )
}