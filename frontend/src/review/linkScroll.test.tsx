import { act, render } from '@testing-library/react'
import type { ReactNode } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { LinkScrollContext, createLinkScroll, followLink, useLinkedScroll, type LinkScroll } from './linkFocus'

function Linked({ id, unitId = null, settled = false, children }: { id: string; unitId?: number | null; settled?: boolean; children?: ReactNode }) {
  const { ref } = useLinkedScroll<HTMLDivElement>(id, unitId, settled)
  return (
    <div id={id} ref={ref}>
      {children}
    </div>
  )
}

let scrolled: string[] = []

function withLink(link: LinkScroll, children: ReactNode) {
  return <LinkScrollContext value={link}>{children}</LinkScrollContext>
}

describe('useLinkedScroll', () => {
  beforeEach(() => {
    scrolled = []
    Element.prototype.scrollIntoView = function scrollIntoView(this: Element) {
      scrolled.push(this.id)
    }
  })

  afterEach(() => {
    Reflect.deleteProperty(Element.prototype, 'scrollIntoView')
  })

  it('scrolls to the unit holding a linked thread, then to the thread, and reaches it', () => {
    const link = createLinkScroll()
    render(withLink(link, (
      <>
        <Linked id="unit-1" unitId={1} />
        <Linked id="unit-2" unitId={2} />
        <Linked id="thread-t" />
      </>
    )))

    act(() => { link.start({ unitId: 2, elementId: 'thread-t' }) })

    expect(scrolled).toEqual(['unit-2', 'thread-t'])
    expect(link.current()?.reached).toBe(true)
  })

  it('ends on a thread rendered inside its unit', () => {
    const link = createLinkScroll()
    render(withLink(link, (
      <Linked id="unit-2" unitId={2} settled>
        <Linked id="thread-t" />
      </Linked>
    )))

    act(() => { link.start({ unitId: 2, elementId: 'thread-t' }) })

    expect(scrolled).toEqual(['thread-t'])
    expect(link.current()?.reached).toBe(true)
  })

  it('waits for the unit diff, then stops looking for a thread its diff does not show', () => {
    const link = createLinkScroll()
    const view = render(withLink(link, <Linked id="unit-2" unitId={2} />))
    act(() => { link.start({ unitId: 2, elementId: 'thread-t' }) })
    expect(link.current()).toEqual({ target: { unitId: 2, elementId: 'thread-t' }, unitShown: true, reached: false })

    view.rerender(withLink(link, <Linked id="unit-2" unitId={2} settled />))
    expect(link.current()?.reached).toBe(true)

    view.rerender(withLink(link, (
      <Linked id="unit-2" unitId={2} settled>
        <Linked id="thread-t" />
      </Linked>
    )))
    expect(scrolled).toEqual(['unit-2'])
  })

  it('scrolls to a linked unit again once its diff has loaded', () => {
    const link = createLinkScroll()
    const view = render(withLink(link, <Linked id="unit-2" unitId={2} />))

    act(() => { link.start({ unitId: 2, elementId: 'unit-2' }) })
    expect(scrolled).toEqual(['unit-2'])
    expect(link.current()?.reached).toBe(false)

    view.rerender(withLink(link, <Linked id="unit-2" unitId={2} settled />))

    expect(scrolled).toEqual(['unit-2', 'unit-2'])
    expect(link.current()?.reached).toBe(true)
  })

  it('does nothing without a link', () => {
    render(<Linked id="unit-2" unitId={2} />)

    expect(scrolled).toEqual([])
  })
})

describe('followLink', () => {
  let resized: () => void = () => undefined
  let observed: Element[] = []

  beforeEach(() => {
    scrolled = []
    Element.prototype.scrollIntoView = function scrollIntoView(this: Element) {
      scrolled.push(this.id)
    }
    vi.stubGlobal('ResizeObserver', class {
      constructor(callback: () => void) {
        resized = callback
        observed = []
      }

      observe(element: Element) {
        observed.push(element)
      }

      disconnect() {
        resized = () => undefined
      }
    })
    document.body.innerHTML = '<div id="unit-2"></div>'
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    Reflect.deleteProperty(Element.prototype, 'scrollIntoView')
    document.body.innerHTML = ''
  })

  it('keeps the reached target in view while the page grows, until the user scrolls', () => {
    const link = createLinkScroll()
    const stop = followLink(link)
    link.start({ unitId: 2, elementId: 'unit-2' })
    link.reached()

    resized()
    expect(scrolled).toEqual(['unit-2'])

    window.dispatchEvent(new WheelEvent('wheel'))
    resized()

    expect(scrolled).toEqual(['unit-2'])
    expect(link.current()).toBeNull()
    stop()
  })

  it('watches the containers of the reached target, such as the conversation panel', () => {
    document.body.innerHTML = '<aside id="panel"><div id="thread-t"></div></aside>'
    const link = createLinkScroll()
    followLink(link)
    link.start({ unitId: null, elementId: 'thread-t' })

    link.reached()

    expect(observed.map((element) => element.id || element.tagName)).toEqual(['BODY', 'thread-t', 'panel', 'BODY', 'HTML'])
  })

  it('ends the link fifteen seconds after it starts, reached or not', () => {
    vi.useFakeTimers()
    const link = createLinkScroll()
    followLink(link)
    link.start({ unitId: 2, elementId: 'thread-never-shown' })

    vi.advanceTimersByTime(14_000)
    expect(link.current()).not.toBeNull()

    vi.advanceTimersByTime(1_000)
    expect(link.current()).toBeNull()
    vi.useRealTimers()
  })

  it('ends the link when the user drags the page away from the target, but not on its own scrolls', () => {
    const link = createLinkScroll()
    followLink(link)
    const target = document.getElementById('unit-2')
    let top = 0
    if (target) {
      target.getBoundingClientRect = () => DOMRect.fromRect({ y: top })
    }
    link.start({ unitId: 2, elementId: 'unit-2' })
    link.place(target)
    link.reached()

    window.dispatchEvent(new Event('scroll'))
    expect(link.current()?.reached).toBe(true)

    top = 300
    window.dispatchEvent(new Event('scroll'))
    expect(link.current()).toBeNull()
  })

  it('does not take a target that was removed from the page for a user scroll', () => {
    const link = createLinkScroll()
    followLink(link)
    const target = document.getElementById('unit-2')
    link.start({ unitId: 2, elementId: 'unit-2' })
    link.place(target)
    link.reached()
    if (target) {
      target.getBoundingClientRect = () => DOMRect.fromRect({ y: 300 })
    }

    target?.remove()
    window.dispatchEvent(new Event('scroll'))

    expect(link.current()?.reached).toBe(true)
  })

  it('forgets where the previous link was placed when a new one starts', () => {
    const link = createLinkScroll()
    followLink(link)
    const target = document.getElementById('unit-2')
    let top = 0
    if (target) {
      target.getBoundingClientRect = () => DOMRect.fromRect({ y: top })
    }
    link.start({ unitId: 2, elementId: 'unit-2' })
    link.place(target)
    top = 400

    link.start({ unitId: 3, elementId: 'unit-3' })
    window.dispatchEvent(new Event('scroll'))

    expect(link.current()?.target.elementId).toBe('unit-3')
  })

  it('ends the link on a key press or a click too, and only listens once', () => {
    for (const event of [new KeyboardEvent('keydown'), new MouseEvent('mousedown')]) {
      const link = createLinkScroll()
      const notified = vi.fn()
      link.subscribe(notified)
      followLink(link)
      link.start({ unitId: 2, elementId: 'unit-2' })

      window.dispatchEvent(event)
      window.dispatchEvent(event)

      expect(link.current()).toBeNull()
      expect(notified).toHaveBeenCalledTimes(2)
    }
  })
})
