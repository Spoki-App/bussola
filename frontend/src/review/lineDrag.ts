import type { DiffRow } from '../api/types'
import { selectRange, type LineSelection } from './selection'

export const EDGE_SCROLL_ZONE = 48
export const EDGE_SCROLL_MAX_STEP = 24

export function dragSelection(rows: DiffRow[], current: LineSelection, key: string): LineSelection {
  const anchor = current.anchor ?? key
  return { anchor, selected: selectRange(rows, anchor, key) }
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
