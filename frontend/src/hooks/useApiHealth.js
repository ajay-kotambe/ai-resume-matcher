/**
 * useApiHealth - polls GET /api/health and exposes connection state.
 *
 * This is the single proof that the React app can talk to FastAPI.
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import { getHealth } from '../services/api'

export default function useApiHealth({ pollIntervalMs = 15000 } = {}) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const mounted = useRef(true)

  const check = useCallback(async () => {
    try {
      const health = await getHealth()
      if (!mounted.current) return
      setData(health)
      setError(null)
    } catch (err) {
      if (!mounted.current) return
      setError(err?.message || 'Backend unreachable')
    } finally {
      if (mounted.current) setLoading(false)
    }
  }, [])

  useEffect(() => {
    mounted.current = true
    check()
    const timer = setInterval(check, pollIntervalMs)
    return () => {
      mounted.current = false
      clearInterval(timer)
    }
  }, [check, pollIntervalMs])

  return {
    data,
    loading,
    error,
    isOnline: Boolean(data) && !error,
    refresh: check,
  }
}