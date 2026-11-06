export interface TextState {
  text: string
  start: number
  end: number
}

export type FormatAction = 'h1' | 'h2' | 'h3' | 'bold' | 'italic' | 'strike' | 'code' | 'codeBlock' | 'quote' | 'link' | 'bullets' | 'numbers' | 'tasks'

function toggleWrap(state: TextState, before: string, after: string, placeholder: string): TextState {
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
const QUOTE = /^> ?/

function heading(level: number): LineStyle {
  return { prefix: () => `${'#'.repeat(level)} `, is: new RegExp(`^#{${String(level)}} `), family: HEADING }
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

const BULLETS: LineStyle = { prefix: () => '- ', is: /^[-*+] (?!\[[ xX]\] )/, family: LIST }
const NUMBERS: LineStyle = { prefix: (index) => `${String(index + 1)}. `, is: /^\d+\. /, family: LIST }
const TASKS: LineStyle = { prefix: () => '- [ ] ', is: /^[-*+] \[[ xX]\] /, family: LIST }
const QUOTED: LineStyle = { prefix: () => '> ', is: QUOTE, family: QUOTE }
const H1 = heading(1)
const H2 = heading(2)
const H3 = heading(3)

const FORMATS: Record<FormatAction, (state: TextState) => TextState> = {
  h1: (state) => toggleLinePrefix(state, H1),
  h2: (state) => toggleLinePrefix(state, H2),
  h3: (state) => toggleLinePrefix(state, H3),
  bold: (state) => toggleWrap(state, '**', '**', 'bold text'),
  italic: (state) => toggleWrap(state, '_', '_', 'italic text'),
  strike: (state) => toggleWrap(state, '~~', '~~', 'strikethrough text'),
  code: (state) => toggleWrap(state, '`', '`', 'code'),
  codeBlock: toggleCodeBlock,
  quote: (state) => toggleLinePrefix(state, QUOTED),
  link: toggleLink,
  bullets: (state) => toggleLinePrefix(state, BULLETS),
  numbers: (state) => toggleLinePrefix(state, NUMBERS),
  tasks: (state) => toggleLinePrefix(state, TASKS),
}

export function applyFormat(state: TextState, action: FormatAction): TextState {
  return FORMATS[action](state)
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
