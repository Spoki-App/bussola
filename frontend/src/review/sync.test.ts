import { describe, expect, it } from 'vitest'

import type { PublishOutcome, SyncResult } from '../api/types'
import { syncMessage } from './sync'

const revision = { id: 2, number: 2, head_sha: 'b', base_sha: 'a', merge_base_sha: 'a', created_at: '2026-10-28T10:00:00Z' }

function result(overrides: Partial<SyncResult> = {}): SyncResult {
  return { refresh: { revision, created: false, warning: null }, published: null, publish_error: null, unsent_comments: 0, viewed_files: [], viewed_error: null, ...overrides }
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

  it('reports files marked as viewed and those that could not be marked', () => {
    const viewed_files: SyncResult['viewed_files'] = [
      { path: 'a.py', status: 'marked', detail: '' },
      { path: 'b.py', status: 'marked', detail: '' },
      { path: 'c.py', status: 'already_viewed', detail: '' },
      { path: 'd.py', status: 'failed', detail: 'Not changed in the pull request' },
    ]

    expect(syncMessage(result({ viewed_files }))).toBe(
      'No new commits. Marked 2 approved files as viewed on GitHub. Not marked as viewed: d.py (Not changed in the pull request).',
    )
  })

  it('explains why no file was marked as viewed', () => {
    expect(syncMessage(result({ viewed_error: 'The pull request head (a) differs from the reviewed head (b).' }))).toBe(
      'No new commits. Files not marked as viewed: The pull request head (a) differs from the reviewed head (b).',
    )
  })
})
