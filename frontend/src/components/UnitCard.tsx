import { memo, useContext, useEffect, useState, type ReactNode } from 'react'

import { describeError } from '../api/client'
import { useApprove, useRevoke, useRevokeSelections, useUnitDiff } from '../api/hooks'
import type { DiffMode, DiffRow, Unit, UnitDiff } from '../api/types'
import type { NavigationRequest } from '../api/navigation'
import type { NavigationClick, ScreenPoint, UnitTarget } from '../review/codeNavigation'
import { TARGET_ROW_SELECTOR, unitElementId, useLinkedScroll } from '../review/linkFocus'
import { unitTitle } from '../review/logic'
import { ReviewLinkContext } from '../review/reviewLink'
import { useAiDescription } from '../hooks/useAiDescription'
import { approvedSelections, rowKey, selectRange, selectionRanges } from '../review/selection'
import { AiActionButton } from './AiActionButton'
import { AiDescription } from './AiDescription'
import { ErrorNote, ImpactBadge, KindBadge, StateBadge } from './Badges'
import { CopyLinkButton } from './CopyLinkButton'
import { DiffWrapButton } from './DiffWrapToggle'
import { ImagePreview } from './ImagePreview'
import { QualifiedName } from './QualifiedName'
import { UnitDiffView, type GutterSide, type TargetLine } from './UnitDiffView'

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
  repoId: number
  unit: Unit
  focused: boolean
  onFocus: (unitId: number) => void
  register: (unitId: number, actions: UnitActions | null) => void
  onComment?: (target: CommentTarget) => void
  onCommentSelectEnd?: () => void
  renderWidgets?: (unit: Unit, diff: UnitDiff, changeKeyOf: (row: DiffRow) => string | undefined) => Record<string, ReactNode>
  highlightRows?: (unit: Unit, diff: UnitDiff) => ReadonlySet<string> | undefined
  onNavigate?: (click: NavigationClick) => void
  canNavigate?: (request: NavigationRequest) => Promise<boolean>
  navigationTarget?: UnitTarget
  linkedLine?: number
}

const APPROVE_LABELS = { approve: 'Approve', approve_under_name: 'Approve under this name', confirm_removal: 'Confirm removal' } as const

const MODE_LABELS: Record<DiffMode, string> = { approved: 'Approved → current', base: 'Base → head' }

function targetLine(target: UnitTarget | undefined, linkedLine: number | undefined): TargetLine | undefined {
  if (target) {
    return { side: target.side === 'base' ? 'old' : 'new', line: target.line }
  }
  return linkedLine === undefined ? undefined : { side: 'new', line: linkedLine }
}

export const UnitCard = memo(function UnitCard({ reviewId, repoId, unit, focused, onFocus, register, onComment, onCommentSelectEnd, renderWidgets, highlightRows, onNavigate, canNavigate, navigationTarget, linkedLine }: Props) {
  const todo = unit.todo
  const [expanded, setExpanded] = useState(todo)
  const [wasTodo, setWasTodo] = useState(todo)
  if (todo !== wasTodo) {
    setWasTodo(todo)
    setExpanded(todo)
  }
  const [mode, setMode] = useState<DiffMode | undefined>(undefined)
  const [seenTarget, setSeenTarget] = useState<UnitTarget | undefined>(undefined)
  if (navigationTarget !== seenTarget) {
    setSeenTarget(navigationTarget)
    if (navigationTarget) {
      setExpanded(true)
    }
    if (navigationTarget?.side === 'base') {
      setMode('base')
    }
  }
  const [selected, setSelected] = useState<ReadonlySet<string>>(new Set())
  const [anchor, setAnchor] = useState<string | null>(null)
  const diff = useUnitDiff(reviewId, unit, mode, expanded)
  const { ref: linkedRef, linked } = useLinkedScroll<HTMLElement>(unitElementId(unit.id), unit.id, expanded && !diff.isPending)
  if (linked && !expanded) {
    setExpanded(true)
  }
  const makeLink = useContext(ReviewLinkContext)
  const approve = useApprove(reviewId)
  const revoke = useRevoke(reviewId)
  const revokeSelections = useRevokeSelections(reviewId)
  const ai = useAiDescription(reviewId, unit)
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

  const diffLoaded = diff.data !== undefined
  useEffect(() => {
    if (!navigationTarget) {
      return
    }
    onFocus(unit.id)
    const element = linkedRef.current?.querySelector(TARGET_ROW_SELECTOR) ?? linkedRef.current
    element?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }, [navigationTarget, diffLoaded, onFocus, unit.id, linkedRef])

  const requestFrom = (row: DiffRow, side: GutterSide, column: number): NavigationRequest | null => {
    const base = side === 'old'
    const line = base ? row.old_line : row.new_line
    if (line === null || (base && diff.data?.mode !== 'base')) {
      return null
    }
    return { path: base ? (unit.old_path ?? unit.path) : unit.path, side: base ? 'base' : 'head', line, column }
  }

  const navigateFrom = (row: DiffRow, side: GutterSide, column: number, point: ScreenPoint) => {
    const request = requestFrom(row, side, column)
    if (onNavigate && request) {
      onNavigate({ ...request, point })
    }
  }

  const canNavigateFrom = (row: DiffRow, side: GutterSide, column: number) => {
    const request = requestFrom(row, side, column)
    return canNavigate && request ? canNavigate(request) : Promise.resolve(false)
  }

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
    <article id={unitElementId(unit.id)} ref={linkedRef} className={`unit-card state-${unit.state}${focused ? ' focused' : ''}`} onClick={() => { onFocus(unit.id) }}>
      <header className="unit-header">
        <button type="button" className="disclosure" aria-expanded={expanded} aria-label={expanded ? 'Collapse unit' : 'Expand unit'} onClick={() => { setExpanded(!expanded) }}>
          {expanded ? '▾' : '▸'}
        </button>
        <KindBadge kind={unit.kind} />
        <QualifiedName module={unit.qualified_name ? unit.module : null} name={unitTitle(unit)} />
        {makeLink && unit.head_start !== null && <CopyLinkButton link={makeLink({ path: unit.path, line: unit.head_start })} label="Copy link to this unit" className="icon" />}
        <StateBadge state={unit.state} />
        {ai.rating && <ImpactBadge rating={ai.rating} />}
        {unit.change_type !== 'modified' && <span className="label">{unit.change_type}</span>}
        {unit.base_changed && <span className="label" title="The base changed since you approved this unit">base changed</span>}
        {unit.rows_total > 0 && <span className="label">{`${String(unit.rows_approved)}/${String(unit.rows_total)} lines approved`}</span>}
        {unit.open_threads > 0 && <span className={`label threads${unit.todo ? '' : ' warn'}`}>{`${String(unit.open_threads)} open thread${unit.open_threads > 1 ? 's' : ''}`}</span>}
        <span className="spacer" />
        {!unit.binary && ai.loaded && !ai.description && !ai.pending && (
          <AiActionButton
            repoId={repoId}
            label="Describe"
            title="Ask the AI provider what this unit does and what the change does to it"
            onRun={(target) => {
              setExpanded(true)
              ai.run(target, false)
            }}
          />
        )}
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
      {!expanded && (ai.pending || ai.error) && <AiDescription repoId={repoId} ai={ai} />}
      {expanded && (
        <div className="unit-body">
          <AiDescription repoId={repoId} ai={ai} />
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
              onNavigate={onNavigate ? navigateFrom : undefined}
              canNavigate={canNavigate ? canNavigateFrom : undefined}
              target={targetLine(navigationTarget, linkedLine)}
              widgets={renderWidgets ? (changeKeyOf) => renderWidgets(unit, diff.data, changeKeyOf) : undefined}
            />
          )}
        </div>
      )}
      {expanded && diff.data && !diff.data.binary && (
        <div className="unit-tools">
          <DiffWrapButton />
        </div>
      )}
    </article>
  )
})
