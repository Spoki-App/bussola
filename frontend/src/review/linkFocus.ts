import { createContext, useContext, useEffect, useRef, useSyncExternalStore, type RefObject } from 'react'

import type { Thread, Unit } from '../api/types'
import { commentAnchors } from './pullRequestLink'
import { isInline } from './threadPlacement'

export interface LinkFocus {
  path: string | null
  line: number | null
  thread: string | null
  comment: string | null
}

export interface FocusTarget {
  unitId: number | null
  elementId: string
}

export interface LinkState {
  target: FocusTarget
  unitShown: boolean
  reached: boolean
}

export interface PendingLink {
  ready: boolean
  resolve: (units: Unit[]) => FocusTarget | null
}

export interface LinkScroll {
  current: () => LinkState | null
  subscribe: (listener: () => void) => () => void
  start: (target: FocusTarget) => void
  unitShown: () => void
  reached: () => void
  done: () => void
  place: (element: Element | null) => void
  movedByUser: () => boolean
}

type LinkRole = 'target' | 'approach' | 'holder' | 'settled' | null

const POSITIVE_NUMBER = /^[1-9]\d*$/

export const LinkScrollContext = createContext<LinkScroll | null>(null)

const FOCUS_PARAMS = ['path', 'line', 'thread', 'comment']

export function withoutLinkFocus(search: string): string {
  const params = new URLSearchParams(search)
  for (const name of FOCUS_PARAMS) {
    params.delete(name)
  }
  const rest = params.toString()
  return rest ? `?${rest}` : ''
}

export function linkFocusFromSearch(search: string): LinkFocus | null {
  const params = new URLSearchParams(search)
  const path = params.get('path')
  const line = params.get('line')
  const focus = {
    path,
    line: path !== null && line !== null && POSITIVE_NUMBER.test(line) ? Number(line) : null,
    thread: params.get('thread'),
    comment: params.get('comment'),
  }
  return focus.path === null && focus.thread === null && focus.comment === null ? null : focus
}

function linkedThread(focus: LinkFocus, threads: Thread[]): Thread | undefined {
  if (focus.thread !== null) {
    return threads.find((thread) => thread.id === focus.thread)
  }
  if (focus.comment === null) {
    return undefined
  }
  const anchors = commentAnchors(focus.comment)
  return threads.find((thread) => thread.comments.some((comment) => anchors.some((anchor) => comment.remote_url?.endsWith(anchor))))
}

interface Ranked {
  unit: Unit
  distance: number
  span: number
}

function rank(unit: Unit, line: number): Ranked | null {
  const { head_start: start, head_end: end } = unit
  if (start === null || end === null) {
    return null
  }
  return { unit, distance: Math.max(start - line, line - end, 0), span: end - start }
}

function closer(best: Ranked | undefined, candidate: Ranked): Ranked {
  if (!best) {
    return candidate
  }
  return best.distance < candidate.distance || (best.distance === candidate.distance && best.span <= candidate.span) ? best : candidate
}

function unitAt(units: Unit[], path: string, line: number | null): Unit | undefined {
  const inFile = units.filter((unit) => unit.path === path)
  const ranked = line === null ? [] : inFile.flatMap((unit) => rank(unit, line) ?? [])
  return ranked.reduce<Ranked | undefined>(closer, undefined)?.unit ?? inFile.at(0)
}

export function unitElementId(unitId: number): string {
  return `unit-${String(unitId)}`
}

export function threadElementId(threadId: string): string {
  return `thread-${threadId}`
}

export function resolveLinkFocus(focus: LinkFocus, units: Unit[], threads: Thread[]): FocusTarget | null {
  const thread = linkedThread(focus, threads)
  if (thread) {
    const unitId = isInline(thread) ? thread.anchor?.unit_id ?? null : null
    if (unitId === null) {
      return { unitId: null, elementId: threadElementId(thread.id) }
    }
    if (units.some((unit) => unit.id === unitId)) {
      return { unitId, elementId: threadElementId(thread.id) }
    }
  }
  const unit = focus.path === null ? undefined : unitAt(units, focus.path, focus.line)
  return unit ? { unitId: unit.id, elementId: unitElementId(unit.id) } : null
}

export function scrollToElement(id: string) {
  document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

export function createLinkScroll(): LinkScroll {
  let state: LinkState | null = null
  let placed: { element: Element; top: number } | null = null
  const listeners = new Set<() => void>()
  const change = (next: LinkState | null) => {
    if (next === state) {
      return
    }
    state = next
    listeners.forEach((listener) => { listener() })
  }
  return {
    current: () => state,
    subscribe: (listener) => {
      listeners.add(listener)
      return () => { listeners.delete(listener) }
    },
    start: (target) => { change({ target, unitShown: false, reached: false }) },
    unitShown: () => { change(state && { ...state, unitShown: true }) },
    reached: () => { change(state && { ...state, reached: true }) },
    done: () => { change(null) },
    place: (element) => {
      if (element) {
        element.scrollIntoView({ block: 'start' })
        placed = { element, top: element.getBoundingClientRect().top }
      }
    },
    movedByUser: () => placed !== null && placed.element.isConnected && Math.abs(placed.element.getBoundingClientRect().top - placed.top) > MOVE_TOLERANCE_PX,
  }
}

function linkRole(state: LinkState | null, elementId: string, unitId: number | null, settled: boolean): LinkRole {
  if (state === null || state.reached) {
    return null
  }
  if (state.target.elementId === elementId) {
    return unitId !== null && !settled ? 'approach' : 'target'
  }
  if (unitId === null || state.target.unitId !== unitId) {
    return null
  }
  if (!state.unitShown) {
    return 'holder'
  }
  return settled ? 'settled' : null
}

const noLink = () => () => undefined

const USER_INPUT_EVENTS = ['wheel', 'touchmove', 'keydown', 'mousedown'] as const
const MOVE_TOLERANCE_PX = 2
const FOLLOW_AFTER_REACHED_MS = 10_000

function linkAnchor(state: LinkState): Element | null {
  const { elementId, unitId } = state.target
  return document.getElementById(elementId) ?? (unitId === null ? null : document.getElementById(unitElementId(unitId)))
}

export function followLink(link: LinkScroll): () => void {
  const keepInView = new ResizeObserver(() => {
    const state = link.current()
    if (state?.reached) {
      link.place(linkAnchor(state))
    }
  })
  keepInView.observe(document.body)
  let deadline: number | undefined
  const unsubscribe = link.subscribe(() => {
    const state = link.current()
    if (!state?.reached || deadline !== undefined) {
      return
    }
    deadline = window.setTimeout(end, FOLLOW_AFTER_REACHED_MS)
    for (let element = linkAnchor(state); element; element = element.parentElement) {
      keepInView.observe(element)
    }
  })
  const stop = () => {
    unsubscribe()
    window.clearTimeout(deadline)
    keepInView.disconnect()
    window.removeEventListener('scroll', endIfMoved)
    for (const event of USER_INPUT_EVENTS) {
      window.removeEventListener(event, end)
    }
  }
  const end = () => {
    stop()
    link.done()
  }
  const endIfMoved = () => {
    if (link.movedByUser()) {
      end()
    }
  }
  for (const event of USER_INPUT_EVENTS) {
    window.addEventListener(event, end, { passive: true })
  }
  window.addEventListener('scroll', endIfMoved, { passive: true })
  return stop
}

export function useLinkedScroll<T extends HTMLElement>(elementId: string, unitId: number | null = null, settled = false): RefObject<T | null> {
  const link = useContext(LinkScrollContext)
  const ref = useRef<T>(null)
  const role = useSyncExternalStore(link?.subscribe ?? noLink, () => linkRole(link?.current() ?? null, elementId, unitId, settled))
  useEffect(() => {
    if (!link || role === null) {
      return
    }
    const now = linkRole(link.current(), elementId, unitId, settled)
    if (now === 'target' || now === 'approach' || now === 'holder') {
      link.place(ref.current)
    }
    if (now === 'holder') {
      link.unitShown()
    } else if (now === 'target' || now === 'settled') {
      link.reached()
    }
  }, [link, role, elementId, unitId, settled])
  return ref
}
