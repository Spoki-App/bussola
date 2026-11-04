import { newCallId, useCancelAiCall } from '../api/ai'
import { useRateUnits } from '../api/descriptions'
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
  const cancelCall = useCancelAiCall()
  return {
    pending: rate.isPending,
    result: rate.data ?? null,
    error: rate.error ?? cancelCall.error,
    run: (target) => {
      cancelCall.reset()
      rate.mutate({ target, call_id: newCallId() })
    },
    cancel: () => {
      if (rate.variables) {
        cancelCall.mutate(rate.variables.call_id)
      }
    },
  }
}
