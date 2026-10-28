import { describe, expect, it } from 'vitest'

import type { DiffRow } from '../api/types'
import { collapsedUnified, hunkText, segmentRows } from './collapse'

function context(index: number): DiffRow {
  return {
    change: 'context',
    old_index: index,
    new_index: index,
    old_line: index + 1,
    new_line: index + 1,
    text: `line ${String(index)}`,
    row_hash: null,
    approved: false,
    selection_id: null,
    placeholder: false,
  }
}

function withChangeAt(length: number, changed: number): DiffRow[] {
  return Array.from({ length }, (_, index) => (index === changed ? { ...context(index), change: 'added', old_index: null, old_line: null } : context(index)))
}

const none = new Set<string>()
const noPins = new Set<number>()

describe('segmentRows', () => {
  it('keeps five lines around a change and hides the rest', () => {
    expect(segmentRows(withChangeAt(30, 15), none, noPins)).toEqual([
      { kind: 'gap', start: 0, end: 9, id: '0-9' },
      { kind: 'rows', start: 10, end: 20 },
      { kind: 'gap', start: 21, end: 29, id: '21-29' },
    ])
  })

  it('does not hide stretches shorter than four lines', () => {
    expect(segmentRows(withChangeAt(9, 7), none, noPins)).toEqual([{ kind: 'rows', start: 0, end: 8 }])
  })

  it('shows an expanded gap', () => {
    expect(segmentRows(withChangeAt(30, 15), new Set(['0-9']), noPins)[0]).toEqual({ kind: 'rows', start: 0, end: 20 })
  })

  it('keeps pinned rows visible', () => {
    const segments = segmentRows(withChangeAt(30, 15), none, new Set([2]))

    expect(segments.slice(0, 3)).toEqual([
      { kind: 'rows', start: 0, end: 2 },
      { kind: 'gap', start: 3, end: 9, id: '3-9' },
      { kind: 'rows', start: 10, end: 20 },
    ])
  })

  it('shows everything when nothing changed', () => {
    expect(segmentRows([context(0), context(1)], none, noPins)).toEqual([{ kind: 'rows', start: 0, end: 1 }])
  })
})

describe('hunkText', () => {
  it('numbers hunks from the hidden lines before them', () => {
    const rows = withChangeAt(30, 15)

    expect(hunkText(rows, 10, 12).split('\n')).toEqual(['@@ -11,3 +11,3 @@', ' line 10', ' line 11', ' line 12'])
    expect(hunkText(rows, 15, 15).split('\n')).toEqual(['@@ -15,0 +16,1 @@', '+line 15'])
  })

  it('joins visible hunks under the file header', () => {
    const rows = withChangeAt(30, 15)

    expect(collapsedUnified('header', rows, segmentRows(rows, none, noPins)).split('\n')[1]).toBe('@@ -11,10 +11,11 @@')
  })
})
