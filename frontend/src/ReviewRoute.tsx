import { useState, type ReactNode } from 'react'

import { describeError } from './api/client'
import { useReview } from './api/hooks'
import { useCreateThread, useThreads } from './api/threads'
import type { DiffRow, Thread, Unit, UnitDiff } from './api/types'
import { ErrorNote } from './components/Badges'
import { Composer } from './components/Composer'
import { FileCommentButton } from './components/FileCommentButton'
import { GitHubButton } from './components/GitHubButton'
import { ThreadPanel } from './components/ThreadPanel'
import { ThreadView } from './components/ThreadView'
import { ReviewPage } from './pages/ReviewPage'
import { draftEndRow, draftRequest, draftRowKeys, isInline, nextDraft, threadRow, type Draft } from './review/threadPlacement'

export function ReviewRoute({ reviewId }: { reviewId: number }) {
  const review = useReview(reviewId)
  const threads = useThreads(reviewId, review.data?.latest_revision?.id)
  const [draft, setDraft] = useState<Draft | null>(null)
  const create = useCreateThread(reviewId)
  const inline = (threads.data ?? []).filter(isInline)
  const openCount = (threads.data ?? []).filter((thread) => thread.status === 'open').length

  const renderWidgets = (unit: Unit, diff: UnitDiff, changeKeyOf: (row: DiffRow) => string | undefined) => {
    const widgets: Record<string, ReactNode[]> = {}
    const place = (row: DiffRow | undefined, node: ReactNode) => {
      const key = row ? changeKeyOf(row) : undefined
      if (key) {
        widgets[key] = [...(widgets[key] ?? []), node]
      }
    }
    for (const thread of inline.filter((candidate: Thread) => candidate.anchor?.unit_id === unit.id)) {
      place(threadRow(thread, diff), <ThreadView key={thread.id} reviewId={reviewId} thread={thread} />)
    }
    if (draft?.unitId === unit.id && draft.mode === diff.mode) {
      const request = draftRequest(draft)
      place(
        draftEndRow(draft, diff.rows),
        <div key="draft" className="thread draft">
          {request.line_count > 1 && <p className="muted draft-range">{`Commenting on ${String(request.line_count)} lines`}</p>}
          <Composer
            submitLabel="Start thread"
            autoFocus
            busy={create.isPending}
            onCancel={() => { setDraft(null) }}
            onSubmit={(body) => { create.mutate({ scope: 'unit', unit_id: unit.id, body, ...request }, { onSuccess: () => { setDraft(null) } }) }}
          />
          {create.error && <ErrorNote message={describeError(create.error)} />}
        </div>,
      )
    }
    return Object.fromEntries(Object.entries(widgets).map(([key, nodes]) => [key, <div key={key} className="widgets">{nodes}</div>]))
  }

  return (
    <ReviewPage
      reviewId={reviewId}
      extensions={{
        onComment: (target) => { setDraft(nextDraft(draft, target, target.extend)) },
        highlightRows: (unit, diff) => (draft?.unitId === unit.id && draft.mode === diff.mode ? draftRowKeys(draft, diff.rows) : undefined),
        renderWidgets,
        fileActions: (path) => <FileCommentButton reviewId={reviewId} path={path} />,
        headerActions: <GitHubButton reviewId={reviewId} />,
        sidePanel: {
          label: `conversation (${String(openCount)})`,
          content: threads.error ? <ErrorNote message={describeError(threads.error)} /> : <ThreadPanel reviewId={reviewId} threads={threads.data ?? []} />,
        },
      }}
    />
  )
}
