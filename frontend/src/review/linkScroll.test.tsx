import { act, render } from '@testing-library/react'
import type { ReactNode } from 'react'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'

import { LinkScrollContext, createLinkScroll, useLinkedScroll, type LinkScroll } from './linkFocus'

function Linked({ id, unitId = null }: { id: string; unitId?: number | null }) {
  const ref = useLinkedScroll<HTMLDivElement>(id, unitId)
  return <div id={id} ref={ref} />
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

  it('scrolls to the holding unit once, even if the thread never shows and the unit mounts again', () => {
    const link = createLinkScroll()
    const view = render(withLink(link, <Linked id="unit-2" unitId={2} />))
    act(() => { link.start({ unitId: 2, elementId: 'thread-t' }) })

    view.unmount()
    render(withLink(link, <Linked id="unit-2" unitId={2} />))

    expect(scrolled).toEqual(['unit-2'])
    expect(link.current()).toEqual({ unitId: null, elementId: 'thread-t' })
  })

  it('finishes on a linked unit', () => {
    const link = createLinkScroll()
    render(withLink(link, <Linked id="unit-2" unitId={2} />))

    act(() => { link.start({ unitId: 2, elementId: 'unit-2' }) })

    expect(scrolled).toEqual(['unit-2'])
    expect(link.current()).toBeNull()
  })

  it('does nothing without a link', () => {
    render(<Linked id="unit-2" unitId={2} />)

    expect(scrolled).toEqual([])
  })
})
