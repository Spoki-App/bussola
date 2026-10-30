import { useMutation, useQuery } from '@tanstack/react-query'

import { getJson, postJson } from './client'
import type { AiStatus, AiTestResult } from './types'

export const aiKey = (repoId?: number) => ['ai', repoId ?? null] as const

export function useAiStatus(repoId?: number) {
  return useQuery({
    queryKey: aiKey(repoId),
    queryFn: () => getJson<AiStatus>(repoId === undefined ? '/ai' : `/repos/${String(repoId)}/ai`),
    retry: false,
  })
}

export function useTestAiConnection() {
  return useMutation({ mutationFn: () => postJson<AiTestResult>('/ai/test') })
}
