import type { DiffRow } from '../api/types'
import { selectRange } from './selection'

export const EDGE_SCROLL_ZONE = 48
export const EDGE_SCROLL_MAX_STEP = 24

export interface LineSelection {
  anchor: string
  selected: Set<string>
}

export function dragSelection(rows: DiffRow[], anchor: string | null, key: string, extend: boolean): LineSelection {
  const start = extend && anchor !== null ? anchor : key
  return { anchor: start, selected: selectRange(rows, start, key) }
}

export function edgeScrollStep(pointerY: number, viewportHeight: number): number {
  if (pointerY < EDGE_SCROLL_ZONE) {
    return -scrollSpeed(EDGE_SCROLL_ZONE - pointerY)
  }
  const bottom = viewportHeight - EDGE_SCROLL_ZONE
  return pointerY > bottom ? scrollSpeed(pointerY - bottom) : 0
}

function scrollSpeed(depth: number): number {
  return Math.ceil((EDGE_SCROLL_MAX_STEP * Math.min(depth, EDGE_SCROLL_ZONE)) / EDGE_SCROLL_ZONE)
}
