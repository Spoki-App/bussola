import { memo, useEffect, useState, type ReactNode } from 'react'

import { describeError } from '../api/client'
import { useApprove, useRevoke, useRevokeSelections, useUnitDiff } from '../api/hooks'
import type { DiffMode, DiffRow, Unit, UnitDiff } from '../api/types'
import { unitTitle } from '../review/logic'
import { approvedSelections, rowKey, selectRange, selectionRanges } from '../review/selection'
import { ErrorNote, KindBadge, StateBadge } from './Badges'
import { ImagePreview } from './ImagePreview'
import { QualifiedName } from './QualifiedName'
import { UnitDiffView, type GutterSide } from './UnitDiffView'

export interface UnitActions {
  toggleApproval: () => void
  comment: () => void
}

export interface CommentTarget {
  unit: Unit
  row: DiffRow
  side: GutterSide
  mode: DiffMode
  extend: boolean
  selecting: boolean
}

interface Props {
  reviewId: number
  unit: Unit
  focused: boolean
  onFocus: (unitId: number) => void
  register: (unitId: number, actions: UnitActions | null) => void
  onComment?: (target: CommentTarget) => void
  onCommentSelectEnd?: () => void
  renderWidgets?: (unit: Unit, diff: UnitDiff, changeKeyOf: (row: DiffRow) => string | undefined) => Record<string, ReactNode>
  highlightRows?: (unit: Unit, diff: UnitDiff) => ReadonlySet<string> | undefined
  nested?: boolean
}

const APPROVE_LABELS = { approve: 'Approve', approve_under_name: 'Approve under this name', confirm_removal: 'Confirm removal' } as const

const MODE_LABELS: Record<DiffMode, string> = { approved: 'Approved → current', base: 'Base → head' }

export const UnitCard = memo(function UnitCard({ reviewId, unit, focused, onFocus, register, onComment, onCommentSelectEnd, renderWidgets, highlightRows, nested = false }: Props) {
  const todo = unit.todo
  const [expanded, setExpanded] = useState(todo)
  const [wasTodo, setWasTodo] = useState(todo)
  if (todo !== wasTodo) {
    setWasTodo(todo)
    setExpanded(todo)
  }
  const [mode, setMode] = useState<DiffMode | undefined>(undefined)
  const [selected, setSelected] = useState<ReadonlySet<string>>(new Set())
  const [anchor, setAnchor] = useState<string | null>(null)
  const diff = useUnitDiff(reviewId, unit, mode, expanded)
  const approve = useApprove(reviewId)
  const revoke = useRevoke(reviewId)
  const revokeSelections = useRevokeSelections(reviewId)
  const rows = diff.data?.rows ?? []
  const busy = approve.isPending || revoke.isPending || revokeSelections.isPending
  const failure = approve.error ?? revoke.error ?? revokeSelections.error

  const clearSelection = () => {
    setSelected(new Set())
    setAnchor(null)
  }
  const approveUnit = () => {
    approve.mutate({ unit_id: unit.id })
  }
  const approveSelection = () => {
    approve.mutate({ unit_id: unit.id, ...selectionRanges(rows, selected) }, { onSuccess: clearSelection })
  }
  const revokeUnit = () => {
    if (unit.approval_id) {
      revoke.mutate(unit.approval_id)
    }
  }
  const revokeRows = () => {
    revokeSelections.mutate(approvedSelections(rows))
  }
  const toggleApproval = () => {
    if (busy) {
      return
    }
    if (selected.size > 0) {
      approveSelection()
    } else if (unit.action === 'revoke') {
      revokeUnit()
    } else if (unit.action === 'revoke_lines') {
      revokeRows()
    } else if (unit.action !== 'none') {
      approveUnit()
    }
  }
  const commentOnFirstChange = () => {
    setExpanded(true)
    const row = rows.find((candidate) => candidate.change !== 'context') ?? rows.at(0)
    if (row && onComment && diff.data) {
      onComment({ unit, row, side: row.change === 'removed' ? 'old' : 'new', mode: diff.data.mode, extend: false, selecting: false })
    }
  }

  useEffect(() => {
    register(unit.id, { toggleApproval, comment: commentOnFirstChange })
    return () => {
      register(unit.id, null)
    }
  })

  const onRowClick = (row: DiffRow, extend: boolean) => {
    const key = rowKey(row)
    if (extend && anchor) {
      setSelected(selectRange(rows, anchor, key))
      return
    }
    const next = new Set(selected)
    if (next.has(key)) {
      next.delete(key)
    } else {
      next.add(key)
    }
    setSelected(next)
    setAnchor(key)
  }

  const canSwitchMode = diff.data?.available_modes.includes('approved') ?? false

  return (
    <article id={`unit-${String(unit.id)}`} className={`unit-card state-${unit.state}${focused ? ' focused' : ''}`} onClick={() => { onFocus(unit.id) }}>
      <header className="unit-header">
        <button type="button" className="disclosure" aria-expanded={expanded} aria-label={expanded ? 'Collapse unit' : 'Expand unit'} onClick={() => { setExpanded(!expanded) }}>
          {expanded ? '▾' : '▸'}
        </button>
        <KindBadge kind={unit.kind} />
        <QualifiedName module={unit.qualified_name ? unit.module : null} name={unitTitle(unit)} nested={nested && Boolean(unit.qualified_name)} />
        <StateBadge state={unit.state} />
        {unit.change_type !== 'modified' && <span className="label">{unit.change_type}</span>}
        {unit.base_changed && <span className="label" title="The base changed since you approved this unit">base changed</span>}
        {unit.rows_total > 0 && <span className="label">{`${String(unit.rows_approved)}/${String(unit.rows_total)} lines approved`}</span>}
        {unit.open_threads > 0 && <span className={`label threads${unit.todo ? '' : ' warn'}`}>{`${String(unit.open_threads)} open thread${unit.open_threads > 1 ? 's' : ''}`}</span>}
        <span className="spacer" />
        {canSwitchMode && (
          <div className="segmented" role="group" aria-label="Diff mode">
            {(['approved', 'base'] as DiffMode[]).map((option) => (
              <button key={option} type="button" className={diff.data?.mode === option ? 'active' : ''} onClick={() => { setMode(option) }}>
                {MODE_LABELS[option]}
              </button>
            ))}
          </div>
        )}
        {selected.size > 0 && (
          <button type="button" className="approve" disabled={busy} onClick={approveSelection}>
            {`Approve selection (${String(selected.size)})`}
          </button>
        )}
        {unit.rows_approved > 0 && (
          <button type="button" disabled={busy || rows.length === 0} onClick={revokeRows}>
            Revoke lines
          </button>
        )}
        {unit.action === 'revoke' && (
          <button type="button" disabled={busy} onClick={revokeUnit}>
            Revoke
          </button>
        )}
        {unit.action in APPROVE_LABELS && (
          <button type="button" className={selected.size > 0 ? 'approve-quiet' : 'approve'} disabled={busy} onClick={approveUnit}>
            {APPROVE_LABELS[unit.action as keyof typeof APPROVE_LABELS]}
          </button>
        )}
      </header>
      {failure && <ErrorNote message={describeError(failure)} />}
      {expanded && (
        <div className="unit-body">
          {diff.data?.approved_text_unavailable && <p className="diff-note">The approved version is too large to keep, so only the base diff is available.</p>}
          {unit.row_approvable && unit.todo && <p className="hint">Click changed lines to select them, shift-click to extend, then approve the selection.</p>}
          {diff.isPending && <p className="diff-note">Loading diff...</p>}
          {diff.error && <ErrorNote message={describeError(diff.error)} />}
          {unit.image && <ImagePreview reviewId={reviewId} unit={unit} />}
          {diff.data && !(unit.image && diff.data.binary) && (
            <UnitDiffView
              diff={diff.data}
              path={unit.path}
              selectable={unit.row_approvable}
              selected={selected}
              onRowClick={onRowClick}
              onLineNumberClick={onComment ? (row, side, extend) => { onComment({ unit, row, side, mode: diff.data.mode, extend, selecting: true }) } : undefined}
              onLineSelectEnd={onCommentSelectEnd}
              highlighted={highlightRows?.(unit, diff.data)}
              widgets={renderWidgets ? (changeKeyOf) => renderWidgets(unit, diff.data, changeKeyOf) : undefined}
            />
          )}
        </div>
      )}
    </article>
  )
})
