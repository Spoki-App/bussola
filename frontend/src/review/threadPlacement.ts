import type { DiffMode, DiffRow, Side, Thread, UnitDiff } from '../api/types'
import type { CommentTarget } from '../components/UnitCard'
import { rowKey } from './selection'

export interface DraftAnchor {
  side: Side
  line_offset: number
}

export interface Draft {
  unitId: number
  mode: DiffMode
  side: Side
  anchor: number
  start: number
  end: number
  selecting: boolean
}

export function draftAnchor(target: CommentTarget): DraftAnchor | null {
  const { row, side, mode } = target
  if (side === 'old' && mode === 'base' && row.old_index !== null) {
    return { side: 'base', line_offset: row.old_index }
  }
  if (row.new_index !== null) {
    return { side: 'head', line_offset: row.new_index }
  }
  return null
}

export function nextDraft(current: Draft | null, target: CommentTarget, extend: boolean): Draft | null {
  if (extend && current?.unitId === target.unit.id && current.mode === target.mode) {
    const offset = sideIndex(target.row, current.side, current.mode)
    const selecting = target.selecting
    return offset === null ? { ...current, selecting } : { ...current, selecting, start: Math.min(current.anchor, offset), end: Math.max(current.anchor, offset) }
  }
  const anchor = draftAnchor(target)
  if (!anchor) {
    return null
  }
  const offset = anchor.line_offset
  return { unitId: target.unit.id, mode: target.mode, side: anchor.side, anchor: offset, start: offset, end: offset, selecting: target.selecting }
}

export function draftRequest(draft: Draft): { side: Side; line_offset: number; line_count: number } {
  return { side: draft.side, line_offset: draft.start, line_count: draft.end - draft.start + 1 }
}

export function draftRowKeys(draft: Draft, rows: DiffRow[]): Set<string> {
  return new Set(
    rows.filter((row) => {
      const offset = sideIndex(row, draft.side, draft.mode)
      return offset !== null && offset >= draft.start && offset <= draft.end
    }).map(rowKey),
  )
}

export function draftEndRow(draft: Draft, rows: DiffRow[]): DiffRow | undefined {
  return rows.find((row) => sideIndex(row, draft.side, draft.mode) === draft.end)
}

export function threadRow(thread: Thread, diff: UnitDiff): DiffRow | undefined {
  const offset = thread.anchor?.line_offset
  if (offset === null || offset === undefined) {
    return undefined
  }
  const last = offset + Math.max(thread.line_count, 1) - 1
  if (thread.side === 'base') {
    return diff.mode === 'base' ? diff.rows.findLast((row) => row.old_index !== null && row.old_index <= last && row.change !== 'added') : undefined
  }
  return diff.rows.findLast((row) => row.new_index !== null && row.new_index <= last)
}

export function isInline(thread: Thread): boolean {
  return thread.scope === 'unit' && thread.anchor !== null && !thread.anchor.outdated && thread.anchor.unit_id !== null
}

function sideIndex(row: DiffRow, side: Side, mode: DiffMode): number | null {
  if (side === 'base') {
    return mode === 'base' && row.change !== 'added' ? row.old_index : null
  }
  return row.new_index
}

export function finishSelection(draft: Draft | null): Draft | null {
  return draft?.selecting ? { ...draft, selecting: false } : draft
}
