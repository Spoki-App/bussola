import { useCallback, useMemo, useState, type ReactNode } from 'react'

import { describeError } from './api/client'
import { useReview } from './api/hooks'
import { useCreateThread, useThreads } from './api/threads'
import type { DiffRow, Thread, Unit, UnitDiff } from './api/types'
import { ErrorNote } from './components/Badges'
import type { CommentTarget } from './components/UnitCard'
import { Composer } from './components/Composer'
import { FileCommentButton } from './components/FileCommentButton'
import { ThreadPanel } from './components/ThreadPanel'
import { ThreadView } from './components/ThreadView'
import { ReviewPage } from './pages/ReviewPage'
import { draftEndRow, draftRequest, draftRowKeys, finishSelection, isInline, isOpen, nextDraft, threadRow, type Draft } from './review/threadPlacement'

export function ReviewRoute({ reviewId }: { reviewId: number }) {
  const review = useReview(reviewId)
  const threads = useThreads(reviewId, review.data?.latest_revision?.id)
  const [draft, setDraft] = useState<Draft | null>(null)
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
        place(
          draftEndRow(draft, diff.rows),
          <div key="draft" className="thread draft">
            {request.line_count > 1 && <p className="muted draft-range">{`Commenting on ${String(request.line_count)} lines`}</p>}
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
    [threadsByUnit, draft, createThread, creating, createError, reviewId],
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
  const fileActions = useCallback((path: string) => <FileCommentButton reviewId={reviewId} path={path} />, [reviewId])
  const sidePanelContent = threads.error ? <ErrorNote message={describeError(threads.error)} /> : <ThreadPanel reviewId={reviewId} threads={threads.data ?? []} />

  return (
    <ReviewPage
      reviewId={reviewId}
      extensions={{
        onComment,
        onCommentSelectEnd,
        highlightRows,
        renderWidgets,
        fileActions,
        sidePanel: { label: `conversation (${String(openCount)})`, content: sidePanelContent },
      }}
    />
  )
}
