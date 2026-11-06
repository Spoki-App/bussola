import { useQuery } from '@tanstack/react-query'

import { getJson } from './client'

export const mentionsKey = (reviewId: number) => ['mentions', reviewId] as const

export function useMentionCandidates(reviewId: number, enabled: boolean) {
  return useQuery({
    queryKey: mentionsKey(reviewId),
    queryFn: () => getJson<string[]>(`/reviews/${String(reviewId)}/mentions`),
    enabled,
    staleTime: Infinity,
    retry: false,
  })
}
