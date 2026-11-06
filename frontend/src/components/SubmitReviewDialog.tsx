import { useState, type KeyboardEvent } from 'react'

import { describeError } from '../api/client'
import { useForge, useSubmitReview } from '../api/forge'
import type { ReviewEvent, ReviewSubmitResult } from '../api/types'
import { useModalDialog } from '../hooks/useModalDialog'
import { REVIEW_EVENTS, isOwnPullRequest, needsSummary } from '../review/submitReview'
import { plural } from '../review/text'
import { ErrorNote } from './Badges'
import { Markdown } from './Markdown'
import { Segmented } from './Segmented'

type Tab = 'write' | 'preview'

const TABS: Record<Tab, string> = { write: 'Write', preview: 'Preview' }
const OWN_PULL_REQUEST = 'You cannot approve or request changes on your own pull request.'

interface Props {
  reviewId: number
  pendingComments: number
  summary: string
  onSummaryChange: (summary: string) => void
  onSubmitted: (result: ReviewSubmitResult) => void
  onClose: () => void
}

export function SubmitReviewDialog({ reviewId, pendingComments, summary, onSummaryChange, onSubmitted, onClose }: Props) {
  const { ref, close } = useModalDialog()
  const forge = useForge(reviewId)
  const submit = useSubmitReview(reviewId)
  const [tab, setTab] = useState<Tab>('write')
  const [event, setEvent] = useState<ReviewEvent>('COMMENT')
  const own = isOwnPullRequest(forge.data)
  const missingSummary = needsSummary(event, pendingComments) && !summary.trim()

  const send = () => {
    if (missingSummary || submit.isPending) {
      return
    }
    submit.mutate(
      { event, body: summary },
      {
        onSuccess: (result) => {
          onSubmitted(result)
          close()
        },
      },
    )
  }
  const onKeyDown = (keyEvent: KeyboardEvent<HTMLTextAreaElement>) => {
    if (keyEvent.key === 'Enter' && (keyEvent.metaKey || keyEvent.ctrlKey)) {
      keyEvent.preventDefault()
      send()
    }
  }

  return (
    <dialog ref={ref} className="picker submit-review-dialog" aria-labelledby="submit-review-title" onClose={onClose}>
      <header className="picker-header">
        <h2 id="submit-review-title">Finish your review</h2>
      </header>
      <Segmented label="Summary" labels={TABS} value={tab} onChange={setTab} />
      {tab === 'write' ? (
        <textarea
          aria-label="Review summary"
          placeholder="Leave a comment (Markdown)"
          rows={6}
          value={summary}
          data-autofocus
          onChange={(changeEvent) => { onSummaryChange(changeEvent.target.value) }}
          onKeyDown={onKeyDown}
        />
      ) : (
        <div className="submit-review-preview">{summary.trim() ? <Markdown text={summary} /> : <p className="muted">Nothing to preview</p>}</div>
      )}
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
      <div className="composer-actions">
        {missingSummary && <span className="muted">{event === 'REQUEST_CHANGES' ? 'Write a summary to request changes.' : 'Write a summary or a comment first.'}</span>}
        <button type="button" onClick={close}>
          Cancel
        </button>
        <button type="button" className="primary" disabled={missingSummary || submit.isPending} onClick={send}>
          {submit.isPending ? 'Submitting...' : 'Submit review'}
        </button>
      </div>
    </dialog>
  )
}
