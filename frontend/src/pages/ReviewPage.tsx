import { useCallback, useMemo, useRef, useState, type ReactNode } from 'react'

import { describeError } from '../api/client'
import { useSync } from '../api/forge'
import { useApprove, useFinishReview, useReview, useUnits } from '../api/hooks'
import type { DiffRow, ReviewDetail, SyncResult, Unit, UnitDiff, UnitFilter } from '../api/types'
import { ErrorNote, ProgressBar } from '../components/Badges'
import { ExternalLink } from '../components/ExternalLink'
import { FileTree } from '../components/FileTree'
import { GitHubSyncStatus } from '../components/GitHubSyncStatus'
import { LinkPullRequest } from '../components/LinkPullRequest'
import { PullRequestDescription } from '../components/PullRequestDescription'
import { ReviewTitle } from '../components/ReviewTitle'
import { SyncSummary } from '../components/SyncSummary'
import { UnitCard, type CommentTarget, type UnitActions } from '../components/UnitCard'
import { UnitTree } from '../components/UnitTree'
import { useKeyboardShortcuts } from '../hooks/useKeyboardShortcuts'
import { Link } from '../Link'
import { buildFileTree, filesInOrder } from '../review/fileTree'
import { buildUnitTree } from '../review/unitTree'
import { readStored, writeStored } from '../settings/storage'
import { FILTER_LABELS, STATE_LABELS, STATE_ORDER, clampIndex, groupByFile, nextTodoIndex, progressPercent, shortSha } from '../review/logic'
import { Segmented } from '../components/Segmented'

export interface ReviewExtensions {
  onComment?: (target: CommentTarget) => void
  onCommentSelectEnd?: () => void
  renderWidgets?: (unit: Unit, diff: UnitDiff, changeKeyOf: (row: DiffRow) => string | undefined) => Record<string, ReactNode>
  highlightRows?: (unit: Unit, diff: UnitDiff) => ReadonlySet<string> | undefined
  fileActions?: (path: string) => ReactNode
  sidePanel?: { label: string; content: ReactNode }
}

interface Props {
  reviewId: number
  extensions?: ReviewExtensions
}

const WIDE_LAYOUT_PX = 1400
const FILES_HIDDEN_KEY = 'rtool.filesHidden'

function scrollToElement(id: string) {
  document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

const SYNC_TITLE =
  'Fetch the branch from its remote and record any new commits as a new revision. If the review is linked to a GitHub pull request, also bring in its comments and send your unsent comments as one review.'
const PULL_SYNC_TITLE = 'Download the latest commits and comments of the pull request from GitHub, record any new commits as a new revision, then send your unsent comments as one review.'
const MARK_TITLE = 'Remember this point. The "Since my last review" filter will then show only what changes after now. Nothing is approved or closed.'

function syncLabel(review: ReviewDetail, pending: boolean): string {
  if (pending) {
    return 'Syncing...'
  }
  return review.pull_request && review.unsent_comments > 0 ? `Sync \u00b7 ${String(review.unsent_comments)} to send` : 'Sync'
}

function ReviewHeader({ review }: { review: ReviewDetail }) {
  const isPullRequest = review.pull_request !== null
  const [message, setMessage] = useState<string | null>(null)
  const [synced, setSynced] = useState<SyncResult | null>(null)
  const sync = useSync(review.id)
  const finish = useFinishReview(review.id)
  const revision = review.latest_revision

  const runSync = () => {
    setMessage(null)
    sync.mutate(undefined, { onSuccess: setSynced })
  }
  useKeyboardShortcuts({ r: runSync })
  const needsLink = synced !== null && !isPullRequest && synced.unsent_comments > 0

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
            <ExternalLink href={review.pull_request.url}>
              View on GitHub
            </ExternalLink>
            {review.pull_request.author && ` \u00b7 by ${review.pull_request.author}`}
          </p>
        )}
        {isPullRequest && <GitHubSyncStatus reviewId={review.id} headSha={revision?.head_sha} />}
        {revision && (
          <p className="muted">
            {`Revision ${String(revision.number)} \u00b7 ${shortSha(revision.head_sha)} \u00b7 checked ${new Date(revision.created_at).toLocaleString()}`}
            {` \u00b7 ${review.last_session_at ? `marked as reviewed ${new Date(review.last_session_at).toLocaleString()}` : 'not marked as reviewed yet'}`}
          </p>
        )}
      </div>
      <div className="review-actions">
        <button type="button" onClick={runSync} disabled={sync.isPending} title={`${review.pull_request_review ? PULL_SYNC_TITLE : SYNC_TITLE} Shortcut: r`}>
          {syncLabel(review, sync.isPending)}
        </button>
        <button
          type="button"
          className="primary"
          title={MARK_TITLE}
          disabled={finish.isPending}
          onClick={() => {
            finish.mutate(undefined, {
              onSuccess: () => {
                setSynced(null)
                setMessage('Marked as reviewed. "Since my last review" now shows only what changes after this point.')
              },
            })
          }}
        >
          Mark as reviewed
        </button>
      </div>
      {message && <p className="notice">{message}</p>}
      {synced && <SyncSummary result={synced} />}
      {needsLink && <LinkPullRequest reviewId={review.id} unsent={synced.unsent_comments} onLinked={runSync} />}
      {(sync.error ?? finish.error) && <ErrorNote message={describeError(sync.error ?? finish.error)} />}
    </header>
  )
}

export function ReviewPage({ reviewId, extensions = {} }: Props) {
  const review = useReview(reviewId)
  const [filter, setFilter] = useState<UnitFilter>('all')
  const revisionId = review.data?.latest_revision?.id
  const units = useUnits(reviewId, revisionId, filter)
  const fileTree = useMemo(() => buildFileTree(groupByFile(units.data ?? [])), [units.data])
  const groups = useMemo(() => filesInOrder(fileTree).map((group) => ({ ...group, tree: buildUnitTree(group.units) })), [fileTree])
  const unitList = useMemo(() => groups.flatMap((group) => group.units), [groups])
  const [focusedIndex, setFocusedIndex] = useState(0)
  const actions = useRef(new Map<number, UnitActions>())
  const [panelOpen, setPanelOpen] = useState(() => window.innerWidth >= WIDE_LAYOUT_PX)
  const [filesHidden, setFilesHidden] = useState(() => readStored(FILES_HIDDEN_KEY) === 'true')
  const toggleFiles = () => {
    setFilesHidden(!filesHidden)
    writeStored(FILES_HIDDEN_KEY, String(!filesHidden))
  }

  const focusUnit = useCallback(
    (unitId: number) => {
      setFocusedIndex(unitList.findIndex((unit) => unit.id === unitId))
    },
    [unitList],
  )

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
      <ReviewHeader review={data} />
      {data.pull_request && <PullRequestDescription pull={data.pull_request} />}
      <section className="review-summary">
        <ProgressBar percent={percent} />
        <p>
          <strong>{`${String(data.approved)} / ${String(data.total)}`}</strong> units approved
          {STATE_ORDER.filter((state) => data.counts[state] > 0).map((state) => (
            <span key={state} className={`count-chip state-${state}`}>{`${STATE_LABELS[state]}: ${String(data.counts[state])}`}</span>
          ))}
          {data.open_threads > 0 && <span className="count-chip">{`Open threads: ${String(data.open_threads)}`}</span>}
        </p>
        <Segmented label="Filter units" labels={FILTER_LABELS} value={filter} onChange={setFilter} />
        <div className="summary-row">
          <p className="shortcuts muted">j / k move, n next to review, a approve or revoke, c comment, r sync. Click a line number to comment; drag over line numbers or shift-click another to comment on several lines.</p>
          {extensions.sidePanel && (
            <button type="button" aria-pressed={panelOpen} onClick={() => { setPanelOpen(!panelOpen) }}>
              {panelOpen ? `Hide ${extensions.sidePanel.label}` : `Show ${extensions.sidePanel.label}`}
            </button>
          )}
        </div>
      </section>
      <div className={`review-layout${panelOpen && extensions.sidePanel ? ' with-panel' : ''}${filesHidden ? ' files-hidden' : ''}`}>
        <aside className="sidebar" aria-label="Files">
          <button type="button" className="sidebar-toggle" aria-expanded={!filesHidden} aria-controls={filesHidden ? undefined : 'file-tree'} title={filesHidden ? 'Show files' : 'Hide files'} onClick={toggleFiles}>
            <SidebarIcon />
            {!filesHidden && <span>Files</span>}
          </button>
          {!filesHidden && (
            <div id="file-tree">
              <FileTree nodes={fileTree} activePath={focusedUnit?.path} onSelect={(path) => { scrollToElement(`file-${path}`) }} />
            </div>
          )}
        </aside>
        <main className="units">
          {units.error && <ErrorNote message={describeError(units.error)} />}
          {units.data && unitList.length === 0 && <p className="muted">{filter === 'all' ? 'No changes between the branches.' : 'Nothing to review here.'}</p>}
          {groups.map((group) => (
            <section key={group.path} id={`file-${group.path}`} className="file-section">
              <FileHeader reviewId={reviewId} path={group.path} oldPath={group.oldPath} complete={group.complete} actions={extensions.fileActions?.(group.path)} />
              <UnitTree
                nodes={group.tree}
                renderUnit={(unit, nested) => (
                  <UnitCard
                    key={unit.id}
                    reviewId={reviewId}
                    unit={unit}
                    nested={nested}
                    focused={focusedUnit?.id === unit.id}
                    onFocus={focusUnit}
                    register={register}
                    onComment={extensions.onComment}
                    onCommentSelectEnd={extensions.onCommentSelectEnd}
                    renderWidgets={extensions.renderWidgets}
                    highlightRows={extensions.highlightRows}
                  />
                )}
              />
            </section>
          ))}
        </main>
        {panelOpen && extensions.sidePanel && <aside className="side-panel">{extensions.sidePanel.content}</aside>}
      </div>
    </div>
  )
}

function SidebarIcon() {
  return (
    <svg className="tree-icon" viewBox="0 0 16 16" aria-hidden="true">
      <rect x="1.5" y="2.5" width="13" height="11" rx="1.5" />
      <path d="M6 2.5v11" />
    </svg>
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
