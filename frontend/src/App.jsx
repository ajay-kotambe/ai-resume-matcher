import { lazy, Suspense } from 'react'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import Navbar from './components/layout/Navbar'
import Dashboard from './pages/Dashboard'
import ErrorPage from './pages/ErrorPage'
import useApiHealth from './hooks/useApiHealth'

// Secondary routes are split out to keep the dashboard's first paint small.
const Matches = lazy(() => import('./pages/Matches'))
const Resumes = lazy(() => import('./pages/Resumes'))
const Jobs = lazy(() => import('./pages/Jobs'))
const CandidateDetail = lazy(() => import('./pages/CandidateDetail'))

function RouteFallback() {
  return (
    <div className="space-y-4" aria-busy="true">
      <div className="h-8 w-56 animate-pulse rounded-lg bg-slate-200" />
      <div className="h-40 animate-pulse rounded-xl bg-slate-100" />
      <div className="h-40 animate-pulse rounded-xl bg-slate-100" />
    </div>
  )
}

export default function App() {
  // Shared health probe so the navbar badge reflects the live API state.
  const { isOnline } = useApiHealth()

  return (
    <BrowserRouter>
      <div className="flex min-h-full flex-col">
        <Navbar isBackendOnline={isOnline} />

        <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-8 sm:px-6 lg:px-8">
          <Suspense fallback={<RouteFallback />}>
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/resumes" element={<Resumes />} />
              <Route path="/jobs" element={<Jobs />} />
              <Route path="/matches" element={<Matches />} />
              <Route path="/candidates/:candidateUid" element={<CandidateDetail />} />
              <Route path="*" element={<ErrorPage />} />
            </Routes>
          </Suspense>
        </main>

        <footer className="border-t border-slate-200 bg-white">
          <div className="mx-auto max-w-7xl px-4 py-4 text-xs text-slate-500 sm:px-6 lg:px-8">
            Deterministic scoring · AI-assisted explanations · FastAPI + SQLAlchemy + SQLite · NVIDIA NIM
            ready
          </div>
        </footer>
      </div>
    </BrowserRouter>
  )
}
