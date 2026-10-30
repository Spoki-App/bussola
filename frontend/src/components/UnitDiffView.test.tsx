import { fireEvent, render } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import type { DiffRow, UnitDiff } from '../api/types'
import { UnitDiffView } from './UnitDiffView'

const LONG_LINE = `        total = combine(${Array.from({ length: 30 }, (_, index) => `argument_${String(index)}`).join(', ')})`

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

const rows = [row('context', 0, 0, 'def total(items):'), row('removed', 1, null, '    return 0'), row('added', null, 1, LONG_LINE), row('added', null, 2, '    return total')]
const diff: UnitDiff = {
  unit_id: 1,
  mode: 'base',
  available_modes: ['base'],
  approved_text_unavailable: false,
  binary: false,
  unified: 'diff --git a/app.py b/app.py\n--- a/app.py\n+++ b/app.py\n',
  rows,
}

function renderDiff() {
  const onRowClick = vi.fn()
  const onLineNumberClick = vi.fn()
  const view = render(<UnitDiffView diff={diff} path="app.py" selectable selected={new Set()} onRowClick={onRowClick} onLineNumberClick={onLineNumberClick} />)
  const longCell = [...view.container.querySelectorAll('td.diff-code')].find((cell) => cell.textContent === LONG_LINE)
  if (!longCell) {
    throw new Error('diff not rendered')
  }
  return { ...view, longCell, onRowClick, onLineNumberClick }
}

describe('UnitDiffView hanging indent', () => {
  it('wraps by default with a hanging indent and one line number per source line', () => {
    const { longCell } = renderDiff()

    expect(longCell.querySelector('.line-indent')?.textContent).toBe('        ')
    expect(longCell.querySelector('.line-body')?.textContent).toBe(LONG_LINE.trimStart())
    const gutters = [...(longCell.closest('tr')?.querySelectorAll('td.diff-gutter') ?? [])].map((cell) => cell.textContent)
    expect(gutters).toEqual(['', '2'])
  })

  it('selects the whole source line from any part of a wrapped line', () => {
    const { longCell, onRowClick, onLineNumberClick } = renderDiff()
    const body = longCell.querySelector('.line-body')
    const gutter = longCell.closest('tr')?.querySelectorAll('td.diff-gutter')[1]
    if (!body || !gutter) {
      throw new Error('wrapped line not rendered')
    }

    fireEvent.click(body)
    fireEvent.click(body, { shiftKey: true })
    fireEvent.mouseDown(gutter, { button: 0, shiftKey: true })

    expect(onRowClick.mock.calls).toEqual([
      [rows[2], false],
      [rows[2], true],
    ])
    expect(onLineNumberClick).toHaveBeenCalledWith(rows[2], 'new', true)
  })
})
