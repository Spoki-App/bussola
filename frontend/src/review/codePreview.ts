import type { Thread } from '../api/types'
import { sourceLines, type SourceLine } from './sourceLines'

export interface PreviewLine {
  tokens: SourceLine
  target: boolean
}

const COMPACT_CONTEXT_LINES = 1
const COMPACT_TARGET_LINES = 3

export function previewLines(thread: Pick<Thread, 'path' | 'line_text' | 'context_before' | 'context_after'>): PreviewLine[] {
  if (thread.line_text === null) {
    return []
  }
  const target = thread.line_text.split('\n')
  const text = [...thread.context_before, ...target, ...thread.context_after].join('\n')
  const first = thread.context_before.length
  return sourceLines(text, thread.path ?? '').map((tokens, index) => ({ tokens, target: index >= first && index < first + target.length }))
}

export function compactPreview(lines: PreviewLine[]): PreviewLine[] {
  const first = lines.findIndex((line) => line.target)
  if (first < 0) {
    return lines
  }
  const targetCount = lines.filter((line) => line.target).length
  const start = Math.max(0, first - COMPACT_CONTEXT_LINES)
  const end = targetCount > COMPACT_TARGET_LINES ? first + COMPACT_TARGET_LINES : first + targetCount + COMPACT_CONTEXT_LINES
  return lines.slice(start, end)
}
