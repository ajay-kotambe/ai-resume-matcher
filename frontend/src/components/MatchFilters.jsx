import { useEffect, useRef, useState } from 'react'
import { cn } from '../utils/cn'

const EDUCATION_LEVELS = [
  { value: '', label: 'Any education' },
  { value: '3', label: 'Bachelor’s or above' },
  { value: '4', label: 'Master’s or above' },
  { value: '5', label: 'Doctorate' },
]

const SORTS = [
  { value: 'score:desc', label: 'Highest match' },
  { value: 'score:asc', label: 'Lowest match' },
  { value: 'experience:desc', label: 'Most experienced' },
  { value: 'name', label: 'Name (A–Z)' },
]

function SkillPicker({ available, value, onChange }) {
  const [open, setOpen] = useState(false)
  const containerRef = useRef(null)

  const selected = value ? value.split(',').map((s) => s.trim()).filter(Boolean) : []

  useEffect(() => {
    if (!open) return undefined
    const onClickOutside = (event) => {
      if (containerRef.current && !containerRef.current.contains(event.target)) setOpen(false)
    }
    const onKey = (event) => {
      if (event.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onClickOutside)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onClickOutside)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  const toggle = (skill) => {
    const next = selected.includes(skill)
      ? selected.filter((item) => item !== skill)
      : [...selected, skill]
    onChange(next.join(','))
  }

  return (
    <div className="relative" ref={containerRef}>
      <button
        type="button"
        onClick={() => setOpen((current) => !current)}
        aria-expanded={open}
        className={cn(
          'flex w-full items-center justify-between gap-2 rounded-lg border bg-white px-3 py-2 text-left text-sm',
          'focus:outline-none focus:ring-2 focus:ring-brand-500',
          selected.length ? 'border-brand-300 text-brand-700' : 'border-slate-300 text-slate-700',
        )}
      >
        <span className="truncate">
          {selected.length ? `${selected.length} skill${selected.length === 1 ? '' : 's'} selected` : 'Any skills'}
        </span>
        <svg className="h-4 w-4 shrink-0 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
          <path strokeLinecap="round" strokeLinejoin="round" d="m19 9-7 7-7-7" />
        </svg>
      </button>

      {selected.length > 0 && (
        <div className="mt-1.5 flex flex-wrap gap-1">
          {selected.map((skill) => (
            <button
              key={skill}
              type="button"
              onClick={() => toggle(skill)}
              className="inline-flex items-center gap-1 rounded bg-brand-50 px-1.5 py-0.5 text-xs font-medium text-brand-700 hover:bg-brand-100"
            >
              {skill}
              <span aria-hidden="true">×</span>
            </button>
          ))}
        </div>
      )}

      {open && (
        <div className="absolute z-20 mt-1 max-h-64 w-full overflow-y-auto rounded-lg border border-slate-200 bg-white p-1 shadow-lg">
          {available.length === 0 ? (
            <p className="px-3 py-2 text-xs text-slate-500">No skills extracted yet.</p>
          ) : (
            available.map((skill) => (
              <label
                key={skill}
                className="flex cursor-pointer items-center gap-2 rounded px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-50"
              >
                <input
                  type="checkbox"
                  checked={selected.includes(skill)}
                  onChange={() => toggle(skill)}
                  className="h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500"
                />
                <span className="truncate">{skill}</span>
              </label>
            ))
          )}
        </div>
      )}
    </div>
  )
}

export default function MatchFilters({ filters, update, reset, availableSkills, total, loading, hasActiveFilters }) {
  return (
    <div className="card space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-900">Search &amp; filter</h2>
        <span className="text-xs text-slate-500">
          {loading ? 'Searching…' : `${total} result${total === 1 ? '' : 's'}`}
        </span>
      </div>

      <div>
        <label htmlFor="filter-q" className="mb-1 block text-xs font-medium text-slate-600">
          Name, email or skill
        </label>
        <input
          id="filter-q"
          type="search"
          value={filters.q}
          onChange={(event) => update({ q: event.target.value })}
          placeholder="e.g. React"
          className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
        />
      </div>

      <div>
        <span className="mb-1 block text-xs font-medium text-slate-600">Must have skills</span>
        <SkillPicker
          available={availableSkills}
          value={filters.skills}
          onChange={(value) => update({ skills: value })}
        />
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label htmlFor="filter-score" className="mb-1 block text-xs font-medium text-slate-600">
            Min match %
          </label>
          <input
            id="filter-score"
            type="number"
            min="0"
            max="100"
            step="5"
            value={filters.min_score}
            onChange={(event) => update({ min_score: event.target.value })}
            placeholder="Any"
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
        </div>
        <div>
          <label htmlFor="filter-exp" className="mb-1 block text-xs font-medium text-slate-600">
            Min years exp.
          </label>
          <input
            id="filter-exp"
            type="number"
            min="0"
            step="0.5"
            value={filters.min_experience}
            onChange={(event) => update({ min_experience: event.target.value })}
            placeholder="Any"
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
        </div>
      </div>

      <div>
        <label htmlFor="filter-edu" className="mb-1 block text-xs font-medium text-slate-600">
          Education
        </label>
        <select
          id="filter-edu"
          value={filters.education_level}
          onChange={(event) => update({ education_level: event.target.value })}
          className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
        >
          {EDUCATION_LEVELS.map((level) => (
            <option key={level.value} value={level.value}>
              {level.label}
            </option>
          ))}
        </select>
      </div>

      <div>
        <label htmlFor="filter-sort" className="mb-1 block text-xs font-medium text-slate-600">
          Sort by
        </label>
        <select
          id="filter-sort"
          value={filters.sort === 'name' ? 'name' : `${filters.sort}:${filters.order}`}
          onChange={(event) => {
            const raw = event.target.value
            if (raw === 'name') {
              update({ sort: 'name', order: 'asc' })
            } else {
              const [sort, order] = raw.split(':')
              update({ sort, order })
            }
          }}
          className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
        >
          {SORTS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </div>

      {hasActiveFilters && (
        <button type="button" onClick={reset} className="btn-ghost w-full">
          Clear all filters
        </button>
      )}
    </div>
  )
}
