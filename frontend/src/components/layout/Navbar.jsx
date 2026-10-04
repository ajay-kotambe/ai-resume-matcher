import { Link, NavLink } from 'react-router-dom'
import { cn } from '../../utils/cn'

const NAV_ITEMS = [
  { to: '/', label: 'Dashboard', end: true },
  { to: '/resumes', label: 'Resumes' },
  { to: '/jobs', label: 'Jobs' },
  { to: '/matches', label: 'Matches' },
]

export default function Navbar({ isBackendOnline }) {
  return (
    <header className="sticky top-0 z-20 border-b border-slate-200 bg-white/90 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between gap-4 px-4 sm:px-6 lg:px-8">
        <Link to="/" className="flex items-center gap-2.5">
          <img src="/logo.svg" alt="" className="h-8 w-8 rounded-lg" />
          <span className="text-sm font-bold leading-tight text-slate-900 sm:text-base">
            AI Resume &amp; Job Matcher
          </span>
        </Link>

        <nav className="hidden items-center gap-1 md:flex">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                cn(
                  'rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                  isActive
                    ? 'bg-brand-50 text-brand-700'
                    : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900',
                )
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="flex items-center gap-3">
          <span
            className={cn('hidden sm:inline-flex', isBackendOnline ? 'badge-ok' : 'badge-error')}
            title="FastAPI connection status"
          >
            <span
              className={cn(
                'h-1.5 w-1.5 rounded-full',
                isBackendOnline ? 'bg-emerald-500' : 'bg-rose-500',
              )}
            />
            {isBackendOnline ? 'API online' : 'API offline'}
          </span>
        </div>
      </div>

      <nav className="flex items-center gap-1 overflow-x-auto border-t border-slate-100 px-2 py-2 md:hidden">
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            className={({ isActive }) =>
              cn(
                'whitespace-nowrap rounded-lg px-3 py-1.5 text-sm font-medium',
                isActive ? 'bg-brand-50 text-brand-700' : 'text-slate-600',
              )
            }
          >
            {item.label}
          </NavLink>
        ))}
      </nav>
    </header>
  )
}