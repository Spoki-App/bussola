import { useState } from 'react'

import { describeError } from '../api/client'
import type { AiReviewState } from '../hooks/useAiReview'
import { aiReviewCoverage, aiReviewProgress, aiReviewSummary } from '../review/aiReview'
import { AiActionButton } from './AiActionButton'
import { AiReviewDetails } from './AiReviewDetails'
import { ErrorNote } from './Badges'
import { Spinner } from './Spinner'

interface Props {
  reviewId: number
  repoId: number
  review: AiReviewState
}

export function AiReview({ reviewId, repoId, review }: Props) {
  const [showing, setShowing] = useState(false)
  const details = (review.status?.runs ?? 0) > 0 && (
    <>
      <button type="button" onClick={() => { setShowing(true) }}>
        Details
      </button>
      {showing && <AiReviewDetails reviewId={reviewId} onClose={() => { setShowing(false) }} />}
    </>
  )
  if (review.running) {
    return (
      <span className="summary-action">
        <span className="muted busy" role="status">
          <Spinner />
          {aiReviewProgress(review.status)}
        </span>
        <button type="button" onClick={review.cancel}>
          Cancel
        </button>
        {details}
      </span>
    )
  }
  const note = review.result ? aiReviewSummary(review.result) : aiReviewCoverage(review.status)
  const status = review.status
  return (
    <span className="summary-action">
      {note && (
        <span className="muted" role="status">
          {note}
        </span>
      )}
      {review.error && <ErrorNote message={describeError(review.error)} />}
      {(!status || status.reviewed_units < status.units) && (
        <AiActionButton
          repoId={repoId}
          label="AI review"
          title="Ask the AI provider to review each unit changed since the last AI review, the highest impact first, and add what it finds as threads"
          onRun={(target) => { review.run(target) }}
        />
      )}
      {status && status.reviewed_units > 0 && (
        <AiActionButton
          repoId={repoId}
          label="Review again"
          title="Ask the AI provider to review the whole pull request again, also the units it already reviewed, keeping the threads it added before"
          onRun={(target) => { review.run(target, true) }}
        />
      )}
      {details}
    </span>
  )
}
