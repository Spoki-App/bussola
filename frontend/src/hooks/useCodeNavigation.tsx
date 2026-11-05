import { useQueryClient, type QueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react'

import { describeError } from '../api/client'
import { UNSETTLED_ANSWER_MS, navigationQuery, prepareNavigation, usePrepareNavigation, type CodeLocation, type NavigationRequest, type NavigationResult, type NavigationTarget, type ServerHint } from '../api/navigation'
import { directTarget, isNavigable, type NavigationClick, type ScreenPoint, type UnitTarget } from '../review/codeNavigation'
import { readStored, writeStored } from '../settings/storage'
import { NavigationPopup, type PopupState } from '../components/NavigationPopup'
import { ServerHintNote } from '../components/ServerHintNote'
import { SourceModal } from '../components/SourceModal'

const BUILDING_POLL_MS = 400
const HINT_KEY_PREFIX = 'bussola.serverHint.'

export type CodeTarget = Pick<NavigationTarget, 'path' | 'line' | 'side' | 'unit_id'>

export interface CodeNavigation {
  navigate: (click: NavigationClick) => void
  show: (target: CodeTarget) => void
  canNavigate: (request: NavigationRequest) => Promise<boolean>
  target: UnitTarget | null
  element: ReactNode
}

interface Popup {
  state: PopupState
  point: ScreenPoint
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

async function resolveNavigation(queryClient: QueryClient, reviewId: number, revisionId: number | undefined, request: NavigationRequest, current: () => boolean, onBuilding: () => void): Promise<NavigationResult | null> {
  const first = await queryClient.query(navigationQuery(reviewId, revisionId, request))
  if (first.ready || !current()) {
    return current() ? first : null
  }
  onBuilding()
  while (!(await prepareNavigation(reviewId, revisionId, request.side)).ready) {
    if (!current()) {
      return null
    }
    await delay(BUILDING_POLL_MS)
  }
  const result = await queryClient.query({ ...navigationQuery(reviewId, revisionId, request), staleTime: 0 })
  return current() ? result : null
}

function takeHint(hint: ServerHint | null): ServerHint | null {
  if (hint === null || readStored(HINT_KEY_PREFIX + hint.family) !== null) {
    return null
  }
  writeStored(HINT_KEY_PREFIX + hint.family, 'shown')
  return hint
}

export function useCodeNavigation(reviewId: number, revisionId: number | undefined, hasUnit: (unitId: number) => boolean): CodeNavigation {
  usePrepareNavigation(reviewId, revisionId)
  const queryClient = useQueryClient()
  const unitShown = useRef(hasUnit)
  useEffect(() => {
    unitShown.current = hasUnit
  })
  const [popup, setPopup] = useState<Popup | null>(null)
  const [stack, setStack] = useState<CodeLocation[]>([])
  const [target, setTarget] = useState<UnitTarget | null>(null)
  const [hint, setHint] = useState<ServerHint | null>(null)
  const latest = useRef(0)
  const inPage = useCallback((found: CodeTarget): found is CodeTarget & { unit_id: number } => found.unit_id !== null && unitShown.current(found.unit_id), [])

  const reveal = useCallback(
    (found: CodeTarget) => {
      if (inPage(found)) {
        setStack([])
        setTarget({ unitId: found.unit_id, line: found.line, side: found.side })
        return
      }
      setStack((current) => [...current, { path: found.path, line: found.line, side: found.side }])
    },
    [inPage],
  )

  const canNavigate = useCallback(
    (request: NavigationRequest) => {
      const query = navigationQuery(reviewId, revisionId, request)
      const state = queryClient.getQueryState(query.queryKey)
      if (state?.status === 'error' && Date.now() - state.errorUpdatedAt < UNSETTLED_ANSWER_MS) {
        return Promise.resolve(false)
      }
      return queryClient.query(query).then(isNavigable, () => false)
    },
    [queryClient, reviewId, revisionId],
  )

  const closePopup = useCallback(() => {
    latest.current += 1
    setPopup(null)
  }, [])

  const navigate = useCallback(
    (click: NavigationClick) => {
      latest.current += 1
      const id = latest.current
      const current = () => latest.current === id
      const { point, ...request } = click
      setPopup({ point, state: { status: 'loading', building: false } })
      resolveNavigation(queryClient, reviewId, revisionId, request, current, () => {
        setPopup({ point, state: { status: 'loading', building: true } })
      })
        .then((result) => {
          if (result === null) {
            return
          }
          const newHint = takeHint(result.server_hint)
          if (newHint) {
            setHint(newHint)
          }
          const direct = directTarget(result)
          if (result.symbol === null || direct) {
            setPopup(null)
            if (direct) {
              reveal(direct)
            }
            return
          }
          setPopup({ point, state: { status: 'ready', result } })
        })
        .catch((error: unknown) => {
          if (current()) {
            setPopup({ point, state: { status: 'error', message: describeError(error) } })
          }
        })
    },
    [queryClient, reviewId, revisionId, reveal],
  )

  const element = (
    <>
      {stack.length > 0 && (
        <SourceModal
          reviewId={reviewId}
          revisionId={revisionId}
          stack={stack}
          onBack={() => { setStack((current) => current.slice(0, -1)) }}
          onClose={() => { setStack([]) }}
          onNavigate={navigate}
          canNavigate={canNavigate}
        />
      )}
      {popup && (
        <NavigationPopup
          state={popup.state}
          point={popup.point}
          onClose={closePopup}
          onChoose={(chosen) => {
            closePopup()
            reveal(chosen)
          }}
        />
      )}
      {hint && !popup && stack.length === 0 && <ServerHintNote hint={hint} onDismiss={() => { setHint(null) }} />}
    </>
  )

  return { navigate, show: reveal, canNavigate, target, element }
}
