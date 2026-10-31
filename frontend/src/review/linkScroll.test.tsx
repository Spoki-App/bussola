import { act, render } from '@testing-library/react'
import type { ReactNode } from 'react'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'

import { LinkScrollContext, createLinkScroll, endOnUserInput, useLinkedScroll, type LinkScroll } from './linkFocus'

function Linked({ id, unitId = null, settled = false, children }: { id: string; unitId?: number | null; settled?: boolean; children?: ReactNode }) {
  const ref = useLinkedScroll<HTMLDivElement>(id, unitId, settled)
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

  it('scrolls to the unit holding a linked thread, then to the thread, and finishes there', () => {
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
    expect(link.current()).toBeNull()
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
    expect(link.current()).toBeNull()
  })

  it('waits for the unit diff, then gives up on a thread its diff does not show', () => {
    const link = createLinkScroll()
    const view = render(withLink(link, <Linked id="unit-2" unitId={2} />))
    act(() => { link.start({ unitId: 2, elementId: 'thread-t' }) })
    expect(link.current()).toEqual({ target: { unitId: 2, elementId: 'thread-t' }, unitShown: true })

    view.rerender(withLink(link, <Linked id="unit-2" unitId={2} settled />))
    expect(link.current()).toBeNull()

    view.rerender(withLink(link, (
      <Linked id="unit-2" unitId={2} settled>
        <Linked id="thread-t" />
      </Linked>
    )))
    expect(scrolled).toEqual(['unit-2'])
  })

  it('scrolls to a linked unit again once its diff has loaded, then finishes', () => {
    const link = createLinkScroll()
    const view = render(withLink(link, <Linked id="unit-2" unitId={2} />))

    act(() => { link.start({ unitId: 2, elementId: 'unit-2' }) })
    expect(scrolled).toEqual(['unit-2'])
    expect(link.current()).not.toBeNull()

    view.rerender(withLink(link, <Linked id="unit-2" unitId={2} settled />))

    expect(scrolled).toEqual(['unit-2', 'unit-2'])
    expect(link.current()).toBeNull()
  })

  it('ends the link as soon as the user scrolls, types or clicks', () => {
    for (const event of [new WheelEvent('wheel'), new KeyboardEvent('keydown'), new MouseEvent('mousedown')]) {
      const link = createLinkScroll()
      const stop = endOnUserInput(link)
      link.start({ unitId: 2, elementId: 'unit-2' })

      window.dispatchEvent(event)

      expect(link.current()).toBeNull()
      stop()
    }
  })

  it('does nothing without a link', () => {
    render(<Linked id="unit-2" unitId={2} />)

    expect(scrolled).toEqual([])
  })
})
