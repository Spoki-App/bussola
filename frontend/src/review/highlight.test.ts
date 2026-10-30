import { parseDiff } from 'react-diff-view'
import { describe, expect, it } from 'vitest'

import { highlightTokens, languageFor } from './highlight'

const UNIFIED = ['--- a/app.py', '+++ b/app.py', '@@ -1,3 +1,3 @@', ' def total(items):', '-    """Old', '+    """New', '     docstring"""', ''].join('\n')

describe('languageFor', () => {
  it('picks the language from the file extension or name', () => {
    expect(['src/app.py', 'web/App.tsx', 'cmd/main.go', 'conf/settings.yml', 'Makefile', 'ui/Page.vue'].map(languageFor)).toEqual(['python', 'tsx', 'go', 'yml', 'makefile', 'xml'])
  })

  it('returns null for unknown files', () => {
    expect(languageFor('data/blob.xyz')).toBeNull()
    expect(languageFor('LICENSE')).toBeNull()
  })
})

describe('highlightTokens', () => {
  it('highlights both sides and keeps multi-line strings together', () => {
    const tokens = highlightTokens(parseDiff(UNIFIED)[0].hunks, 'python')

    const firstLine = JSON.stringify(tokens?.new[0])
    const docstringEnd = JSON.stringify(tokens?.new[2])
    expect(firstLine).toContain('hljs-keyword')
    expect(docstringEnd).toContain('hljs-string')
    expect(JSON.stringify(tokens?.old[1])).toContain('hljs-string')
  })

  it('marks JSON keys apart from string values', () => {
    const json = ['--- a/en.json', '+++ b/en.json', '@@ -1,1 +1,1 @@', '-{"title": "Old", "count": 1, "on": true}', '+{"title": "New", "count": 2, "on": false}', ''].join('\n')

    const line = JSON.stringify(highlightTokens(parseDiff(json)[0].hunks, languageFor('src/App/locale/en.json'))?.new[0])
    expect(line).toContain('hljs-attr')
    expect(line).toContain('hljs-string')
    expect(line).toContain('hljs-number')
    expect(line).toContain('hljs-literal')
  })

  it('splits interpolation braces and Python format specs from the expression', () => {
    const line = (language: string, code: string) => {
      const diff = ['--- a/x', '+++ b/x', '@@ -0,0 +1,1 @@', `+${code}`, ''].join('\n')
      return highlightTokens(parseDiff(diff)[0].hunks, language)?.new[0]
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

  it('leaves plain text when the language is unknown', () => {
    expect(highlightTokens(parseDiff(UNIFIED)[0].hunks, null)).toBeUndefined()
  })
})
