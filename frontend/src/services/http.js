/**
 * Centralised Axios client for the FastAPI backend.
 *
 * Resolution order for the base URL:
 *  1. `VITE_API_BASE_URL` from `.env` (optional, use for deployed backends)
 *  2. empty string -> rely on the Vite dev proxy (/api -> http://127.0.0.1:8000)
 *
 * Copy `.env.example` to `.env` inside `frontend/` to override.
 */

import axios from 'axios'

const envBaseUrl = import.meta.env.VITE_API_BASE_URL

export const API_BASE_URL = envBaseUrl ? envBaseUrl.replace(/\/$/, '') : ''

export const API_PREFIX = '/api'

export const http = axios.create({
  baseURL: `${API_BASE_URL}${API_PREFIX}`,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
    Accept: 'application/json',
  },
})

// ---- Request interceptor (Phase 2: attach auth token) ----
http.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error),
)

// ---- Response interceptor: normalise errors ----
http.interceptors.response.use(
  (response) => response,
  (error) => {
    const payload = error?.response?.data
    const normalised = {
      status: error?.response?.status ?? 0,
      message:
        payload?.message ||
        payload?.detail ||
        error?.message ||
        'Network error - is the backend running?',
      details: payload?.details ?? payload?.detail ?? null,
      raw: error,
    }
    return Promise.reject(normalised)
  },
)

export default http