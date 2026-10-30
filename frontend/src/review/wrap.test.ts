import { parseDiff, type TokenNode } from 'react-diff-view'
import { describe, expect, it } from 'vitest'

import { diffTokens } from './highlight'
import { hangingIndent, withHangingIndent } from './wrap'

function text(value: string): TokenNode {
  return { type: 'text', value }
}

function span(className: string, ...children: TokenNode[]): TokenNode {
  return { type: 'element', className, children }
}

describe('hanging indent', () => {
  it('moves the leading whitespace into an indent and the rest into a body', () => {
    expect(hangingIndent([text('    return '), span('hljs-number', text('0'))])).toEqual([
      { type: 'indent', className: 'line-indent', children: [text('    ')] },
      { type: 'body', className: 'line-body', children: [text('return '), span('hljs-number', text('0'))] },
    ])
  })

  it('splits nested tokens such as an edit mark that covers part of the indentation', () => {
    const edit = { type: 'edit', children: [text('  x')] }
    expect(hangingIndent([text('\t'), edit, text(' = 1')])).toEqual([
      { type: 'indent', className: 'line-indent', children: [text('\t'), { type: 'edit', children: [text('  ')] }] },
      { type: 'body', className: 'line-body', children: [{ type: 'edit', children: [text('x')] }, text(' = 1')] },
    ])
  })

  it('leaves lines without indentation and blank lines as they are', () => {
    const plain = [text('def total():')]
    const blank = [text('    ')]
    expect(hangingIndent(plain)).toBe(plain)
    expect(hangingIndent(blank)).toBe(blank)
    expect(hangingIndent([])).toEqual([])
  })

  it('is part of the highlighted diff tokens', () => {
    const unified = ['--- a/app.py', '+++ b/app.py', '@@ -1,2 +1,2 @@', ' def total(items):', '-    return 0', '+    return sum(items)', ''].join('\n')
    const tokens = diffTokens(parseDiff(unified)[0].hunks, 'python')
    expect(tokens?.new[1].map((token) => token.type)).toEqual(['indent', 'body'])
    expect(tokens?.old[1].map((token) => token.type)).toEqual(['indent', 'body'])
  })

  it('applies to both sides of the diff', () => {
    const tokens = withHangingIndent({ old: [[text('  a')]], new: [[text('b')], [text('  c')]] })
    expect(tokens.old[0].map((token) => token.type)).toEqual(['indent', 'body'])
    expect(tokens.new[0]).toEqual([text('b')])
    expect(tokens.new[1].map((token) => token.type)).toEqual(['indent', 'body'])
  })
})
