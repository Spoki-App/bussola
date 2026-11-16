import { useMemo, useState } from 'react'

import { useAiReviewRun, useAiReviewRuns } from '../api/aiReview'
import { describeError } from '../api/client'
import { useForge, useSubmitReview } from '../api/forge'
import { useThreads } from '../api/threads'
import type { ReviewEvent, ReviewSubmitResult } from '../api/types'
import { useModalDialog } from '../hooks/useModalDialog'
import { REVIEW_EVENTS, aiReviewDraft, isOwnPullRequest, latestNewAiReview, needsSummary, type AiReviewDraft } from '../review/submitReview'
import { plural } from '../review/text'
import { ErrorNote } from './Badges'
import { Composer } from './Composer'

const OWN_PULL_REQUEST = 'You cannot approve or request changes on your own pull request.'
const SUBMIT_TITLE = 'Send your unsent comments to GitHub as one review with a summary, and comment, approve or request changes.'

interface Props {
  reviewId: number
  pendingComments: number
  summary: string
  defaultEvent?: ReviewEvent
  onSummaryChange: (summary: string) => void
  onSubmitted: (result: ReviewSubmitResult) => void
  onClose: () => void
}

export function SubmitReviewDialog({ reviewId, pendingComments, summary, defaultEvent = 'COMMENT', onSummaryChange, onSubmitted, onClose }: Props) {
  const { ref, close } = useModalDialog()
  const forge = useForge(reviewId)
  const submit = useSubmitReview(reviewId)
  const [chosen, setEvent] = useState<ReviewEvent | null>(null)
  const own = isOwnPullRequest(forge.data)
  const event = own ? 'COMMENT' : (chosen ?? defaultEvent)
  const required = needsSummary(event, pendingComments)
  const missingSummary = required && !summary.trim()

  const send = (body: string) => {
    submit.mutateAsync({ event, body }).then(
      (result) => {
        onSubmitted(result)
        close()
      },
      () => undefined,
    )
  }

  return (
    <dialog ref={ref} className="picker submit-review-dialog" aria-labelledby="submit-review-title" onClose={onClose}>
      <header className="picker-header">
        <h2 id="submit-review-title">Finish your review</h2>
      </header>
      <Composer
        reviewId={reviewId}
        placeholder="Review summary (Markdown)"
        submitLabel={submit.isPending ? 'Submitting...' : 'Submit review'}
        initial={summary}
        busy={submit.isPending}
        autoFocus
        allowEmpty={!required}
        hint={missingSummary ? (event === 'REQUEST_CHANGES' ? 'Write a summary to request changes.' : 'Write a summary or a comment first.') : undefined}
        onChange={onSummaryChange}
        onSubmit={send}
        onCancel={close}
      >
        <fieldset className="submit-review-events" aria-label="Review type">
          {(Object.entries(REVIEW_EVENTS) as [ReviewEvent, (typeof REVIEW_EVENTS)[ReviewEvent]][]).map(([option, { label, description }]) => {
            const disabled = own && option !== 'COMMENT'
            return (
              <label key={option} className={disabled ? 'disabled' : ''} title={disabled ? OWN_PULL_REQUEST : undefined}>
                <input type="radio" name="review-event" value={option} checked={event === option} disabled={disabled} onChange={() => { setEvent(option) }} />
                <span>
                  <strong>{label}</strong>
                  <span className="muted">{description}</span>
                </span>
              </label>
            )
          })}
        </fieldset>
        {own && <p className="muted">{OWN_PULL_REQUEST}</p>}
        {pendingComments > 0 && <p className="muted">{`${plural(pendingComments, 'pending comment')} will be sent with this review.`}</p>}
        {submit.error && <ErrorNote message={describeError(submit.error)} />}
      </Composer>
    </dialog>
  )
}

function useAiReviewDraft(reviewId: number, revisionId: number | undefined): AiReviewDraft | null {
  const forge = useForge(reviewId)
  const runs = useAiReviewRuns(reviewId)
  const reviewedAt = forge.data?.viewer_reviewed_at ?? null
  const run = forge.data ? latestNewAiReview(runs.data, reviewedAt) : null
  const detail = useAiReviewRun(reviewId, run?.id ?? null)
  const threads = useThreads(reviewId, revisionId)
  return useMemo(() => (detail.data && threads.data ? aiReviewDraft(detail.data, threads.data, reviewedAt) : null), [detail.data, threads.data, reviewedAt])
}

interface SubmitReviewProps {
  reviewId: number
  revisionId: number | undefined
  pendingComments: number
  onSubmitted: (result: ReviewSubmitResult) => void
}

export function SubmitReview({ reviewId, revisionId, pendingComments, onSubmitted }: SubmitReviewProps) {
  const [open, setOpen] = useState(false)
  const [summary, setSummary] = useState('')
  const [draftedRun, setDraftedRun] = useState<number | null>(null)
  const [defaultEvent, setDefaultEvent] = useState<ReviewEvent>('COMMENT')
  const draft = useAiReviewDraft(reviewId, revisionId)

  const start = () => {
    setDefaultEvent(draft?.event ?? 'COMMENT')
    if (draft && draft.runId !== draftedRun) {
      setDraftedRun(draft.runId)
      if (!summary.trim()) {
        setSummary(draft.text)
      }
    }
    setOpen(true)
  }

  return (
    <>
      <button type="button" title={SUBMIT_TITLE} onClick={start}>
        Submit review
      </button>
      {open && (
        <SubmitReviewDialog
          reviewId={reviewId}
          pendingComments={pendingComments}
          summary={summary}
          defaultEvent={defaultEvent}
          onSummaryChange={setSummary}
          onSubmitted={(result) => {
            setSummary('')
            onSubmitted(result)
          }}
          onClose={() => { setOpen(false) }}
        />
      )}
    </>
  )
}
