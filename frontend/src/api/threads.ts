import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { deleteJson, getJson, patchJson, postJson } from './client'
import { keys } from './hooks'
import type { Comment, NewThreadRequest, Thread, ThreadStatus } from './types'

const threadsKey = (reviewId: number) => ['threads', reviewId] as const

export function useThreads(reviewId: number, revisionId: number | undefined) {
  return useQuery({
    queryKey: [...threadsKey(reviewId), revisionId],
    queryFn: () => getJson<Thread[]>(`/reviews/${String(reviewId)}/threads?revision_id=${String(revisionId)}`),
    enabled: revisionId !== undefined,
  })
}

function useThreadMutation<TArgs, TResult>(reviewId: number, mutationFn: (args: TArgs) => Promise<TResult>) {
  const client = useQueryClient()
  return useMutation({
    mutationFn,
    onSuccess: () =>
      Promise.all([
        client.invalidateQueries({ queryKey: threadsKey(reviewId) }),
        client.invalidateQueries({ queryKey: keys.units(reviewId) }),
        client.invalidateQueries({ queryKey: keys.review(reviewId) }),
      ]),
  })
}

export function useCreateThread(reviewId: number) {
  return useThreadMutation(reviewId, (body: NewThreadRequest) => postJson<Thread>(`/reviews/${String(reviewId)}/threads`, body))
}

export function useReply(reviewId: number) {
  return useThreadMutation(reviewId, ({ threadId, body }: { threadId: string; body: string }) => postJson<Comment>(`/threads/${threadId}/comments`, { body }))
}

export function useSetThreadStatus(reviewId: number) {
  return useThreadMutation(reviewId, ({ threadId, status }: { threadId: string; status: ThreadStatus }) => patchJson<Thread>(`/threads/${threadId}`, { status }))
}

export function useEditComment(reviewId: number) {
  return useThreadMutation(reviewId, ({ commentId, body }: { commentId: string; body: string }) => patchJson<Comment>(`/comments/${commentId}`, { body }))
}

export function useDeleteComment(reviewId: number) {
  return useThreadMutation(reviewId, (commentId: string) => deleteJson<Comment>(`/comments/${commentId}`))
}
