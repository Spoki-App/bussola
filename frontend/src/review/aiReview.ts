import type { AiReviewResult, AiReviewStatus } from '../api/types'
import { plural } from './text'

export function aiReviewProgress(status: AiReviewStatus | null): string {
  if (!status?.running || status.phase === null) {
    return 'Starting the AI review...'
  }
  const count = `${String(status.done)} of ${plural(status.total, 'unit')}`
  return status.phase === 'rating' ? `Rating the impact first: ${count}...` : `AI review: ${count} reviewed...`
}

export function aiReviewSummary(result: AiReviewResult): string {
  const reviewed = `${plural(result.reviewed, 'unit')} reviewed, ${plural(result.findings, 'finding')} added as threads.`
  if (result.cancelled) {
    return `Cancelled, ${reviewed}`
  }
  if (result.reviewed === 0 && result.failed === 0) {
    return 'No unit changed since the last AI review.'
  }
  return result.failed === 0 ? reviewed : `${reviewed} ${plural(result.failed, 'unit')} could not be reviewed: ${result.error ?? 'unknown error'}`
}

export function aiReviewCoverage(status: AiReviewStatus | null): string | null {
  if (!status || status.reviewed_units === 0) {
    return null
  }
  return status.reviewed_units === status.units ? 'Every unit has an AI review.' : `${String(status.reviewed_units)} of ${plural(status.units, 'unit')} have an AI review.`
}
