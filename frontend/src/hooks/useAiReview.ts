import { useEffect } from 'react'

import { newCallId, useCancelAiCall } from '../api/ai'
import { useAiReviewResults, useAiReviewStatus, usePendingAiReviewCalls, useRunAiReview } from '../api/aiReview'
import type { AiReviewResult, AiReviewStatus } from '../api/types'

export interface AiReviewState {
  running: boolean
  cancellable: boolean
  status: AiReviewStatus | null
  result: AiReviewResult | null
  error: Error | null
  run: (target: string) => void
  cancel: () => void
}

export function useAiReview(reviewId: number): AiReviewState {
  const review = useRunAiReview(reviewId)
  const calls = usePendingAiReviewCalls(reviewId)
  const cancelCall = useCancelAiCall()
  const status = useAiReviewStatus(reviewId, calls.length > 0)
  const running = calls.length > 0 || status.data?.running === true
  const refresh = useAiReviewResults(reviewId)
  const step = status.data?.running ? `${status.data.phase ?? ''}:${String(status.data.done)}` : null
  useEffect(() => {
    if (step !== null) {
      void refresh()
    }
  }, [step, refresh])
  return {
    running,
    cancellable: calls.length > 0,
    status: status.data ?? null,
    result: review.data ?? null,
    error: review.error ?? cancelCall.error,
    run: (target) => {
      cancelCall.reset()
      review.mutate({ target, call_id: newCallId() })
    },
    cancel: () => {
      for (const callId of calls) {
        cancelCall.mutate(callId)
      }
    },
  }
}
