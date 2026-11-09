import { describe, expect, it } from 'vitest'

import { MAX_CHAT_SNIPPETS, snippetLabel, snippetPlace, withSnippet, type ChatSnippetDraft } from './askAi'

function lines(offset: number): ChatSnippetDraft {
  return { range: { unit_id: 1, side: 'head', line_offset: offset, line_count: 2 }, label: `lines from ${String(offset)}` }
}

describe('ask AI', () => {
  it('adds a range once and keeps the latest ones', () => {
    expect(withSnippet([lines(0)], { ...lines(0), label: 'again' })).toEqual([lines(0)])
    const many = Array.from({ length: MAX_CHAT_SNIPPETS }, (_, index) => lines(index))
    expect(withSnippet(many, lines(99))).toEqual([...many.slice(1), lines(99)])
  })

  it('names the lines of a snippet', () => {
    expect(snippetLabel({ path: 'app.py', qualified_name: 'Cart.total' }, 2, 'head')).toBe('app.py::Cart.total, 2 lines')
    expect(snippetLabel({ path: 'README.md', qualified_name: '' }, 1, 'base')).toBe('README.md, 1 line before')
    expect(snippetPlace({ unit: 'app.py::total', side: 'after', first_line: 2, last_line: 2 })).toBe('app.py::total, line 2 after')
    expect(snippetPlace({ unit: 'app.py::total', side: 'before', first_line: 1, last_line: 3 })).toBe('app.py::total, lines 1-3 before')
    expect(snippetPlace({ unit: 'app.py', side: 'after', first_line: null, last_line: null })).toBe('app.py, after')
  })
})
