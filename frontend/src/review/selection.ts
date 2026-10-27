import type { DiffRow, LineRange } from '../api/types'

export interface SelectionRanges {
  head_range: LineRange | null
  base_range: LineRange | null
}

export function rowKey(row: DiffRow): string {
  return `${row.change}:${String(row.old_index)}:${String(row.new_index)}`
}

export function isSelectable(row: DiffRow): boolean {
  return row.change !== 'context' && row.row_hash !== null && !row.approved
}

export function selectRange(rows: DiffRow[], anchorKey: string, focusKey: string): Set<string> {
  const keys = rows.map(rowKey)
  const anchor = keys.indexOf(anchorKey)
  const focus = keys.indexOf(focusKey)
  if (anchor < 0 || focus < 0) {
    return new Set()
  }
  const [start, end] = anchor <= focus ? [anchor, focus] : [focus, anchor]
  return new Set(
    rows
      .slice(start, end + 1)
      .filter(isSelectable)
      .map(rowKey),
  )
}

export function selectionRanges(rows: DiffRow[], selected: ReadonlySet<string>): SelectionRanges {
  const chosen = rows.filter((row) => selected.has(rowKey(row)))
  return {
    head_range: span(chosen.filter((row) => row.change === 'added').map((row) => row.new_line)),
    base_range: span(chosen.filter((row) => row.change === 'removed').map((row) => row.old_line)),
  }
}

export function approvedSelections(rows: DiffRow[]): string[] {
  return [...new Set(rows.flatMap((row) => (row.selection_id ? [row.selection_id] : [])))]
}

function span(lines: (number | null)[]): LineRange | null {
  const present = lines.filter((line): line is number => line !== null)
  return present.length === 0 ? null : [Math.min(...present), Math.max(...present)]
}
