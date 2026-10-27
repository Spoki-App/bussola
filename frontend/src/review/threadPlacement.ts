import type { DiffRow, Side, Thread, UnitDiff } from '../api/types'
import type { CommentTarget } from '../components/UnitCard'

export interface DraftAnchor {
  side: Side
  line_offset: number
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

export function threadRow(thread: Thread, diff: UnitDiff): DiffRow | undefined {
  const offset = thread.anchor?.line_offset
  if (offset === null || offset === undefined) {
    return undefined
  }
  if (thread.side === 'base') {
    return diff.mode === 'base' ? diff.rows.find((row) => row.old_index === offset && row.change !== 'added') : undefined
  }
  return diff.rows.find((row) => row.new_index === offset)
}

export function isInline(thread: Thread): boolean {
  return thread.scope === 'unit' && thread.anchor !== null && !thread.anchor.outdated && thread.anchor.unit_id !== null
}
