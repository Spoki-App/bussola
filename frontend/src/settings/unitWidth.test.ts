import { describe, expect, it } from 'vitest'

import { lineLengthOrigin, nextUnitWidth, unitColumns, type UnitWidth } from './unitWidth'

describe('unitColumns', () => {
  it('uses the repository line length for auto, the preset columns, and none for full width', () => {
    expect(unitColumns('auto', { columns: 88, source: 'pyproject.toml black' })).toBe(88)
    expect(unitColumns('auto', undefined)).toBe(120)
    expect(unitColumns('100ch', { columns: 88, source: null })).toBe(100)
    expect(unitColumns('160ch', undefined)).toBe(160)
    expect(unitColumns('full', { columns: 88, source: null })).toBeUndefined()
  })
})

describe('nextUnitWidth', () => {
  it('steps through the sizes and starts again from auto', () => {
    let width: UnitWidth = 'auto'
    const seen: UnitWidth[] = [width]
    for (let step = 0; step < 6; step++) {
      width = nextUnitWidth(width)
      seen.push(width)
    }
    expect(seen).toEqual(['auto', '80ch', '100ch', '120ch', '160ch', 'full', 'auto'])
  })
})

describe('lineLengthOrigin', () => {
  it('names where the line length comes from', () => {
    expect(lineLengthOrigin({ columns: 120, source: 'pyproject.toml ruff' })).toBe('120, from pyproject.toml ruff')
    expect(lineLengthOrigin({ columns: 120, source: null })).toBe('120, the default: the repository sets no line length')
    expect(lineLengthOrigin(undefined)).toBe('120, until the repository line length is read')
  })
})
