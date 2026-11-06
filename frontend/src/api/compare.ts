import { useQuery } from '@tanstack/react-query'

import { getJson, postJson } from './client'
import type { Comparison, ComparisonRequest, Move } from './types'

export function useMoves(reviewId: number, revisionId: number | undefined) {
  return useQuery({
    queryKey: ['moves', reviewId, revisionId],
    queryFn: () => getJson<Move[]>(`/reviews/${String(reviewId)}/moves?revision_id=${String(revisionId)}`),
    enabled: revisionId !== undefined,
    staleTime: Infinity,
  })
}

export function useComparison(reviewId: number, request: ComparisonRequest) {
  return useQuery({
    queryKey: ['compare', reviewId, request],
    queryFn: () => postJson<Comparison>(`/reviews/${String(reviewId)}/compare`, request),
    staleTime: Infinity,
  })
}
