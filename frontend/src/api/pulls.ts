import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { getJson, postJson } from './client'
import { keys } from './hooks'
import type { PullRequestList, PullSyncResult, ReviewDetail } from './types'

const pullsKey = (repoId: number) => ['pulls', repoId] as const

export function usePullRequests(repoId: number) {
  return useQuery({ queryKey: pullsKey(repoId), queryFn: () => getJson<PullRequestList>(`/repos/${String(repoId)}/pulls`), retry: false })
}

export function useReviewPullRequest(repoId: number) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (number: number) => postJson<ReviewDetail>(`/repos/${String(repoId)}/pulls/${String(number)}/review`),
    onSuccess: () => Promise.all([client.invalidateQueries({ queryKey: keys.reviews(repoId) }), client.invalidateQueries({ queryKey: pullsKey(repoId) })]),
  })
}

export function useSyncPullRequests(repoId: number) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: () => postJson<PullSyncResult>(`/repos/${String(repoId)}/pulls/sync`),
    onSuccess: () => Promise.all([client.invalidateQueries({ queryKey: keys.reviews(repoId) }), client.invalidateQueries({ queryKey: pullsKey(repoId) })]),
  })
}

export function useOpenPullRequestLink() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (url: string) => postJson<ReviewDetail>('/pulls/open', { url }),
    onSuccess: (review) => Promise.all([client.invalidateQueries({ queryKey: keys.repos }), client.invalidateQueries({ queryKey: keys.reviews(review.repo_id) })]),
  })
}
