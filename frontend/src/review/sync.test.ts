import { describe, expect, it } from 'vitest'

import type { PublishOutcome, SyncResult } from '../api/types'
import { syncMessage } from './sync'

const revision = { id: 2, number: 2, head_sha: 'b', base_sha: 'a', merge_base_sha: 'a', created_at: '2026-10-28T10:00:00Z' }

function result(overrides: Partial<SyncResult> = {}): SyncResult {
  return { refresh: { revision, created: false, warning: null }, published: null, publish_error: null, unsent_comments: 0, ...overrides }
}

function outcome(status: PublishOutcome['status']): PublishOutcome {
  return { comment_ids: ['c'], status, detail: 'Review comment', url: null }
}

describe('syncMessage', () => {
  it('reports new commits and sent comments', () => {
    const published = { review_url: 'https://github.com/acme/widgets/pull/7#r1', outcomes: [outcome('published'), outcome('updated'), outcome('failed')] }

    expect(syncMessage(result({ refresh: { revision, created: true, warning: null }, published }))).toBe(
      'New commits found: revision 2 recorded. Sent 2 comments to GitHub.',
    )
  })

  it('explains why comments were not sent', () => {
    expect(syncMessage(result({ publish_error: 'Push the branch first.' }))).toBe('No new commits. Comments not sent: Push the branch first.')
  })
})
