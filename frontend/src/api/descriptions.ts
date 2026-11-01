import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { getJson, postJson } from './client'
import type { Unit, UnitDescription } from './types'

export const descriptionsKey = (reviewId: number, revisionId: number) => ['descriptions', reviewId, revisionId] as const

export interface DescribeRequest {
  target: string
  regenerate: boolean
}

function unitPath(reviewId: number, unit: Unit) {
  return `/reviews/${String(reviewId)}/units/${String(unit.id)}/description`
}

export function useUnitDescription(reviewId: number, unit: Unit, enabled: boolean) {
  return useQuery({
    enabled,
    queryKey: descriptionsKey(reviewId, unit.revision_id),
    queryFn: () => getJson<UnitDescription[]>(`/reviews/${String(reviewId)}/descriptions?revision_id=${String(unit.revision_id)}`),
    select: (descriptions) => descriptions.find((description) => description.unit_id === unit.id) ?? null,
    retry: false,
  })
}

export function useDescribeUnit(reviewId: number, unit: Unit) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (request: DescribeRequest) => postJson<UnitDescription>(unitPath(reviewId, unit), request),
    onSuccess: (described) => {
      client.setQueryData<UnitDescription[]>(descriptionsKey(reviewId, unit.revision_id), (descriptions = []) => [
        ...descriptions.filter((description) => description.unit_id !== described.unit_id),
        described,
      ])
    },
  })
}

export function useCancelDescription(reviewId: number, unit: Unit) {
  return useMutation({ mutationFn: () => postJson<{ cancelled: boolean }>(`${unitPath(reviewId, unit)}/cancel`) })
}
