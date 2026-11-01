import { useCancelDescription, useDescribeUnit, useUnitDescription } from '../api/descriptions'
import type { Unit, UnitDescription } from '../api/types'

export interface AiDescriptionState {
  description: UnitDescription | null
  pending: boolean
  error: unknown
  run: (target: string, regenerate: boolean) => void
  cancel: () => void
}

export function useAiDescription(reviewId: number, unit: Unit, enabled: boolean): AiDescriptionState {
  const stored = useUnitDescription(reviewId, unit, enabled)
  const describe = useDescribeUnit(reviewId, unit)
  const cancelCall = useCancelDescription(reviewId, unit)
  return {
    description: stored.data ?? null,
    pending: describe.isPending,
    error: describe.error ?? cancelCall.error,
    run: (target, regenerate) => {
      cancelCall.reset()
      describe.mutate({ target, regenerate })
    },
    cancel: () => {
      describe.reset()
      cancelCall.mutate()
    },
  }
}
