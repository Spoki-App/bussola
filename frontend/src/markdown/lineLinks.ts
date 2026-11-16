import type { Side } from '../api/types'

export interface LineLink {
  side: Side
  line: number
  path?: string
}

const LINE_LINK = /^#(after|before)(?:-|:(.+):)(\d+)$/

function decoded(href: string): string {
  try {
    return decodeURIComponent(href)
  } catch {
    return href
  }
}

export function lineLinkOf(href: string): LineLink | null {
  const match = LINE_LINK.exec(decoded(href))
  if (!match) {
    return null
  }
  const [, side, path, line] = match
  return { side: side === 'before' ? 'base' : 'head', line: Number(line), ...(path ? { path } : {}) }
}

const MARKDOWN_LINK = /\[([^\]]*)\]\(<?([^)\s>]+)>?\)/g

export function lineLinksAsText(markdown: string): string {
  return markdown.replace(MARKDOWN_LINK, (link, text: string, href: string) => (lineLinkOf(href) ? text : link))
}

export function lineLinkLabel(link: LineLink): string {
  const where = link.path ? ` of ${link.path}` : ' in the diff'
  return `Show ${link.side === 'base' ? 'old' : 'new'} line ${String(link.line)}${where}`
}
