import { useSyncExternalStore } from 'react'

import { readStored, writeStored } from './storage'

const STORAGE_KEY = 'bussola.diffWrap'

const listeners = new Set<() => void>()
let current: boolean | undefined

function loadDiffWrap(): boolean {
  return readStored(STORAGE_KEY) !== 'false'
}

function snapshot(): boolean {
  current ??= loadDiffWrap()
  return current
}

function update(wrap: boolean): void {
  current = wrap
  document.documentElement.dataset.diffWrap = wrap ? 'on' : 'off'
  for (const listener of listeners) {
    listener()
  }
}

export function setDiffWrap(wrap: boolean): void {
  writeStored(STORAGE_KEY, String(wrap))
  update(wrap)
}

export function syncDiffWrap(): void {
  update(loadDiffWrap())
  window.addEventListener('storage', (event) => {
    if (event.key === STORAGE_KEY || event.key === null) {
      update(loadDiffWrap())
    }
  })
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener)
  return () => {
    listeners.delete(listener)
  }
}

export function useDiffWrap(): boolean {
  return useSyncExternalStore(subscribe, snapshot)
}
