import { useSyncExternalStore } from 'react'

const NAVIGATE_EVENT = 'bussola:navigate'

function subscribe(onChange: () => void) {
  window.addEventListener('popstate', onChange)
  window.addEventListener(NAVIGATE_EVENT, onChange)
  return () => {
    window.removeEventListener('popstate', onChange)
    window.removeEventListener(NAVIGATE_EVENT, onChange)
  }
}

export function usePathname(): string {
  return useSyncExternalStore(subscribe, () => window.location.pathname)
}

export function useSearch(): string {
  return useSyncExternalStore(subscribe, () => window.location.search)
}

export function navigate(to: string, { replace = false }: { replace?: boolean } = {}) {
  if (replace) {
    window.history.replaceState(null, '', to)
  } else {
    window.history.pushState(null, '', to)
  }
  window.dispatchEvent(new Event(NAVIGATE_EVENT))
}

const REVIEW_PATH = /^\/reviews\/(\d+)\/?$/

export function reviewPath(reviewId: number): string {
  return `/reviews/${String(reviewId)}`
}

export function showReview(reviewId: number, search = '') {
  navigate(`${reviewPath(reviewId)}${search}`, { replace: true })
}

export function reviewIdFromPath(pathname: string): number | null {
  const match = REVIEW_PATH.exec(pathname)
  return match ? Number(match[1]) : null
}
