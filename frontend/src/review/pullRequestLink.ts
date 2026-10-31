const PULL_REQUEST_URL = /^(?:https?:\/\/)?(?:www\.)?github\.com\/[\w.-]+\/[\w.-]+\/pull\/\d+(?:[/?#].*)?$/
const ADD_REPOSITORY_PARAM = 'add_repo'
const PULL_REQUEST_PATH = /^\/github\.com\/([\w.-]+\/[\w.-]+)\/pull\/\d+(?:\/.*)?$/

const GITHUB_PREFIX = /^(?:https?:\/\/)?(?:www\.)?github\.com\//
const COMMENT_ANCHOR = /#(?:discussion_r|r|issuecomment-)(\d+)$/

export interface PullRequestTarget {
  url: string
  pathname: string
  search: string
}

export function commentAnchors(comment: string): string[] {
  return [`#discussion_r${comment}`, `#issuecomment-${comment}`]
}

export function pullRequestTargetFromUrl(text: string): PullRequestTarget {
  const trimmed = text.trim()
  const comment = COMMENT_ANCHOR.exec(trimmed)?.[1]
  const pathname = `/github.com/${trimmed.replace(GITHUB_PREFIX, '').replace(/[?#].*$/, '')}`
  return { url: githubUrl(pathname), pathname, search: comment ? `?${new URLSearchParams({ comment }).toString()}` : '' }
}

export function isPullRequestUrl(text: string): boolean {
  return PULL_REQUEST_URL.test(text.trim())
}

export function pullRequestRepositoryFromPath(pathname: string): string | null {
  return PULL_REQUEST_PATH.exec(pathname)?.[1] ?? null
}

export function pullRequestUrlFromPath(pathname: string): string | null {
  return pullRequestRepositoryFromPath(pathname) === null ? null : githubUrl(pathname)
}

function githubUrl(pathname: string): string {
  return `https:/${pathname}`
}

export interface AddRepositoryRequest {
  repository: string
  url: string
  search: string
}

export function addRepositoryPath(then: string): string {
  return `/?${new URLSearchParams({ [ADD_REPOSITORY_PARAM]: then }).toString()}`
}

export function addRepositoryRequestFromSearch(search: string): AddRepositoryRequest | null {
  const then = new URLSearchParams(search).get(ADD_REPOSITORY_PARAM)
  if (then === null) {
    return null
  }
  const target = sameOriginUrl(then)
  const repository = target === null ? null : pullRequestRepositoryFromPath(target.pathname)
  return target === null || repository === null ? null : { repository, url: githubUrl(target.pathname), search: target.search }
}

function sameOriginUrl(path: string): URL | null {
  try {
    const url = new URL(path, window.location.origin)
    return url.origin === window.location.origin ? url : null
  } catch {
    return null
  }
}
