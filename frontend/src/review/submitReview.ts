import type { AiReviewRun, AiReviewRunDetail, ForgeOverview, ReviewEvent, ReviewSubmitResult, Thread } from '../api/types'
import { lineLinksAsText } from '../markdown/lineLinks'
import { sentCount } from './sync'
import { isOpen } from './threadPlacement'
import { plural } from './text'

export const REVIEW_EVENTS: Record<ReviewEvent, { label: string; description: string; submitted: string }> = {
  COMMENT: { label: 'Comment', description: 'Submit general feedback without explicit approval.', submitted: 'Review submitted on GitHub.' },
  APPROVE: { label: 'Approve', description: 'Submit feedback and approve merging these changes.', submitted: 'Approved on GitHub.' },
  REQUEST_CHANGES: { label: 'Request changes', description: 'Submit feedback that must be addressed before merging.', submitted: 'Changes requested on GitHub.' },
}

export function isOwnPullRequest(forge: ForgeOverview | undefined): boolean {
  const viewer = forge?.viewer
  return Boolean(viewer) && viewer === forge?.pull_request?.author
}

export interface AiReviewDraft {
  runId: number
  text: string
  event: ReviewEvent
}

export function latestNewAiReview(runs: AiReviewRun[] | undefined, reviewedAt: string | null): AiReviewRun | null {
  const run = runs?.find((candidate) => candidate.finished_at)
  if (!run?.finished_at) {
    return null
  }
  return reviewedAt === null || Date.parse(run.finished_at) > Date.parse(reviewedAt) ? run : null
}

export function aiReviewDraft(run: AiReviewRunDetail, threads: Thread[]): AiReviewDraft {
  const open = new Set(threads.filter(isOpen).map((thread) => thread.id))
  const summaries = run.parts.map((part) => lineLinksAsText((part.summary ?? '').trim())).filter(Boolean)
  const leftOpen = run.parts.some((part) => part.findings.some((finding) => open.has(finding.thread_id)))
  return { runId: run.id, text: summaries.join('\n\n'), event: leftOpen ? 'REQUEST_CHANGES' : 'COMMENT' }
}

export function needsSummary(event: ReviewEvent, pendingComments: number): boolean {
  return event === 'REQUEST_CHANGES' || (event === 'COMMENT' && pendingComments === 0)
}

export function submittedMessage(result: ReviewSubmitResult): string {
  const sent = sentCount(result.published)
  const parts = result.published.review_url ? [REVIEW_EVENTS[result.event].submitted] : []
  if (sent > 0) {
    parts.push(`Sent ${plural(sent, 'comment')} to GitHub.`)
  }
  if (result.unsent_comments > 0) {
    parts.push(`${plural(result.unsent_comments, 'comment')} not sent yet; Sync sends ${result.unsent_comments === 1 ? 'it' : 'them'} again.`)
  }
  return parts.join(' ')
}
