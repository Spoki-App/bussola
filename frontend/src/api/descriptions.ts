import { useMutation, useMutationState, useQuery, useQueryClient } from '@tanstack/react-query'

import { getJson, postJson } from './client'
import type { Unit, UnitDescription } from './types'

const descriptionsKey = (reviewId: number, revisionId: number) => ['descriptions', reviewId, revisionId] as const

interface DescribeRequest {
  target: string
  call_id: string
  regenerate: boolean
}

function unitPath(reviewId: number, unit: Unit) {
  return `/reviews/${String(reviewId)}/units/${String(unit.id)}/description`
}

export function useUnitDescription(reviewId: number, unit: Unit) {
  return useQuery({
    queryKey: descriptionsKey(reviewId, unit.revision_id),
    queryFn: () => getJson<UnitDescription[]>(`/reviews/${String(reviewId)}/descriptions?revision_id=${String(unit.revision_id)}`),
    select: (descriptions) => descriptions.find((description) => description.unit_id === unit.id) ?? null,
    retry: false,
  })
}

export const describeKey = (reviewId: number, unit: Unit) => ['describe', reviewId, unit.id] as const

export function useDescribeUnit(reviewId: number, unit: Unit) {
  const client = useQueryClient()
  return useMutation({
    mutationKey: describeKey(reviewId, unit),
    mutationFn: (request: DescribeRequest) => postJson<UnitDescription>(unitPath(reviewId, unit), request),
    onSuccess: (described) => {
      const queryKey = descriptionsKey(reviewId, unit.revision_id)
      client.setQueryData<UnitDescription[]>(queryKey, (descriptions) =>
        descriptions && [...descriptions.filter((description) => description.unit_id !== described.unit_id), described],
      )
      return client.invalidateQueries({ queryKey })
    },
  })
}

export function usePendingDescribeCalls(reviewId: number, unit: Unit): string[] {
  return useMutationState({
    filters: { mutationKey: describeKey(reviewId, unit), status: 'pending' },
    select: (mutation) => (mutation.state.variables as DescribeRequest).call_id,
  })
}
