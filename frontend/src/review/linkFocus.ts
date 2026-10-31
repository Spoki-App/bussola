import { createContext, useContext, useEffect, useRef, type RefObject } from 'react'

import type { Thread, Unit } from '../api/types'
import { pullRequestUrlFromPath } from './pullRequestLink'
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

export interface LinkScroll {
  target: FocusTarget
  done: () => void
}

export interface AddRepositoryRequest {
  repository: string
  then: string
}

const POSITIVE_NUMBER = /^[1-9]\d*$/
const REPOSITORY = /^[\w.-]{1,100}\/[\w.-]{1,100}$/
const ADD_REPOSITORY_PARAM = 'add_repo'
const THEN_PARAM = 'then'

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
    const shown = unitId !== null && units.some((unit) => unit.id === unitId)
    return { unitId: shown ? unitId : null, elementId: threadElementId(thread.id) }
  }
  const unit = focus.path === null ? undefined : unitAt(units, focus.path, focus.line)
  return unit ? { unitId: unit.id, elementId: unitElementId(unit.id) } : null
}

export function scrollToElement(id: string) {
  document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

export function useLinkedScroll<T extends HTMLElement>(elementId: string, unitId: number | null = null): RefObject<T | null> {
  const link = useContext(LinkScrollContext)
  const ref = useRef<T>(null)
  const isTarget = link?.target.elementId === elementId
  const holdsTarget = unitId !== null && link?.target.unitId === unitId
  useEffect(() => {
    if (!link || !(isTarget || holdsTarget)) {
      return
    }
    ref.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    if (isTarget) {
      link.done()
    }
  }, [link, isTarget, holdsTarget])
  return ref
}

export function addRepositoryPath(repository: string, then: string): string {
  return `/?${new URLSearchParams({ [ADD_REPOSITORY_PARAM]: repository, [THEN_PARAM]: then }).toString()}`
}

export function addRepositoryRequestFromSearch(search: string): AddRepositoryRequest | null {
  const params = new URLSearchParams(search)
  const repository = params.get(ADD_REPOSITORY_PARAM)
  const then = params.get(THEN_PARAM)
  const thenPath = then?.split('?')[0] ?? ''
  return repository !== null && REPOSITORY.test(repository) && then !== null && pullRequestUrlFromPath(thenPath) !== null ? { repository, then } : null
}
