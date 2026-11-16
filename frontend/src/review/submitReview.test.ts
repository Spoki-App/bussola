import { describe, expect, it } from 'vitest'

import type { AiReviewRun, AiReviewRunDetail, PublishOutcome, Thread } from '../api/types'
import { aiReviewDraft, latestNewAiReview, needsSummary, submittedMessage } from './submitReview'

const sent: PublishOutcome = { comment_ids: ['a'], status: 'published', detail: 'Review comment', url: null }
const failed: PublishOutcome = { comment_ids: ['b'], status: 'failed', detail: 'HTTP 422', url: null }

const run = (id: number, finishedAt: string | null, reviewed = 1): AiReviewRun => ({
  id,
  status: finishedAt ? 'completed' : 'running',
  again: false,
  provider: 'anthropic',
  provider_label: 'Anthropic API',
  model: null,
  effort: null,
  reviewed,
  findings: 0,
  failed: 0,
  error: null,
  started_at: '2026-11-12T10:00:00Z',
  finished_at: finishedAt,
})

const part = (summary: string | null): AiReviewRunDetail['parts'][number] => ({ units: [], summary, findings: [], lookups: [], error: null })

const thread = (status: Thread['status'], createdAt: string, ai = true) =>
  ({ id: createdAt, status, resolvable: true, created_at: createdAt, created_by: { id: 1, email: '', name: 'AI', ai } }) as Thread

describe('submit review', () => {
  it('picks the latest finished AI review that reviewed units when it is newer than the last submitted review', () => {
    const runs = [run(4, null), run(3, '2026-11-12T11:00:00Z', 0), run(2, '2026-11-12T10:05:00Z'), run(1, '2026-11-10T10:05:00Z')]

    expect(latestNewAiReview(runs, null)?.id).toBe(2)
    expect(latestNewAiReview(runs, '2026-11-11T00:00:00Z')?.id).toBe(2)
    expect(latestNewAiReview(runs, '2026-11-12T10:05:00Z')).toBeNull()
    expect(latestNewAiReview([run(4, null), run(3, '2026-11-12T11:00:00Z', 0)], null)).toBeNull()
    expect(latestNewAiReview(undefined, null)).toBeNull()
  })

  it('drafts the summary from the AI review and requests changes while AI comments since the last review are open', () => {
    const detail: AiReviewRunDetail = {
      ...run(2, '2026-11-12T10:05:00Z'),
      rating: null,
      links: [],
      parts: [part('Fix the total.\n\n- [refunds](#after:app.py:3) are skipped'), part(null), part('  Also see [the old line](<#before:app.py:9>).  ')],
    }
    const reviewedAt = '2026-11-11T00:00:00Z'

    expect(aiReviewDraft(detail, [thread('resolved', '2026-11-12T10:01:00Z'), thread('open', '2026-11-11T10:01:00Z')], reviewedAt)).toEqual({
      runId: 2,
      text: 'Fix the total.\n\n- refunds are skipped\n\nAlso see the old line.',
      event: 'REQUEST_CHANGES',
    })
    expect(aiReviewDraft(detail, [thread('open', '2026-11-10T10:01:00Z')], reviewedAt).event).toBe('COMMENT')
    expect(aiReviewDraft(detail, [thread('open', '2026-11-12T10:01:00Z', false)], reviewedAt).event).toBe('COMMENT')
    expect(aiReviewDraft(detail, [thread('resolved', '2026-11-12T10:01:00Z')], reviewedAt).event).toBe('COMMENT')
    expect(aiReviewDraft(detail, [thread('open', '2026-11-10T10:01:00Z')], null).event).toBe('REQUEST_CHANGES')
  })

  it('needs a summary to request changes and to comment with nothing pending', () => {
    expect(needsSummary('REQUEST_CHANGES', 3)).toBe(true)
    expect(needsSummary('COMMENT', 0)).toBe(true)
    expect(needsSummary('COMMENT', 1)).toBe(false)
    expect(needsSummary('APPROVE', 0)).toBe(false)
  })

  it('says what was submitted and what is still pending', () => {
    const message = submittedMessage({ event: 'REQUEST_CHANGES', published: { review_url: 'https://github.com/acme/widgets/pull/7#pullrequestreview-1', outcomes: [sent, sent, failed] }, unsent_comments: 1 })

    expect(message).toBe('Changes requested on GitHub. Sent 2 comments to GitHub. 1 comment not sent yet; Sync sends it again.')
  })

  it('names only the comments when no review was needed', () => {
    expect(submittedMessage({ event: 'COMMENT', published: { review_url: null, outcomes: [sent] }, unsent_comments: 0 })).toBe('Sent 1 comment to GitHub.')
  })
})
