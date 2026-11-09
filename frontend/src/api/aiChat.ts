import { useMutation, useMutationState, useQuery, useQueryClient } from '@tanstack/react-query'

import { deleteJson, getJson, postJson } from './client'
import { keys } from './hooks'
import { threadsKey } from './threads'
import type { AiChatMessage, CodeRangeRequest } from './types'

export interface AiChatRequest {
  target: string
  call_id: string
  message: string
  snippets: CodeRangeRequest[]
}

const chatKey = (reviewId: number) => ['ai-chat', reviewId] as const
const sendKey = (reviewId: number) => ['send-ai-chat', reviewId] as const
const chatPath = (reviewId: number) => `/reviews/${String(reviewId)}/ai-chat`

export function useAiChat(reviewId: number) {
  return useQuery({ queryKey: chatKey(reviewId), queryFn: () => getJson<AiChatMessage[]>(chatPath(reviewId)), retry: false })
}

export function useSendAiChat(reviewId: number) {
  const client = useQueryClient()
  return useMutation({
    mutationKey: sendKey(reviewId),
    mutationFn: (request: AiChatRequest) => postJson<AiChatMessage[]>(chatPath(reviewId), request),
    onSuccess: async (added) => {
      client.setQueryData<AiChatMessage[]>(chatKey(reviewId), (current) => [...(current ?? []), ...added])
      if (added.some((message) => message.comments.length > 0)) {
        await Promise.all([threadsKey(reviewId), keys.units(reviewId), keys.review(reviewId)].map((queryKey) => client.invalidateQueries({ queryKey })))
      }
    },
  })
}

export function usePendingAiChat(reviewId: number): AiChatRequest[] {
  return useMutationState({
    filters: { mutationKey: sendKey(reviewId), status: 'pending' },
    select: (mutation) => mutation.state.variables as AiChatRequest,
  })
}

export function useClearAiChat(reviewId: number) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: () => deleteJson<AiChatMessage[]>(chatPath(reviewId)),
    onSuccess: (messages) => {
      client.setQueryData(chatKey(reviewId), messages)
    },
  })
}
