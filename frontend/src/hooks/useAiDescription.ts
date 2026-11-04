import { newCallId, useCancelAiCall } from '../api/ai'
import { useDescribeUnit, usePendingDescribeCalls, useUnitDescription } from '../api/descriptions'
import type { DescribedUnit, Unit, UnitDescription } from '../api/types'

export interface AiDescriptionState {
  description: DescribedUnit | null
  rating: UnitDescription | null
  loaded: boolean
  pending: boolean
  error: Error | null
  run: (target: string, regenerate: boolean) => void
  cancel: () => void
}

export function useAiDescription(reviewId: number, unit: Unit): AiDescriptionState {
  const stored = useUnitDescription(reviewId, unit)
  const describe = useDescribeUnit(reviewId, unit)
  const running = usePendingDescribeCalls(reviewId, unit)
  const cancelCall = useCancelAiCall()
  const rating = stored.data ?? null
  return {
    description: rating && isDescribed(rating) ? rating : null,
    rating,
    loaded: !stored.isPending,
    pending: running.length > 0,
    error: describe.error ?? cancelCall.error,
    run: (target, regenerate) => {
      cancelCall.reset()
      describe.mutate({ target, regenerate, call_id: newCallId() })
    },
    cancel: () => {
      describe.reset()
      for (const callId of running) {
        cancelCall.mutate(callId)
      }
    },
  }
}

function isDescribed(rating: UnitDescription): rating is DescribedUnit {
  return rating.description !== null
}
