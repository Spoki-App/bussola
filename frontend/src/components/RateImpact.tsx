import { describeError } from '../api/client'
import type { RateImpactState } from '../hooks/useRateImpact'
import { ratingSummary } from '../review/impact'
import { AiActionButton } from './AiActionButton'
import { ErrorNote } from './Badges'
import { Spinner } from './Spinner'

interface Props {
  repoId: number
  rating: RateImpactState
}

export function RateImpact({ repoId, rating }: Props) {
  if (rating.pending) {
    return (
      <span className="summary-action">
        <span className="muted busy" role="status">
          <Spinner />
          Rating the impact of each unit...
        </span>
        <button type="button" onClick={rating.cancel}>
          Cancel
        </button>
      </span>
    )
  }
  return (
    <span className="summary-action">
      {rating.result && (
        <span className="muted" role="status">
          {ratingSummary(rating.result)}
        </span>
      )}
      {rating.error && <ErrorNote message={describeError(rating.error)} />}
      <AiActionButton repoId={repoId} label="Rate impact" title="Ask the AI provider to rate the impact of each unit that has no current rating" onRun={rating.run} />
    </span>
  )
}
