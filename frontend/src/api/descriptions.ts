import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

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

export function useDescribeUnit(reviewId: number, unit: Unit) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (request: DescribeRequest) => postJson<UnitDescription>(unitPath(reviewId, unit), request),
    onSuccess: async (described) => {
      const queryKey = descriptionsKey(reviewId, unit.revision_id)
      await client.cancelQueries({ queryKey })
      client.setQueryData<UnitDescription[]>(queryKey, (descriptions = []) => [
        ...descriptions.filter((description) => description.unit_id !== described.unit_id),
        described,
      ])
    },
  })
}
