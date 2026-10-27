import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { getJson, postJson, putJson } from './client'
import type { ForgeOverview, PublishResult } from './types'

const forgeKey = (reviewId: number) => ['forge', reviewId] as const

export function useForge(reviewId: number, enabled: boolean) {
  return useQuery({ queryKey: forgeKey(reviewId), queryFn: () => getJson<ForgeOverview>(`/reviews/${String(reviewId)}/forge`), enabled, retry: false })
}

export function useLinkPullRequest(reviewId: number) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (prNumber: number) => putJson<ForgeOverview>(`/reviews/${String(reviewId)}/forge`, { pr_number: prNumber }),
    onSuccess: (overview) => {
      client.setQueryData(forgeKey(reviewId), overview)
    },
  })
}

export function usePublish(reviewId: number) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (draft: boolean) => postJson<PublishResult>(`/reviews/${String(reviewId)}/forge/publish`, { draft }),
    onSettled: () => client.invalidateQueries({ queryKey: forgeKey(reviewId) }),
  })
}
