const PULL_REQUEST_URL = /^(?:https?:\/\/)?(?:www\.)?github\.com\/([\w.-]+\/[\w.-]+)\/pull\/\d+(?:[/?#].*)?$/
const PULL_REQUEST_PATH = /^\/github\.com\/[\w.-]+\/[\w.-]+\/pull\/\d+(?:\/.*)?$/

export function isPullRequestUrl(text: string): boolean {
  return PULL_REQUEST_URL.test(text.trim())
}

export function pullRequestRepository(url: string): string | null {
  return PULL_REQUEST_URL.exec(url.trim())?.[1] ?? null
}

export function pullRequestUrlFromPath(pathname: string): string | null {
  return PULL_REQUEST_PATH.test(pathname) ? `https:/${pathname}` : null
}
