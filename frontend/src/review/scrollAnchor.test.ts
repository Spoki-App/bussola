import { afterEach, describe, expect, it, vi } from 'vitest'

import { captureScrollAnchor, restoreScrollAnchor } from './scrollAnchor'

function place(element: Element, top: number, height: number) {
  vi.spyOn(element, 'getBoundingClientRect').mockImplementation(() => DOMRect.fromRect({ x: 0, y: top, width: 100, height }))
}

function panel() {
  const scroller = document.createElement('div')
  scroller.innerHTML = '<header></header><section><aside style="position: sticky"></aside><p id="first"></p><p id="second"></p></section>'
  document.body.append(scroller)
  return scroller
}

function part(scroller: Element, selector: string): Element {
  const element = scroller.querySelector(selector)
  if (!element) {
    throw new Error(selector)
  }
  return element
}

describe('scroll anchor', () => {
  afterEach(() => {
    vi.restoreAllMocks()
    document.body.replaceChildren()
  })

  it('picks the innermost element of the content under the top inset, skipping sticky ones', () => {
    const scroller = panel()
    scroller.scrollTop = 300
    place(scroller, 100, 400)
    place(part(scroller, 'section'), -200, 900)
    place(part(scroller, 'section > aside'), 130, 30)
    place(part(scroller, '#first'), -200, 250)
    place(part(scroller, '#second'), 50, 300)

    expect(captureScrollAnchor(scroller, part(scroller, 'section'), 30)).toEqual({ element: part(scroller, '#second'), offset: -80, height: 300 })
  })

  it('has no anchor at the top of the panel', () => {
    const scroller = panel()

    expect(captureScrollAnchor(scroller, part(scroller, 'section'))).toBeNull()
  })

  it('scrolls so the anchor sits at the same distance under the top inset again', () => {
    const scroller = panel()
    const second = part(scroller, '#second')
    place(scroller, 0, 800)
    place(second, 400, 100)

    restoreScrollAnchor(scroller, { element: second, offset: 20, height: 100 }, 40)

    expect(scroller.scrollTop).toBe(340)
  })

  it('keeps the same share of an element cut by the top edge when its height changes', () => {
    const scroller = panel()
    const second = part(scroller, '#second')
    place(scroller, 0, 800)
    place(second, 400, 100)

    restoreScrollAnchor(scroller, { element: second, offset: -100, height: 200 })

    expect(scroller.scrollTop).toBe(450)
  })

  it('goes back to the top without an anchor, or when the anchor is gone', () => {
    const scroller = panel()
    scroller.scrollTop = 500
    restoreScrollAnchor(scroller, null)
    expect(scroller.scrollTop).toBe(0)

    scroller.scrollTop = 500
    restoreScrollAnchor(scroller, { element: document.createElement('p'), offset: 0, height: 10 })
    expect(scroller.scrollTop).toBe(0)
  })
})
