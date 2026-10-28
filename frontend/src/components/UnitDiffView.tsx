import { useMemo, useState, type MouseEvent, type ReactNode } from 'react'
import { Decoration, Diff, Hunk, getChangeKey, isDelete, isInsert, parseDiff, type ChangeData, type HunkData } from 'react-diff-view'
import 'react-diff-view/style/index.css'

import type { DiffRow, UnitDiff } from '../api/types'
import { collapsedUnified, segmentRows, type Segment } from '../review/collapse'
import { isSelectable, rowKey } from '../review/selection'

const PLACEHOLDER_GUTTER = '⋯'
const FILE_HEADER_LINES = 3

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

function hiddenLabel(segment: Segment): string {
  const count = segment.end - segment.start + 1
  return `Show ${String(count)} hidden line${count === 1 ? '' : 's'}`
}

function renderSegments(segments: Segment[], hunks: HunkData[], expand: (id: string) => void) {
  let hunkIndex = 0
  return segments.map((segment) => {
    if (segment.kind === 'rows') {
      const hunk = hunks[hunkIndex]
      hunkIndex += 1
      return <Hunk key={`rows-${String(segment.start)}`} hunk={hunk} />
    }
    return (
      <Decoration key={`gap-${segment.id}`} className="diff-gap">
        <button type="button" className="gap-button" onClick={() => { expand(segment.id) }}>
          {hiddenLabel(segment)}
        </button>
      </Decoration>
    )
  })
}

export function UnitDiffView({ diff, selectable, selected, onRowClick, onLineNumberClick, widgets }: Props) {
  const [expanded, setExpanded] = useState<ReadonlySet<string>>(new Set())
  const index = useMemo(() => buildIndex(diff.rows), [diff.rows])
  const widgetMap = widgets ? widgets(index.changeKeyOf) : undefined
  const pinnedKeys = Object.keys(widgetMap ?? {}).join(',')
  const segments = useMemo(() => {
    const keys = new Set(pinnedKeys.split(','))
    const pinned = new Set(diff.rows.flatMap((row, position) => (keys.has(index.changeKeyOf(row) ?? '') ? [position] : [])))
    return segmentRows(diff.rows, expanded, pinned)
  }, [diff.rows, expanded, index, pinnedKeys])
  const file = useMemo(() => {
    const header = diff.unified.split('\n').slice(0, FILE_HEADER_LINES).join('\n')
    return parseDiff(collapsedUnified(header, diff.rows, segments))[0]
  }, [diff.unified, diff.rows, segments])

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
      widgets={widgetMap}
      className={selectable ? 'diff selectable' : 'diff'}
      generateLineClassName={({ changes, defaultGenerate }) => {
        const rows = changes.map((change) => index.rowOf(change))
        const classes = [defaultGenerate()]
        if (rows.some((row) => row?.approved)) {
          classes.push('row-approved')
        }
        if (rows.some((row) => row?.placeholder)) {
          classes.push('row-placeholder')
        }
        return classes.join(' ')
      }}
      renderGutter={({ change, side }) => gutterNumber(index.rowOf(change), side)}
      gutterEvents={{
        onClick: ({ change, side }) => {
          const row = change ? index.rowOf(change) : undefined
          if (row && onLineNumberClick) {
            onLineNumberClick(row, side ?? (row.change === 'removed' ? 'old' : 'new'))
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
      {(hunks) => renderSegments(segments, hunks, (id) => { setExpanded(new Set([...expanded, id])) })}
    </Diff>
  )
}
