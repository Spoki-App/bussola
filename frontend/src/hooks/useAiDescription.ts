import { useRef } from 'react'

import { newCallId, useCancelAiCall } from '../api/ai'
import { useDescribeUnit, useUnitDescription } from '../api/descriptions'
import type { Unit, UnitDescription } from '../api/types'

export interface AiDescriptionState {
  description: UnitDescription | null
  pending: boolean
  error: Error | null
  run: (target: string, regenerate: boolean) => void
  cancel: () => void
}

export function useAiDescription(reviewId: number, unit: Unit): AiDescriptionState {
  const stored = useUnitDescription(reviewId, unit)
  const describe = useDescribeUnit(reviewId, unit)
  const cancelCall = useCancelAiCall()
  const callId = useRef<string | null>(null)
  return {
    description: stored.data ?? null,
    pending: describe.isPending,
    error: describe.error ?? cancelCall.error,
    run: (target, regenerate) => {
      cancelCall.reset()
      callId.current = newCallId()
      describe.mutate({ target, regenerate, call_id: callId.current })
    },
    cancel: () => {
      describe.reset()
      if (callId.current !== null) {
        cancelCall.mutate(callId.current)
      }
    },
  }
}
