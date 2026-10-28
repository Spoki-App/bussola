import { postJson } from './client'

const SERVER_OPENED_HOST = 'github.com'

export function canOpenThroughServer(href: string): boolean {
  try {
    const url = new URL(href)
    return url.protocol === 'https:' && url.hostname === SERVER_OPENED_HOST
  } catch {
    return false
  }
}

export function openExternal(href: string) {
  const fallback = () => {
    window.open(href, '_blank', 'noopener,noreferrer')
  }
  if (!canOpenThroughServer(href)) {
    fallback()
    return
  }
  postJson<unknown>('/open-url', { url: href }).catch(fallback)
}
