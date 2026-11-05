import type { Side } from '../api/types'

export interface LineLink {
  side: Side
  line: number
}

const LINE_LINK = /^#(after|before)-(\d+)$/

export function lineLinkOf(href: string): LineLink | null {
  const match = LINE_LINK.exec(href)
  return match ? { side: match[1] === 'before' ? 'base' : 'head', line: Number(match[2]) } : null
}
