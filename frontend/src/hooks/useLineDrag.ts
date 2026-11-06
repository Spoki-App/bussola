import { useCallback, useEffect, useRef } from 'react'

import { edgeScrollStep } from '../review/lineDrag'

export function useLineDrag<T>(onMove: (target: T, y: number) => void, onEnd: () => void): (target: T, y: number) => void {
  const stopDrag = useRef<(() => void) | null>(null)
  const move = useRef(onMove)
  const end = useRef(onEnd)

  useEffect(() => {
    move.current = onMove
    end.current = onEnd
  })

  useEffect(() => () => stopDrag.current?.(), [])

  return useCallback((target: T, y: number) => {
    stopDrag.current?.()
    let pointerY = y
    let movedY = y
    let frame = 0
    const onMouseMove = (event: MouseEvent) => {
      pointerY = event.clientY
    }
    const stop = () => {
      cancelAnimationFrame(frame)
      window.removeEventListener('mousemove', onMouseMove)
      window.removeEventListener('mouseup', onMouseUp)
      stopDrag.current = null
    }
    const onMouseUp = () => {
      stop()
      end.current()
    }
    const tick = () => {
      const step = edgeScrollStep(pointerY, window.innerHeight)
      if (step !== 0) {
        window.scrollBy(0, step)
      }
      if (step !== 0 || pointerY !== movedY) {
        movedY = pointerY
        move.current(target, pointerY)
      }
      frame = requestAnimationFrame(tick)
    }
    window.addEventListener('mousemove', onMouseMove)
    window.addEventListener('mouseup', onMouseUp)
    frame = requestAnimationFrame(tick)
    stopDrag.current = stop
  }, [])
}
