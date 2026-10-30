import { act, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { DiffRow, UnitDiff } from '../api/types'
import { setDiffLayout } from '../hooks/useDiffLayout'
import { rowKey } from '../review/selection'
import { DEFAULT_DIFF_LAYOUT, type DiffLayout } from '../settings/diffLayout'
import { UnitDiffView } from './UnitDiffView'

const HEADER = 'diff --git a/app.py b/app.py\n--- a/app.py\n+++ b/app.py\n'

function row(change: DiffRow['change'], oldIndex: number | null, newIndex: number | null, text: string): DiffRow {
  return {
    change,
    old_index: oldIndex,
    new_index: newIndex,
    old_line: oldIndex === null ? null : oldIndex + 1,
    new_line: newIndex === null ? null : newIndex + 1,
    text,
    row_hash: change === 'context' ? null : text,
    approved: false,
    selection_id: null,
    placeholder: false,
  }
}

const header = row('context', 0, 0, 'def total(items):')
const removed = row('removed', 1, null, '    return 0')
const added = row('added', null, 1, '    return sum(items)')
const rewritten = [header, removed, added]
const inserted = [row('added', null, 0, 'def total(items):'), row('added', null, 1, '    return 0')]

function diff(rows: DiffRow[]): UnitDiff {
  return { unit_id: 1, mode: 'base', available_modes: ['base'], approved_text_unavailable: false, binary: false, unified: HEADER, rows }
}

function resizeWindow(width: number) {
  act(() => {
    Object.defineProperty(window, 'innerWidth', { configurable: true, value: width })
    window.dispatchEvent(new Event('resize'))
  })
}

function chooseLayout(layout: DiffLayout) {
  act(() => {
    setDiffLayout({ ...DEFAULT_DIFF_LAYOUT, layout })
  })
}

interface Options {
  rows?: DiffRow[]
  threads?: DiffRow[]
  highlighted?: ReadonlySet<string>
  onRowClick?: (row: DiffRow, extend: boolean) => void
  onLineNumberClick?: (row: DiffRow, side: 'old' | 'new', extend: boolean) => void
}

function view({ rows = rewritten, threads = [], highlighted, onRowClick, onLineNumberClick }: Options = {}) {
  const { container } = render(
    <UnitDiffView
      diff={diff(rows)}
      path="app.py"
      selectable={onRowClick !== undefined}
      selected={new Set()}
      onRowClick={onRowClick ?? (() => undefined)}
      onLineNumberClick={onLineNumberClick}
      highlighted={highlighted}
      widgets={(changeKeyOf) => Object.fromEntries(threads.map((thread) => [changeKeyOf(thread) ?? '', <p key={thread.text}>{`thread on ${thread.text.trim()}`}</p>]))}
    />,
  )
  return container.querySelector('table') as HTMLTableElement
}

function cellsOf(element: HTMLElement): HTMLTableCellElement[] {
  return [...(element.closest('tr') as HTMLTableRowElement).cells]
}

function codeCell(table: HTMLTableElement, text: string): HTMLTableCellElement {
  const cell = [...table.querySelectorAll<HTMLTableCellElement>('td.diff-code')].find((candidate) => candidate.textContent === text)
  if (!cell) {
    throw new Error(`No code cell with ${text}`)
  }
  return cell
}

function gutter(table: HTMLTableElement, text: string, side: 'old' | 'new'): HTMLTableCellElement {
  return cellsOf(codeCell(table, text))[side === 'old' ? 0 : 2]
}

describe('UnitDiffView layout', () => {
  afterEach(() => {
    act(() => {
      setDiffLayout(DEFAULT_DIFF_LAYOUT)
    })
    window.localStorage.clear()
    resizeWindow(1024)
  })

  it('switches between split and unified when the window crosses the threshold', () => {
    resizeWindow(1600)
    const table = view()
    expect(table).toHaveClass('diff-split')

    resizeWindow(1200)
    expect(table).toHaveClass('diff-unified')

    resizeWindow(1400)
    expect(table).toHaveClass('diff-split')
  })

  it('keeps a new unit unified on a wide window', () => {
    resizeWindow(2400)
    expect(view({ rows: inserted })).toHaveClass('diff-unified')
  })

  it('pairs each removed line with its replacement in a multi-line rewrite', () => {
    const rows = [header, row('removed', 1, null, '    a = 0'), row('removed', 2, null, '    b = 0'), row('added', null, 1, '    a = 1'), row('added', null, 2, '    b = 1')]
    chooseLayout('split')
    const table = view({ rows })

    expect(cellsOf(codeCell(table, '    a = 0'))[3]).toHaveTextContent('a = 1')
    expect(cellsOf(codeCell(table, '    b = 0'))[3]).toHaveTextContent('b = 1')
  })

  it('keeps removed lines before added lines in unified view', () => {
    const rows = [header, row('removed', 1, null, '    a = 0'), row('removed', 2, null, '    b = 0'), row('added', null, 1, '    a = 1'), row('added', null, 2, '    b = 1')]
    chooseLayout('unified')
    const table = view({ rows })

    const lines = [...table.querySelectorAll('td.diff-code')].map((cell) => cell.textContent.trim())
    expect(lines).toEqual(['def total(items):', 'a = 0', 'b = 0', 'a = 1', 'b = 1'])
  })

  it('follows a layout chosen in another tab', () => {
    const table = view()
    expect(table).toHaveClass('diff-unified')

    act(() => {
      window.localStorage.setItem('bussola.diffLayout', JSON.stringify({ layout: 'split', threshold: 1400 }))
      window.dispatchEvent(new StorageEvent('storage', { key: 'bussola.diffLayout' }))
    })
    expect(table).toHaveClass('diff-split')
  })

  it.each([
    ['removed', removed, 0],
    ['added', added, 1],
  ] as const)('puts a thread on a %s line on its own side', (_, line, side) => {
    chooseLayout('split')
    view({ threads: [line] })

    const cell = screen.getByText(`thread on ${line.text.trim()}`).closest('td') as HTMLTableCellElement
    const cells = cellsOf(cell)
    expect(cells).toHaveLength(2)
    expect(cells[side]).toBe(cell)
    expect(cells[1 - side]).toBeEmptyDOMElement()
  })

  it('spans both columns with a thread on an unchanged line', () => {
    chooseLayout('split')
    view({ threads: [header] })

    const cell = screen.getByText('thread on def total(items):').closest('td') as HTMLTableCellElement
    expect(cellsOf(cell)).toEqual([cell])
    expect(cell.colSpan).toBe(4)
  })

  it('reports the clicked side and shift-click from both columns', () => {
    chooseLayout('split')
    const onLineNumberClick = vi.fn()
    const table = view({ onLineNumberClick })

    const oldGutter = gutter(table, '    return 0', 'old')
    expect(oldGutter).toHaveTextContent('2')
    fireEvent.mouseDown(oldGutter, { button: 0 })
    fireEvent.mouseUp(window)
    expect(onLineNumberClick).toHaveBeenLastCalledWith(removed, 'old', false)

    fireEvent.mouseDown(gutter(table, '    return sum(items)', 'new'), { button: 0, shiftKey: true })
    expect(onLineNumberClick).toHaveBeenLastCalledWith(added, 'new', true)
  })

  it('marks the commented side of a split line only', () => {
    chooseLayout('split')
    const table = view({ highlighted: new Set([rowKey(removed)]) })

    const line = codeCell(table, '    return 0').closest('tr')
    expect(line).toHaveClass('row-commented-old')
    expect(line).not.toHaveClass('row-commented')
    expect(line).not.toHaveClass('row-commented-new')
  })
})

const LONG_LINE = `        total = combine(${Array.from({ length: 30 }, (_, index) => `argument_${String(index)}`).join(', ')})`
const wrapped = [header, row('removed', 1, null, '    return 0'), row('added', null, 1, LONG_LINE)]

function newGutter(table: HTMLTableElement, text: string, layout: DiffLayout): HTMLTableCellElement {
  return cellsOf(codeCell(table, text))[layout === 'split' ? 2 : 1]
}

describe('UnitDiffView hanging indent', () => {
  afterEach(() => {
    act(() => {
      setDiffLayout(DEFAULT_DIFF_LAYOUT)
    })
    window.localStorage.clear()
  })

  it.each(['unified', 'split'] as const)('splits indentation from code with one line number per source line in %s view', (layout) => {
    chooseLayout(layout)
    const table = view({ rows: wrapped })
    const cell = codeCell(table, LONG_LINE)

    expect(cell.querySelector('.line-indent')?.textContent).toBe('        ')
    expect(cell.querySelector('.line-body')?.textContent).toBe(LONG_LINE.trimStart())
    expect(codeCell(table, '    return 0').querySelector('.line-indent')?.textContent).toBe('    ')
    expect(newGutter(table, LONG_LINE, layout)).toHaveTextContent(/^2$/)
  })

  it.each(['unified', 'split'] as const)('selects the whole source line from any part of a wrapped line in %s view', (layout) => {
    chooseLayout(layout)
    const onRowClick = vi.fn()
    const onLineNumberClick = vi.fn()
    const table = view({ rows: wrapped, onRowClick, onLineNumberClick })
    const body = codeCell(table, LONG_LINE).querySelector('.line-body') as HTMLElement

    fireEvent.click(body)
    fireEvent.click(body, { shiftKey: true })
    fireEvent.mouseDown(newGutter(table, LONG_LINE, layout), { button: 0, shiftKey: true })
    fireEvent.mouseUp(window)

    expect(onRowClick.mock.calls).toEqual([
      [wrapped[2], false],
      [wrapped[2], true],
    ])
    expect(onLineNumberClick).toHaveBeenCalledWith(wrapped[2], 'new', true)
  })
})
