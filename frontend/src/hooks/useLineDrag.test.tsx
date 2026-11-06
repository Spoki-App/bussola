import { fireEvent, render } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { useLineDrag } from './useLineDrag'

function setup() {
  const onMove = vi.fn()
  const onEnd = vi.fn()
  let start: (target: string, y: number) => void = () => undefined
  function Harness() {
    start = useLineDrag(onMove, onEnd)
    return null
  }
  const view = render(<Harness />)
  start('gutter', 100)
  return { onEnd, unmount: view.unmount }
}

describe('useLineDrag', () => {
  it('ends the drag on mouseup', () => {
    const { onEnd } = setup()

    fireEvent.mouseUp(window)
    fireEvent.mouseUp(window)

    expect(onEnd).toHaveBeenCalledOnce()
  })

  it('ends the drag when the pointer moves with the button already released', () => {
    const { onEnd } = setup()

    fireEvent.mouseMove(window, { clientY: 120, buttons: 1 })
    expect(onEnd).not.toHaveBeenCalled()
    fireEvent.mouseMove(window, { clientY: 140, buttons: 0 })

    expect(onEnd).toHaveBeenCalledOnce()
  })

  it('ends the drag when the window loses focus', () => {
    const { onEnd } = setup()

    fireEvent.blur(window)

    expect(onEnd).toHaveBeenCalledOnce()
  })

  it('ends the drag when the view goes away mid-drag', () => {
    const { onEnd, unmount } = setup()

    unmount()

    expect(onEnd).toHaveBeenCalledOnce()
  })
})
