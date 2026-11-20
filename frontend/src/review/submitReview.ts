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

const isAfter = (time: string, reviewedAt: string | null) => reviewedAt === null || Date.parse(time) > Date.parse(reviewedAt)

export function latestNewAiReview(runs: AiReviewRun[] | undefined, reviewedAt: string | null): AiReviewRun | null {
  const run = runs?.find((candidate) => candidate.finished_at && candidate.reviewed > 0)
  return run?.finished_at && isAfter(run.finished_at, reviewedAt) ? run : null
}

export function aiReviewDraft(run: AiReviewRunDetail, threads: Thread[], reviewedAt: string | null): AiReviewDraft {
  const summaries = run.parts.map((part) => lineLinksAsText((part.summary ?? '').trim())).filter(Boolean)
  const leftOpen = threads.some((thread) => thread.created_by.ai && isOpen(thread) && isAfter(thread.created_at, reviewedAt))
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
  return parts.join(' ')
}

export type SubmitStep = 'syncing' | 'finishing' | 'done' | 'sync-failed' | 'finish-failed'

export const SUBMIT_STEPS: Record<SubmitStep, string> = {
  syncing: 'Syncing...',
  finishing: 'Synced. Marking as reviewed...',
  done: 'Synced and marked as reviewed.',
  'sync-failed': 'Sync failed, so it was not marked as reviewed: press Sync, then Mark as reviewed.',
  'finish-failed': 'Synced, but Mark as reviewed failed: press Mark as reviewed to try again.',
}
