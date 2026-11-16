import { describe, expect, it } from 'vitest'

import { nextUnitWidth, unitColumns, unitWidthTitle } from './unitWidth'

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
    expect((['auto', '80ch', '100ch', '120ch', '160ch', 'full'] as const).map(nextUnitWidth)).toEqual(['80ch', '100ch', '120ch', '160ch', 'full', 'auto'])
  })
})

describe('unitWidthTitle', () => {
  it('names where the auto line length comes from', () => {
    expect(unitWidthTitle('auto', { columns: 120, source: 'pyproject.toml ruff' })).toBe('Unit width: Auto, 120, from pyproject.toml ruff')
    expect(unitWidthTitle('auto', { columns: 120, source: null })).toBe('Unit width: Auto, 120, the default: the repository sets no line length')
    expect(unitWidthTitle('auto', undefined)).toBe('Unit width: Auto, 120, until the repository line length is read')
    expect(unitWidthTitle('100ch', undefined)).toBe('Unit width: 100 columns')
  })
})
