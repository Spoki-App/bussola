import { describe, expect, it } from 'vitest'

import type { AiReviewRun, AiReviewRunDetail, PublishOutcome, Thread } from '../api/types'
import { aiReviewDraft, latestNewAiReview, needsSummary, submittedMessage } from './submitReview'

const sent: PublishOutcome = { comment_ids: ['a'], status: 'published', detail: 'Review comment', url: null }
const failed: PublishOutcome = { comment_ids: ['b'], status: 'failed', detail: 'HTTP 422', url: null }

const run = (id: number, finishedAt: string | null): AiReviewRun => ({
  id,
  status: finishedAt ? 'completed' : 'running',
  again: false,
  provider: 'anthropic',
  provider_label: 'Anthropic API',
  model: null,
  reviewed: 1,
  findings: 0,
  failed: 0,
  error: null,
  started_at: '2026-11-12T10:00:00Z',
  finished_at: finishedAt,
})

const part = (summary: string | null, threadIds: string[]): AiReviewRunDetail['parts'][number] => ({
  units: [],
  summary,
  findings: threadIds.map((thread_id) => ({ thread_id, place: 'app.py:1', body: 'Finding' })),
  lookups: [],
  error: null,
})

const thread = (id: string, status: Thread['status']) => ({ id, status }) as Thread

describe('submit review', () => {
  it('picks the latest finished AI review when it is newer than the last submitted review', () => {
    const runs = [run(3, null), run(2, '2026-11-12T10:05:00Z'), run(1, '2026-11-10T10:05:00Z')]

    expect(latestNewAiReview(runs, null)?.id).toBe(2)
    expect(latestNewAiReview(runs, '2026-11-11T00:00:00Z')?.id).toBe(2)
    expect(latestNewAiReview(runs, '2026-11-12T10:05:00Z')).toBeNull()
    expect(latestNewAiReview([run(3, null)], null)).toBeNull()
    expect(latestNewAiReview(undefined, null)).toBeNull()
  })

  it('drafts the summary from the AI review and requests changes while its comments are open', () => {
    const detail: AiReviewRunDetail = {
      ...run(2, '2026-11-12T10:05:00Z'),
      rating: null,
      links: [],
      parts: [part('Fix the total.\n\n- [refunds](#after:app.py:3) are skipped', ['a']), part(null, []), part('  Also see [the old line](<#before:app.py:9>).  ', ['b'])],
    }

    expect(aiReviewDraft(detail, [thread('a', 'resolved'), thread('b', 'open')])).toEqual({
      runId: 2,
      text: 'Fix the total.\n\n- refunds are skipped\n\nAlso see the old line.',
      event: 'REQUEST_CHANGES',
    })
    expect(aiReviewDraft(detail, [thread('a', 'resolved'), thread('b', 'resolved')]).event).toBe('COMMENT')
    expect(aiReviewDraft(detail, []).event).toBe('COMMENT')
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
