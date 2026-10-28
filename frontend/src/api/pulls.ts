import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { getJson, postJson } from './client'
import { invalidate, keys, useInvalidatingMutation } from './hooks'
import type { PullRequestList, PullSyncResult, ReviewDetail } from './types'

const pullsKey = (repoId: number) => ['pulls', repoId] as const

export function usePullRequests(repoId: number) {
  return useQuery({ queryKey: pullsKey(repoId), queryFn: () => getJson<PullRequestList>(`/repos/${String(repoId)}/pulls`), retry: false })
}

export function useReviewPullRequest(repoId: number) {
  return useInvalidatingMutation([keys.reviews(repoId), pullsKey(repoId)], (number: number) =>
    postJson<ReviewDetail>(`/repos/${String(repoId)}/pulls/${String(number)}/review`),
  )
}

export function useSyncPullRequests(repoId: number) {
  return useInvalidatingMutation([keys.reviews(repoId), pullsKey(repoId)], () => postJson<PullSyncResult>(`/repos/${String(repoId)}/pulls/sync`))
}

export function useOpenPullRequestLink() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (url: string) => postJson<ReviewDetail>('/pulls/open', { url }),
    onSuccess: (review) => invalidate(client, [keys.repos, keys.reviews(review.repo_id)]),
  })
}
