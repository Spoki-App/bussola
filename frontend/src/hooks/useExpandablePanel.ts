import { useCallback, useEffect, useLayoutEffect, useRef, useState, type KeyboardEvent } from 'react'

import { captureScrollAnchor, restoreScrollAnchor, type ScrollAnchor } from '../review/scrollAnchor'
import { isTyping } from './useKeyboardShortcuts'

const FOCUSABLE = 'a[href], summary, button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [tabindex]:not([tabindex="-1"]), [contenteditable="true"]'

export function focusableIn(root: Element): HTMLElement[] {
  return [...root.querySelectorAll<HTMLElement>(FOCUSABLE)].filter((element) => !element.closest('[hidden], [inert], details:not([open]) > :not(summary)'))
}

function insideOtherDialog(target: EventTarget | null): boolean {
  return target instanceof Element && target.closest('dialog[open]') !== null
}

export function useExpandablePanel() {
  const column = useRef<HTMLElement>(null)
  const frame = useRef<HTMLDivElement>(null)
  const trigger = useRef<HTMLButtonElement>(null)
  const closeButton = useRef<HTMLButtonElement>(null)
  const header = useRef<HTMLDivElement>(null)
  const content = useRef<HTMLDivElement>(null)
  const [expanded, setExpanded] = useState(false)
  const moving = useRef<{ anchor: ScrollAnchor | null } | null>(null)

  const scrollPlace = useCallback((open: boolean) => ({ scroller: open ? frame.current : column.current, inset: open ? (header.current?.offsetHeight ?? 0) : 0 }), [])

  const change = useCallback(
    (next: boolean) => {
      if (next === expanded) {
        return
      }
      const { scroller, inset } = scrollPlace(expanded)
      moving.current = { anchor: scroller && content.current ? captureScrollAnchor(scroller, content.current, inset) : null }
      setExpanded(next)
    },
    [expanded, scrollPlace],
  )
  const expand = useCallback(() => { change(true) }, [change])
  const collapse = useCallback(() => { change(false) }, [change])

  useLayoutEffect(() => {
    const moved = moving.current
    if (!moved) {
      return
    }
    moving.current = null
    const { scroller, inset } = scrollPlace(expanded)
    if (scroller) {
      restoreScrollAnchor(scroller, moved.anchor, inset)
    }
    if (!expanded) {
      trigger.current?.focus({ preventScroll: true })
    } else if (!frame.current?.contains(document.activeElement)) {
      closeButton.current?.focus({ preventScroll: true })
    }
  }, [expanded, scrollPlace])

  useEffect(() => {
    if (!expanded) {
      return undefined
    }
    const onKeyDown = (event: globalThis.KeyboardEvent) => {
      if (event.key === 'Escape' && !event.defaultPrevented && !isTyping(event.target) && !insideOtherDialog(event.target)) {
        event.preventDefault()
        collapse()
      }
    }
    const onFocusIn = (event: FocusEvent) => {
      const root = frame.current
      if (root && event.target instanceof Node && !root.contains(event.target) && !insideOtherDialog(event.target)) {
        const inside = focusableIn(root).at(0) ?? closeButton.current
        inside?.focus({ preventScroll: true })
      }
    }
    window.addEventListener('keydown', onKeyDown)
    document.addEventListener('focusin', onFocusIn)
    return () => {
      window.removeEventListener('keydown', onKeyDown)
      document.removeEventListener('focusin', onFocusIn)
    }
  }, [expanded, collapse])

  const keepTabInside = useCallback(
    (event: KeyboardEvent<HTMLElement>) => {
      const root = frame.current
      if (!expanded || !root || event.key !== 'Tab' || event.defaultPrevented) {
        return
      }
      const items = focusableIn(root)
      const first = items.at(0)
      const last = items.at(-1)
      if (!first || !last) {
        return
      }
      const active = document.activeElement
      if (event.shiftKey && (active === first || !root.contains(active))) {
        event.preventDefault()
        last.focus()
      } else if (!event.shiftKey && active === last) {
        event.preventDefault()
        first.focus()
      }
    },
    [expanded],
  )

  return { expanded, expand, collapse, columnRef: column, frameRef: frame, triggerRef: trigger, closeButtonRef: closeButton, headerRef: header, contentRef: content, keepTabInside }
}
