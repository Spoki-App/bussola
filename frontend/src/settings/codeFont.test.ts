import { afterEach, describe, expect, it } from 'vitest'

import { DEFAULT_CODE_FONT, applyCodeFont, clampSize, fontStack, isInstalled, loadCodeFont, saveCodeFont } from './codeFont'

function fakeContext(installed: string) {
  const context = {
    font: '',
    measureText: (text: string) => ({ width: context.font.includes(`"${installed}"`) ? text.length * 2 : text.length }),
  }
  return context as unknown as CanvasRenderingContext2D
}

describe('code font settings', () => {
  afterEach(() => {
    window.localStorage.clear()
    document.documentElement.removeAttribute('style')
  })

  it('puts the chosen family before the default stack and strips characters that would break CSS', () => {
    expect(fontStack({ family: 'Fira "Code"; }', size: 12 })).toMatch(/^"Fira Code", ui-monospace/)
    expect(fontStack(DEFAULT_CODE_FONT)).toMatch(/^ui-monospace/)
  })

  it('keeps the size within limits', () => {
    expect([clampSize(4), clampSize(13.4), clampSize(80), clampSize(Number.NaN)]).toEqual([9, 13, 24, 12])
  })

  it('remembers the choice and ignores unreadable storage', () => {
    saveCodeFont({ family: 'JetBrains Mono', size: 14 })
    expect(loadCodeFont()).toEqual({ family: 'JetBrains Mono', size: 14 })

    window.localStorage.setItem('rtool.codeFont', '{not json')
    expect(loadCodeFont()).toEqual(DEFAULT_CODE_FONT)
  })

  it('applies the font to the page', () => {
    applyCodeFont({ family: 'Menlo', size: 15 })

    expect(document.documentElement.style.getPropertyValue('--mono')).toMatch(/^"Menlo"/)
    expect(document.documentElement.style.getPropertyValue('--code-size')).toBe('15px')
  })

  it('detects installed fonts by how they change text width', () => {
    const context = fakeContext('Hack')

    expect(isInstalled('Hack', context)).toBe(true)
    expect(isInstalled('Missing Mono', context)).toBe(false)
  })
})
