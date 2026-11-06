import type { CodeRange, CodeRangeRequest, ComparisonRequest, Move } from '../api/types'

export interface MoveLink {
  direction: 'to' | 'from'
  other: CodeRange
  identical: boolean
  comparison: ComparisonRequest
}

export function rangeRequest({ unit_id, side, line_offset, line_count }: CodeRangeRequest): CodeRangeRequest {
  return { unit_id, side, line_offset, line_count }
}

export function moveLinksByUnit(moves: Move[]): Map<number, MoveLink[]> {
  const links = new Map<number, MoveLink[]>()
  const add = (unitId: number, link: MoveLink) => {
    links.set(unitId, [...(links.get(unitId) ?? []), link])
  }
  for (const move of moves) {
    const comparison = { left: rangeRequest(move.removed), right: rangeRequest(move.added) }
    add(move.removed.unit_id, { direction: 'to', other: move.added, identical: move.identical, comparison })
    add(move.added.unit_id, { direction: 'from', other: move.removed, identical: move.identical, comparison })
  }
  return links
}

export function rangeName(range: Pick<CodeRange, 'qualified_name' | 'path'>): string {
  return range.qualified_name || range.path
}

export function rangeLines(range: Pick<CodeRange, 'first_line' | 'last_line'>): string {
  const { first_line: first, last_line: last } = range
  if (first === null || last === null) {
    return ''
  }
  return first === last ? `line ${String(first)}` : `lines ${String(first)}-${String(last)}`
}

export function moveTitle(link: MoveLink): string {
  const where = [link.other.path, rangeLines(link.other)].filter(Boolean).join(' ')
  const verb = link.direction === 'to' ? 'Moved to' : 'Moved from'
  return `${verb} ${rangeName(link.other)} (${where})${link.identical ? ', identical' : ', with changes'}. Click to compare.`
}
