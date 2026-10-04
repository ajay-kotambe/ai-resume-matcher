export function cn(...classes) {
  return classes.filter(Boolean).join(' ')
}

export const EMPTY = '\u2014'

export function formatDate(value) {
  if (!value) return EMPTY
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? EMPTY : date.toLocaleString()
}

export function formatRelativeTime(value) {
  if (!value) return EMPTY
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return EMPTY
  const seconds = Math.round((Date.now() - date.getTime()) / 1000)
  if (seconds < 60) return `${seconds}s ago`
  const minutes = Math.round(seconds / 60)
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.round(minutes / 60)
  return `${hours}h ago`
}

/** 96.8123 -> "96.8" */
export function formatScore(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return EMPTY
  return Number(value).toFixed(1)
}
