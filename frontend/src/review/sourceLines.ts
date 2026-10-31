import type { ElementContent } from 'hast'

import { highlightCode, languageFor } from './highlight'

export interface SourceToken {
  text: string
  className: string
}

export type SourceLine = SourceToken[]

const MAX_HIGHLIGHTED_CHARS = 400_000

function classesOf(node: ElementContent): string[] {
  if (node.type !== 'element') {
    return []
  }
  const className = node.properties.className
  return Array.isArray(className) ? className.map(String) : []
}

function appendText(lines: SourceLine[], text: string, className: string) {
  text.split('\n').forEach((part, index) => {
    if (index > 0) {
      lines.push([])
    }
    if (part) {
      lines[lines.length - 1].push({ text: part, className })
    }
  })
}

function collect(nodes: ElementContent[], classes: string[], lines: SourceLine[]) {
  for (const node of nodes) {
    if (node.type === 'text') {
      appendText(lines, node.value, classes.join(' '))
    } else if (node.type === 'element') {
      collect(node.children, [...classes, ...classesOf(node)], lines)
    }
  }
}

function highlighted(text: string, path: string): ElementContent[] | null {
  const language = languageFor(path)
  if (language === null || text.length > MAX_HIGHLIGHTED_CHARS) {
    return null
  }
  try {
    return highlightCode(text, language)
  } catch {
    return null
  }
}

export function sourceLines(text: string, path: string): SourceLine[] {
  const body = text.endsWith('\n') ? text.slice(0, -1) : text
  const lines: SourceLine[] = [[]]
  const nodes = highlighted(body, path)
  if (nodes) {
    collect(nodes, [], lines)
  } else {
    appendText(lines, body, '')
  }
  return lines
}
