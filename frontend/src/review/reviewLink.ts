import { createContext } from 'react'

export interface LinkPlace {
  path?: string
  line?: number
  thread?: string
}

export type MakeLink = (place?: LinkPlace) => string

const PULL_REQUEST_URL = /^https:\/\/(?:www\.)?github\.com\/([\w.-]+\/[\w.-]+)\/pull\/(\d+)(?:[/?#].*)?$/

export const ReviewLinkContext = createContext<MakeLink | null>(null)

export function reviewLinkMaker(pullRequestUrl: string | null | undefined): MakeLink | null {
  const match = PULL_REQUEST_URL.exec(pullRequestUrl ?? '')
  if (match === null) {
    return null
  }
  const [, repo, pr] = match
  return ({ path, line, thread } = {}) => {
    const params = new URLSearchParams({ repo, pr })
    if (path !== undefined) {
      params.set('path', path)
      if (line !== undefined) {
        params.set('line', String(line))
      }
    }
    if (thread !== undefined) {
      params.set('thread', thread)
    }
    return `bussola://review?${params.toString().replaceAll('%2F', '/')}`
  }
}
