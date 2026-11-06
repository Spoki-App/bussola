import { describe, expect, it } from 'vitest'

import type { PublishOutcome } from '../api/types'
import { needsSummary, submittedMessage } from './submitReview'

const sent: PublishOutcome = { comment_ids: ['a'], status: 'published', detail: 'Review comment', url: null }
const failed: PublishOutcome = { comment_ids: ['b'], status: 'failed', detail: 'HTTP 422', url: null }

describe('submit review', () => {
  it('needs a summary to request changes and to comment with nothing pending', () => {
    expect(needsSummary('REQUEST_CHANGES', 3)).toBe(true)
    expect(needsSummary('COMMENT', 0)).toBe(true)
    expect(needsSummary('COMMENT', 1)).toBe(false)
    expect(needsSummary('APPROVE', 0)).toBe(false)
  })

  it('says what was submitted and what is still pending', () => {
    const message = submittedMessage({ event: 'REQUEST_CHANGES', published: { review_url: null, outcomes: [sent, sent, failed] }, unsent_comments: 1 })

    expect(message).toBe('Changes requested on GitHub. Sent 2 comments. 1 comment not sent yet; Sync sends it again.')
  })
})
