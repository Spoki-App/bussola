import { useEffect, useMemo, useRef, useState, type MouseEvent, type ReactNode } from 'react'
import { Decoration, Diff, Hunk, getChangeKey, isDelete, isInsert, parseDiff, type ChangeData, type HunkData } from 'react-diff-view'
import 'react-diff-view/style/index.css'

import type { DiffRow, UnitDiff } from '../api/types'
import { useViewType } from '../hooks/useDiffLayout'
import { columnAt, isNavigationClick, type ScreenPoint } from '../review/codeNavigation'
import { collapsedUnified, segmentRows, type Segment } from '../review/collapse'
import { diffTokens, languageFor } from '../review/highlight'
import { isSelectable, rowKey } from '../review/selection'
import { plural } from '../review/text'
import { hasModification } from '../settings/diffLayout'

const PLACEHOLDER_GUTTER = '⋯'
const FILE_HEADER_LINES = 3

export type GutterSide = 'old' | 'new'

export interface TargetLine {
  side: GutterSide
  line: number
}

interface Props {
  diff: UnitDiff
  path: string
  selectable: boolean
  selected: ReadonlySet<string>
  onRowClick: (row: DiffRow, extend: boolean) => void
  onLineNumberClick?: (row: DiffRow, side: GutterSide, extend: boolean) => void
  onLineSelectEnd?: () => void
  highlighted?: ReadonlySet<string>
  widgets?: (rowFor: (row: DiffRow) => string | undefined) => Record<string, ReactNode>
  onNavigate?: (row: DiffRow, side: GutterSide, column: number, point: ScreenPoint) => void
  target?: TargetLine
}

interface RowIndex {
  rowOf: (change: ChangeData | null) => DiffRow | undefined
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
      if (!change) {
        return undefined
      }
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

function gutterSide(row: DiffRow): GutterSide {
  return row.change === 'removed' ? 'old' : 'new'
}

function rowClasses(row: DiffRow | undefined, highlighted: ReadonlySet<string> | undefined, targetRow: DiffRow | undefined): string[] {
  if (!row) {
    return []
  }
  return [
    ...(row.approved ? ['row-approved'] : []),
    ...(row.placeholder ? ['row-placeholder'] : []),
    ...(highlighted?.has(rowKey(row)) ? ['row-commented'] : []),
    ...(row === targetRow ? ['row-target'] : []),
  ]
}

function lineClasses(rows: (DiffRow | undefined)[], highlighted: ReadonlySet<string> | undefined, targetRow: DiffRow | undefined): string[] {
  const [oldRow, newRow] = rows
  if (rows.length === 2 && oldRow !== newRow) {
    return [...rowClasses(oldRow, highlighted, targetRow).map((name) => `${name}-old`), ...rowClasses(newRow, highlighted, targetRow).map((name) => `${name}-new`)]
  }
  return rowClasses(oldRow, highlighted, targetRow)
}

function targetPosition(rows: DiffRow[], target: TargetLine | undefined): number {
  if (!target) {
    return -1
  }
  return rows.findIndex((row) => (target.side === 'new' ? row.change !== 'removed' && row.new_line === target.line : row.change !== 'added' && row.old_line === target.line))
}

function hiddenLabel(segment: Segment): string {
  const count = segment.end - segment.start + 1
  return `Show ${plural(count, 'hidden line')}`
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

export function UnitDiffView({ diff, path, selectable, selected, onRowClick, onLineNumberClick, onLineSelectEnd, widgets, highlighted, onNavigate, target }: Props) {
  const modified = useMemo(() => hasModification(diff.rows), [diff.rows])
  const viewType = useViewType(modified)
  const dragging = useRef(false)
  const endSelection = useRef(onLineSelectEnd)

  useEffect(() => {
    endSelection.current = onLineSelectEnd
  })

  useEffect(() => {
    const onMouseUp = () => {
      if (dragging.current) {
        dragging.current = false
        endSelection.current?.()
      }
    }
    window.addEventListener('mouseup', onMouseUp)
    return () => {
      window.removeEventListener('mouseup', onMouseUp)
    }
  }, [])

  const [expanded, setExpanded] = useState<ReadonlySet<string>>(new Set())
  const index = useMemo(() => buildIndex(diff.rows), [diff.rows])
  const widgetMap = widgets ? widgets(index.changeKeyOf) : undefined
  const pinnedKeys = Object.keys(widgetMap ?? {}).join(',')
  const targetIndex = targetPosition(diff.rows, target)
  const segments = useMemo(() => {
    const keys = new Set(pinnedKeys.split(','))
    const pinned = new Set(diff.rows.flatMap((row, position) => (keys.has(index.changeKeyOf(row) ?? '') || position === targetIndex ? [position] : [])))
    return segmentRows(diff.rows, expanded, pinned)
  }, [diff.rows, expanded, index, pinnedKeys, targetIndex])
  const targetRow = targetIndex < 0 ? undefined : diff.rows[targetIndex]
  const header = diff.unified.split('\n').slice(0, FILE_HEADER_LINES).join('\n')
  const file = useMemo(
    () => parseDiff(collapsedUnified(header, diff.rows, segments), viewType === 'split' ? { nearbySequences: 'zip' } : {})[0],
    [header, diff.rows, segments, viewType],
  )
  const tokens = useMemo(() => {
    const whole: Segment[] = diff.rows.length > 0 ? [{ kind: 'rows', start: 0, end: diff.rows.length - 1 }] : []
    return diffTokens(parseDiff(collapsedUnified(header, diff.rows, whole))[0]?.hunks ?? [], languageFor(path))
  }, [header, diff.rows, path])

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
      viewType={viewType}
      diffType={file.type}
      hunks={file.hunks}
      tokens={tokens}
      selectedChanges={selectedChanges}
      widgets={widgetMap}
      className={selectable ? 'diff selectable' : 'diff'}
      generateLineClassName={({ changes, defaultGenerate }) => {
        const rows = (changes as (ChangeData | null)[]).map(index.rowOf)
        return [defaultGenerate(), ...lineClasses(rows, highlighted, targetRow)].join(' ')
      }}
      renderGutter={({ change, side }) => gutterNumber(index.rowOf(change), side)}
      gutterEvents={{
        onMouseDown: ({ change, side }, event: MouseEvent<HTMLElement>) => {
          const row = index.rowOf(change)
          if (!row || !onLineNumberClick || event.button !== 0) {
            return
          }
          event.preventDefault()
          dragging.current = true
          onLineNumberClick(row, side ?? gutterSide(row), event.shiftKey)
        },
        onMouseEnter: ({ change, side }) => {
          const row = index.rowOf(change)
          if (row && onLineNumberClick && dragging.current) {
            onLineNumberClick(row, side ?? gutterSide(row), true)
          }
        },
      }}
      codeEvents={{
        onMouseDown: (_, event: MouseEvent<HTMLElement>) => {
          if (onNavigate && isNavigationClick(event)) {
            event.preventDefault()
          }
        },
        onClick: ({ change, side }, event: MouseEvent<HTMLElement>) => {
          const row = index.rowOf(change)
          if (onNavigate && isNavigationClick(event)) {
            const column = columnAt(event.currentTarget, event.clientX, event.clientY)
            if (row && column !== null) {
              onNavigate(row, side ?? gutterSide(row), column, { x: event.clientX, y: event.clientY })
            }
            return
          }
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
