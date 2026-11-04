import { act, fireEvent, render } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { clearCaret, placeCaret } from '../test/caret'
import { CHECK_DELAY_MS, LINK_NAME, useSymbolLink, type SymbolCheck } from './useSymbolLink'

class FakeHighlight {
  ranges: Range[]

  constructor(...ranges: Range[]) {
    this.ranges = ranges
  }
}

const highlights = new Map<string, FakeHighlight>()

function Harness({ check }: { check: SymbolCheck }) {
  const link = useSymbolLink()
  return (
    <code
      data-testid="code"
      onMouseMove={(event) => { link.hover(event, event.currentTarget, check) }}
      onMouseLeave={link.leave}
    >
      <span className="hljs-keyword">return</span> price(<span className="hljs-string">{'"item"'}</span>, count)
    </code>
  )
}

function setup(navigable: (column: number) => boolean = () => true) {
  const check = vi.fn((column: number) => Promise.resolve(navigable(column)))
  const { getByTestId } = render(<Harness check={check} />)
  const code = getByTestId('code')
  const pointAt = (word: string) => {
    const walker = document.createTreeWalker(code, NodeFilter.SHOW_TEXT)
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
      const index = (node.textContent ?? '').indexOf(word)
      if (index >= 0) {
        placeCaret(node, index + 1)
        return
      }
    }
  }
  const move = (word: string, modifier: { metaKey?: boolean; ctrlKey?: boolean } = { metaKey: true }) => {
    pointAt(word)
    fireEvent.mouseMove(code, { clientX: 1, clientY: 1, ...modifier })
  }
  const underlined = () => (code.classList.contains(LINK_NAME) ? (highlights.get(LINK_NAME)?.ranges[0].toString() ?? '') : null)
  const settle = () => act(() => vi.advanceTimersByTimeAsync(CHECK_DELAY_MS))
  return { check, code, move, underlined, settle }
}

describe('useSymbolLink', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    highlights.clear()
    vi.stubGlobal('CSS', { highlights })
    vi.stubGlobal('Highlight', FakeHighlight)
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
    clearCaret()
  })

  it('underlines a navigable symbol under the pointer while Cmd or Ctrl is held, checking it once', async () => {
    const { check, move, underlined, settle } = setup()

    move('price')
    move('rice')
    expect(underlined()).toBeNull()
    await settle()
    move('ice', { ctrlKey: true })
    await settle()

    expect(underlined()).toBe('price')
    expect(check).toHaveBeenCalledTimes(1)
    expect(check).toHaveBeenCalledWith('return '.length)
  })

  it('follows the pointer to another symbol and asks again only after the pointer rests', async () => {
    const { check, move, underlined, settle } = setup()
    move('price')
    await settle()

    move('count')
    expect(underlined()).toBeNull()
    await settle()

    expect(underlined()).toBe('count')
    expect(check).toHaveBeenCalledTimes(2)
  })

  it('never underlines keywords, strings, punctuation or symbols with nowhere to go', async () => {
    const { check, move, underlined, settle } = setup((column) => column !== 'return price("item", '.length)

    for (const word of ['return', 'item', '(', 'count']) {
      move(word)
      await settle()
      expect(underlined()).toBeNull()
    }
    expect(check).toHaveBeenCalledTimes(1)
  })

  it('shows the underline when the modifier is pressed over a symbol and removes it as soon as it is released', async () => {
    const { check, move, underlined, settle } = setup()
    move('price', {})
    await settle()
    expect(check).not.toHaveBeenCalled()

    fireEvent.keyDown(window, { key: 'Meta', metaKey: true })
    await settle()
    expect(underlined()).toBe('price')

    fireEvent.keyUp(window, { key: 'Meta', metaKey: false })
    expect(underlined()).toBeNull()
    expect(highlights.has(LINK_NAME)).toBe(false)
  })

  it('removes the underline when the pointer leaves the code or the window loses focus', async () => {
    const { code, move, underlined, settle } = setup()
    move('price')
    await settle()
    fireEvent.mouseLeave(code)
    expect(underlined()).toBeNull()

    move('price')
    await settle()
    fireEvent.blur(window)
    expect(underlined()).toBeNull()
  })

  it('drops an answer that arrives after the pointer moved away', async () => {
    let answer: (navigable: boolean) => void = () => undefined
    const check = vi.fn(() => new Promise<boolean>((resolve) => { answer = resolve }))
    const { getByTestId } = render(<Harness check={check} />)
    const code = getByTestId('code')
    placeCaret(code.childNodes[1], 2)
    fireEvent.mouseMove(code, { metaKey: true })
    await act(() => vi.advanceTimersByTimeAsync(CHECK_DELAY_MS))

    fireEvent.mouseLeave(code)
    answer(true)
    await act(() => vi.advanceTimersByTimeAsync(0))

    expect(code).not.toHaveClass(LINK_NAME)
  })
})
