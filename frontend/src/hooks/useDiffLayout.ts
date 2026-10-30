import { useSyncExternalStore } from 'react'
import type { ViewType } from 'react-diff-view'

import { loadDiffLayout, resolveViewType, saveDiffLayout, type DiffLayoutSettings } from '../settings/diffLayout'

const listeners = new Set<() => void>()
let current: DiffLayoutSettings | null = null

function snapshot(): DiffLayoutSettings {
  current ??= loadDiffLayout()
  return current
}

function subscribe(listener: () => void) {
  listeners.add(listener)
  return () => {
    listeners.delete(listener)
  }
}

function subscribeWithResize(listener: () => void) {
  const unsubscribe = subscribe(listener)
  window.addEventListener('resize', listener)
  return () => {
    unsubscribe()
    window.removeEventListener('resize', listener)
  }
}

export function setDiffLayout(settings: DiffLayoutSettings): void {
  const previous = snapshot()
  if (previous.layout === settings.layout && previous.threshold === settings.threshold) {
    return
  }
  current = settings
  saveDiffLayout(settings)
  listeners.forEach((listener) => { listener() })
}

export function useDiffLayout(): DiffLayoutSettings {
  return useSyncExternalStore(subscribe, snapshot)
}

export function useViewType(modified: boolean): ViewType {
  return useSyncExternalStore(subscribeWithResize, () => {
    const { layout, threshold } = snapshot()
    return resolveViewType(layout, window.innerWidth >= threshold, modified)
  })
}
