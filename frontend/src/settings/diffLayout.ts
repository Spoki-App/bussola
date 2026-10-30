import type { DiffRow } from '../api/types'
import { readStored, writeStored } from './storage'

export type DiffLayout = 'auto' | 'split' | 'unified'
export type ViewType = 'split' | 'unified'

export interface DiffLayoutSettings {
  layout: DiffLayout
  threshold: number
}

export const DIFF_LAYOUT_LABELS: Record<DiffLayout, string> = { auto: 'Automatic', split: 'Split', unified: 'Unified' }
export const DEFAULT_DIFF_LAYOUT: DiffLayoutSettings = { layout: 'auto', threshold: 1400 }
export const MIN_SPLIT_THRESHOLD = 600
export const MAX_SPLIT_THRESHOLD = 4000

const STORAGE_KEY = 'bussola.diffLayout'

export function isDiffLayout(value: unknown): value is DiffLayout {
  return typeof value === 'string' && value in DIFF_LAYOUT_LABELS
}

export function clampThreshold(threshold: number): number {
  return Number.isFinite(threshold) ? Math.min(MAX_SPLIT_THRESHOLD, Math.max(MIN_SPLIT_THRESHOLD, Math.round(threshold))) : DEFAULT_DIFF_LAYOUT.threshold
}

export function loadDiffLayout(): DiffLayoutSettings {
  try {
    const stored: unknown = JSON.parse(readStored(STORAGE_KEY) ?? 'null')
    if (stored && typeof stored === 'object') {
      const layout = 'layout' in stored && isDiffLayout(stored.layout) ? stored.layout : DEFAULT_DIFF_LAYOUT.layout
      const threshold = 'threshold' in stored && typeof stored.threshold === 'number' ? clampThreshold(stored.threshold) : DEFAULT_DIFF_LAYOUT.threshold
      return { layout, threshold }
    }
  } catch {
    return DEFAULT_DIFF_LAYOUT
  }
  return DEFAULT_DIFF_LAYOUT
}

export function saveDiffLayout(settings: DiffLayoutSettings): void {
  writeStored(STORAGE_KEY, JSON.stringify(settings))
}

export function hasModification(rows: DiffRow[]): boolean {
  let removed = false
  let added = false
  for (const row of rows) {
    if (row.change === 'context') {
      removed = false
      added = false
      continue
    }
    removed ||= row.change === 'removed'
    added ||= row.change === 'added'
    if (removed && added) {
      return true
    }
  }
  return false
}

export function resolveViewType(layout: DiffLayout, wide: boolean, rows: DiffRow[]): ViewType {
  if (layout !== 'auto') {
    return layout
  }
  return wide && hasModification(rows) ? 'split' : 'unified'
}
