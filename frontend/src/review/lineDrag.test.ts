import { describe, expect, it } from 'vitest'

import type { DiffRow } from '../api/types'
import { EDGE_SCROLL_MAX_STEP, EDGE_SCROLL_ZONE, dragSelection, edgeScrollStep } from './lineDrag'
import { NO_SELECTION, rowKey, type LineSelection } from './selection'

function row(change: DiffRow['change'], oldIndex: number | null, newIndex: number | null, extra: Partial<DiffRow> = {}): DiffRow {
  return {
    change,
    old_index: oldIndex,
    new_index: newIndex,
    old_line: oldIndex === null ? null : oldIndex + 1,
    new_line: newIndex === null ? null : newIndex + 1,
    text: 'x',
    row_hash: change === 'context' ? null : `h${String(oldIndex)}${String(newIndex)}`,
    approved: false,
    selection_id: null,
    placeholder: false,
    ...extra,
  }
}

const rows = [
  row('context', 0, 0),
  row('removed', 1, null),
  row('added', null, 1),
  row('added', null, 2, { approved: true, selection_id: 's1' }),
  row('added', null, 3),
  row('context', 2, 4),
  row('added', null, 5),
]
const keys = rows.map(rowKey)

function press(position: number, current: LineSelection = NO_SELECTION): LineSelection {
  return { ...current, anchor: keys[position] }
}

function drag(path: number[], current: LineSelection = NO_SELECTION): LineSelection {
  const [first, ...moves] = path
  return moves.reduce((selection, position) => dragSelection(rows, selection, keys[position]), press(first, current))
}

describe('dragSelection', () => {
  it('leaves the lines to approve as they were until the pointer moves', () => {
    const selected = new Set([keys[1]])

    expect(drag([4], { selected, anchor: keys[1] })).toEqual({ selected, anchor: keys[4] })
  })

  it('selects every changed line between the pressed line and the line under the pointer', () => {
    expect([...drag([1, 2, 3, 4]).selected]).toEqual([keys[1], keys[2], keys[4]])
  })

  it('selects upwards when dragging above the pressed line', () => {
    expect([...drag([6, 5, 4, 3, 2]).selected]).toEqual([keys[2], keys[4], keys[6]])
  })

  it('shrinks the range when the pointer moves back towards the pressed line', () => {
    expect([...drag([1, 2, 4, 6, 4]).selected]).toEqual([keys[1], keys[2], keys[4]])
    expect([...drag([1, 4, 1]).selected]).toEqual([keys[1]])
  })

  it('crosses over the pressed line keeping it as the anchor', () => {
    expect(drag([4, 6, 2])).toEqual({ anchor: keys[4], selected: new Set([keys[2], keys[4]]) })
  })

  it('selects nothing while only context and approved lines are covered, keeping the anchor', () => {
    expect(drag([0, 0])).toEqual({ anchor: keys[0], selected: new Set() })
    expect(drag([3, 3])).toEqual({ anchor: keys[3], selected: new Set() })
  })

  it('extends from the existing anchor when the press itself extends the selection', () => {
    const current = { selected: new Set([keys[1]]), anchor: keys[1] }

    expect(dragSelection(rows, dragSelection(rows, current, keys[4]), keys[6])).toEqual({ anchor: keys[1], selected: new Set([keys[1], keys[2], keys[4], keys[6]]) })
  })

  it('starts a new range from the pressed line when there is no anchor to extend', () => {
    expect(dragSelection(rows, NO_SELECTION, keys[4])).toEqual({ anchor: keys[4], selected: new Set([keys[4]]) })
  })
})

describe('edgeScrollStep', () => {
  const height = 1000

  it('does not scroll away from the edges', () => {
    expect(edgeScrollStep(EDGE_SCROLL_ZONE, height)).toBe(0)
    expect(edgeScrollStep(height / 2, height)).toBe(0)
    expect(edgeScrollStep(height - EDGE_SCROLL_ZONE, height)).toBe(0)
  })

  it('scrolls up near the top and down near the bottom, faster closer to the edge', () => {
    const slowUp = edgeScrollStep(EDGE_SCROLL_ZONE - 4, height)
    const slowDown = edgeScrollStep(height - EDGE_SCROLL_ZONE + 4, height)

    expect(slowUp).toBeLessThan(0)
    expect(slowDown).toBeGreaterThan(0)
    expect(edgeScrollStep(0, height)).toBe(-EDGE_SCROLL_MAX_STEP)
    expect(edgeScrollStep(height, height)).toBe(EDGE_SCROLL_MAX_STEP)
    expect(Math.abs(slowUp)).toBeLessThan(EDGE_SCROLL_MAX_STEP)
    expect(slowDown).toBeLessThan(EDGE_SCROLL_MAX_STEP)
  })

  it('keeps the top speed when the pointer leaves the window', () => {
    expect(edgeScrollStep(-200, height)).toBe(-EDGE_SCROLL_MAX_STEP)
    expect(edgeScrollStep(height + 200, height)).toBe(EDGE_SCROLL_MAX_STEP)
  })
})
