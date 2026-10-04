import { useState } from 'react'
import { session } from '../utils/storage'

const STORAGE_KEY = 'demo_environment_notice_dismissed'

/**
 * Permanent, dismissible notice explaining the Render free-tier cold start.
 *
 * Dismissal is remembered for the browser session only, so a judge who closes
 * it once does not see it again while they are still presenting, but a fresh
 * visitor always gets the explanation up front.
 */
export default function DemoEnvironmentNotice() {
  const [dismissed, setDismissed] = useState(() => session.get(STORAGE_KEY, false) === true)

  if (dismissed) return null

  const dismiss = () => {
    session.set(STORAGE_KEY, true)
    setDismissed(true)
  }

  return (
    <aside
      role="note"
      aria-label="Demo environment notice"
      className="animate-fade-in rounded-xl border border-sky-200 bg-sky-50/70 px-4 py-3 shadow-card sm:px-5"
    >
      <div className="flex items-start gap-3">
        <span
          className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-sky-100 text-base"
          aria-hidden="true"
        >
          ⚡
        </span>

        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold text-sky-900">Demo Environment Notice</p>
          <p className="mt-1 text-sm leading-relaxed text-sky-800">
            Our backend is hosted on Render&rsquo;s free tier and may enter sleep mode after
            inactivity. The first request may take up to 60 seconds while the backend wakes up. Please
            wait for the loading indicator.
          </p>
        </div>

        <button
          type="button"
          onClick={dismiss}
          aria-label="Dismiss demo environment notice"
          className="-m-1 shrink-0 rounded-md p-1 text-sky-400 transition-colors hover:bg-sky-100 hover:text-sky-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500"
        >
          <svg
            className="h-4 w-4"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            aria-hidden="true"
          >
            <path d="M6 6l12 12M18 6 6 18" />
          </svg>
        </button>
      </div>
    </aside>
  )
}