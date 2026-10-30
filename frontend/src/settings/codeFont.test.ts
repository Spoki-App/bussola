import { afterEach, describe, expect, it } from 'vitest'

import { DEFAULT_CODE_FONT, applyCodeFont, clampSize, featureSettings, fontStack, isInstalled, loadCodeFont, saveCodeFont } from './codeFont'

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
    expect(fontStack({ ...DEFAULT_CODE_FONT, family: 'Fira "Code"; }' })).toMatch(/^"Fira Code", ui-monospace/)
    expect(fontStack(DEFAULT_CODE_FONT)).toMatch(/^ui-monospace/)
  })

  it('keeps the size within limits', () => {
    expect([clampSize(4), clampSize(13.4), clampSize(80), clampSize(Number.NaN)]).toEqual([9, 13, 24, 12])
  })

  it('remembers the choice and ignores unreadable storage', () => {
    saveCodeFont({ family: 'JetBrains Mono', size: 14, ligatures: false, features: 'ss01' })
    expect(loadCodeFont()).toEqual({ family: 'JetBrains Mono', size: 14, ligatures: false, features: 'ss01' })

    window.localStorage.setItem('bussola.codeFont', JSON.stringify({ family: 'Menlo', size: 13 }))
    expect(loadCodeFont()).toEqual({ ...DEFAULT_CODE_FONT, family: 'Menlo', size: 13 })

    window.localStorage.setItem('bussola.codeFont', '{not json')
    expect(loadCodeFont()).toEqual(DEFAULT_CODE_FONT)
  })

  it('applies the font to the page', () => {
    applyCodeFont({ family: 'Menlo', size: 15, ligatures: false, features: '' })

    expect(document.documentElement.style.getPropertyValue('--mono')).toMatch(/^"Menlo"/)
    expect(document.documentElement.style.getPropertyValue('--code-size')).toBe('15px')
    expect(document.documentElement.style.getPropertyValue('--code-ligatures')).toBe('none')
  })

  it('turns valid OpenType tags into feature settings and ligatures off explicitly', () => {
    expect(featureSettings({ ...DEFAULT_CODE_FONT, features: 'ss01, ss02 bad! zero ss01' })).toBe('"ss01" 1, "ss02" 1, "zero" 1')
    expect(featureSettings(DEFAULT_CODE_FONT)).toBe('normal')
    expect(featureSettings({ ...DEFAULT_CODE_FONT, ligatures: false })).toBe('"liga" 0, "calt" 0, "dlig" 0')
  })

  it('detects installed fonts by how they change text width', () => {
    const context = fakeContext('Hack')

    expect(isInstalled('Hack', context)).toBe(true)
    expect(isInstalled('Missing Mono', context)).toBe(false)
  })
})
