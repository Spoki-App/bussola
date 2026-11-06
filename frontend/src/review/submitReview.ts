import type { ForgeOverview, ReviewEvent, ReviewSubmitResult } from '../api/types'
import { sentCount } from './sync'
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

export function needsSummary(event: ReviewEvent, pendingComments: number): boolean {
  return event === 'REQUEST_CHANGES' || (event === 'COMMENT' && pendingComments === 0)
}

export function submittedMessage(result: ReviewSubmitResult): string {
  const sent = sentCount(result.published)
  const parts = [REVIEW_EVENTS[result.event].submitted]
  if (sent > 0) {
    parts.push(`Sent ${plural(sent, 'comment')}.`)
  }
  if (result.unsent_comments > 0) {
    parts.push(`${plural(result.unsent_comments, 'comment')} not sent yet; Sync sends ${result.unsent_comments === 1 ? 'it' : 'them'} again.`)
  }
  return parts.join(' ')
}
