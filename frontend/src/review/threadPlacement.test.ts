import { describe, expect, it } from 'vitest'

import type { DiffRow, Thread, Unit, UnitDiff } from '../api/types'
import type { CommentTarget } from '../components/UnitCard'
import { rowKey } from './selection'
import { draftAnchor, draftEndRow, draftRequest, draftRowKeys, finishSelection, isInline, nextDraft, threadRow } from './threadPlacement'

function row(change: DiffRow['change'], oldIndex: number | null, newIndex: number | null, text: string): DiffRow {
  return {
    change,
    old_index: oldIndex,
    new_index: newIndex,
    old_line: oldIndex === null ? null : oldIndex + 1,
    new_line: newIndex === null ? null : newIndex + 1,
    text,
    row_hash: change === 'context' ? null : text,
    approved: false,
    selection_id: null,
    placeholder: false,
  }
}

const rows: DiffRow[] = [row('context', 0, 0, 'a'), row('removed', 1, null, 'b'), row('added', null, 1, 'c'), row('added', null, 2, 'd'), row('context', 2, 3, 'e')]
const unit = { id: 1 } as Unit

function target(index: number, extend = false, mode: CommentTarget['mode'] = 'base'): CommentTarget {
  const picked = rows[index]
  return { unit, row: picked, side: picked.change === 'removed' ? 'old' : 'new', mode, extend, selecting: false }
}

function diff(mode: UnitDiff['mode']): UnitDiff {
  return { unit_id: 1, mode, available_modes: ['base'], approved_text_unavailable: false, binary: false, unified: '', rows }
}

function thread(side: Thread['side'], offset: number | null, lineCount = 1, outdated = false): Thread {
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
    line_count: lineCount,
    context_before: [],
    context_after: [],
    anchor: { revision_id: 1, line_offset: offset, outdated, unit_id: outdated ? null : 1, file_line: null, end_file_line: null },
    comments: [],
    can_delete: false,
  }
}

describe('draftAnchor', () => {
  it('anchors removed lines on the base side only in base mode', () => {
    expect(draftAnchor(target(1))).toEqual({ side: 'base', line_offset: 1 })
    expect(draftAnchor(target(1, false, 'approved'))).toBeNull()
  })

  it('anchors other lines on the head side', () => {
    expect(draftAnchor(target(2))).toEqual({ side: 'head', line_offset: 1 })
    expect(draftAnchor(target(0, false, 'approved'))).toEqual({ side: 'head', line_offset: 0 })
  })
})

describe('nextDraft', () => {
  it('starts a one-line draft on click', () => {
    expect(draftRequest(nextDraft(null, target(2), false) ?? fail())).toEqual({ side: 'head', line_offset: 1, line_count: 1 })
  })

  it('extends from the first clicked line in either direction on shift-click', () => {
    const first = nextDraft(null, target(3), false)
    const extended = nextDraft(first, target(0, true), true) ?? fail()

    expect(draftRequest(extended)).toEqual({ side: 'head', line_offset: 0, line_count: 3 })
    expect(draftRowKeys(extended, rows)).toEqual(new Set([rowKey(rows[0]), rowKey(rows[2]), rowKey(rows[3])]))
    expect(draftEndRow(extended, rows)?.text).toBe('d')
  })

  it('ignores shift-clicks on lines of the other side', () => {
    const first = nextDraft(null, target(2), false)

    expect(nextDraft(first, target(1, true), true)).toEqual(first)
  })

  it('keeps the draft in selecting mode while dragging until the selection ends', () => {
    const pressed = nextDraft(null, { ...target(2), selecting: true }, false)
    const dragged = nextDraft(pressed, { ...target(4, true), selecting: true }, true) ?? fail()

    expect(dragged.selecting).toBe(true)
    expect(draftRequest(dragged)).toEqual({ side: 'head', line_offset: 1, line_count: 3 })
    expect(finishSelection(dragged)?.selecting).toBe(false)
  })

  it('starts over when shift-clicking in another unit', () => {
    const first = nextDraft(null, target(2), false)
    const other = { ...target(3, true), unit: { id: 2 } as Unit }

    expect(nextDraft(first, other, true)?.unitId).toBe(2)
  })
})

describe('threadRow and isInline', () => {
  it('places threads under their last line', () => {
    expect(threadRow(thread('head', 1), diff('base'))?.text).toBe('c')
    expect(threadRow(thread('head', 1, 2), diff('base'))?.text).toBe('d')
    expect(threadRow(thread('base', 1), diff('base'))?.text).toBe('b')
    expect(threadRow(thread('base', 1), diff('approved'))).toBeUndefined()
  })

  it('keeps outdated threads out of the diff', () => {
    expect(isInline(thread('head', 1))).toBe(true)
    expect(isInline(thread('head', null, 1, true))).toBe(false)
  })
})

function fail(): never {
  throw new Error('expected a draft')
}
