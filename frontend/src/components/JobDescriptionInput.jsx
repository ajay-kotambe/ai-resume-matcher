import { cn } from '../utils/cn'

const SAMPLE = `Senior Full Stack Engineer

About the role
We are looking for a Senior Full Stack Engineer to build and scale our
customer-facing web platform.

Required skills
- Strong JavaScript and TypeScript
- React and Redux for frontend development
- Node.js and Express for backend services
- REST API design
- PostgreSQL
- 3+ years of professional experience

Preferred skills
- Docker
- Kubernetes
- AWS
- CI/CD

Minimum qualifications
Bachelor's degree in Computer Science or equivalent.

Responsibilities
- Design and ship features across the full stack
- Review code and mentor junior engineers
- Improve application performance and reliability`

export default function JobDescriptionInput({ value, onChange, disabled = false, error = null }) {
  const words = value.trim() ? value.trim().split(/\s+/).length : 0

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <label htmlFor="job-description" className="text-sm font-semibold text-slate-900">
          Job description
        </label>
        <button
          type="button"
          onClick={() => onChange(SAMPLE)}
          disabled={disabled}
          className="text-xs font-medium text-brand-600 hover:text-brand-700 disabled:opacity-50"
        >
          Load sample JD
        </button>
      </div>

      <textarea
        id="job-description"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        disabled={disabled}
        rows={14}
        spellCheck={false}
        placeholder="Paste the complete job description here — role title, required and preferred skills, minimum experience, education requirements and responsibilities."
        className={cn(
          'w-full rounded-lg border bg-white px-3.5 py-3 font-mono text-[13px] leading-relaxed text-slate-800',
          'placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-brand-500',
          'disabled:cursor-not-allowed disabled:bg-slate-50',
          error ? 'border-rose-300 focus:ring-rose-400' : 'border-slate-300',
        )}
      />

      <div className="flex items-center justify-between text-xs">
        <span className={cn(words > 0 ? 'text-slate-500' : 'text-slate-400')}>
          {words} word{words === 1 ? '' : 's'}
          {words > 0 && words < 15 && ' — add more detail for accurate requirements'}
        </span>
        {value && (
          <button
            type="button"
            onClick={() => onChange('')}
            disabled={disabled}
            className="font-medium text-slate-500 hover:text-slate-700 disabled:opacity-50"
          >
            Clear
          </button>
        )}
      </div>

      {error && <p className="text-sm text-rose-600">{error}</p>}
    </div>
  )
}