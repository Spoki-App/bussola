import { createContext, useContext, useEffect, useRef, useSyncExternalStore, type RefObject } from 'react'

import type { Thread, Unit } from '../api/types'
import { pullRequestRepository, pullRequestUrlFromPath } from './pullRequestLink'
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
}

export interface LinkScroll {
  current: () => LinkState | null
  subscribe: (listener: () => void) => () => void
  start: (target: FocusTarget) => void
  unitShown: () => void
  done: () => void
}

type LinkRole = 'target' | 'approach' | 'holder' | 'settled' | null

export interface AddRepositoryRequest {
  repository: string
  then: string
}

const POSITIVE_NUMBER = /^[1-9]\d*$/
const ADD_REPOSITORY_PARAM = 'add_repo'

export const LinkScrollContext = createContext<LinkScroll | null>(null)

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
  const anchor = `#discussion_r${focus.comment}`
  return threads.find((thread) => thread.comments.some((comment) => comment.remote_url?.endsWith(anchor)))
}

function headSpan(unit: Unit, line: number): number | null {
  return unit.head_start !== null && unit.head_end !== null && unit.head_start <= line && line <= unit.head_end ? unit.head_end - unit.head_start : null
}

function unitAt(units: Unit[], path: string, line: number | null): Unit | undefined {
  const inFile = units.filter((unit) => unit.path === path)
  const containing = line === null ? [] : inFile.flatMap((unit) => {
    const span = headSpan(unit, line)
    return span === null ? [] : [{ unit, span }]
  })
  const narrowest = containing.reduce<{ unit: Unit; span: number } | undefined>((best, candidate) => (best && best.span <= candidate.span ? best : candidate), undefined)
  return narrowest?.unit ?? inFile.at(0)
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
  const listeners = new Set<() => void>()
  const change = (next: LinkState | null) => {
    state = next
    listeners.forEach((listener) => { listener() })
  }
  return {
    current: () => state,
    subscribe: (listener) => {
      listeners.add(listener)
      return () => { listeners.delete(listener) }
    },
    start: (target) => { change({ target, unitShown: false }) },
    unitShown: () => { change(state && { ...state, unitShown: true }) },
    done: () => { change(null) },
  }
}

function linkRole(state: LinkState | null, elementId: string, unitId: number | null, settled: boolean): LinkRole {
  if (state === null) {
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
      ref.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }
    if (now === 'holder') {
      link.unitShown()
    } else if (now === 'target' || now === 'settled') {
      link.done()
    }
  }, [link, role, elementId, unitId, settled])
  return ref
}

export function addRepositoryPath(then: string): string {
  return `/?${new URLSearchParams({ [ADD_REPOSITORY_PARAM]: then }).toString()}`
}

export function addRepositoryRequestFromSearch(search: string): AddRepositoryRequest | null {
  const then = new URLSearchParams(search).get(ADD_REPOSITORY_PARAM)
  const url = then === null ? null : pullRequestUrlFromPath(then.split('?')[0])
  const repository = url === null ? null : pullRequestRepository(url)
  return then !== null && repository !== null ? { repository, then } : null
}
