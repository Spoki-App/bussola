import type { Blockquote, Root } from 'mdast'
import { visit } from 'unist-util-visit'

const ALERT_MARKER = /^\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\][ \t]*\n?/i

const TITLES: Record<string, string> = {
  note: 'Note',
  tip: 'Tip',
  important: 'Important',
  warning: 'Warning',
  caution: 'Caution',
}

function alertKind(node: Blockquote): string | null {
  const first = node.children.at(0)
  if (first?.type !== 'paragraph') {
    return null
  }
  const text = first.children.at(0)
  if (text?.type !== 'text') {
    return null
  }
  const match = ALERT_MARKER.exec(text.value)
  if (!match) {
    return null
  }
  text.value = text.value.slice(match[0].length)
  if (!text.value) {
    first.children.shift()
  }
  if (first.children.at(0)?.type === 'break') {
    first.children.shift()
  }
  if (first.children.length === 0) {
    node.children.shift()
  }
  return match[1].toLowerCase()
}

export function remarkAlerts() {
  return (tree: Root) => {
    visit(tree, 'blockquote', (node: Blockquote) => {
      const kind = alertKind(node)
      if (kind === null) {
        return
      }
      node.data = { hName: 'div', hProperties: { className: ['markdown-alert', `markdown-alert-${kind}`] } }
      node.children.unshift({ type: 'paragraph', data: { hProperties: { className: ['markdown-alert-title'] } }, children: [{ type: 'text', value: TITLES[kind] }] })
    })
  }
}
