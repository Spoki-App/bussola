import { describe, expect, it } from 'vitest'

import type { Impact, Unit, UnitDescription } from '../api/types'
import { byImpact, matchesImpact, ratingSummary } from './impact'
import type { FileGroup } from './logic'

function unit(id: number, path: string, name: string): Unit {
  return { id, path, qualified_name: name, kind: 'function' } as Unit
}

function rating(unitId: number, impact: Impact): UnitDescription {
  return { unit_id: unitId, description: null, impact, impact_reason: 'Why.', provider: 'fake', provider_label: 'Fake', model: null, created_at: '', outdated: false }
}

function group(path: string, units: Unit[]): FileGroup {
  return { path, oldPath: null, units, todo: 0, complete: true }
}

describe('matchesImpact', () => {
  it('keeps every unit for any impact and only unrated units for not rated', () => {
    expect(matchesImpact(undefined, 'all')).toBe(true)
    expect(matchesImpact(rating(1, 'low'), 'all')).toBe(true)
    expect(matchesImpact(undefined, 'unrated')).toBe(true)
    expect(matchesImpact(rating(1, 'low'), 'unrated')).toBe(false)
  })

  it('keeps units with the chosen impact', () => {
    expect(matchesImpact(rating(1, 'high'), 'high')).toBe(true)
    expect(matchesImpact(rating(1, 'medium'), 'high')).toBe(false)
    expect(matchesImpact(undefined, 'high')).toBe(false)
  })
})

describe('byImpact', () => {
  it('puts the files and units with the highest impact first, unrated last, and keeps ties in order', () => {
    const groups = [group('a.py', [unit(1, 'a.py', 'one'), unit(2, 'a.py', 'two')]), group('b.py', [unit(3, 'b.py', 'three'), unit(4, 'b.py', 'four'), unit(5, 'b.py', 'five')])]
    const ratings = new Map([
      [1, rating(1, 'low')],
      [3, rating(3, 'medium')],
      [4, rating(4, 'high')],
      [5, rating(5, 'medium')],
    ])

    const sorted = byImpact(groups, ratings)

    expect(sorted.map((file) => [file.path, file.units.map((item) => item.id)])).toEqual([
      ['b.py', [4, 3, 5]],
      ['a.py', [1, 2]],
    ])
  })
})

describe('ratingSummary', () => {
  it('says how many units were rated, failed or skipped', () => {
    expect(ratingSummary({ rated: 3, failed: 0, cancelled: false, error: null })).toBe('3 units rated.')
    expect(ratingSummary({ rated: 1, failed: 2, cancelled: false, error: 'Timed out' })).toBe('1 unit rated. 2 units could not be rated: Timed out')
    expect(ratingSummary({ rated: 0, failed: 0, cancelled: false, error: null })).toBe('Every unit already has a current impact rating.')
    expect(ratingSummary({ rated: 2, failed: 0, cancelled: true, error: null })).toBe('Cancelled, 2 units rated.')
  })
})
