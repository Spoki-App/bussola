import type { Review } from '../api/types'

export function plural(count: number, word: string): string {
  return `${String(count)} ${word}${count === 1 ? '' : 's'}`
}

export function matchesWords(haystack: string, query: string): boolean {
  const text = haystack.toLowerCase()
  return query.toLowerCase().split(/\s+/).filter(Boolean).every((word) => text.includes(word))
}

export function projectName(repoPath: string): string {
  return repoPath.split(/[\\/]/).filter(Boolean).at(-1) ?? repoPath
}

export function reviewDocumentTitle(review: Pick<Review, 'repo_path' | 'head_ref' | 'pull_request'>): string {
  const project = projectName(review.repo_path)
  const pull = review.pull_request
  if (!pull) {
    return `${project} ${review.head_ref}`
  }
  return `${project}#${String(pull.number)} ${pull.title ?? 'Pull request'}`
}
