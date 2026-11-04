import type { Review, ReviewPullRequest } from '../api/types'

export function pullRequestTitle(pull: ReviewPullRequest): string {
  return pull.title ?? 'Pull request'
}

export function reviewDocumentTitle(review: Pick<Review, 'repo_name' | 'head_ref' | 'pull_request'>): string {
  const pull = review.pull_request
  if (!pull) {
    return `${review.repo_name} ${review.head_ref}`
  }
  return `${review.repo_name}#${String(pull.number)} ${pullRequestTitle(pull)}`
}
