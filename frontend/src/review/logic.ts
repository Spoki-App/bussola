import type { Review, Unit, UnitFilter, UnitState } from '../api/types'

export const TODO_STATES: ReadonlySet<UnitState> = new Set<UnitState>(['new', 'changed', 'partial', 'removed'])

export const STATE_LABELS: Record<UnitState, string> = {
  approved: 'Approved',
  approved_moved: 'Approved (moved)',
  changed: 'Changed since approval',
  partial: 'Partly approved',
  removed: 'Removed',
  new: 'New',
}

export const STATE_ORDER: UnitState[] = ['new', 'changed', 'partial', 'removed', 'approved', 'approved_moved']

export const FILTER_LABELS: Record<UnitFilter, string> = {
  all: 'All',
  todo: 'To review',
  since_last: 'Since my last review',
}

export interface FileGroup {
  path: string
  oldPath: string | null
  units: Unit[]
  todo: number
  complete: boolean
}

export function isTodo(state: UnitState): boolean {
  return TODO_STATES.has(state)
}

export function isApproved(state: UnitState): boolean {
  return !isTodo(state)
}

export function groupByFile(units: Unit[]): FileGroup[] {
  const groups = new Map<string, FileGroup>()
  for (const unit of units) {
    const group = groups.get(unit.path) ?? { path: unit.path, oldPath: unit.old_path, units: [], todo: 0, complete: true }
    group.units.push(unit)
    if (isTodo(unit.state)) {
      group.todo += 1
      group.complete = false
    }
    groups.set(unit.path, group)
  }
  return [...groups.values()]
}

export function progressPercent(review: Pick<Review, 'approved' | 'total'>): number {
  return review.total === 0 ? 100 : Math.round((review.approved / review.total) * 100)
}

export function nextTodoIndex(units: Unit[], fromIndex: number): number {
  for (let step = 1; step <= units.length; step += 1) {
    const index = (fromIndex + step + units.length) % units.length
    if (isTodo(units[index].state)) {
      return index
    }
  }
  return -1
}

export function clampIndex(index: number, length: number): number {
  return length === 0 ? -1 : Math.min(Math.max(index, 0), length - 1)
}

export function unitTitle(unit: Unit): string {
  if (unit.qualified_name) {
    return unit.qualified_name
  }
  return unit.kind === 'module' ? 'Module code' : 'Whole file'
}

export function shortSha(sha: string): string {
  return sha.slice(0, 8)
}
