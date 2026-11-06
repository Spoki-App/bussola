import { describe, expect, it } from 'vitest'

import type { DiffRow } from '../api/types'
import { approvedSelections, clickRow, NO_SELECTION, rowKey, selectRange, selectionRanges, type LineSelection } from './selection'

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

  it('selects removed lines without the added lines paired with them', () => {
    const paired = [row('removed', 0, null), row('added', null, 0), row('removed', 1, null), row('added', null, 1)]

    expect([...selectRange(paired, rowKey(paired[0]), rowKey(paired[2]))]).toEqual([rowKey(paired[0]), rowKey(paired[2])])
  })
})

describe('clickRow', () => {
  const click = (current: LineSelection, index: number, extend = false) => clickRow(rows, current, rowKey(rows[index]), extend)

  it('replaces the selection with the clicked line and makes it the anchor', () => {
    const first = click(NO_SELECTION, 1)
    const second = click(first, 4)

    expect([...second.selected]).toEqual([rowKey(rows[4])])
    expect(second.anchor).toBe(rowKey(rows[4]))
  })

  it('keeps a line selected when it is clicked again', () => {
    const again = click(click(NO_SELECTION, 2), 2)

    expect([...again.selected]).toEqual([rowKey(rows[2])])
  })

  it('extends the selection from the anchor with shift, skipping approved and context lines', () => {
    const extended = click(click(NO_SELECTION, 1), 4, true)

    expect([...extended.selected]).toEqual([rowKey(rows[1]), rowKey(rows[2]), rowKey(rows[4])])
    expect(extended.anchor).toBe(rowKey(rows[1]))
  })

  it('resizes the range from the same anchor on consecutive shift clicks', () => {
    const grown = click(click(NO_SELECTION, 2), 4, true)
    const shrunk = click(grown, 2, true)
    const flipped = click(shrunk, 1, true)

    expect([...shrunk.selected]).toEqual([rowKey(rows[2])])
    expect([...flipped.selected]).toEqual([rowKey(rows[1]), rowKey(rows[2])])
    expect(flipped.anchor).toBe(rowKey(rows[2]))
  })

  it('starts a new selection on shift click when there is no anchor', () => {
    expect(click(NO_SELECTION, 4, true)).toEqual({ selected: new Set([rowKey(rows[4])]), anchor: rowKey(rows[4]) })
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
