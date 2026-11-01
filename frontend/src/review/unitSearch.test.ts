import { describe, expect, it } from 'vitest'

import type { Unit } from '../api/types'
import type { FileGroup } from './logic'
import { fullName, matchesUnitQuery, searchGroups } from './unitSearch'

function unit(path: string, module: string | null, qualifiedName: string, oldPath: string | null = null, id = 1): Unit {
  return {
    id,
    revision_id: 1,
    path,
    old_path: oldPath,
    module,
    kind: qualifiedName ? 'function' : 'module',
    qualified_name: qualifiedName,
    state: 'new',
    change_type: 'modified',
    base_changed: false,
    approval_id: null,
    row_approvable: false,
    rows_total: 0,
    rows_approved: 0,
    binary: false,
    image: false,
    todo: true,
    action: 'approve',
    open_threads: 0,
    head_start: null,
    head_end: null,
  }
}

const findLine = unit('src/bussola/review/anchoring.py', 'bussola.review.anchoring', 'find_line')

describe('fullName', () => {
  it('puts the module before the name', () => {
    expect(fullName('bussola.review.anchoring', 'find_line')).toBe('bussola.review.anchoring.find_line')
    expect(fullName(null, 'find_line')).toBe('find_line')
  })
})

describe('matchesUnitQuery', () => {
  it('matches everything when the query is blank', () => {
    expect(matchesUnitQuery(findLine, '  ')).toBe(true)
  })

  it('matches part of the module, ignoring case', () => {
    expect(matchesUnitQuery(findLine, 'Review.Anchoring')).toBe(true)
    expect(matchesUnitQuery(findLine, 'bussola.forge')).toBe(false)
  })

  it('matches across the module and the name', () => {
    expect(matchesUnitQuery(findLine, 'anchoring.find_')).toBe(true)
  })

  it('matches every word of the query, in any order', () => {
    expect(matchesUnitQuery(findLine, 'find_line anchoring')).toBe(true)
    expect(matchesUnitQuery(findLine, 'find_line forge')).toBe(false)
  })

  it('matches the name and the file path', () => {
    expect(matchesUnitQuery(findLine, 'find_line')).toBe(true)
    expect(matchesUnitQuery(findLine, 'src/bussola/review')).toBe(true)
  })

  it('matches the module of module code and the old path of a moved file', () => {
    expect(matchesUnitQuery(unit('src/bussola/cli.py', 'bussola.cli', ''), 'bussola.cli')).toBe(true)
    expect(matchesUnitQuery(unit('web/new.ts', 'web/new', 'run', 'web/old.ts'), 'old')).toBe(true)
  })
})

describe('searchGroups', () => {
  const cart = 'src/shop/cart.py'
  const units = [
    unit(cart, 'shop.cart', 'Cart', null, 1),
    unit(cart, 'shop.cart', 'Cart.total', null, 2),
    unit(cart, 'shop.cart', 'Cart.Line.price', null, 3),
    unit(cart, 'shop.cart', 'helper', null, 4),
  ]
  const group: FileGroup = { path: cart, oldPath: null, units, todo: 4, complete: false }

  function names(groups: FileGroup[]): string[] {
    return groups.flatMap((found) => found.units.map((item) => item.qualified_name))
  }

  it('keeps the classes around a matching method so it is not shown as a stand-in', () => {
    expect(names(searchGroups([group], 'total'))).toEqual(['Cart', 'Cart.total'])
    expect(names(searchGroups([group], 'price'))).toEqual(['Cart', 'Cart.Line.price'])
  })

  it('keeps the counts of the whole file and drops files without matches', () => {
    const other: FileGroup = { path: 'web/app.ts', oldPath: null, units: [unit('web/app.ts', 'web/app', 'run', null, 5)], todo: 1, complete: false }

    const found = searchGroups([group, other], 'helper')

    expect(found.map((file) => [file.path, file.todo, file.complete])).toEqual([[cart, 4, false]])
  })
})
