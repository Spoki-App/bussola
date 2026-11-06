import type { ForgeOverview, ReviewEvent, ReviewSubmitResult } from '../api/types'
import { plural } from './text'

export const REVIEW_EVENTS: Record<ReviewEvent, { label: string; description: string }> = {
  COMMENT: { label: 'Comment', description: 'Submit general feedback without explicit approval.' },
  APPROVE: { label: 'Approve', description: 'Submit feedback and approve merging these changes.' },
  REQUEST_CHANGES: { label: 'Request changes', description: 'Submit feedback that must be addressed before merging.' },
}

const SUBMITTED: Record<ReviewEvent, string> = {
  COMMENT: 'Review submitted on GitHub.',
  APPROVE: 'Approved on GitHub.',
  REQUEST_CHANGES: 'Changes requested on GitHub.',
}

export function isOwnPullRequest(forge: ForgeOverview | undefined): boolean {
  const viewer = forge?.viewer
  return Boolean(viewer) && viewer === forge?.pull_request?.author
}

export function needsSummary(event: ReviewEvent, pendingComments: number): boolean {
  return event === 'REQUEST_CHANGES' || (event === 'COMMENT' && pendingComments === 0)
}

export function submittedMessage(result: ReviewSubmitResult): string {
  const sent = result.published.outcomes.filter((outcome) => outcome.status === 'published' || outcome.status === 'updated').length
  const parts = [SUBMITTED[result.event]]
  if (sent > 0) {
    parts.push(`Sent ${plural(sent, 'comment')}.`)
  }
  if (result.unsent_comments > 0) {
    parts.push(`${plural(result.unsent_comments, 'comment')} not sent yet; Sync sends ${result.unsent_comments === 1 ? 'it' : 'them'} again.`)
  }
  return parts.join(' ')
}
