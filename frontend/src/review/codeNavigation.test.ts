import { afterEach, describe, expect, it } from 'vitest'

import type { Documentation, NavigationResult, NavigationTarget } from '../api/navigation'
import { clearCaret, placeCaret } from '../test/caret'
import { columnAt, directTarget, emptyMessage, groupTargets, isNavigable, isNavigationClick, isSymbolToken, missingDocumentation, rangeOf, symbolAt, symbolSpan, textOffset, titleOf } from './codeNavigation'

function target(role: NavigationTarget['role'], path: string, line: number, unitId: number | null = null): NavigationTarget {
  return { role, path, line, column: 0, preview: `line ${String(line)}`, side: 'head', unit_id: unitId }
}

function result(targets: NavigationTarget[], origin: NavigationResult['origin'] = 'reference'): NavigationResult {
  return { ready: true, symbol: 'price', origin, resolver: 'tree-sitter', targets, server_hint: null, documentation: null }
}

const RENDER: Documentation = { qualified_name: 'django.shortcuts.render', package: 'Django', version: '5.1', url: null, text: null, source: null }

function codeCell(): HTMLElement {
  const cell = document.createElement('td')
  cell.innerHTML = '<span class="hljs-keyword">return</span> <span>price</span>(item)'
  document.body.append(cell)
  return cell
}

describe('code navigation helpers', () => {
  afterEach(() => {
    clearCaret()
    document.body.innerHTML = ''
  })

  it('treats Cmd+click and Ctrl+click with the main button as navigation', () => {
    expect(isNavigationClick({ metaKey: true, ctrlKey: false, button: 0 })).toBe(true)
    expect(isNavigationClick({ metaKey: false, ctrlKey: true, button: 0 })).toBe(true)
    expect(isNavigationClick({ metaKey: false, ctrlKey: false, button: 0 })).toBe(false)
    expect(isNavigationClick({ metaKey: true, ctrlKey: false, button: 2 })).toBe(false)
  })

  it('measures the offset of a caret across highlighted spans', () => {
    const cell = codeCell()
    const priceText = cell.querySelectorAll('span')[1].firstChild as Text

    expect(textOffset(cell, priceText, 2)).toBe('return pr'.length)
    expect(textOffset(cell, cell, 2)).toBe('return '.length)
  })

  it('finds the column under the pointer and ignores carets outside the cell', () => {
    const cell = codeCell()
    const priceText = cell.querySelectorAll('span')[1].firstChild as Text
    const elsewhere = document.createTextNode('other')
    document.body.append(elsewhere)
    placeCaret(priceText, 1)

    expect(columnAt(cell, 10, 10)).toBe('return p'.length)
    placeCaret(elsewhere, 1)
    expect(columnAt(cell, 10, 10)).toBeNull()
  })

  it('finds the symbol around an offset, including at its end, and nothing on punctuation or numbers', () => {
    const line = 'total = price_2(item.$cost) + 42'

    expect(symbolSpan(line, 0)).toEqual({ start: 0, end: 5 })
    expect(symbolSpan(line, 5)).toEqual({ start: 0, end: 5 })
    expect(symbolSpan(line, line.indexOf('_2') + 1)).toEqual({ start: 8, end: 15 })
    expect(symbolSpan(line, line.indexOf('$cost') + 2)).toEqual({ start: 21, end: 26 })
    expect(symbolSpan(line, line.indexOf('=') + 1)).toBeNull()
    expect(symbolSpan(line, line.indexOf('42') + 1)).toBeNull()
    expect(symbolSpan('', 0)).toBeNull()
  })

  it('classifies keywords, strings, comments and punctuation as not symbols, but code inside interpolations as symbols', () => {
    expect(isSymbolToken([])).toBe(true)
    expect(isSymbolToken(['hljs-title', 'function_'])).toBe(true)
    expect(isSymbolToken(['hljs-keyword'])).toBe(false)
    expect(isSymbolToken(['hljs-string'])).toBe(false)
    expect(isSymbolToken(['hljs-doctag', 'hljs-comment'])).toBe(false)
    expect(isSymbolToken(['hljs-punctuation'])).toBe(false)
    expect(isSymbolToken(['hljs-subst', 'hljs-string'])).toBe(true)
    expect(isSymbolToken(['hljs-keyword', 'hljs-subst', 'hljs-string'])).toBe(false)
  })

  it('finds the symbol under the pointer only in code tokens', () => {
    const cell = document.createElement('td')
    cell.innerHTML = '<span class="hljs-keyword">return</span> pri<mark>ce</mark>(<span class="hljs-string">"item"</span>, <span class="hljs-string hljs-subst">count</span>)'
    document.body.append(cell)
    const [keyword, mark, string, interpolation] = cell.querySelectorAll('span, mark')

    placeCaret(mark.firstChild as Text, 1)
    const span = symbolAt(cell, 0, 0)
    expect(span).toEqual({ start: 7, end: 12 })
    expect(span && rangeOf(cell, span)?.toString()).toBe('price')

    placeCaret(keyword.firstChild as Text, 2)
    expect(symbolAt(cell, 0, 0)).toBeNull()
    placeCaret(string.firstChild as Text, 2)
    expect(symbolAt(cell, 0, 0)).toBeNull()
    placeCaret(interpolation.firstChild as Text, 2)
    expect(symbolAt(cell, 0, 0)).toEqual({ start: 21, end: 26 })
  })

  it('is navigable only when the index is ready and the symbol has targets', () => {
    expect(isNavigable(result([target('definition', 'lib.py', 1)]))).toBe(true)
    expect(isNavigable(result([]))).toBe(false)
    expect(isNavigable({ ...result([target('definition', 'lib.py', 1)]), symbol: null })).toBe(false)
    expect(isNavigable({ ...result([target('definition', 'lib.py', 1)]), ready: false })).toBe(false)
  })

  it('is navigable for a name from an external package, which shows its documentation', () => {
    const external = { ...result([]), documentation: RENDER }

    expect(isNavigable(external)).toBe(true)
    expect(titleOf(external)).toBe('django.shortcuts.render')
    expect(missingDocumentation(RENDER)).toBe('No documentation found for django.shortcuts.render.')
    expect(missingDocumentation({ ...RENDER, text: 'Renders a template.' })).toBeNull()
  })

  it('lists definitions first, then usages grouped by file in their order', () => {
    const groups = groupTargets([target('usage', 'b.py', 3), target('definition', 'lib.py', 1), target('usage', 'a.py', 7), target('usage', 'b.py', 9)])

    expect(groups.definitions.map((item) => item.path)).toEqual(['lib.py'])
    expect(groups.files.map((file) => [file.path, file.targets.map((item) => item.line)])).toEqual([
      ['b.py', [3, 9]],
      ['a.py', [7]],
    ])
  })

  it('opens a single target directly, in the review or not', () => {
    expect(directTarget(result([target('definition', 'lib.py', 1, 4)]))?.unit_id).toBe(4)
    expect(directTarget(result([target('definition', 'lib.py', 1)]))?.path).toBe('lib.py')
    expect(directTarget(result([target('definition', 'lib.py', 1, 4), target('definition', 'other.py', 1, 5)]))).toBeNull()
  })

  it('names the list after what was clicked', () => {
    expect(titleOf(result([], 'reference'))).toBe('Definitions of price')
    expect(titleOf(result([], 'definition'))).toBe('Usages of price')
    expect(emptyMessage(result([], 'definition'))).toBe('No usages of price found.')
  })
})
