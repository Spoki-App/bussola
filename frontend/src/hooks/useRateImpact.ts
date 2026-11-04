import { newCallId, useCancelAiCall } from '../api/ai'
import { usePendingRateCalls, useRateUnits } from '../api/descriptions'
import type { RateImpactResult } from '../api/types'

export interface RateImpactState {
  pending: boolean
  result: RateImpactResult | null
  error: Error | null
  run: (target: string) => void
  cancel: () => void
}

export function useRateImpact(reviewId: number): RateImpactState {
  const rate = useRateUnits(reviewId)
  const running = usePendingRateCalls(reviewId)
  const cancelCall = useCancelAiCall()
  return {
    pending: running.length > 0,
    result: rate.data ?? null,
    error: rate.error ?? cancelCall.error,
    run: (target) => {
      cancelCall.reset()
      rate.mutate({ target, call_id: newCallId() })
    },
    cancel: () => {
      for (const callId of running) {
        cancelCall.mutate(callId)
      }
    },
  }
}
