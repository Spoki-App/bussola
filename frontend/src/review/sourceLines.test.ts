import { describe, expect, it } from 'vitest'

import { sourceLines } from './sourceLines'

function lineText(line: { text: string }[]): string {
  return line.map((token) => token.text).join('')
}

describe('sourceLines', () => {
  it('splits highlighted code into lines, keeping tokens that span several lines', () => {
    const lines = sourceLines('def total(items):\n    """Sum\n    all."""\n    return 0\n', 'cart.py')

    expect(lines.map(lineText)).toEqual(['def total(items):', '    """Sum', '    all."""', '    return 0'])
    expect(lines[0].find((token) => token.text === 'def')?.className).toContain('hljs-keyword')
    expect(lines[2].find((token) => token.text.includes('all.'))?.className).toContain('hljs-string')
  })

  it('keeps unknown languages as plain text', () => {
    const lines = sourceLines('one\n\nthree', 'notes.unknownext')

    expect(lines).toEqual([[{ text: 'one', className: '' }], [], [{ text: 'three', className: '' }]])
  })
})
