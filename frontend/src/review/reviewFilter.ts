import type { Review } from '../api/types'
import { readStored, writeStored } from '../settings/storage'

export type ReviewFilter = 'open' | 'merged' | 'closed' | 'all'

export const REVIEW_FILTER_LABELS: Record<ReviewFilter, string> = { open: 'Open', merged: 'Merged', closed: 'Closed', all: 'All' }
export const DEFAULT_REVIEW_FILTER: ReviewFilter = 'open'

const STORAGE_KEY = 'bussola.reviewFilter'

function isReviewFilter(value: unknown): value is ReviewFilter {
  return typeof value === 'string' && value in REVIEW_FILTER_LABELS
}

export function reviewStatus(review: Review): Exclude<ReviewFilter, 'all'> {
  const state = review.pull_request?.state
  if (state === 'MERGED') {
    return 'merged'
  }
  return state === 'CLOSED' ? 'closed' : 'open'
}

export function matchesReviewFilter(review: Review, filter: ReviewFilter): boolean {
  return filter === 'all' || reviewStatus(review) === filter
}

export function loadReviewFilter(): ReviewFilter {
  const stored = readStored(STORAGE_KEY)
  return isReviewFilter(stored) ? stored : DEFAULT_REVIEW_FILTER
}

export function saveReviewFilter(filter: ReviewFilter): void {
  writeStored(STORAGE_KEY, filter)
}
