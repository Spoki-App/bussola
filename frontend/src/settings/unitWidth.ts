import { useSyncExternalStore } from 'react'

import type { LineLength } from '../api/lineLength'
import { readStored, writeStored } from './storage'

export type UnitWidth = 'auto' | '80ch' | '100ch' | '120ch' | '160ch' | 'full'

export const UNIT_WIDTH_LABELS: Record<UnitWidth, string> = { auto: 'Auto', '80ch': '80', '100ch': '100', '120ch': '120', '160ch': '160', full: 'Full' }
export const DEFAULT_UNIT_WIDTH: UnitWidth = 'auto'
export const DEFAULT_LINE_LENGTH = 120

const STORAGE_KEY = 'bussola.unitWidth'
const WIDTHS = Object.keys(UNIT_WIDTH_LABELS) as UnitWidth[]

const listeners = new Set<() => void>()
let current: UnitWidth | undefined

function isUnitWidth(value: string | null): value is UnitWidth {
  return value !== null && Object.hasOwn(UNIT_WIDTH_LABELS, value)
}

function loadUnitWidth(): UnitWidth {
  const stored = readStored(STORAGE_KEY)
  return isUnitWidth(stored) ? stored : DEFAULT_UNIT_WIDTH
}

function snapshot(): UnitWidth {
  current ??= loadUnitWidth()
  return current
}

function update(width: UnitWidth): void {
  current = width
  listeners.forEach((listener) => { listener() })
}

function onStorage(event: StorageEvent): void {
  if (event.key === STORAGE_KEY || event.key === null) {
    update(loadUnitWidth())
  }
}

function subscribe(listener: () => void): () => void {
  if (listeners.size === 0) {
    window.addEventListener('storage', onStorage)
  }
  listeners.add(listener)
  return () => {
    listeners.delete(listener)
    if (listeners.size === 0) {
      window.removeEventListener('storage', onStorage)
    }
  }
}

export function setUnitWidth(width: UnitWidth): void {
  writeStored(STORAGE_KEY, width)
  update(width)
}

export function useUnitWidth(): UnitWidth {
  return useSyncExternalStore(subscribe, snapshot)
}

export function nextUnitWidth(width: UnitWidth): UnitWidth {
  return WIDTHS[(WIDTHS.indexOf(width) + 1) % WIDTHS.length] ?? DEFAULT_UNIT_WIDTH
}

export function unitColumns(width: UnitWidth, lineLength: LineLength | undefined): number | undefined {
  if (width === 'full') {
    return undefined
  }
  return width === 'auto' ? (lineLength?.columns ?? DEFAULT_LINE_LENGTH) : Number.parseInt(width)
}

export function lineLengthOrigin(lineLength: LineLength | undefined): string {
  if (!lineLength) {
    return `${String(DEFAULT_LINE_LENGTH)}, until the repository line length is read`
  }
  return lineLength.source ? `${String(lineLength.columns)}, from ${lineLength.source}` : `${String(lineLength.columns)}, the default: the repository sets no line length`
}
