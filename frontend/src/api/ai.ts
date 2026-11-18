import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { getJson, postJson, putJson } from './client'
import type { AiConfig, AiConfigFields, AiModels, AiOperationChoice, AiOperationKey, AiPrompts, AiProviderName, AiStatus, AiTestResult } from './types'

export const aiKey = (repoId?: number) => ['ai', repoId ?? null] as const

export function useAiStatus(repoId?: number) {
  return useQuery({
    queryKey: aiKey(repoId),
    queryFn: () => getJson<AiStatus>(repoId === undefined ? '/ai' : `/repos/${String(repoId)}/ai`),
    retry: false,
  })
}

const aiConfigKey = ['ai-config'] as const
const aiModelsKey = ['ai-models'] as const

export function useAiConfig() {
  return useQuery({ queryKey: aiConfigKey, queryFn: () => getJson<AiConfig>('/ai/config'), retry: false })
}

export function useSaveAiConfig() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (fields: AiConfigFields) => putJson<AiStatus>('/ai/config', fields),
    onSuccess: () =>
      Promise.all([
        client.invalidateQueries({ queryKey: ['ai'] }),
        client.invalidateQueries({ queryKey: aiConfigKey }),
        client.invalidateQueries({ queryKey: aiModelsKey }),
      ]),
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

const aiPromptsKey = ['ai-prompts'] as const

export function useAiPrompts() {
  return useQuery({ queryKey: aiPromptsKey, queryFn: () => getJson<AiPrompts>('/ai/prompts'), retry: false })
}

export function useSaveAiOperation(key: AiOperationKey) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (choice: AiOperationChoice & { prompt: string }) => putJson<AiStatus>(`/ai/operations/${key}`, choice),
    onSuccess: () =>
      Promise.all([
        client.invalidateQueries({ queryKey: ['ai'] }),
        client.invalidateQueries({ queryKey: aiPromptsKey }),
        client.invalidateQueries({ queryKey: aiModelsKey }),
      ]),
  })
}

export function useAiModels(provider: AiProviderName | null, operation?: AiOperationKey, enabled = true) {
  const query = new URLSearchParams({ provider: provider ?? '', ...(operation && { operation }) })
  return useQuery({
    queryKey: [...aiModelsKey, provider, operation ?? null],
    queryFn: () => getJson<AiModels>(`/ai/models?${query.toString()}`),
    retry: false,
    staleTime: Infinity,
    enabled: enabled && provider !== null,
  })
}
