import { useEffect, useRef, useState, type ReactNode } from 'react'

const SIDES = ['old', 'new'] as const
type Side = (typeof SIDES)[number]

const CODE_COLUMN: Record<Side, number> = { old: 1, new: 3 }

interface Lane {
  left: number
  width: number
  content: number
}

type Lanes = Partial<Record<Side, Lane>>

function sideOf(cell: Element | null): Side | undefined {
  return cell instanceof HTMLTableCellElement ? SIDES.find((side) => CODE_COLUMN[side] === cell.cellIndex) : undefined
}

function codeCells(table: HTMLTableElement, side: Side): HTMLTableCellElement[] {
  return [...table.querySelectorAll<HTMLTableCellElement>('tr.diff-line > td.diff-code')].filter((cell) => sideOf(cell) === side)
}

function laneOf(table: HTMLTableElement, side: Side, offset: number): Lane | null {
  const cells = codeCells(table, side)
  const first = cells.at(0)
  if (!first) {
    return null
  }
  return { left: first.offsetLeft, width: first.offsetWidth, content: Math.max(...cells.map((cell) => cell.scrollWidth)) + offset }
}

function horizontalDelta(event: WheelEvent): number {
  if (Math.abs(event.deltaX) > Math.abs(event.deltaY)) {
    return event.deltaX
  }
  return event.shiftKey ? event.deltaY : 0
}

export function SplitScroll({ children }: { children: ReactNode }) {
  const root = useRef<HTMLDivElement>(null)
  const bars = useRef<Partial<Record<Side, HTMLDivElement | null>>>({})
  const offsets = useRef<Record<Side, number>>({ old: 0, new: 0 })
  const [lanes, setLanes] = useState<Lanes>({})

  useEffect(() => {
    const table = root.current?.querySelector('table')
    if (!table) {
      return undefined
    }
    const measure = () => {
      const next: Lanes = {}
      for (const side of SIDES) {
        const lane = laneOf(table, side, offsets.current[side])
        if (lane && lane.content > lane.width) {
          next[side] = lane
        } else {
          offsets.current[side] = 0
          table.style.setProperty(`--scroll-${side}`, '0px')
        }
      }
      setLanes(next)
    }
    const onWheel = (event: WheelEvent) => {
      const delta = horizontalDelta(event)
      const side = sideOf(event.target instanceof Element ? event.target.closest('td.diff-code') : null)
      const bar = side ? bars.current[side] : null
      if (!bar || delta === 0) {
        return
      }
      const before = bar.scrollLeft
      bar.scrollLeft += delta
      if (bar.scrollLeft !== before) {
        event.preventDefault()
      }
    }
    const observer = new ResizeObserver(measure)
    observer.observe(table)
    measure()
    table.addEventListener('wheel', onWheel, { passive: false })
    return () => {
      observer.disconnect()
      table.removeEventListener('wheel', onWheel)
    }
  }, [])

  const follow = (side: Side) => {
    const offset = bars.current[side]?.scrollLeft ?? 0
    offsets.current[side] = offset
    root.current?.querySelector('table')?.style.setProperty(`--scroll-${side}`, `${String(offset)}px`)
  }

  return (
    <div ref={root} className="split-scroll">
      {children}
      <div className="split-scrollbars">
        {SIDES.map((side) => {
          const lane = lanes[side]
          return lane ? (
            <div
              key={side}
              ref={(bar) => { bars.current[side] = bar }}
              className="split-scrollbar"
              data-side={side}
              style={{ left: lane.left, width: lane.width }}
              onScroll={() => { follow(side) }}
            >
              <div style={{ width: lane.content }} />
            </div>
          ) : null
        })}
      </div>
    </div>
  )
}
