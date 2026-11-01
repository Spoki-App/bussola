import { afterEach, describe, expect, it } from 'vitest'

import type { NavigationResult, NavigationTarget } from '../api/navigation'
import { clearCaret, placeCaret } from '../test/caret'
import { columnAt, directTarget, emptyMessage, groupTargets, isNavigationClick, textOffset, titleOf } from './codeNavigation'

function target(role: NavigationTarget['role'], path: string, line: number, unitId: number | null = null): NavigationTarget {
  return { role, path, line, column: 0, preview: `line ${String(line)}`, side: 'head', unit_id: unitId }
}

function result(targets: NavigationTarget[], origin: NavigationResult['origin'] = 'reference'): NavigationResult {
  return { ready: true, symbol: 'price', origin, resolver: 'tree-sitter', targets, server_hint: null }
}

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

  it('lists definitions first, then usages grouped by file in their order', () => {
    const groups = groupTargets([target('usage', 'b.py', 3), target('definition', 'lib.py', 1), target('usage', 'a.py', 7), target('usage', 'b.py', 9)])

    expect(groups.definitions.map((item) => item.path)).toEqual(['lib.py'])
    expect(groups.files.map((file) => [file.path, file.targets.map((item) => item.line)])).toEqual([
      ['b.py', [3, 9]],
      ['a.py', [7]],
    ])
  })

  it('jumps directly only to a single target that is part of the review', () => {
    expect(directTarget(result([target('definition', 'lib.py', 1, 4)]))?.unit_id).toBe(4)
    expect(directTarget(result([target('definition', 'lib.py', 1)]))).toBeNull()
    expect(directTarget(result([target('definition', 'lib.py', 1, 4), target('definition', 'other.py', 1, 5)]))).toBeNull()
  })

  it('names the list after what was clicked', () => {
    expect(titleOf(result([], 'reference'))).toBe('Definitions of price')
    expect(titleOf(result([], 'definition'))).toBe('Usages of price')
    expect(emptyMessage(result([], 'definition'))).toBe('No usages of price found.')
  })
})
