import type { NavigationRequest, NavigationResult, NavigationTarget } from '../api/navigation'
import type { Side } from '../api/types'

export interface ScreenPoint {
  x: number
  y: number
}

export interface NavigationClick extends NavigationRequest {
  point: ScreenPoint
}

export interface UnitTarget {
  unitId: number
  line: number
  side: Side
  seq: number
}

interface ModifierClick {
  metaKey: boolean
  ctrlKey: boolean
  button: number
}

interface CaretPositionLike {
  offsetNode: Node
  offset: number
}

interface CaretDocument {
  caretPositionFromPoint?: (x: number, y: number) => CaretPositionLike | null
  caretRangeFromPoint?: (x: number, y: number) => Range | null
}

export interface TargetFile {
  path: string
  targets: NavigationTarget[]
}

export interface TargetGroups {
  definitions: NavigationTarget[]
  files: TargetFile[]
  ordered: NavigationTarget[]
}

export function isNavigationClick(event: ModifierClick): boolean {
  return event.button === 0 && (event.metaKey || event.ctrlKey)
}

function caretAt(x: number, y: number): { node: Node; offset: number } | null {
  const caretDocument: CaretDocument = document
  if (caretDocument.caretPositionFromPoint) {
    const position = caretDocument.caretPositionFromPoint(x, y)
    return position ? { node: position.offsetNode, offset: position.offset } : null
  }
  if (caretDocument.caretRangeFromPoint) {
    const range = caretDocument.caretRangeFromPoint(x, y)
    return range ? { node: range.startContainer, offset: range.startOffset } : null
  }
  return null
}

export function textOffset(container: Node, node: Node, offset: number): number {
  const range = document.createRange()
  range.setStart(container, 0)
  range.setEnd(node, offset)
  return range.toString().length
}

export function columnAt(container: Element, x: number, y: number): number | null {
  const caret = caretAt(x, y)
  if (!caret || !container.contains(caret.node)) {
    return null
  }
  return textOffset(container, caret.node, caret.offset)
}

export function groupTargets(targets: NavigationTarget[]): TargetGroups {
  const definitions = targets.filter((target) => target.role === 'definition')
  const files: TargetFile[] = []
  for (const target of targets.filter((candidate) => candidate.role === 'usage')) {
    const file = files.find((candidate) => candidate.path === target.path)
    if (file) {
      file.targets.push(target)
    } else {
      files.push({ path: target.path, targets: [target] })
    }
  }
  return { definitions, files, ordered: [...definitions, ...files.flatMap((file) => file.targets)] }
}

export function directTarget(result: NavigationResult): NavigationTarget | null {
  const [only] = result.targets
  return result.targets.length === 1 && only.unit_id !== null ? only : null
}

export function emptyMessage(result: NavigationResult): string {
  return result.origin === 'definition' ? `No usages of ${result.symbol ?? ''} found.` : `No definition of ${result.symbol ?? ''} found.`
}

export function titleOf(result: NavigationResult): string {
  return result.origin === 'definition' ? `Usages of ${result.symbol ?? ''}` : `Definitions of ${result.symbol ?? ''}`
}
