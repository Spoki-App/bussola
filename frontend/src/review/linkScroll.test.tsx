import { render } from '@testing-library/react'
import type { ReactNode } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { LinkScrollContext, useLinkedScroll, type FocusTarget } from './linkFocus'

function Linked({ id, unitId = null }: { id: string; unitId?: number | null }) {
  const ref = useLinkedScroll<HTMLDivElement>(id, unitId)
  return <div id={id} ref={ref} />
}

function renderLinked(target: FocusTarget, done: () => void, children: ReactNode) {
  const scrolled: string[] = []
  Element.prototype.scrollIntoView = function scrollIntoView(this: Element) {
    scrolled.push(this.id)
  }
  render(<LinkScrollContext value={{ target, done }}>{children}</LinkScrollContext>)
  return scrolled
}

describe('useLinkedScroll', () => {
  afterEach(() => {
    Reflect.deleteProperty(Element.prototype, 'scrollIntoView')
  })

  it('scrolls to the unit holding a linked thread, then to the thread, and finishes there', () => {
    const done = vi.fn()

    const scrolled = renderLinked({ unitId: 2, elementId: 'thread-t' }, done, (
      <>
        <Linked id="unit-1" unitId={1} />
        <Linked id="unit-2" unitId={2} />
        <Linked id="thread-t" />
      </>
    ))

    expect(scrolled).toEqual(['unit-2', 'thread-t'])
    expect(done).toHaveBeenCalledTimes(1)
  })

  it('finishes on a linked unit', () => {
    const done = vi.fn()

    const scrolled = renderLinked({ unitId: 2, elementId: 'unit-2' }, done, <Linked id="unit-2" unitId={2} />)

    expect(scrolled).toEqual(['unit-2'])
    expect(done).toHaveBeenCalledTimes(1)
  })

  it('does nothing without a link', () => {
    const scrolled: string[] = []
    Element.prototype.scrollIntoView = function scrollIntoView(this: Element) {
      scrolled.push(this.id)
    }

    render(<Linked id="unit-2" unitId={2} />)

    expect(scrolled).toEqual([])
  })
})
