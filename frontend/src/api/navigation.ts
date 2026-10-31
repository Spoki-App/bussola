import { useQuery } from '@tanstack/react-query'

import { getJson, postJson } from './client'
import type { Side } from './types'

export type TargetRole = 'definition' | 'usage'

export interface NavigationTarget {
  role: TargetRole
  path: string
  line: number
  column: number
  preview: string
  side: Side
  unit_id: number | null
}

export interface ServerHint {
  family: string
  language: string
  install: string
}

export interface NavigationResult {
  ready: boolean
  symbol: string | null
  origin: 'definition' | 'reference' | null
  resolver: 'tree-sitter' | 'language-server'
  targets: NavigationTarget[]
  server_hint: ServerHint | null
}

export interface SourceFile {
  path: string
  side: Side
  commit: string
  text: string
  url: string | null
}

export interface CodeLocation {
  path: string
  line: number
  side: Side
}

export interface NavigationRequest extends CodeLocation {
  column: number
}

const INDEX_STALE_MS = Number.POSITIVE_INFINITY

function revisionQuery(revisionId: number | undefined, side: Side): string {
  const params = new URLSearchParams({ side })
  if (revisionId !== undefined) {
    params.set('revision_id', String(revisionId))
  }
  return params.toString()
}

export function fetchNavigation(reviewId: number, revisionId: number | undefined, request: NavigationRequest): Promise<NavigationResult> {
  const params = new URLSearchParams(revisionQuery(revisionId, request.side))
  params.set('path', request.path)
  params.set('line', String(request.line))
  params.set('column', String(request.column))
  return getJson<NavigationResult>(`/reviews/${String(reviewId)}/navigation?${params.toString()}`)
}

export function usePrepareNavigation(reviewId: number, revisionId: number | undefined) {
  return useQuery({
    queryKey: ['navigation-index', reviewId, revisionId],
    queryFn: () => postJson<{ ready: boolean }>(`/reviews/${String(reviewId)}/navigation/index?${revisionQuery(revisionId, 'head')}`),
    enabled: revisionId !== undefined,
    staleTime: INDEX_STALE_MS,
    retry: false,
  })
}

export function useSourceFile(reviewId: number, revisionId: number | undefined, location: CodeLocation | undefined) {
  const path = location?.path ?? ''
  const side = location?.side ?? 'head'
  return useQuery({
    queryKey: ['source', reviewId, revisionId, side, path],
    queryFn: () => getJson<SourceFile>(`/reviews/${String(reviewId)}/source?${revisionQuery(revisionId, side)}&path=${encodeURIComponent(path)}`),
    enabled: location !== undefined,
    staleTime: INDEX_STALE_MS,
  })
}
