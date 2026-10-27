import { describe, expect, it } from 'vitest'

import type { DiffRow, Thread, UnitDiff } from '../api/types'
import { draftAnchor, isInline, threadRow } from './threadPlacement'
import type { CommentTarget } from '../components/UnitCard'

const rows: DiffRow[] = [
  { change: 'context', old_index: 0, new_index: 0, old_line: 1, new_line: 1, text: 'a', row_hash: null, approved: false, selection_id: null },
  { change: 'removed', old_index: 1, new_index: null, old_line: 2, new_line: null, text: 'b', row_hash: 'x', approved: false, selection_id: null },
  { change: 'added', old_index: null, new_index: 1, old_line: null, new_line: 2, text: 'c', row_hash: 'y', approved: false, selection_id: null },
]

function diff(mode: UnitDiff['mode']): UnitDiff {
  return { unit_id: 1, mode, available_modes: ['base'], approved_text_unavailable: false, binary: false, unified: '', rows }
}

function thread(side: Thread['side'], offset: number | null, outdated = false): Thread {
  return {
    id: 't',
    scope: 'unit',
    path: 'a.py',
    kind: 'function',
    qualified_name: 'f',
    side,
    status: 'open',
    created_by: { id: 1, email: 'a@b.c', name: 'A' },
    created_at: '',
    line_text: 'b',
    context_before: [],
    context_after: [],
    anchor: { revision_id: 1, line_offset: offset, outdated, unit_id: outdated ? null : 1, file_line: null },
    comments: [],
  }
}

describe('draftAnchor', () => {
  const target = (row: DiffRow, side: CommentTarget['side'], mode: CommentTarget['mode']) => ({ unit: {} as CommentTarget['unit'], row, side, mode })

  it('anchors removed lines on the base side only in base mode', () => {
    expect(draftAnchor(target(rows[1], 'old', 'base'))).toEqual({ side: 'base', line_offset: 1 })
    expect(draftAnchor(target(rows[1], 'old', 'approved'))).toBeNull()
  })

  it('anchors other lines on the head side', () => {
    expect(draftAnchor(target(rows[2], 'new', 'base'))).toEqual({ side: 'head', line_offset: 1 })
    expect(draftAnchor(target(rows[0], 'old', 'approved'))).toEqual({ side: 'head', line_offset: 0 })
  })
})

describe('threadRow and isInline', () => {
  it('places head threads on the head line and base threads only in base mode', () => {
    expect(threadRow(thread('head', 1), diff('base'))?.text).toBe('c')
    expect(threadRow(thread('base', 1), diff('base'))?.text).toBe('b')
    expect(threadRow(thread('base', 1), diff('approved'))).toBeUndefined()
  })

  it('keeps outdated threads out of the diff', () => {
    expect(isInline(thread('head', 1))).toBe(true)
    expect(isInline(thread('head', null, true))).toBe(false)
  })
})
