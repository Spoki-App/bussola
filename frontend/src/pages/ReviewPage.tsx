import { useCallback, useRef, useState, type ReactNode } from 'react'

import { describeError } from '../api/client'
import { useApprove, useFinishReview, useRefresh, useReview, useUnits } from '../api/hooks'
import type { DiffRow, ReviewDetail, Unit, UnitDiff, UnitFilter } from '../api/types'
import { ErrorNote, ProgressBar } from '../components/Badges'
import { FileTree } from '../components/FileTree'
import { ReviewTitle } from '../components/ReviewTitle'
import { UnitCard, type CommentTarget, type UnitActions } from '../components/UnitCard'
import { useKeyboardShortcuts } from '../hooks/useKeyboardShortcuts'
import { Link } from '../Link'
import { FILTER_LABELS, STATE_LABELS, STATE_ORDER, clampIndex, groupByFile, nextTodoIndex, progressPercent, shortSha } from '../review/logic'

export interface ReviewExtensions {
  onComment?: (target: CommentTarget) => void
  renderWidgets?: (unit: Unit, diff: UnitDiff, changeKeyOf: (row: DiffRow) => string | undefined) => Record<string, ReactNode>
  unitFooter?: (unit: Unit) => ReactNode
  fileActions?: (path: string) => ReactNode
  sidePanel?: { label: string; content: ReactNode }
  headerActions?: ReactNode
}

interface Props {
  reviewId: number
  extensions?: ReviewExtensions
}

const WIDE_LAYOUT_PX = 1400

function scrollToElement(id: string) {
  document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

function ReviewHeader({ review, extra }: { review: ReviewDetail; extra?: ReactNode }) {
  const [fetchRemote, setFetchRemote] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const refresh = useRefresh(review.id)
  const finish = useFinishReview(review.id)
  const revision = review.latest_revision

  const runRefresh = () => {
    refresh.mutate(fetchRemote, {
      onSuccess: (result) => {
        setMessage(result.created ? `Revision ${String(result.revision.number)} recorded.` : 'No new commits.')
      },
    })
  }

  return (
    <header className="review-header">
      <div className="review-title">
        <Link to="/" className="muted">
          {review.repo_path.split('/').at(-1)}
        </Link>
        <h1>
          <ReviewTitle review={review} />
        </h1>
        {review.pull_request?.url && (
          <p className="muted">
            <a href={review.pull_request.url} target="_blank" rel="noreferrer">
              View on GitHub
            </a>
            {review.pull_request.author && ` · by ${review.pull_request.author}`}
            {' · Refresh with fetch pulls the latest commits of the pull request'}
          </p>
        )}
        {revision && (
          <p className="muted">
            {`Revision ${String(revision.number)} · ${shortSha(revision.head_sha)} · refreshed ${new Date(revision.created_at).toLocaleString()}`}
          </p>
        )}
      </div>
      <div className="review-actions">
        <label className="checkbox">
          <input type="checkbox" checked={fetchRemote} onChange={(event) => { setFetchRemote(event.target.checked) }} />
          fetch
        </label>
        <button type="button" onClick={runRefresh} disabled={refresh.isPending} title="Refresh (r)">
          {refresh.isPending ? 'Refreshing...' : 'Refresh'}
        </button>
        <button
          type="button"
          className="primary"
          disabled={finish.isPending}
          onClick={() => {
            finish.mutate(undefined, { onSuccess: () => { setMessage('Review session saved. "Since my last review" now starts here.') } })
          }}
        >
          Finish review
        </button>
        {extra}
      </div>
      {message && <p className="notice">{message}</p>}
      {(refresh.error ?? finish.error) && <ErrorNote message={describeError(refresh.error ?? finish.error)} />}
    </header>
  )
}

export function ReviewPage({ reviewId, extensions = {} }: Props) {
  const review = useReview(reviewId)
  const [filter, setFilter] = useState<UnitFilter>('all')
  const revisionId = review.data?.latest_revision?.id
  const units = useUnits(reviewId, revisionId, filter)
  const unitList = units.data ?? []
  const groups = groupByFile(unitList)
  const [focusedIndex, setFocusedIndex] = useState(0)
  const actions = useRef(new Map<number, UnitActions>())
  const refresh = useRefresh(reviewId)
  const [panelOpen, setPanelOpen] = useState(() => window.innerWidth >= WIDE_LAYOUT_PX)

  const register = useCallback((unitId: number, unitActions: UnitActions | null) => {
    if (unitActions) {
      actions.current.set(unitId, unitActions)
    } else {
      actions.current.delete(unitId)
    }
  }, [])

  const focus = (index: number) => {
    const target = clampIndex(index, unitList.length)
    if (target < 0) {
      return
    }
    setFocusedIndex(target)
    scrollToElement(`unit-${String(unitList[target].id)}`)
  }
  const focusedUnit = unitList.at(clampIndex(focusedIndex, unitList.length))

  useKeyboardShortcuts({
    j: () => { focus(focusedIndex + 1) },
    k: () => { focus(focusedIndex - 1) },
    n: () => {
      const next = nextTodoIndex(unitList, focusedIndex)
      if (next >= 0) {
        focus(next)
      }
    },
    a: () => { if (focusedUnit) actions.current.get(focusedUnit.id)?.toggleApproval() },
    c: () => { if (focusedUnit) actions.current.get(focusedUnit.id)?.comment() },
    r: () => { refresh.mutate(false) },
  })

  if (review.isPending) {
    return <p className="page muted">Loading review...</p>
  }
  if (review.error) {
    return <ErrorNote message={describeError(review.error)} />
  }
  const data = review.data
  const percent = progressPercent(data)

  return (
    <div className="review-page">
      <ReviewHeader review={data} extra={extensions.headerActions} />
      <section className="review-summary">
        <ProgressBar percent={percent} />
        <p>
          <strong>{`${String(data.approved)} / ${String(data.total)}`}</strong> units approved
          {STATE_ORDER.filter((state) => data.counts[state] > 0).map((state) => (
            <span key={state} className={`count-chip state-${state}`}>{`${STATE_LABELS[state]}: ${String(data.counts[state])}`}</span>
          ))}
          {data.open_threads > 0 && <span className="count-chip">{`Open threads: ${String(data.open_threads)}`}</span>}
        </p>
        <div className="segmented" role="tablist" aria-label="Filter units">
          {(Object.keys(FILTER_LABELS) as UnitFilter[]).map((option) => (
            <button key={option} type="button" role="tab" aria-selected={filter === option} className={filter === option ? 'active' : ''} onClick={() => { setFilter(option) }}>
              {FILTER_LABELS[option]}
            </button>
          ))}
        </div>
        <div className="summary-row">
          <p className="shortcuts muted">j / k move, n next to review, a approve or revoke, c comment, r refresh</p>
          {extensions.sidePanel && (
            <button type="button" aria-pressed={panelOpen} onClick={() => { setPanelOpen(!panelOpen) }}>
              {panelOpen ? `Hide ${extensions.sidePanel.label}` : `Show ${extensions.sidePanel.label}`}
            </button>
          )}
        </div>
      </section>
      <div className={`review-layout${panelOpen && extensions.sidePanel ? ' with-panel' : ''}`}>
        <aside className="sidebar">
          <FileTree groups={groups} onSelect={(path) => { scrollToElement(`file-${path}`) }} />
        </aside>
        <main className="units">
          {units.error && <ErrorNote message={describeError(units.error)} />}
          {units.data && unitList.length === 0 && <p className="muted">{filter === 'all' ? 'No changes between the branches.' : 'Nothing to review here.'}</p>}
          {groups.map((group) => (
            <section key={group.path} id={`file-${group.path}`} className="file-section">
              <FileHeader reviewId={reviewId} path={group.path} oldPath={group.oldPath} complete={group.complete} actions={extensions.fileActions?.(group.path)} />
              {group.units.map((unit) => (
                <UnitCard
                  key={unit.id}
                  reviewId={reviewId}
                  unit={unit}
                  focused={focusedUnit?.id === unit.id}
                  onFocus={() => { setFocusedIndex(unitList.indexOf(unit)) }}
                  register={register}
                  onComment={extensions.onComment}
                  renderWidgets={extensions.renderWidgets}
                  footer={extensions.unitFooter?.(unit)}
                />
              ))}
            </section>
          ))}
        </main>
        {panelOpen && extensions.sidePanel && <aside className="side-panel">{extensions.sidePanel.content}</aside>}
      </div>
    </div>
  )
}

interface FileHeaderProps {
  reviewId: number
  path: string
  oldPath: string | null
  complete: boolean
  actions?: ReactNode
}

function FileHeader({ reviewId, path, oldPath, complete, actions }: FileHeaderProps) {
  const approve = useApprove(reviewId)
  return (
    <div className="file-header">
      <h2>
        {oldPath && <span className="muted">{`${oldPath} → `}</span>}
        {path}
      </h2>
      <div className="file-actions">
        {actions}
        {!complete && (
          <button type="button" disabled={approve.isPending} onClick={() => { approve.mutate({ path }) }}>
            Approve file
          </button>
        )}
      </div>
    </div>
  )
}
