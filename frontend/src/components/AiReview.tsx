import { describeError } from '../api/client'
import type { AiReviewState } from '../hooks/useAiReview'
import { aiReviewCoverage, aiReviewProgress, aiReviewSummary } from '../review/aiReview'
import { AiActionButton } from './AiActionButton'
import { ErrorNote } from './Badges'

interface Props {
  repoId: number
  review: AiReviewState
}

export function AiReview({ repoId, review }: Props) {
  if (review.running) {
    return (
      <>
        <span className="muted" role="status">
          {aiReviewProgress(review.status)}
        </span>
        {review.cancellable && (
          <button type="button" onClick={review.cancel}>
            Cancel
          </button>
        )}
      </>
    )
  }
  const note = review.result ? aiReviewSummary(review.result) : aiReviewCoverage(review.status)
  return (
    <>
      {note && (
        <span className="muted" role="status">
          {note}
        </span>
      )}
      {review.error && <ErrorNote message={describeError(review.error)} />}
      <AiActionButton
        repoId={repoId}
        label="AI review"
        title="Ask the AI provider to review each unit changed since the last AI review, the highest impact first, and add what it finds as threads"
        onRun={review.run}
      />
    </>
  )
}
