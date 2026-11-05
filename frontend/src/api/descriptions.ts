import { useMutation, useMutationState, useQuery, useQueryClient } from '@tanstack/react-query'

import { getJson, postJson } from './client'
import type { RateImpactResult, Unit, UnitDescription } from './types'

const RATING_POLL_MS = 2000

export const descriptionsKey = (reviewId: number, revisionId?: number) => ['descriptions', reviewId, ...(revisionId === undefined ? [] : [revisionId])] as const

interface AiCall {
  target: string
  call_id: string
}

interface DescribeRequest extends AiCall {
  regenerate: boolean
}

function unitPath(reviewId: number, unit: Unit) {
  return `/reviews/${String(reviewId)}/units/${String(unit.id)}/description`
}

function descriptionsQuery(reviewId: number, revisionId: number) {
  return {
    queryKey: descriptionsKey(reviewId, revisionId),
    queryFn: () => getJson<UnitDescription[]>(`/reviews/${String(reviewId)}/descriptions?revision_id=${String(revisionId)}`),
    retry: false,
  }
}

export function useDescriptions(reviewId: number, revisionId: number | undefined, poll: boolean) {
  return useQuery({ ...descriptionsQuery(reviewId, revisionId ?? 0), enabled: revisionId !== undefined, refetchInterval: poll ? RATING_POLL_MS : false })
}

export function useUnitDescription(reviewId: number, unit: Unit) {
  return useQuery({
    ...descriptionsQuery(reviewId, unit.revision_id),
    select: (descriptions) => descriptions.find((description) => description.unit_id === unit.id) ?? null,
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

const rateKey = (reviewId: number) => ['rate-impact', reviewId] as const

export function useRateUnits(reviewId: number) {
  const client = useQueryClient()
  return useMutation({
    mutationKey: rateKey(reviewId),
    mutationFn: (request: AiCall) => postJson<RateImpactResult>(`/reviews/${String(reviewId)}/impact`, request),
    onSettled: () => client.invalidateQueries({ queryKey: descriptionsKey(reviewId) }),
  })
}

export function usePendingRateCalls(reviewId: number): string[] {
  return useMutationState({
    filters: { mutationKey: rateKey(reviewId), status: 'pending' },
    select: (mutation) => (mutation.state.variables as AiCall).call_id,
  })
}
