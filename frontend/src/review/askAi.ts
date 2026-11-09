import { createContext } from 'react'

import type { CodeRangeRequest, Side, Unit } from '../api/types'
import { plural } from './text'

export interface ChatSnippetDraft {
  range: CodeRangeRequest
  label: string
}

export const MAX_CHAT_SNIPPETS = 10

export const AskAiContext = createContext<((snippet: ChatSnippetDraft) => void) | null>(null)

export function sameRange(first: CodeRangeRequest, second: CodeRangeRequest): boolean {
  return first.unit_id === second.unit_id && first.side === second.side && first.line_offset === second.line_offset && first.line_count === second.line_count
}

export function withSnippet(snippets: ChatSnippetDraft[], added: ChatSnippetDraft): ChatSnippetDraft[] {
  if (snippets.some((snippet) => sameRange(snippet.range, added.range))) {
    return snippets
  }
  return [...snippets, added].slice(-MAX_CHAT_SNIPPETS)
}

export function snippetLabel(unit: Pick<Unit, 'path' | 'qualified_name'>, lineCount: number, side: Side): string {
  const name = unit.qualified_name ? `${unit.path}::${unit.qualified_name}` : unit.path
  return `${name}, ${plural(lineCount, 'line')}${side === 'base' ? ' before' : ''}`
}

export function snippetPlace(snippet: { unit: string; side: 'after' | 'before'; first_line: number | null; last_line: number | null }): string {
  if (snippet.first_line === null) {
    return `${snippet.unit}, ${snippet.side}`
  }
  const span = snippet.first_line === snippet.last_line ? `line ${String(snippet.first_line)}` : `lines ${String(snippet.first_line)}-${String(snippet.last_line)}`
  return `${snippet.unit}, ${span} ${snippet.side}`
}
