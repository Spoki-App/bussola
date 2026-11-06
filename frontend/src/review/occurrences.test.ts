import { parseDiff, type TextNode, type TokenNode } from 'react-diff-view'
import { describe, expect, it } from 'vitest'

import { diffTokens } from './highlight'
import { markOccurrences, occurrenceSpans, OCCURRENCE_CLASS } from './occurrences'

function unitTokens(lines: string[]) {
  const unified = ['--- a/app.py', '+++ b/app.py', `@@ -1,${String(lines.filter((line) => !line.startsWith('+')).length)} +1,${String(lines.filter((line) => !line.startsWith('-')).length)} @@`, ...lines, ''].join('\n')
  const tokens = diffTokens(parseDiff(unified)[0].hunks, 'python')
  if (!tokens) {
    throw new Error('no tokens')
  }
  return tokens
}

function marked(line: TokenNode[]): string[] {
  const found: string[] = []
  const visit = (node: TokenNode, inside: boolean) => {
    if (node.type === 'text') {
      if (inside) {
        found.push((node as TextNode).value)
      }
      return
    }
    for (const child of node.children ?? []) {
      visit(child, inside || node.className === OCCURRENCE_CLASS)
    }
  }
  line.forEach((node) => {
    visit(node, false)
  })
  return found
}

const UNIT = [
  ' def total(items, total_tax):',
  '-    total = sum(items)',
  '+    total = sum(item.price for item in items)',
  '     # total of items',
  '     label = "total"',
  '     return total + total_tax',
]

describe('markOccurrences', () => {
  it('marks every occurrence of the name on both sides of the unit', () => {
    const tokens = markOccurrences(unitTokens(UNIT), 'total')

    expect(tokens.old.map(marked)).toEqual([['total'], ['total'], [], [], ['total']])
    expect(tokens.new.map(marked)).toEqual([['total'], ['total'], [], [], ['total']])
  })

  it('matches whole identifiers only, not longer names or parts of them', () => {
    const tokens = markOccurrences(unitTokens(UNIT), 'item')

    expect(tokens.new.map(marked)).toEqual([[], ['item', 'item'], [], [], []])
  })

  it('skips keywords, strings and comments', () => {
    const tokens = unitTokens(UNIT)

    expect(occurrenceSpans(tokens.new[2], 'total')).toEqual([])
    expect(occurrenceSpans(tokens.new[3], 'total')).toEqual([])
    expect(occurrenceSpans(tokens.new[1], 'for')).toEqual([])
  })

  it('finds a name split by a changed word mark', () => {
    const tokens = unitTokens([' def run():', '-    refresh_balance()', '+    refresh_credit_balance()'])

    const pieces = marked(markOccurrences(tokens, 'refresh_credit_balance').new[1])

    expect(pieces.length).toBeGreaterThan(1)
    expect(pieces.join('')).toBe('refresh_credit_balance')
    expect(marked(markOccurrences(tokens, 'refresh_balance').old[1]).join('')).toBe('refresh_balance')
  })

  it('keeps lines without the name unchanged', () => {
    const tokens = unitTokens(UNIT)
    const result = markOccurrences(tokens, 'label')

    expect(result.new[0]).toBe(tokens.new[0])
    expect(marked(result.new[3])).toEqual(['label'])
  })
})
