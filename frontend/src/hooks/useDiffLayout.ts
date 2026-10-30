import { useSyncExternalStore } from 'react'

import { loadDiffLayout, saveDiffLayout, type DiffLayoutSettings } from '../settings/diffLayout'

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

export function setDiffLayout(settings: DiffLayoutSettings): void {
  current = settings
  saveDiffLayout(settings)
  listeners.forEach((listener) => { listener() })
}

export function useDiffLayout(): DiffLayoutSettings {
  return useSyncExternalStore(subscribe, snapshot)
}

function subscribeResize(listener: () => void) {
  window.addEventListener('resize', listener)
  return () => {
    window.removeEventListener('resize', listener)
  }
}

export function useWindowAtLeast(width: number): boolean {
  return useSyncExternalStore(subscribeResize, () => window.innerWidth >= width)
}
