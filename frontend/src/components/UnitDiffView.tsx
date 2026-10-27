import { useMemo, type MouseEvent, type ReactNode } from 'react'
import { Diff, Hunk, getChangeKey, isDelete, isInsert, parseDiff, type ChangeData } from 'react-diff-view'
import 'react-diff-view/style/index.css'

import type { DiffRow, UnitDiff } from '../api/types'
import { isSelectable, rowKey } from '../review/selection'

const PLACEHOLDER_GUTTER = '⋯'

export type GutterSide = 'old' | 'new'

interface Props {
  diff: UnitDiff
  selectable: boolean
  selected: ReadonlySet<string>
  onRowClick: (row: DiffRow, extend: boolean) => void
  onLineNumberClick?: (row: DiffRow, side: GutterSide) => void
  widgets?: (rowFor: (row: DiffRow) => string | undefined) => Record<string, ReactNode>
}

interface RowIndex {
  rowOf: (change: ChangeData) => DiffRow | undefined
  changeKeyOf: (row: DiffRow) => string | undefined
}

function buildIndex(rows: DiffRow[]): RowIndex {
  const inserted = new Map<number, DiffRow>()
  const deleted = new Map<number, DiffRow>()
  const normal = new Map<number, DiffRow>()
  for (const row of rows) {
    if (row.change === 'added' && row.new_index !== null) {
      inserted.set(row.new_index + 1, row)
    } else if (row.change === 'removed' && row.old_index !== null) {
      deleted.set(row.old_index + 1, row)
    } else if (row.new_index !== null) {
      normal.set(row.new_index + 1, row)
    }
  }
  return {
    rowOf: (change) => {
      if (isInsert(change)) {
        return inserted.get(change.lineNumber)
      }
      if (isDelete(change)) {
        return deleted.get(change.lineNumber)
      }
      return normal.get(change.newLineNumber)
    },
    changeKeyOf: (row) => {
      if (row.change === 'added' && row.new_index !== null) {
        return `I${String(row.new_index + 1)}`
      }
      if (row.change === 'removed' && row.old_index !== null) {
        return `D${String(row.old_index + 1)}`
      }
      return row.old_index === null ? undefined : `N${String(row.old_index + 1)}`
    },
  }
}

function gutterNumber(row: DiffRow | undefined, side: GutterSide): string {
  if (!row) {
    return ''
  }
  const index = side === 'old' ? row.old_index : row.new_index
  const line = side === 'old' ? row.old_line : row.new_line
  if (index === null) {
    return ''
  }
  return line === null ? PLACEHOLDER_GUTTER : String(line)
}

export function UnitDiffView({ diff, selectable, selected, onRowClick, onLineNumberClick, widgets }: Props) {
  const file = useMemo(() => parseDiff(diff.unified)[0], [diff.unified])
  const index = useMemo(() => buildIndex(diff.rows), [diff.rows])

  if (diff.binary) {
    return <p className="diff-note">Binary file, no diff available.</p>
  }
  if (diff.rows.length === 0) {
    return <p className="diff-note">Empty.</p>
  }

  const selectedChanges = file.hunks
    .flatMap((hunk) => hunk.changes)
    .filter((change) => {
      const row = index.rowOf(change)
      return row !== undefined && selected.has(rowKey(row))
    })
    .map(getChangeKey)

  return (
    <Diff
      viewType="unified"
      diffType={file.type}
      hunks={file.hunks}
      selectedChanges={selectedChanges}
      widgets={widgets ? widgets(index.changeKeyOf) : undefined}
      className={selectable ? 'diff selectable' : 'diff'}
      generateLineClassName={({ changes, defaultGenerate }) => {
        const approved = changes.some((change) => index.rowOf(change)?.approved)
        return approved ? `${defaultGenerate()} row-approved` : defaultGenerate()
      }}
      renderGutter={({ change, side }) => gutterNumber(index.rowOf(change), side)}
      gutterEvents={{
        onClick: ({ change, side }) => {
          const row = change ? index.rowOf(change) : undefined
          if (row && side && onLineNumberClick) {
            onLineNumberClick(row, side)
          }
        },
      }}
      codeEvents={{
        onClick: ({ change }, event: MouseEvent<HTMLElement>) => {
          const row = change ? index.rowOf(change) : undefined
          if (selectable && row && isSelectable(row)) {
            onRowClick(row, event.shiftKey)
          }
        },
      }}
    >
      {(hunks) => hunks.map((hunk) => <Hunk key={hunk.content} hunk={hunk} />)}
    </Diff>
  )
}
