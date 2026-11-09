import { useMutation, useMutationState, useQuery, useQueryClient } from '@tanstack/react-query'

import { deleteJson, getJson, postJson } from './client'
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
    onSuccess: (added) => {
      client.setQueryData<AiChatMessage[]>(chatKey(reviewId), (current) => [...(current ?? []), ...added])
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
