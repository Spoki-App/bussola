import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { getJson, postJson, putJson } from './client'
import { invalidate, keys, useInvalidatingMutation } from './hooks'
import { mentionsKey } from './mentions'
import { threadsKey } from './threads'
import type { ConversationSync, ForgeOverview, MergeOptions, MergeRequest, MergeResult, ReviewEvent, ReviewSubmitResult, SyncResult } from './types'

const forgeKey = (reviewId: number) => ['forge', reviewId] as const
const githubSyncKey = (reviewId: number) => ['github-sync', reviewId] as const

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
      void client.invalidateQueries({ queryKey: mentionsKey(reviewId) })
    },
  })
}

export function useSync(reviewId: number) {
  return useInvalidatingMutation([keys.units(reviewId), keys.review(reviewId), threadsKey(reviewId), forgeKey(reviewId)], () =>
    postJson<SyncResult>(`/reviews/${String(reviewId)}/sync`),
  )
}

export function useSubmitReview(reviewId: number) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (request: { event: ReviewEvent; body: string }) => postJson<ReviewSubmitResult>(`/reviews/${String(reviewId)}/forge/review`, request),
    onSuccess: () => {
      void invalidate(client, [keys.review(reviewId), threadsKey(reviewId), githubSyncKey(reviewId)])
    },
  })
}

export function useGitHubSync(reviewId: number, headSha: string | undefined) {
  const client = useQueryClient()
  return useQuery({
    queryKey: [...githubSyncKey(reviewId), headSha],
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

export function useMergeOptions(reviewId: number) {
  return useQuery({ queryKey: [...forgeKey(reviewId), 'merge'], queryFn: () => getJson<MergeOptions>(`/reviews/${String(reviewId)}/forge/merge`), retry: false })
}

export function useMerge(reviewId: number) {
  return useInvalidatingMutation([keys.review(reviewId), forgeKey(reviewId), threadsKey(reviewId)], (request: MergeRequest) =>
    postJson<MergeResult>(`/reviews/${String(reviewId)}/forge/merge`, request),
  )
}
