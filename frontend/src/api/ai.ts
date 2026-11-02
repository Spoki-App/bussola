import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { getJson, postJson, putJson } from './client'
import type { AiConfig, AiConfigFields, AiStatus, AiTestResult } from './types'

export const aiKey = (repoId?: number) => ['ai', repoId ?? null] as const

export function useAiStatus(repoId?: number) {
  return useQuery({
    queryKey: aiKey(repoId),
    queryFn: () => getJson<AiStatus>(repoId === undefined ? '/ai' : `/repos/${String(repoId)}/ai`),
    retry: false,
  })
}

const aiConfigKey = ['ai-config'] as const

export function useAiConfig() {
  return useQuery({ queryKey: aiConfigKey, queryFn: () => getJson<AiConfig>('/ai/config'), retry: false })
}

export function useSaveAiConfig() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (fields: AiConfigFields) => putJson<AiStatus>('/ai/config', fields),
    onSuccess: () => Promise.all([client.invalidateQueries({ queryKey: ['ai'] }), client.invalidateQueries({ queryKey: aiConfigKey })]),
  })
}

export function useTestAiConnection() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: () => postJson<AiTestResult>('/ai/test'),
    onSettled: () => client.invalidateQueries({ queryKey: ['ai'] }),
  })
}

export function newCallId(): string {
  return Array.from(crypto.getRandomValues(new Uint8Array(16)), (byte) => byte.toString(16).padStart(2, '0')).join('')
}

export function useCancelAiCall() {
  return useMutation({ mutationFn: (callId: string) => postJson<{ cancelled: boolean }>(`/ai/calls/${encodeURIComponent(callId)}/cancel`) })
}
