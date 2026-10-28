import { describe, expect, it } from 'vitest'

import type { DiffRow } from '../api/types'
import { approvedSelections, rowKey, selectRange, selectionRanges } from './selection'

function row(change: DiffRow['change'], oldIndex: number | null, newIndex: number | null, extra: Partial<DiffRow> = {}): DiffRow {
  return {
    change,
    old_index: oldIndex,
    new_index: newIndex,
    old_line: oldIndex === null ? null : oldIndex + 10,
    new_line: newIndex === null ? null : newIndex + 10,
    text: 'x',
    row_hash: change === 'context' ? null : `h${String(oldIndex)}${String(newIndex)}`,
    approved: false,
    selection_id: null,
    placeholder: false,
    ...extra,
  }
}

const rows = [row('context', 0, 0), row('removed', 1, null), row('added', null, 1), row('added', null, 2, { approved: true, selection_id: 's1' }), row('added', null, 3)]

describe('selectRange', () => {
  it('selects only changed, not yet approved rows between anchor and focus in either direction', () => {
    const forward = selectRange(rows, rowKey(rows[0]), rowKey(rows[4]))
    const backward = selectRange(rows, rowKey(rows[4]), rowKey(rows[0]))

    expect([...forward]).toEqual([rowKey(rows[1]), rowKey(rows[2]), rowKey(rows[4])])
    expect(backward).toEqual(forward)
  })
})

describe('selectionRanges', () => {
  it('turns selected rows into file line ranges per side', () => {
    const selected = new Set([rowKey(rows[1]), rowKey(rows[2]), rowKey(rows[4])])

    expect(selectionRanges(rows, selected)).toEqual({ head_range: [11, 13], base_range: [11, 11] })
  })

  it('leaves a side empty when nothing on it is selected', () => {
    expect(selectionRanges(rows, new Set([rowKey(rows[2])]))).toEqual({ head_range: [11, 11], base_range: null })
  })
})

describe('approvedSelections', () => {
  it('lists distinct selection ids of approved rows', () => {
    expect(approvedSelections([...rows, row('added', null, 4, { approved: true, selection_id: 's1' })])).toEqual(['s1'])
  })
})
