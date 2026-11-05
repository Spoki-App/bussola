import { useMutation, useMutationState, useQuery, useQueryClient } from '@tanstack/react-query'
import { useCallback } from 'react'

import { getJson, postJson } from './client'
import { descriptionsKey } from './descriptions'
import { keys } from './hooks'
import { threadsKey } from './threads'
import type { AiReviewResult, AiReviewRun, AiReviewRunDetail, AiReviewStatus } from './types'

const PROGRESS_POLL_MS = 1000

interface AiCall {
  target: string
  call_id: string
  again: boolean
}

export const aiReviewKey = (reviewId: number) => ['ai-review', reviewId] as const
const runsKey = (reviewId: number) => ['ai-review-runs', reviewId] as const
const runKey = (reviewId: number) => ['run-ai-review', reviewId] as const

const reviewPath = (reviewId: number) => `/reviews/${String(reviewId)}/ai-review`

export function useAiReviewStatus(reviewId: number, poll: boolean) {
  return useQuery({
    queryKey: aiReviewKey(reviewId),
    queryFn: () => getJson<AiReviewStatus>(reviewPath(reviewId)),
    retry: false,
    refetchInterval: (query) => (poll || query.state.data?.running ? PROGRESS_POLL_MS : false),
  })
}

export function useAiReviewResults(reviewId: number) {
  const client = useQueryClient()
  return useCallback(
    () => Promise.all([threadsKey(reviewId), descriptionsKey(reviewId), keys.units(reviewId), keys.review(reviewId), runsKey(reviewId)].map((queryKey) => client.invalidateQueries({ queryKey }))),
    [client, reviewId],
  )
}

export function useRunAiReview(reviewId: number) {
  const client = useQueryClient()
  const refresh = useAiReviewResults(reviewId)
  return useMutation({
    mutationKey: runKey(reviewId),
    mutationFn: (request: AiCall) => postJson<AiReviewResult>(reviewPath(reviewId), request),
    onSettled: () => Promise.all([refresh(), client.invalidateQueries({ queryKey: aiReviewKey(reviewId) })]),
  })
}

export function usePendingAiReviewCalls(reviewId: number): string[] {
  return useMutationState({
    filters: { mutationKey: runKey(reviewId), status: 'pending' },
    select: (mutation) => (mutation.state.variables as AiCall).call_id,
  })
}

export function useCancelAiReview(reviewId: number) {
  return useMutation({ mutationFn: () => postJson<{ cancelled: boolean }>(`${reviewPath(reviewId)}/cancel`) })
}

export function useAiReviewRuns(reviewId: number) {
  return useQuery({ queryKey: runsKey(reviewId), queryFn: () => getJson<AiReviewRun[]>(`${reviewPath(reviewId)}/runs`), retry: false })
}

export function useAiReviewRun(reviewId: number, runId: number | null) {
  return useQuery({
    queryKey: [...runsKey(reviewId), runId],
    queryFn: () => getJson<AiReviewRunDetail>(`${reviewPath(reviewId)}/runs/${String(runId)}`),
    enabled: runId !== null,
    retry: false,
  })
}
