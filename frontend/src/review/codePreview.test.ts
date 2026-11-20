import { describe, expect, it } from 'vitest'

import { compactPreview, previewLines } from './codePreview'

const thread = {
  path: 'src/shop/cart.py',
  line_text: '    total = 0\n    for item in items:\n        total += item\n    return total',
  context_before: ['def total(items):', '    """Sum."""', '    items = list(items)'],
  context_after: ['', 'def other():', '    pass'],
}

function texts(lines: ReturnType<typeof previewLines>): string[] {
  return lines.map((line) => line.tokens.map((token) => token.text).join(''))
}

describe('previewLines', () => {
  it('marks the commented lines between their context and highlights the code', () => {
    const lines = previewLines(thread)

    expect(lines.map((line) => line.target)).toEqual([false, false, false, true, true, true, true, false, false, false])
    expect(texts(lines)[3]).toBe('    total = 0')
    expect(lines[0].tokens.some((token) => token.className.includes('hljs-keyword'))).toBe(true)
  })

  it('has nothing to show without commented lines', () => {
    expect(previewLines({ ...thread, line_text: null })).toEqual([])
  })
})

describe('compactPreview', () => {
  it('keeps a line of context around a few commented lines', () => {
    const short = previewLines({ ...thread, line_text: '    total = 0\n    return total' })

    expect(texts(compactPreview(short))).toEqual(['    items = list(items)', '    total = 0', '    return total', ''])
  })

  it('cuts a long range after its first commented lines', () => {
    expect(texts(compactPreview(previewLines(thread)))).toEqual(['    items = list(items)', '    total = 0', '    for item in items:', '        total += item'])
  })

  it('keeps short previews whole', () => {
    const short = previewLines({ ...thread, line_text: 'return 0', context_before: [], context_after: ['pass'] })

    expect(compactPreview(short)).toEqual(short)
  })
})
