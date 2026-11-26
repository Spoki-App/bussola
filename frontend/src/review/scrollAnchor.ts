export interface ScrollAnchor {
  element: Element
  offset: number
  height: number
}

function staysInPlace(element: Element): boolean {
  const position = getComputedStyle(element).position
  return position === 'sticky' || position === 'fixed'
}

function topChild(parent: Element, top: number): Element | undefined {
  return [...parent.children].find((child) => {
    const box = child.getBoundingClientRect()
    return box.height > 0 && box.bottom > top && !staysInPlace(child)
  })
}

export function captureScrollAnchor(scroller: Element, content: Element, inset = 0): ScrollAnchor | null {
  if (scroller.scrollTop === 0) {
    return null
  }
  const top = scroller.getBoundingClientRect().top + inset
  let anchor: Element | null = null
  for (let child = topChild(content, top); child; child = topChild(child, top)) {
    anchor = child
  }
  if (!anchor) {
    return null
  }
  const box = anchor.getBoundingClientRect()
  return { element: anchor, offset: box.top - top, height: box.height }
}

export function restoreScrollAnchor(scroller: Element, anchor: ScrollAnchor | null, inset = 0) {
  if (!anchor || !scroller.contains(anchor.element)) {
    scroller.scrollTop = 0
    return
  }
  const box = anchor.element.getBoundingClientRect()
  const offset = anchor.offset < 0 && anchor.height > 0 ? (anchor.offset * box.height) / anchor.height : anchor.offset
  scroller.scrollTop += box.top - scroller.getBoundingClientRect().top - inset - offset
}
