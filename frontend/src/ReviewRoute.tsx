import { useState, type ReactNode } from 'react'

import { describeError } from './api/client'
import { useReview } from './api/hooks'
import { useCreateThread, useThreads } from './api/threads'
import type { DiffRow, Thread, Unit, UnitDiff } from './api/types'
import { ErrorNote } from './components/Badges'
import { Composer } from './components/Composer'
import { FileCommentButton } from './components/FileCommentButton'
import { ThreadPanel } from './components/ThreadPanel'
import { ThreadView } from './components/ThreadView'
import type { CommentTarget } from './components/UnitCard'
import { ReviewPage } from './pages/ReviewPage'
import { draftAnchor, isInline, threadRow } from './review/threadPlacement'

export function ReviewRoute({ reviewId }: { reviewId: number }) {
  const review = useReview(reviewId)
  const threads = useThreads(reviewId, review.data?.latest_revision?.id)
  const [draft, setDraft] = useState<CommentTarget | null>(null)
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
    const anchor = draft?.unit.id === unit.id ? draftAnchor(draft) : null
    if (draft && anchor) {
      place(
        draft.row,
        <div key="draft" className="thread draft">
          <Composer
            submitLabel="Start thread"
            autoFocus
            busy={create.isPending}
            onCancel={() => { setDraft(null) }}
            onSubmit={(body) => { create.mutate({ scope: 'unit', unit_id: unit.id, body, ...anchor }, { onSuccess: () => { setDraft(null) } }) }}
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
        onComment: (target) => { setDraft(draftAnchor(target) ? target : null) },
        renderWidgets,
        fileActions: (path) => <FileCommentButton reviewId={reviewId} path={path} />,
        sidePanel: {
          label: `conversation (${String(openCount)})`,
          content: threads.error ? <ErrorNote message={describeError(threads.error)} /> : <ThreadPanel reviewId={reviewId} threads={threads.data ?? []} />,
        },
      }}
    />
  )
}
