import { useCallback, useMemo, useState, type ReactNode } from 'react'

import { describeError } from './api/client'
import { useMoves } from './api/compare'
import { useReview } from './api/hooks'
import { useCreateThread, useThreads } from './api/threads'
import type { CodeRangeRequest, ComparisonRequest, DiffRow, Thread, Unit, UnitDiff } from './api/types'
import { ErrorNote } from './components/Badges'
import { CompareDialog } from './components/CompareDialog'
import type { CommentTarget } from './components/UnitCard'
import { Composer } from './components/Composer'
import { FileCommentButton } from './components/FileCommentButton'
import { MoveLinks } from './components/MoveLinks'
import { ThreadPanel } from './components/ThreadPanel'
import { ThreadView } from './components/ThreadView'
import { useSearch } from './navigation'
import { ReviewPage } from './pages/ReviewPage'
import { linkFocusFromSearch, resolveLinkFocus } from './review/linkFocus'
import { unitTitle } from './review/logic'
import { moveLinksByUnit } from './review/moves'
import { plural } from './review/text'
import { draftEndRow, draftRequest, draftRowKeys, finishSelection, isInline, isOpen, nextDraft, threadRow, type Draft } from './review/threadPlacement'

interface CompareStart {
  range: CodeRangeRequest
  label: string
}

export function ReviewRoute({ reviewId }: { reviewId: number }) {
  const review = useReview(reviewId)
  const revisionId = review.data?.latest_revision?.id
  const threads = useThreads(reviewId, revisionId)
  const moves = useMoves(reviewId, revisionId)
  const [draft, setDraft] = useState<Draft | null>(null)
  const [compareStart, setCompareStart] = useState<CompareStart | null>(null)
  const [comparison, setComparison] = useState<ComparisonRequest | null>(null)
  const moveLinks = useMemo(() => moveLinksByUnit(moves.data ?? []), [moves.data])
  const { mutate: createThread, isPending: creating, error: createError } = useCreateThread(reviewId)
  const threadsByUnit = useMemo(() => {
    const grouped = new Map<number, Thread[]>()
    for (const thread of (threads.data ?? []).filter(isInline)) {
      const unitId = thread.anchor?.unit_id
      if (unitId !== undefined && unitId !== null) {
        grouped.set(unitId, [...(grouped.get(unitId) ?? []), thread])
      }
    }
    return grouped
  }, [threads.data])
  const openCount = (threads.data ?? []).filter(isOpen).length
  const search = useSearch()
  const linkFocus = useMemo(() => linkFocusFromSearch(search), [search])
  const threadsSettled = threads.data !== undefined || threads.error !== null
  const link = useMemo(
    () =>
      linkFocus
        ? {
            key: search,
            ready: threadsSettled || (linkFocus.thread === null && linkFocus.comment === null),
            resolve: (units: Unit[]) => resolveLinkFocus(linkFocus, units, threads.data ?? []),
          }
        : undefined,
    [search, linkFocus, threadsSettled, threads.data],
  )

  const renderWidgets = useCallback(
    (unit: Unit, diff: UnitDiff, changeKeyOf: (row: DiffRow) => string | undefined) => {
      const widgets: Record<string, ReactNode[]> = {}
      const place = (row: DiffRow | undefined, node: ReactNode) => {
        const key = row ? changeKeyOf(row) : undefined
        if (key) {
          widgets[key] = [...(widgets[key] ?? []), node]
        }
      }
      for (const thread of threadsByUnit.get(unit.id) ?? []) {
        place(threadRow(thread, diff), <ThreadView key={thread.id} reviewId={reviewId} thread={thread} />)
      }
      if (draft?.unitId === unit.id && draft.mode === diff.mode && !draft.selecting) {
        const request = draftRequest(draft)
        const range = { unit_id: unit.id, ...request }
        const compare = () => {
          if (compareStart) {
            setComparison({ left: compareStart.range, right: range })
            setCompareStart(null)
          } else {
            setCompareStart({ range, label: `${plural(request.line_count, 'line')} of ${unitTitle(unit)}` })
          }
          setDraft(null)
        }
        place(
          draftEndRow(draft, diff.rows),
          <div key="draft" className="thread draft">
            <div className="draft-header">
              <p className="muted draft-range">{request.line_count > 1 ? `Commenting on ${String(request.line_count)} lines` : ''}</p>
              <button type="button" className="link" title={compareStart ? `Compare with ${compareStart.label}` : 'Keep these lines as the first range, then select a second range to compare with'} onClick={compare}>
                {compareStart ? 'Compare with first range' : 'Compare with...'}
              </button>
            </div>
            <Composer
              submitLabel="Start thread"
              autoFocus
              busy={creating}
              onCancel={() => { setDraft(null) }}
              onSubmit={(body) => { createThread({ scope: 'unit', unit_id: unit.id, body, ...request }, { onSuccess: () => { setDraft(null) } }) }}
            />
            {createError && <ErrorNote message={describeError(createError)} />}
          </div>,
        )
      }
      return Object.fromEntries(Object.entries(widgets).map(([key, nodes]) => [key, <div key={key} className="widgets">{nodes}</div>]))
    },
    [threadsByUnit, draft, createThread, creating, createError, reviewId, compareStart],
  )

  const onComment = useCallback((target: CommentTarget) => {
    setDraft((current) => nextDraft(current, target, target.extend))
  }, [])
  const onCommentSelectEnd = useCallback(() => {
    setDraft(finishSelection)
  }, [])
  const highlightRows = useCallback(
    (unit: Unit, diff: UnitDiff) => (draft?.unitId === unit.id && draft.mode === diff.mode ? draftRowKeys(draft, diff.rows) : undefined),
    [draft],
  )
  const unitLabels = useCallback(
    (unit: Unit) => {
      const links = moveLinks.get(unit.id)
      return links ? <MoveLinks links={links} onCompare={setComparison} /> : null
    },
    [moveLinks],
  )
  const fileActions = useCallback((path: string) => <FileCommentButton reviewId={reviewId} path={path} />, [reviewId])
  const sidePanelContent = threads.error ? <ErrorNote message={describeError(threads.error)} /> : <ThreadPanel reviewId={reviewId} threads={threads.data ?? []} />

  return (
    <>
      <ReviewPage
        reviewId={reviewId}
        extensions={{
          onComment,
          onCommentSelectEnd,
          highlightRows,
          renderWidgets,
          fileActions,
          sidePanel: { label: 'conversation', count: openCount, content: sidePanelContent },
          link,
          unitLabels,
        }}
      />
      {compareStart && (
        <div className="compare-bar" role="status">
          <span>{`First range: ${compareStart.label}. Select the second range by its line numbers and choose Compare.`}</span>
          <button type="button" className="link" onClick={() => { setCompareStart(null) }}>
            Cancel
          </button>
        </div>
      )}
      {comparison && <CompareDialog reviewId={reviewId} request={comparison} onClose={() => { setComparison(null) }} />}
    </>
  )
}
