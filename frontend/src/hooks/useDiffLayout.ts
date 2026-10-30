import { useSyncExternalStore } from 'react'
import type { ViewType } from 'react-diff-view'

import { isDiffLayoutKey, loadDiffLayout, resolveViewType, saveDiffLayout, type DiffLayoutSettings } from '../settings/diffLayout'

const listeners = new Set<() => void>()
let current: DiffLayoutSettings | null = null
let wideMedia: { threshold: number; query: MediaQueryList } | null = null

function snapshot(): DiffLayoutSettings {
  current ??= loadDiffLayout()
  return current
}

function notify() {
  listeners.forEach((listener) => { listener() })
}

function releaseWideMedia() {
  wideMedia?.query.removeEventListener('change', notify)
  wideMedia = null
}

function isWide(threshold: number): boolean {
  if (wideMedia?.threshold !== threshold) {
    releaseWideMedia()
    const query = window.matchMedia(`(min-width: ${String(threshold)}px)`)
    query.addEventListener('change', notify)
    wideMedia = { threshold, query }
  }
  return wideMedia.query.matches
}

function replace(settings: DiffLayoutSettings) {
  current = settings
  releaseWideMedia()
  notify()
}

function onStorage(event: StorageEvent) {
  if (isDiffLayoutKey(event.key)) {
    replace(loadDiffLayout())
  }
}

function subscribe(listener: () => void) {
  if (listeners.size === 0) {
    window.addEventListener('storage', onStorage)
  }
  listeners.add(listener)
  return () => {
    listeners.delete(listener)
    if (listeners.size === 0) {
      window.removeEventListener('storage', onStorage)
      releaseWideMedia()
    }
  }
}

export function setDiffLayout(settings: DiffLayoutSettings): void {
  const previous = snapshot()
  if (previous.layout === settings.layout && previous.threshold === settings.threshold) {
    return
  }
  saveDiffLayout(settings)
  replace(settings)
}

export function useDiffLayout(): DiffLayoutSettings {
  return useSyncExternalStore(subscribe, snapshot)
}

export function useViewType(modified: boolean): ViewType {
  return useSyncExternalStore(subscribe, () => {
    const { layout, threshold } = snapshot()
    return resolveViewType(layout, modified, () => isWide(threshold))
  })
}
