import type { Review } from '../api/types'

export type ReviewFilter = 'open' | 'merged' | 'closed' | 'all'

export const REVIEW_FILTER_LABELS: Record<ReviewFilter, string> = { open: 'Open', merged: 'Merged', closed: 'Closed', all: 'All' }
export const DEFAULT_REVIEW_FILTER: ReviewFilter = 'open'

const STORAGE_KEY = 'rtool.reviewFilter'

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
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY)
    return isReviewFilter(stored) ? stored : DEFAULT_REVIEW_FILTER
  } catch {
    return DEFAULT_REVIEW_FILTER
  }
}

export function saveReviewFilter(filter: ReviewFilter): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, filter)
  } catch {
    return
  }
}
