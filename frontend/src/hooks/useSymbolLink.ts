import { useCallback, useEffect, useRef } from 'react'

import { rangeOf, symbolAt, type SymbolSpan } from '../review/codeNavigation'

export const LINK_NAME = 'navigation-link'
export const CHECK_DELAY_MS = 80

export type SymbolCheck = (column: number) => Promise<boolean>

export interface SymbolLink {
  hover: (event: PointerState, code: Element, check: SymbolCheck) => void
  leave: () => void
}

interface PointerState {
  clientX: number
  clientY: number
  metaKey: boolean
  ctrlKey: boolean
}

interface Pointer {
  code: Element
  x: number
  y: number
  check: SymbolCheck
}

interface Hovered {
  code: Element
  start: number
}

function hasModifier(event: { metaKey: boolean; ctrlKey: boolean }): boolean {
  return event.metaKey || event.ctrlKey
}

function supportsHighlights(): boolean {
  return typeof CSS !== 'undefined' && 'highlights' in CSS
}

function showLink(code: Element, span: SymbolSpan) {
  const range = rangeOf(code, span)
  if (!range) {
    return
  }
  code.classList.add(LINK_NAME)
  if (supportsHighlights()) {
    CSS.highlights.set(LINK_NAME, new Highlight(range))
  }
}

function hideLink(code: Element) {
  code.classList.remove(LINK_NAME)
  if (supportsHighlights()) {
    CSS.highlights.delete(LINK_NAME)
  }
}

export function useSymbolLink(): SymbolLink {
  const pointer = useRef<Pointer | null>(null)
  const hovered = useRef<Hovered | null>(null)
  const timer = useRef<number | undefined>(undefined)

  const clear = useCallback(() => {
    window.clearTimeout(timer.current)
    if (hovered.current) {
      hideLink(hovered.current.code)
      hovered.current = null
    }
  }, [])

  const update = useCallback(
    (modifier: boolean) => {
      const at = pointer.current
      const span = at && modifier ? symbolAt(at.code, at.x, at.y) : null
      if (!at || !span) {
        clear()
        return
      }
      if (hovered.current?.code === at.code && hovered.current.start === span.start) {
        return
      }
      clear()
      const current = { code: at.code, start: span.start }
      hovered.current = current
      timer.current = window.setTimeout(() => {
        void at.check(span.start).then((navigable) => {
          if (navigable && hovered.current === current) {
            showLink(at.code, span)
          }
        })
      }, CHECK_DELAY_MS)
    },
    [clear],
  )

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (pointer.current) {
        update(hasModifier(event))
      }
    }
    window.addEventListener('keydown', onKey)
    window.addEventListener('keyup', onKey)
    window.addEventListener('blur', clear)
    return () => {
      window.removeEventListener('keydown', onKey)
      window.removeEventListener('keyup', onKey)
      window.removeEventListener('blur', clear)
      clear()
    }
  }, [update, clear])

  const hover = useCallback(
    (event: PointerState, code: Element, check: SymbolCheck) => {
      pointer.current = { code, x: event.clientX, y: event.clientY, check }
      update(hasModifier(event))
    },
    [update],
  )

  const leave = useCallback(() => {
    pointer.current = null
    clear()
  }, [clear])

  return { hover, leave }
}
