import { useQuery } from '@tanstack/react-query'

import { getJson } from './client'

export function useMentionCandidates(reviewId: number, enabled: boolean) {
  return useQuery({
    queryKey: ['mentions', reviewId],
    queryFn: () => getJson<string[]>(`/reviews/${String(reviewId)}/mentions`),
    enabled,
    staleTime: Infinity,
    retry: false,
  })
}
