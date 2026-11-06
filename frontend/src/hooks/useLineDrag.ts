import { useCallback, useEffect, useRef } from 'react'

import { edgeScrollStep } from '../review/lineDrag'

interface Drag {
  x: number
  y: number
  frame: number
}

export function useLineDrag(onMove: (x: number, y: number) => void, onEnd: () => void): (x: number, y: number) => void {
  const drag = useRef<Drag | null>(null)
  const move = useRef(onMove)
  const end = useRef(onEnd)

  useEffect(() => {
    move.current = onMove
    end.current = onEnd
  })

  useEffect(() => {
    const onMouseMove = (event: MouseEvent) => {
      if (drag.current) {
        drag.current.y = event.clientY
        move.current(drag.current.x, event.clientY)
      }
    }
    const onMouseUp = () => {
      if (drag.current) {
        cancelAnimationFrame(drag.current.frame)
        drag.current = null
        end.current()
      }
    }
    window.addEventListener('mousemove', onMouseMove)
    window.addEventListener('mouseup', onMouseUp)
    return () => {
      window.removeEventListener('mousemove', onMouseMove)
      window.removeEventListener('mouseup', onMouseUp)
      if (drag.current) {
        cancelAnimationFrame(drag.current.frame)
      }
    }
  }, [])

  return useCallback((x: number, y: number) => {
    const scroll = () => {
      const current = drag.current
      if (!current) {
        return
      }
      const step = edgeScrollStep(current.y, window.innerHeight)
      if (step !== 0) {
        window.scrollBy(0, step)
        move.current(current.x, current.y)
      }
      current.frame = requestAnimationFrame(scroll)
    }
    drag.current = { x, y, frame: requestAnimationFrame(scroll) }
  }, [])
}
