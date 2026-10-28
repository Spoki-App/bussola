import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { getJson, postJson, putJson } from './client'
import { invalidate, keys, useInvalidatingMutation } from './hooks'
import { threadsKey } from './threads'
import type { ConversationSync, ForgeOverview, SyncResult } from './types'

const forgeKey = (reviewId: number) => ['forge', reviewId] as const

export const GITHUB_SYNC_INTERVAL_MS = 3 * 60 * 1000
const GITHUB_SYNC_STALE_MS = 60 * 1000

export function useForge(reviewId: number) {
  return useQuery({ queryKey: forgeKey(reviewId), queryFn: () => getJson<ForgeOverview>(`/reviews/${String(reviewId)}/forge`), retry: false })
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

export function useSync(reviewId: number) {
  return useInvalidatingMutation([keys.units(reviewId), keys.review(reviewId), threadsKey(reviewId), forgeKey(reviewId)], () =>
    postJson<SyncResult>(`/reviews/${String(reviewId)}/sync`),
  )
}

export function useGitHubSync(reviewId: number, headSha: string | undefined) {
  const client = useQueryClient()
  return useQuery({
    queryKey: ['github-sync', reviewId, headSha],
    queryFn: async () => {
      const result = await postJson<ConversationSync>(`/reviews/${String(reviewId)}/forge/sync`)
      const stale = result.changes > 0 ? [keys.review(reviewId), keys.units(reviewId), threadsKey(reviewId), forgeKey(reviewId)] : [keys.review(reviewId)]
      await invalidate(client, stale)
      return result
    },
    enabled: headSha !== undefined,
    refetchInterval: GITHUB_SYNC_INTERVAL_MS,
    staleTime: GITHUB_SYNC_STALE_MS,
    retry: false,
  })
}
