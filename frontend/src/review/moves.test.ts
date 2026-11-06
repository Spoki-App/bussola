import { describe, expect, it } from 'vitest'

import type { CodeRange, Move } from '../api/types'
import { moveLinksByUnit, moveTitle, rangeLines } from './moves'

function range(unitId: number, name: string, side: CodeRange['side'], first: number, last: number): CodeRange {
  return { unit_id: unitId, side, line_offset: 2, line_count: last - first + 1, path: `${name}.py`, qualified_name: name, kind: 'function', first_line: first, last_line: last }
}

const MOVE: Move = { removed: range(1, 'checkout', 'base', 4, 8), added: range(2, 'validate', 'head', 9, 13), similarity: 1, identical: true }

describe('move links', () => {
  it('links both places of a move to the same comparison', () => {
    const links = moveLinksByUnit([MOVE])
    const comparison = { left: { unit_id: 1, side: 'base', line_offset: 2, line_count: 5 }, right: { unit_id: 2, side: 'head', line_offset: 2, line_count: 5 } }

    expect(links.get(1)).toEqual([{ direction: 'to', other: MOVE.added, identical: true, comparison }])
    expect(links.get(2)).toEqual([{ direction: 'from', other: MOVE.removed, identical: true, comparison }])
  })

  it('describes where the code went', () => {
    const [link] = moveLinksByUnit([{ ...MOVE, identical: false }]).get(1) ?? []

    expect(moveTitle(link)).toBe('Moved to validate (validate.py lines 9-13), with changes. Click to compare.')
  })

  it('names a single line or no line', () => {
    expect(rangeLines({ first_line: 3, last_line: 3 })).toBe('line 3')
    expect(rangeLines({ first_line: null, last_line: null })).toBe('')
  })
})
