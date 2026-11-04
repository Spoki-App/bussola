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
}

interface ModifierKeys {
  metaKey: boolean
  ctrlKey: boolean
}

interface ModifierClick extends ModifierKeys {
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

export interface SymbolSpan {
  start: number
  end: number
}

export interface TargetFile {
  path: string
  targets: NavigationTarget[]
}

export interface TargetGroups {
  definitions: NavigationTarget[]
  files: TargetFile[]
}

const NOT_SYMBOL_CLASSES = new Set(['hljs-keyword', 'hljs-string', 'hljs-comment', 'hljs-doctag', 'hljs-number', 'hljs-literal', 'hljs-regexp', 'hljs-char', 'hljs-punctuation', 'hljs-operator'])
const CODE_CLASS = 'hljs-subst'
const SYMBOL_CHAR = /[\p{L}\p{N}_$]/u
const SYMBOL_START = /[\p{L}_$]/u

export function hasNavigationModifier(event: ModifierKeys): boolean {
  return event.metaKey || event.ctrlKey
}

export function isNavigationClick(event: ModifierClick): boolean {
  return event.button === 0 && hasNavigationModifier(event)
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

function caretIn(container: Element, x: number, y: number): { node: Node; column: number } | null {
  const caret = caretAt(x, y)
  return caret && container.contains(caret.node) ? { node: caret.node, column: textOffset(container, caret.node, caret.offset) } : null
}

export function columnAt(container: Element, x: number, y: number): number | null {
  return caretIn(container, x, y)?.column ?? null
}

export function symbolSpan(text: string, offset: number): SymbolSpan | null {
  const at = SYMBOL_CHAR.test(text.charAt(offset)) ? offset : offset - 1
  if (at < 0 || !SYMBOL_CHAR.test(text.charAt(at))) {
    return null
  }
  let start = at
  while (start > 0 && SYMBOL_CHAR.test(text.charAt(start - 1))) {
    start -= 1
  }
  let end = at + 1
  while (end < text.length && SYMBOL_CHAR.test(text.charAt(end))) {
    end += 1
  }
  return SYMBOL_START.test(text.charAt(start)) ? { start, end } : null
}

export function isSymbolToken(classesInnermostFirst: string[]): boolean {
  const deciding = classesInnermostFirst.find((name) => name === CODE_CLASS || NOT_SYMBOL_CLASSES.has(name))
  return deciding === undefined || deciding === CODE_CLASS
}

function classesAround(container: Element, node: Node): string[] {
  const classes: string[] = []
  for (let element = node.parentElement; element && element !== container; element = element.parentElement) {
    classes.push(...[...element.classList].reverse())
  }
  return classes
}

export function symbolAt(container: Element, x: number, y: number): SymbolSpan | null {
  const caret = caretIn(container, x, y)
  return caret && isSymbolToken(classesAround(container, caret.node)) ? symbolSpan(container.textContent, caret.column) : null
}

export function navigationColumn(container: Element, x: number, y: number): number | null {
  return symbolAt(container, x, y)?.start ?? columnAt(container, x, y)
}

export function rangeOf(container: Element, span: SymbolSpan): Range | null {
  const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT)
  const range = document.createRange()
  let seen = 0
  let started = false
  for (let node = walker.nextNode(); node; node = walker.nextNode()) {
    const length = node.textContent?.length ?? 0
    if (!started && span.start < seen + length) {
      range.setStart(node, span.start - seen)
      started = true
    }
    if (started && span.end <= seen + length) {
      range.setEnd(node, span.end - seen)
      return range
    }
    seen += length
  }
  return null
}

export function isNavigable(result: NavigationResult): boolean {
  return result.ready && result.symbol !== null && result.targets.length > 0
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
  return { definitions, files }
}

export function directTarget(result: NavigationResult): NavigationTarget | null {
  const [only] = result.targets
  return result.targets.length === 1 ? only : null
}

function wording(result: NavigationResult): { title: string; empty: string } {
  const symbol = result.symbol ?? ''
  return result.origin === 'definition'
    ? { title: `Usages of ${symbol}`, empty: `No usages of ${symbol} found.` }
    : { title: `Definitions of ${symbol}`, empty: `No definition of ${symbol} found.` }
}

export function emptyMessage(result: NavigationResult): string {
  return wording(result).empty
}

export function titleOf(result: NavigationResult): string {
  return wording(result).title
}
