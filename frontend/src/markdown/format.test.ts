import { describe, expect, it } from 'vitest'

import { applyFormat, changedRange, toggleWrap, type FormatAction, type TextState } from './format'

function parse(marked: string): TextState {
  const start = marked.indexOf('[')
  const end = marked.indexOf(']') - 1
  return { text: marked.replace('[', '').replace(']', ''), start, end }
}

function show(state: TextState): string {
  return `${state.text.slice(0, state.start)}[${state.text.slice(state.start, state.end)}]${state.text.slice(state.end)}`
}

function format(marked: string, action: FormatAction): string {
  return show(applyFormat(parse(marked), action))
}

describe('toggleWrap', () => {
  it('wraps the selection and keeps it selected', () => {
    expect(show(toggleWrap(parse('a [word] b'), '**', '**', 'bold'))).toBe('a **[word]** b')
  })

  it('inserts a selected placeholder at the cursor', () => {
    expect(show(toggleWrap(parse('a []b'), '**', '**', 'bold'))).toBe('a **[bold]**b')
  })

  it('unwraps when applied again to the same selection', () => {
    expect(show(toggleWrap(parse('a **[word]** b'), '**', '**', 'bold'))).toBe('a [word] b')
  })

  it('unwraps a selection that includes the markers', () => {
    expect(show(toggleWrap(parse('a [**word**] b'), '**', '**', 'bold'))).toBe('a [word] b')
  })
})

describe('applyFormat', () => {
  it.each<[FormatAction, string]>([
    ['bold', '**[x]**'],
    ['italic', '_[x]_'],
    ['strike', '~~[x]~~'],
    ['code', '`[x]`'],
  ])('%s wraps and toggles back', (action, wrapped) => {
    expect(format('[x]', action)).toBe(wrapped)
    expect(format(wrapped, action)).toBe('[x]')
  })

  it('wraps a code block on its own lines', () => {
    expect(format('see [x = 1] here', 'codeBlock')).toBe('see \n```\n[x = 1]\n```\n here')
    expect(format('[x = 1]', 'codeBlock')).toBe('```\n[x = 1]\n```')
    expect(format('```\n[x = 1]\n```', 'codeBlock')).toBe('[x = 1]')
  })

  it('links the selection and selects the url', () => {
    expect(applyFormat({ text: 'see docs now', start: 4, end: 8 }, 'link')).toEqual({ text: 'see [docs](url) now', start: 11, end: 14 })
  })

  it('removes a link when applied to its url', () => {
    expect(show(applyFormat({ text: 'see [docs](url) now', start: 11, end: 14 }, 'link'))).toBe('see [docs] now')
  })

  it('inserts a link placeholder at the cursor', () => {
    expect(applyFormat({ text: 'a ', start: 2, end: 2 }, 'link')).toEqual({ text: 'a [text](url)', start: 3, end: 7 })
  })

  it('prefixes every selected line and toggles back', () => {
    const quoted = applyFormat({ text: 'one\ntwo\nthree', start: 1, end: 5 }, 'quote')
    expect(quoted).toEqual({ text: '> one\n> two\nthree', start: 0, end: 11 })
    expect(applyFormat(quoted, 'quote')).toEqual({ text: 'one\ntwo\nthree', start: 0, end: 7 })
  })

  it('numbers lines and switches between list kinds', () => {
    const numbered = applyFormat({ text: 'a\nb', start: 0, end: 3 }, 'numbers')
    expect(numbered.text).toBe('1. a\n2. b')
    expect(applyFormat(numbered, 'tasks').text).toBe('- [ ] a\n- [ ] b')
    expect(applyFormat(applyFormat(numbered, 'tasks'), 'bullets').text).toBe('- a\n- b')
  })

  it('replaces a heading level and keeps the cursor on the line', () => {
    expect(applyFormat({ text: '# Title', start: 4, end: 4 }, 'h2')).toEqual({ text: '## Title', start: 5, end: 5 })
    expect(applyFormat({ text: '## Title', start: 5, end: 5 }, 'h2')).toEqual({ text: 'Title', start: 2, end: 2 })
    expect(applyFormat({ text: '', start: 0, end: 0 }, 'h3')).toEqual({ text: '### ', start: 4, end: 4 })
  })
})

describe('changedRange', () => {
  it('finds the smallest replaced range', () => {
    expect(changedRange('a **x** b', 'a x b')).toEqual({ from: 2, to: 7, insert: 'x' })
    expect(changedRange('ab', 'a_b_')).toEqual({ from: 1, to: 2, insert: '_b_' })
    expect(changedRange('same', 'same')).toEqual({ from: 4, to: 4, insert: '' })
  })
})
