import type { Thread, Unit } from '../api/types'
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
  fallbackId: string | null
  inPanel: boolean
}

export interface AddRepositoryRequest {
  repository: string
  then: string
}

const MAX_PATH_LENGTH = 1024
const POSITIVE_NUMBER = /^[1-9]\d{0,8}$/
const THREAD_ID = /^[0-9a-f]{32}$/
const COMMENT_ID = /^[1-9]\d{0,19}$/
const REPOSITORY = /^[\w.-]{1,100}\/[\w.-]{1,100}$/
const PULL_REQUEST_PATH = /^\/github\.com\/[\w.-]+\/[\w.-]+\/pull\/\d+(?:\/[^?#]*)?(?:\?[^#]*)?$/
const ADD_REPOSITORY_PARAM = 'add_repo'
const THEN_PARAM = 'then'
const FOCUS_PARAMS = ['path', 'line', 'thread', 'comment'] as const
const SCROLL_POLL_MS = 100
const SCROLL_TIMEOUT_MS = 5000

function matching(value: string | null, pattern: RegExp): string | null {
  return value !== null && pattern.test(value) ? value : null
}

function validPath(value: string | null): string | null {
  if (value === null || value.length > MAX_PATH_LENGTH || value.startsWith('/')) {
    return null
  }
  return value.split('/').some((segment) => segment === '' || segment === '.' || segment === '..') ? null : value
}

export function linkFocusFromSearch(search: string): LinkFocus | null {
  const params = new URLSearchParams(search)
  const path = validPath(params.get('path'))
  const line = path === null ? null : matching(params.get('line'), POSITIVE_NUMBER)
  const focus = {
    path,
    line: line === null ? null : Number(line),
    thread: matching(params.get('thread'), THREAD_ID),
    comment: matching(params.get('comment'), COMMENT_ID),
  }
  return focus.path === null && focus.thread === null && focus.comment === null ? null : focus
}

export function focusSearch(focus: LinkFocus | null): string {
  if (focus === null) {
    return ''
  }
  const params = new URLSearchParams()
  for (const key of FOCUS_PARAMS) {
    const value = focus[key]
    if (value !== null) {
      params.set(key, String(value))
    }
  }
  return `?${params.toString()}`
}

function linkedThread(focus: LinkFocus, threads: Thread[]): Thread | undefined {
  if (focus.thread !== null) {
    return threads.find((thread) => thread.id === focus.thread)
  }
  const anchor = `#discussion_r${focus.comment ?? ''}`
  return focus.comment === null ? undefined : threads.find((thread) => thread.comments.some((comment) => comment.remote_url?.endsWith(anchor)))
}

function unitAt(units: Unit[], path: string, line: number | null): Unit | undefined {
  const inFile = units.filter((unit) => unit.path === path)
  const containing = line === null ? undefined : inFile.find((unit) => unit.head_start !== null && unit.head_end !== null && unit.head_start <= line && line <= unit.head_end)
  return containing ?? inFile.at(0)
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
    return {
      unitId: shown ? unitId : null,
      elementId: threadElementId(thread.id),
      fallbackId: shown ? unitElementId(unitId) : null,
      inPanel: !shown,
    }
  }
  const unit = focus.path === null ? undefined : unitAt(units, focus.path, focus.line)
  return unit ? { unitId: unit.id, elementId: unitElementId(unit.id), fallbackId: null, inPanel: false } : null
}

export function scrollWhenPresent(target: FocusTarget, timeoutMs = SCROLL_TIMEOUT_MS): () => void {
  const deadline = Date.now() + timeoutMs
  let fallbackShown = false
  const timer = window.setInterval(() => {
    const element = document.getElementById(target.elementId)
    if (element) {
      window.clearInterval(timer)
      element.scrollIntoView({ behavior: 'smooth', block: 'start' })
      return
    }
    const fallback = target.fallbackId === null || fallbackShown ? null : document.getElementById(target.fallbackId)
    if (fallback) {
      fallbackShown = true
      fallback.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }
    if (Date.now() >= deadline) {
      window.clearInterval(timer)
    }
  }, SCROLL_POLL_MS)
  return () => { window.clearInterval(timer) }
}

export function pullRequestRepository(url: string): string | null {
  const match = /^https:\/\/github\.com\/([\w.-]+\/[\w.-]+)\/pull\/\d+/.exec(url)
  return match ? match[1] : null
}

export function addRepositoryPath(repository: string, then: string): string {
  return `/?${new URLSearchParams({ [ADD_REPOSITORY_PARAM]: repository, [THEN_PARAM]: then }).toString()}`
}

export function addRepositoryRequestFromSearch(search: string): AddRepositoryRequest | null {
  const params = new URLSearchParams(search)
  const repository = matching(params.get(ADD_REPOSITORY_PARAM), REPOSITORY)
  const then = matching(params.get(THEN_PARAM), PULL_REQUEST_PATH)
  return repository && then ? { repository, then } : null
}
