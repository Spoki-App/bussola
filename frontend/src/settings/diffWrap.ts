import { useSyncExternalStore } from 'react'

import { readStored, writeStored } from './storage'

const STORAGE_KEY = 'bussola.diffWrap'

const listeners = new Set<() => void>()
let current: boolean | undefined

export function loadDiffWrap(): boolean {
  return readStored(STORAGE_KEY) !== 'false'
}

function snapshot(): boolean {
  current ??= loadDiffWrap()
  return current
}

export function setDiffWrap(wrap: boolean): void {
  current = wrap
  writeStored(STORAGE_KEY, String(wrap))
  for (const listener of listeners) {
    listener()
  }
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
