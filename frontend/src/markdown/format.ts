export interface TextState {
  text: string
  start: number
  end: number
}

export type FormatAction = 'h1' | 'h2' | 'h3' | 'bold' | 'italic' | 'strike' | 'code' | 'codeBlock' | 'quote' | 'link' | 'bullets' | 'numbers' | 'tasks'

export function toggleWrap(state: TextState, before: string, after: string, placeholder: string): TextState {
  const { text, start, end } = state
  const selected = text.slice(start, end)
  if (text.slice(start - before.length, start) === before && text.slice(end, end + after.length) === after) {
    return { text: text.slice(0, start - before.length) + selected + text.slice(end + after.length), start: start - before.length, end: end - before.length }
  }
  if (selected.length >= before.length + after.length && selected.startsWith(before) && selected.endsWith(after)) {
    const inner = selected.slice(before.length, selected.length - after.length)
    return { text: text.slice(0, start) + inner + text.slice(end), start, end: start + inner.length }
  }
  const inner = selected || placeholder
  return { text: text.slice(0, start) + before + inner + after + text.slice(end), start: start + before.length, end: start + before.length + inner.length }
}

interface LineStyle {
  prefix: (index: number) => string
  is: RegExp
  family: RegExp
}

const LIST = /^(?:[-*+] \[[ xX]\] |[-*+] |\d+\. )/
const HEADING = /^#{1,6} /

function heading(level: number): LineStyle {
  return { prefix: () => `${'#'.repeat(level)} `, is: new RegExp(`^#{${String(level)}} `), family: HEADING }
}

const LINE_STYLES: Partial<Record<FormatAction, LineStyle>> = {
  h1: heading(1),
  h2: heading(2),
  h3: heading(3),
  quote: { prefix: () => '> ', is: /^> ?/, family: /^> ?/ },
  bullets: { prefix: () => '- ', is: /^[-*+] (?!\[[ xX]\] )/, family: LIST },
  numbers: { prefix: (index) => `${String(index + 1)}. `, is: /^\d+\. /, family: LIST },
  tasks: { prefix: () => '- [ ] ', is: /^[-*+] \[[ xX]\] /, family: LIST },
}

function toggleLinePrefix(state: TextState, style: LineStyle): TextState {
  const { text, start } = state
  const end = state.end > start && text[state.end - 1] === '\n' ? state.end - 1 : state.end
  const blockStart = text.lastIndexOf('\n', start - 1) + 1
  const lineEnd = text.indexOf('\n', end)
  const blockEnd = lineEnd === -1 ? text.length : lineEnd
  const lines = text.slice(blockStart, blockEnd).split('\n')
  const remove = lines.every((line) => style.is.test(line))
  const changed = lines.map((line, index) => (remove ? line.replace(style.is, '') : style.prefix(index) + line.replace(style.family, '')))
  const block = changed.join('\n')
  const next = text.slice(0, blockStart) + block + text.slice(blockEnd)
  if (state.start !== state.end) {
    return { text: next, start: blockStart, end: blockStart + block.length }
  }
  const cursor = Math.max(blockStart, start + changed[0].length - lines[0].length)
  return { text: next, start: cursor, end: cursor }
}

function toggleLink(state: TextState): TextState {
  const { text, start, end } = state
  const labelStart = text.lastIndexOf('[', start - 2)
  if (text.slice(start - 2, start) === '](' && text[end] === ')' && labelStart !== -1) {
    const label = text.slice(labelStart + 1, start - 2)
    return { text: text.slice(0, labelStart) + label + text.slice(end + 1), start: labelStart, end: labelStart + label.length }
  }
  if (start === end) {
    return toggleWrap(state, '[', '](url)', 'text')
  }
  const label = text.slice(start, end)
  const urlStart = start + label.length + 3
  return { text: `${text.slice(0, start)}[${label}](url)${text.slice(end)}`, start: urlStart, end: urlStart + 3 }
}

function toggleCodeBlock(state: TextState): TextState {
  const { text, start, end } = state
  if (text.slice(start - 4, start) === '```\n' && text.slice(end, end + 4) === '\n```') {
    return toggleWrap(state, '```\n', '\n```', '')
  }
  const lead = start === 0 || text[start - 1] === '\n' ? '' : '\n'
  const trail = end === text.length || text[end] === '\n' ? '' : '\n'
  return toggleWrap(state, `${lead}\`\`\`\n`, `\n\`\`\`${trail}`, 'code')
}

export function applyFormat(state: TextState, action: FormatAction): TextState {
  const lineStyle = LINE_STYLES[action]
  if (lineStyle) {
    return toggleLinePrefix(state, lineStyle)
  }
  switch (action) {
    case 'bold':
      return toggleWrap(state, '**', '**', 'bold text')
    case 'italic':
      return toggleWrap(state, '_', '_', 'italic text')
    case 'strike':
      return toggleWrap(state, '~~', '~~', 'strikethrough text')
    case 'code':
      return toggleWrap(state, '`', '`', 'code')
    case 'codeBlock':
      return toggleCodeBlock(state)
    default:
      return toggleLink(state)
  }
}

export function changedRange(before: string, after: string): { from: number; to: number; insert: string } {
  let from = 0
  const limit = Math.min(before.length, after.length)
  while (from < limit && before[from] === after[from]) {
    from += 1
  }
  let tail = 0
  while (tail < limit - from && before[before.length - 1 - tail] === after[after.length - 1 - tail]) {
    tail += 1
  }
  return { from, to: before.length - tail, insert: after.slice(from, after.length - tail) }
}
