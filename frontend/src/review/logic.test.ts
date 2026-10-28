import { describe, expect, it } from 'vitest'

import type { Unit, UnitState } from '../api/types'
import { groupByFile, isTodo, nextTodoIndex, progressPercent, unitTitle } from './logic'

function unit(id: number, path: string, state: UnitState, qualifiedName = `f${String(id)}`): Unit {
  return {
    id,
    revision_id: 1,
    path,
    old_path: null,
    kind: qualifiedName ? 'function' : 'module',
    qualified_name: qualifiedName,
    state,
    change_type: 'modified',
    base_changed: false,
    approval_id: null,
    row_approvable: false,
    rows_total: 0,
    rows_approved: 0,
    base_start: 1,
    base_end: 2,
    head_start: 1,
    head_end: 2,
    binary: false,
    image: false,
    open_threads: 0,
  }
}

describe('unit states', () => {
  it('treats new, changed, partial and removed as to review', () => {
    const todo = (['new', 'changed', 'partial', 'removed', 'approved', 'approved_moved'] as UnitState[]).filter(isTodo)

    expect(todo).toEqual(['new', 'changed', 'partial', 'removed'])
  })
})

describe('groupByFile', () => {
  it('groups units by path and marks files without pending units as complete', () => {
    const groups = groupByFile([unit(1, 'a.py', 'approved'), unit(2, 'b.py', 'new'), unit(3, 'a.py', 'approved_moved')])

    expect(groups.map((group) => [group.path, group.units.length, group.todo, group.complete])).toEqual([
      ['a.py', 2, 0, true],
      ['b.py', 1, 1, false],
    ])
  })
})

describe('nextTodoIndex', () => {
  const units = [unit(1, 'a.py', 'new'), unit(2, 'a.py', 'approved'), unit(3, 'b.py', 'changed')]

  it('finds the next unit to review after the current one', () => {
    expect(nextTodoIndex(units, 0)).toBe(2)
  })

  it('wraps around to the start', () => {
    expect(nextTodoIndex(units, 2)).toBe(0)
  })

  it('returns -1 when everything is approved', () => {
    expect(nextTodoIndex([unit(1, 'a.py', 'approved')], 0)).toBe(-1)
  })
})

describe('progressPercent and titles', () => {
  it('computes rounded progress and treats an empty review as done', () => {
    expect(progressPercent({ approved: 1, total: 3 })).toBe(33)
    expect(progressPercent({ approved: 0, total: 0 })).toBe(100)
  })

  it('names module units', () => {
    expect(unitTitle(unit(1, 'a.py', 'new', ''))).toBe('Module code')
  })
})
