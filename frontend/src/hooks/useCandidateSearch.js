/**
 * useCandidateSearch - debounced server-side search + filtering.
 *
 * All filtering happens in SQL on the backend; this hook only manages
 * request state and debouncing.
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import { searchCandidates } from '../services/api'

export const DEFAULT_FILTERS = {
  q: '',
  min_score: '',
  skills: '',
  min_experience: '',
  education_level: '',
  sort: 'score',
  order: 'desc',
}

/** The API returns 404 `no_candidates_found` when filters exclude everything. */
function isEmptyResult(error) {
  return error?.status === 404 && error?.raw?.response?.data?.error === 'no_candidates_found'
}

export default function useCandidateSearch({ enabled = true, jobUid = null, debounceMs = 350 } = {}) {
  const [filters, setFilters] = useState(DEFAULT_FILTERS)
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const requestId = useRef(0)

  const run = useCallback(async (activeFilters, uid) => {
    const id = ++requestId.current
    setLoading(true)
    try {
      const result = await searchCandidates({
        q: activeFilters.q || undefined,
        min_score: activeFilters.min_score || undefined,
        skills: activeFilters.skills || undefined,
        min_experience: activeFilters.min_experience || undefined,
        education_level: activeFilters.education_level || undefined,
        sort: activeFilters.sort,
        order: activeFilters.order,
        job_uid: uid || undefined,
      })
      // Ignore responses from superseded requests.
      if (id === requestId.current) {
        setData(result)
        setError(null)
      }
    } catch (err) {
      if (id !== requestId.current) return
      if (isEmptyResult(err)) {
        setData({ candidates: [], summary: null, available_skills: [], total: 0 })
        setError(null)
      } else {
        setData(null)
        setError(err)
      }
    } finally {
      if (id === requestId.current) setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (!enabled) return undefined
    const timer = setTimeout(() => run(filters, jobUid), debounceMs)
    return () => clearTimeout(timer)
  }, [filters, jobUid, enabled, run, debounceMs])

  const update = useCallback((patch) => {
    setFilters((current) => ({ ...current, ...patch }))
  }, [])

  const reset = useCallback(() => setFilters(DEFAULT_FILTERS), [])

  const hasActiveFilters = Object.entries(DEFAULT_FILTERS).some(
    ([key, value]) =>
      key !== 'sort' && key !== 'order' && value !== '' && value !== DEFAULT_FILTERS[key],
  )

  return {
    filters,
    update,
    reset,
    hasActiveFilters,
    data,
    candidates: data?.candidates ?? [],
    summary: data?.summary ?? null,
    availableSkills: data?.available_skills ?? [],
    total: data?.total ?? 0,
    loading,
    error,
    refresh: () => run(filters, jobUid),
  }
}