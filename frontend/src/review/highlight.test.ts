import { parseDiff, type TextNode, type TokenNode } from 'react-diff-view'
import { describe, expect, it } from 'vitest'

import { diffTokens, languageFor } from './highlight'

const UNIFIED = ['--- a/app.py', '+++ b/app.py', '@@ -1,3 +1,3 @@', ' def total(items):', '-    """Old', '+    """New', '     docstring"""', ''].join('\n')

function textRuns(line: TokenNode[]): { value: string; marked: boolean }[] {
  const runs: { value: string; marked: boolean }[] = []
  const visit = (node: TokenNode, inside: boolean) => {
    if (node.type === 'text') {
      const { value } = node as TextNode
      const last = runs.at(-1)
      if (last?.marked === inside) {
        last.value += value
      } else {
        runs.push({ value, marked: inside })
      }
      return
    }
    for (const child of (node as { children?: TokenNode[] }).children ?? []) {
      visit(child, inside || node.type === 'edit')
    }
  }
  for (const node of line) {
    visit(node, false)
  }
  return runs
}

function markedRuns(line: TokenNode[]): string[] {
  return textRuns(line).flatMap((run) => (run.marked ? [run.value] : []))
}

function bracketed(line: TokenNode[]): string {
  return textRuns(line)
    .map((run) => (run.marked ? `[${run.value}]` : run.value))
    .join('')
}

describe('languageFor', () => {
  it('picks the language from the file extension or name', () => {
    expect(['src/app.py', 'web/App.tsx', 'cmd/main.go', 'conf/settings.yml', 'Makefile', 'ui/Page.vue'].map(languageFor)).toEqual(['python', 'tsx', 'go', 'yml', 'makefile', 'xml'])
  })

  it('returns null for unknown files', () => {
    expect(languageFor('data/blob.xyz')).toBeNull()
    expect(languageFor('LICENSE')).toBeNull()
  })
})

describe('diffTokens', () => {
  it('highlights both sides and keeps multi-line strings together', () => {
    const tokens = diffTokens(parseDiff(UNIFIED)[0].hunks, 'python')

    const firstLine = JSON.stringify(tokens?.new[0])
    const docstringEnd = JSON.stringify(tokens?.new[2])
    expect(firstLine).toContain('hljs-keyword')
    expect(docstringEnd).toContain('hljs-string')
    expect(JSON.stringify(tokens?.old[1])).toContain('hljs-string')
  })

  it('marks JSON keys apart from string values', () => {
    const json = ['--- a/en.json', '+++ b/en.json', '@@ -1,1 +1,1 @@', '-{"title": "Old", "count": 1, "on": true}', '+{"title": "New", "count": 2, "on": false}', ''].join('\n')

    const line = JSON.stringify(diffTokens(parseDiff(json)[0].hunks, languageFor('src/App/locale/en.json'))?.new[0])
    expect(line).toContain('hljs-attr')
    expect(line).toContain('hljs-string')
    expect(line).toContain('hljs-number')
    expect(line).toContain('hljs-literal')
  })

  it('splits interpolation braces and Python format specs from the expression', () => {
    const line = (language: string, code: string) => {
      const diff = ['--- a/x', '+++ b/x', '@@ -0,0 +1,1 @@', `+${code}`, ''].join('\n')
      return diffTokens(parseDiff(diff)[0].hunks, language)?.new[0]
    }
    const punctuationOf = (node: unknown): string[] => {
      const { type, properties, children } = node as { type: string; properties?: { className?: string[] }; children?: unknown[] }
      if (type === 'text') {
        return []
      }
      const own = properties?.className?.includes('hljs-punctuation') ? [(children?.[0] as { value: string }).value] : []
      return [...own, ...(children ?? []).flatMap(punctuationOf)]
    }

    expect(line('python', 'f"{name!r:>10} {a != b} {(lambda: 1)()} {{literal}}"')?.flatMap(punctuationOf)).toEqual(['{', '!r:>10', '}', '{', '}', '{', '}'])
    expect(line('ts', 'const s = `a ${b + f(":")} c`')?.flatMap(punctuationOf)).toEqual(['${', '}'])
    expect(JSON.stringify(line('python', 'x = "plain {text}"'))).not.toContain('hljs-punctuation')
  })

  it('marks the changed words of similar lines on both sides', () => {
    const diff = [
      '--- a/x.py',
      '+++ b/x.py',
      '@@ -1,2 +1,2 @@',
      '-if len(specs) == 1 and declaration.start_point.row == specs[0].start_point.row:',
      '+if len(specs) == 1 and start_row(declaration) == start_row(specs[0]):',
      '-    name_node = specs[0].child_by_field_name("name")',
      '+    return build(totally, different, things)',
      '',
    ].join('\n')
    const tokens = diffTokens(parseDiff(diff)[0].hunks, 'python')

    expect(tokens?.old.map(markedRuns)).toEqual([['.start_point.row', '.start_point.row'], ['name_node = specs[0].child_by_field_name("name")']])
    expect(tokens?.new.map(markedRuns)).toEqual([['start_row(', ')', 'start_row(', ')'], ['return build(totally, different, things)']])
  })

  it('pairs a removed line with the most similar added line of its block and marks only the changed parts of a renamed name', () => {
    const diff = [
      '--- a/x.py',
      '+++ b/x.py',
      '@@ -1,1 +1,3 @@',
      '-    _refresh_balance_on_commit(account, recharge_credit.id)',
      '+    # The wallet was decremented straight on the row.',
      '+    # current_credit must follow once this commits.',
      '+    refresh_credit_balance_on_commit(account.id, recharge_credit.id, delta=-total)',
      '',
    ].join('\n')
    const tokens = diffTokens(parseDiff(diff)[0].hunks, 'python')

    expect(tokens?.old.map(markedRuns)).toEqual([['_']])
    expect(tokens?.new.map(markedRuns)).toEqual([
      ['# The wallet was decremented straight on the row.'],
      ['# current_credit must follow once this commits.'],
      ['_credit', '.id', ', delta=-total'],
    ])
  })

  it('marks only the added indentation of a line that moved into a block, at the start of the line', () => {
    const diff = ['--- a/x.py', '+++ b/x.py', '@@ -1,1 +1,1 @@', '-    load(page)', '+        load(page)', ''].join('\n')
    const tokens = diffTokens(parseDiff(diff)[0].hunks, null)

    expect(tokens?.old.map(markedRuns)).toEqual([[]])
    expect(tokens?.new.map(bracketed)).toEqual(['[    ]    load(page)'])
  })

  it('marks the whole text of lines with no counterpart next to lines that only moved', () => {
    const diff = [
      '--- a/x.py',
      '+++ b/x.py',
      '@@ -1,3 +1,4 @@',
      '-for page in pages:',
      '+try:',
      '-    load(page)',
      '+        load(page)',
      '+    finally:',
      '-log()',
      '',
    ].join('\n')
    const tokens = diffTokens(parseDiff(diff)[0].hunks, 'python')

    expect(tokens?.old.map(markedRuns)).toEqual([['for page in pages:'], [], ['log()']])
    expect(tokens?.new.map(markedRuns)).toEqual([['try:'], ['    '], ['finally:']])
  })

  it('leaves added lines unmarked when no line in their block was modified', () => {
    const diff = ['--- a/x.py', '+++ b/x.py', '@@ -1,1 +1,2 @@', '-old_name()', '+brand_new(thing)', '+    another()', ''].join('\n')
    const tokens = diffTokens(parseDiff(diff)[0].hunks, 'python')

    expect(tokens?.old.map(markedRuns)).toEqual([[]])
    expect(tokens?.new.map(markedRuns)).toEqual([[], []])
  })

  it('marks changed words without syntax colours when the language is unknown', () => {
    const tokens = diffTokens(parseDiff(UNIFIED)[0].hunks, null)

    expect(JSON.stringify(tokens)).not.toContain('hljs-')
    expect(markedRuns(tokens?.new[1] ?? [])).toEqual(['New'])
  })
})
