const PULL_REQUEST_URL = /^(?:https?:\/\/)?(?:www\.)?github\.com\/[\w.-]+\/[\w.-]+\/pull\/\d+(?:[/?#].*)?$/
const ADD_REPOSITORY_PARAM = 'add_repo'
const PULL_REQUEST_PATH = /^\/github\.com\/([\w.-]+\/[\w.-]+)\/pull\/\d+(?:\/.*)?$/

export function isPullRequestUrl(text: string): boolean {
  return PULL_REQUEST_URL.test(text.trim())
}

export function pullRequestRepositoryFromPath(pathname: string): string | null {
  return PULL_REQUEST_PATH.exec(pathname)?.[1] ?? null
}

export function pullRequestUrlFromPath(pathname: string): string | null {
  return PULL_REQUEST_PATH.test(pathname) ? githubUrl(pathname) : null
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
  const then = new URLSearchParams(search).get(ADD_REPOSITORY_PARAM) ?? ''
  const queryStart = then.includes('?') ? then.indexOf('?') : then.length
  const pathname = then.slice(0, queryStart)
  const repository = pullRequestRepositoryFromPath(pathname)
  return repository === null ? null : { repository, url: githubUrl(pathname), search: then.slice(queryStart) }
}
