import { useEffect } from 'react'

import { newCallId, useCancelAiCall } from '../api/ai'
import { useAiReviewResults, useAiReviewStatus, useCancelAiReview, usePendingAiReviewCalls, useRunAiReview } from '../api/aiReview'
import type { AiReviewResult, AiReviewStatus } from '../api/types'

export interface AiReviewState {
  running: boolean
  status: AiReviewStatus | null
  result: AiReviewResult | null
  error: Error | null
  run: (target: string, again?: boolean) => void
  cancel: () => void
}

export function useAiReview(reviewId: number): AiReviewState {
  const review = useRunAiReview(reviewId)
  const calls = usePendingAiReviewCalls(reviewId)
  const cancelCall = useCancelAiCall()
  const cancelReview = useCancelAiReview(reviewId)
  const status = useAiReviewStatus(reviewId, calls.length > 0)
  const running = calls.length > 0 || status.data?.running === true
  const refresh = useAiReviewResults(reviewId)
  const step = status.data?.running ? `${status.data.phase ?? ''}:${String(status.data.done)}:${String(status.data.lookups)}` : null
  useEffect(() => {
    if (step !== null) {
      void refresh()
    }
  }, [step, refresh])
  return {
    running,
    status: status.data ?? null,
    result: review.data ?? null,
    error: review.error ?? cancelCall.error ?? cancelReview.error,
    run: (target, again = false) => {
      cancelCall.reset()
      cancelReview.reset()
      review.mutate({ target, call_id: newCallId(), again })
    },
    cancel: () => {
      for (const callId of calls) {
        cancelCall.mutate(callId)
      }
      cancelReview.mutate()
    },
  }
}
