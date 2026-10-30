import { afterEach, describe, expect, it } from 'vitest'

import type { Review } from '../api/types'
import { DEFAULT_REVIEW_FILTER, loadReviewFilter, matchesReviewFilter, saveReviewFilter } from './reviewFilter'

function review(state: string | null, linked = true): Review {
  return {
    id: 1,
    repo_id: 1,
    repo_path: '/repo',
    head_ref: 'feature',
    base_ref: 'main',
    latest_revision: null,
    counts: { approved: 0, approved_moved: 0, changed: 0, partial: 0, removed: 0, new: 0 },
    total: 0,
    approved: 0,
    open_threads: 0,
    total_threads: 0,
    last_session_at: null,
    pull_request: linked ? { number: 7, title: 'Sum', url: null, author: null, state, description: null } : null,
    pull_request_review: linked,
  }
}

describe('review filter', () => {
  afterEach(() => {
    window.localStorage.clear()
  })

  it('shows open pull requests and branch reviews by default', () => {
    const reviews = [review('OPEN'), review(null, false), review('MERGED'), review('CLOSED')]

    expect(reviews.map((item) => matchesReviewFilter(item, DEFAULT_REVIEW_FILTER))).toEqual([true, true, false, false])
    expect(reviews.map((item) => matchesReviewFilter(item, 'merged'))).toEqual([false, false, true, false])
    expect(reviews.map((item) => matchesReviewFilter(item, 'all'))).toEqual([true, true, true, true])
  })

  it('remembers the chosen filter', () => {
    expect(loadReviewFilter()).toBe('open')
    saveReviewFilter('merged')
    expect(loadReviewFilter()).toBe('merged')
    window.localStorage.setItem('bussola.reviewFilter', 'bogus')
    expect(loadReviewFilter()).toBe('open')
  })
})
