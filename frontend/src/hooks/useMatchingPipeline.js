/**
 * useMatchingPipeline - drives the full analysis flow and reports each stage
 * so the UI can show progress instead of appearing frozen.
 */

import { useCallback, useState } from 'react'
import { runMatching } from '../services/api'

export const STAGES = [
  { key: 'uploading', label: 'Uploading resumes' },
  { key: 'extracting', label: 'Extracting resume information' },
  { key: 'analyzing', label: 'Analyzing job description' },
  { key: 'matching', label: 'Calculating candidate matches' },
  { key: 'explaining', label: 'Generating explanations' },
]

const DONE = 'done'

export default function useMatchingPipeline() {
  const [stage, setStage] = useState(null)
  const [uploadPercent, setUploadPercent] = useState(0)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  const isProcessing = Boolean(stage)

  /**
   * Advance through the visible stages on a timer while the single request is
   * in flight. The real work happens server-side in one call; this keeps the
   * recruiter informed rather than showing a frozen spinner.
   */
  const advance = useCallback(() => {
    let index = 0
    setStage(STAGES[0].key)
    const timer = setInterval(() => {
      index += 1
      if (index >= STAGES.length) {
        clearInterval(timer)
        return
      }
      setStage(STAGES[index].key)
    }, 1400)
    return timer
  }, [])

  const analyze = useCallback(
    async (files, jobDescription, useAi = false) => {
      setError(null)
      setResult(null)
      setUploadPercent(0)
      const timer = advance()
      try {
        const data = await runMatching(files, jobDescription, {
          useAi,
          onProgress: setUploadPercent,
        })
        setStage(DONE)
        setResult(data)
        return data
      } catch (err) {
        setError(err)
        setStage(null)
        throw err
      } finally {
        clearInterval(timer)
        // Hold the completed state briefly so the checkmark is visible.
        setTimeout(() => setStage(null), 900)
      }
    },
    [advance],
  )

  const reset = useCallback(() => {
    setStage(null)
    setResult(null)
    setError(null)
    setUploadPercent(0)
  }, [])

  const stages = STAGES.map((item) => ({
    ...item,
    status:
      stage === DONE
        ? DONE
        : stage === item.key
          ? 'active'
          : STAGES.findIndex((s) => s.key === stage) > STAGES.indexOf(item)
            ? DONE
            : 'pending',
  }))

  return {
    analyze,
    reset,
    stages,
    activeStage: stage,
    isProcessing,
    uploadPercent,
    result,
    error,
  }
}