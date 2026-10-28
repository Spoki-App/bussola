import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { deleteJson, getJson, postJson } from './client'
import type {
  ApprovalRequest,
  DirectoryListing,
  RepositoryScan,
  DiffMode,
  Refs,
  Repo,
  Review,
  ReviewDetail,
  Reviewer,
  Unit,
  UnitDiff,
  UnitFilter,
} from './types'

const REVIEW_POLL_MS = 5000

export const keys = {
  repos: ['repos'] as const,
  refs: (repoId: number) => ['refs', repoId] as const,
  reviews: (repoId: number) => ['reviews', repoId] as const,
  review: (reviewId: number) => ['review', reviewId] as const,
  units: (reviewId: number) => ['units', reviewId] as const,
  diffs: (reviewId: number) => ['diff', reviewId] as const,
}

export function useMe() {
  return useQuery({ queryKey: ['me'], queryFn: () => getJson<Reviewer>('/me') })
}

export function useRepos() {
  return useQuery({ queryKey: keys.repos, queryFn: () => getJson<Repo[]>('/repos') })
}

export function useAddRepo() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (path: string) => postJson<Repo>('/repos', { path }),
    onSuccess: () =>
      Promise.all([client.invalidateQueries({ queryKey: keys.repos }), client.invalidateQueries({ queryKey: ['repository-scan'] })]),
  })
}

export function useDirectories(path: string | undefined) {
  return useQuery({
    queryKey: ['directories', path ?? ''],
    queryFn: () => getJson<DirectoryListing>(path === undefined ? '/directories' : `/directories?path=${encodeURIComponent(path)}`),
    placeholderData: (previous) => previous,
    retry: false,
  })
}

const SCAN_STALE_MS = 5 * 60 * 1000

export function useRepositoryScan() {
  return useQuery({
    queryKey: ['repository-scan'],
    queryFn: () => getJson<RepositoryScan>('/directories/repositories'),
    staleTime: SCAN_STALE_MS,
    retry: false,
  })
}

export function useRefs(repoId: number, enabled: boolean) {
  return useQuery({ queryKey: keys.refs(repoId), queryFn: () => getJson<Refs>(`/repos/${String(repoId)}/refs`), enabled })
}

export function useReviews(repoId: number) {
  return useQuery({ queryKey: keys.reviews(repoId), queryFn: () => getJson<Review[]>(`/repos/${String(repoId)}/reviews`) })
}

export function useCreateReview(repoId: number) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (body: { head_ref: string; base_ref: string }) => postJson<ReviewDetail>(`/repos/${String(repoId)}/reviews`, body),
    onSuccess: () => client.invalidateQueries({ queryKey: keys.reviews(repoId) }),
  })
}

export function useReview(reviewId: number) {
  return useQuery({
    queryKey: keys.review(reviewId),
    queryFn: () => getJson<ReviewDetail>(`/reviews/${String(reviewId)}`),
    refetchInterval: REVIEW_POLL_MS,
  })
}

export function useUnits(reviewId: number, revisionId: number | undefined, filter: UnitFilter) {
  return useQuery({
    queryKey: [...keys.units(reviewId), revisionId, filter],
    queryFn: () => getJson<Unit[]>(`/reviews/${String(reviewId)}/units?revision_id=${String(revisionId)}&filter=${filter}`),
    enabled: revisionId !== undefined,
    placeholderData: (previous) => previous,
  })
}

export function useUnitDiff(reviewId: number, unitId: number, mode: DiffMode | undefined, enabled: boolean) {
  return useQuery({
    queryKey: [...keys.diffs(reviewId), unitId, mode],
    queryFn: () => getJson<UnitDiff>(`/reviews/${String(reviewId)}/units/${String(unitId)}/diff${mode ? `?mode=${mode}` : ''}`),
    enabled,
  })
}

function useReviewMutation<TArgs, TResult>(reviewId: number, mutationFn: (args: TArgs) => Promise<TResult>) {
  const client = useQueryClient()
  return useMutation({
    mutationFn,
    onSuccess: () =>
      Promise.all([
        client.invalidateQueries({ queryKey: keys.units(reviewId) }),
        client.invalidateQueries({ queryKey: keys.diffs(reviewId) }),
        client.invalidateQueries({ queryKey: keys.review(reviewId) }),
      ]),
  })
}

export function useApprove(reviewId: number) {
  return useReviewMutation(reviewId, (body: ApprovalRequest) => postJson<unknown>(`/reviews/${String(reviewId)}/approvals`, body))
}

export function useRevoke(reviewId: number) {
  return useReviewMutation(reviewId, (approvalId: string) => deleteJson<unknown>(`/reviews/${String(reviewId)}/approvals/${approvalId}`))
}

export function useRevokeSelections(reviewId: number) {
  return useReviewMutation(reviewId, (selectionIds: string[]) =>
    Promise.all(selectionIds.map((id) => deleteJson<unknown>(`/reviews/${String(reviewId)}/row-approvals/${id}`))),
  )
}

export function useFinishReview(reviewId: number) {
  return useReviewMutation(reviewId, () => postJson<unknown>(`/reviews/${String(reviewId)}/sessions`))
}
