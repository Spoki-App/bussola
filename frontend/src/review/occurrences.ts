import type { HunkTokens, TextNode, TokenNode } from 'react-diff-view'

import { isSymbolToken, symbolSpan, type SymbolSpan } from './codeNavigation'

export const OCCURRENCE_CLASS = 'diff-occurrence'

interface Leaf {
  value: string
  classes: string[]
}

function classNames(node: TokenNode): string[] {
  const { className, properties } = node as { className?: unknown; properties?: { className?: unknown } }
  const names = className ?? properties?.className
  if (Array.isArray(names)) {
    return names.filter((name): name is string => typeof name === 'string').reverse()
  }
  return typeof names === 'string' ? [names] : []
}

function isText(node: TokenNode): node is TextNode {
  return typeof node.value === 'string'
}

function leaves(nodes: TokenNode[], classes: string[] = []): Leaf[] {
  return nodes.flatMap((node) => (isText(node) ? [{ value: node.value, classes }] : leaves(node.children ?? [], [...classNames(node), ...classes])))
}

function classesAt(parts: Leaf[], offset: number): string[] {
  let end = 0
  return parts.find((part) => (end += part.value.length) > offset)?.classes ?? []
}

export function occurrenceSpans(line: TokenNode[], name: string): SymbolSpan[] {
  const parts = leaves(line)
  const text = parts.map((part) => part.value).join('')
  const spans: SymbolSpan[] = []
  for (let at = name ? text.indexOf(name) : -1; at >= 0; at = text.indexOf(name, at + name.length)) {
    const span = symbolSpan(text, at)
    if (span?.start === at && span.end === at + name.length && isSymbolToken(classesAt(parts, at))) {
      spans.push(span)
    }
  }
  return spans
}

function wrap(nodes: TokenNode[], spans: SymbolSpan[], offset: { at: number }): TokenNode[] {
  return nodes.flatMap((node): TokenNode[] => {
    if (!isText(node)) {
      return [{ ...node, children: wrap(node.children ?? [], spans, offset) }]
    }
    const start = offset.at
    const end = start + node.value.length
    offset.at = end
    const cuts = [start, end, ...spans.flatMap((span) => [span.start, span.end]).filter((cut) => cut > start && cut < end)].sort((a, b) => a - b)
    return cuts.slice(1).map((cut, index) => {
      const piece = { ...node, value: node.value.slice(cuts[index] - start, cut - start) }
      const inside = spans.some((span) => cuts[index] >= span.start && cut <= span.end)
      return inside ? { type: 'occurrence', className: OCCURRENCE_CLASS, children: [piece] } : piece
    })
  })
}

function markLine(line: TokenNode[], name: string): TokenNode[] {
  const spans = occurrenceSpans(line, name)
  return spans.length === 0 ? line : wrap(line, spans, { at: 0 })
}

export function markOccurrences(tokens: HunkTokens, name: string): HunkTokens {
  return { old: tokens.old.map((line) => markLine(line, name)), new: tokens.new.map((line) => markLine(line, name)) }
}
