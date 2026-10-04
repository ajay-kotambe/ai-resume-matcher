/**
 * API service layer for the AI Resume Matcher.
 *
 * Every backend call lives here so components stay presentational.
 */

import http, { API_BASE_URL } from './http'

// --- Health ---------------------------------------------------------------
export const getHealth = async () => (await http.get('/health')).data
export const getStatus = async () => (await http.get('/health/status')).data
export const getRootInfo = async () => (await http.get(`${API_BASE_URL}/`)).data

// --- Resumes --------------------------------------------------------------
/**
 * Upload resumes with real progress reporting.
 * @param {File[]} files
 * @param {(percent: number) => void} [onProgress]
 */
export async function uploadResumes(files, onProgress) {
  const form = new FormData()
  files.forEach((file) => form.append('files', file))

  const { data } = await http.post('/resumes/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: (event) => {
      if (onProgress && event.total) {
        onProgress(Math.round((event.loaded / event.total) * 100))
      }
    },
  })
  return data
}

export const listResumes = async () => (await http.get('/resumes')).data
export const deleteResumes = async () => (await http.delete('/resumes')).data

// --- Jobs -----------------------------------------------------------------
export async function analyzeJobDescription(jobDescription, useAi = false) {
  const { data } = await http.post('/jobs/analyze', {
    job_description: jobDescription,
    use_ai: Boolean(useAi),
  })
  return data
}

/** Returns the most recently analysed job, or throws 404 when none exist. */
export const listJobs = async () => (await http.get('/jobs')).data

// --- Matching -------------------------------------------------------------
/** Upload resumes + job description in one request (dashboard flow). */
export async function runMatching(files, jobDescription, { useAi = false, onProgress } = {}) {
  const form = new FormData()
  form.append('job_description', jobDescription)
  form.append('use_ai', String(Boolean(useAi)))
  files.forEach((file) => form.append('files', file))

  const { data } = await http.post('/matching/analyze-and-upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 300000,
    onUploadProgress: (event) => {
      if (onProgress && event.total) {
        onProgress(Math.round((event.loaded / event.total) * 100))
      }
    },
  })
  return data
}

/** Re-score already-uploaded resumes against the latest job. */
export const rerunMatching = async (payload = {}) => (await http.post('/matching/analyze', payload)).data

// --- Candidates -----------------------------------------------------------
/**
 * Search + filter candidates. Runs against processed server-side data.
 */
export async function searchCandidates(params = {}) {
  const clean = {}
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') clean[key] = value
  })
  const { data } = await http.get('/candidates', { params: clean })
  return data
}

export const getCandidate = async (candidateUid) =>
  (await http.get(`/candidates/${candidateUid}`)).data