import { useQuery } from '@tanstack/react-query'

import { getJson } from './client'

export interface LineLength {
  columns: number
  source: string | null
}

export function useLineLength(reviewId: number, revisionId: number | undefined) {
  return useQuery({
    queryKey: ['line-length', reviewId, revisionId],
    queryFn: () => getJson<LineLength>(`/reviews/${String(reviewId)}/line-length?revision_id=${String(revisionId)}`),
    enabled: revisionId !== undefined,
    staleTime: Infinity,
  })
}
