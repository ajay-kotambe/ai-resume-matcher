import { useRouteError, isRouteErrorResponse, Link } from 'react-router-dom'

export default function ErrorPage() {
  const error = useRouteError()
  const status = isRouteErrorResponse(error) ? error.status : 500
  const message = isRouteErrorResponse(error)
    ? error.statusText || 'Something went wrong.'
    : error?.message || 'Unexpected application error.'

  return (
    <div className="card mx-auto max-w-lg text-center animate-fade-in">
      <p className="text-5xl font-bold text-brand-600">{status}</p>
      <h1 className="mt-3 text-lg font-semibold text-slate-900">{message}</h1>
      <p className="mt-2 text-sm text-slate-600">
        The route does not exist or the app hit an unexpected state.
      </p>
      <Link to="/" className="btn-primary mt-6">
        Back to dashboard
      </Link>
    </div>
  )
}