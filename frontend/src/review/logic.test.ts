import { describe, expect, it } from 'vitest'

import type { Unit, UnitState } from '../api/types'
import { focusedPosition, groupByFile, nextTodoIndex, progressPercent, unitTitle } from './logic'

function unit(id: number, path: string, state: UnitState, qualifiedName = `f${String(id)}`): Unit {
  return {
    id,
    revision_id: 1,
    path,
    old_path: null,
    module: null,
    kind: qualifiedName ? 'function' : 'module',
    qualified_name: qualifiedName,
    state,
    change_type: 'modified',
    base_changed: false,
    approval_id: null,
    row_approvable: false,
    rows_total: 0,
    rows_approved: 0,
    binary: false,
    image: false,
    todo: !state.startsWith('approved'),
    action: state.startsWith('approved') ? 'revoke' : 'approve',
    open_threads: 0,
  }
}

describe('groupByFile', () => {
  it('groups units by path and marks files without pending units as complete', () => {
    const groups = groupByFile([unit(1, 'a.py', 'approved'), unit(2, 'b.py', 'new'), unit(3, 'a.py', 'approved_moved')])

    expect(groups.map((group) => [group.path, group.units.length, group.todo, group.complete])).toEqual([
      ['a.py', 2, 0, true],
      ['b.py', 1, 1, false],
    ])
  })
})

describe('focusedPosition', () => {
  const units = [unit(1, 'a.py', 'new'), unit(2, 'a.py', 'new'), unit(3, 'b.py', 'new')]

  it('follows the focused unit when the list changes', () => {
    expect(focusedPosition(units, 3)).toBe(2)
    expect(focusedPosition(units.slice(1), 3)).toBe(1)
  })

  it('focuses nothing when the focused unit is filtered out', () => {
    expect(focusedPosition([units[0], units[1]], 3)).toBe(-1)
  })

  it('starts on the first unit', () => {
    expect(focusedPosition(units, null)).toBe(0)
    expect(focusedPosition([], null)).toBe(-1)
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
