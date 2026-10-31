import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react'

import { describeError } from '../api/client'
import { fetchNavigation, prepareNavigation, usePrepareNavigation, type CodeLocation, type NavigationRequest, type NavigationResult, type NavigationTarget, type ServerHint } from '../api/navigation'
import { directTarget, type NavigationClick, type ScreenPoint, type UnitTarget } from '../review/codeNavigation'
import { readStored, writeStored } from '../settings/storage'
import { NavigationPopup, type PopupState } from '../components/NavigationPopup'
import { ServerHintNote } from '../components/ServerHintNote'
import { SourceModal } from '../components/SourceModal'

const BUILDING_POLL_MS = 400
const HINT_KEY_PREFIX = 'bussola.serverHint.'
const MODIFIER_CLASS = 'navigation-modifier'
const MODIFIER_KEYS = new Set(['Meta', 'Control'])

export interface CodeNavigation {
  navigate: (click: NavigationClick) => void
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

async function resolveNavigation(reviewId: number, revisionId: number | undefined, request: NavigationRequest, current: () => boolean, onBuilding: () => void): Promise<NavigationResult | null> {
  const first = await fetchNavigation(reviewId, revisionId, request)
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
  const result = await fetchNavigation(reviewId, revisionId, request)
  return current() ? result : null
}

function takeHint(hint: ServerHint | null): ServerHint | null {
  if (hint === null || readStored(HINT_KEY_PREFIX + hint.family) !== null) {
    return null
  }
  writeStored(HINT_KEY_PREFIX + hint.family, 'shown')
  return hint
}

function useModifierCursor() {
  useEffect(() => {
    const update = (event: KeyboardEvent) => {
      if (MODIFIER_KEYS.has(event.key)) {
        document.body.classList.toggle(MODIFIER_CLASS, event.type === 'keydown')
      }
    }
    const clear = () => {
      document.body.classList.remove(MODIFIER_CLASS)
    }
    window.addEventListener('keydown', update)
    window.addEventListener('keyup', update)
    window.addEventListener('blur', clear)
    return () => {
      window.removeEventListener('keydown', update)
      window.removeEventListener('keyup', update)
      window.removeEventListener('blur', clear)
      clear()
    }
  }, [])
}

export function useCodeNavigation(reviewId: number, revisionId: number | undefined, hasUnit: (unitId: number) => boolean): CodeNavigation {
  usePrepareNavigation(reviewId, revisionId)
  const unitShown = useRef(hasUnit)
  useEffect(() => {
    unitShown.current = hasUnit
  })
  useModifierCursor()
  const [popup, setPopup] = useState<Popup | null>(null)
  const [stack, setStack] = useState<CodeLocation[]>([])
  const [target, setTarget] = useState<UnitTarget | null>(null)
  const [hint, setHint] = useState<ServerHint | null>(null)
  const latest = useRef(0)
  const inPage = useCallback((found: NavigationTarget): found is NavigationTarget & { unit_id: number } => found.unit_id !== null && unitShown.current(found.unit_id), [])

  const reveal = useCallback(
    (found: NavigationTarget) => {
      if (inPage(found)) {
        setStack([])
        setTarget({ unitId: found.unit_id, line: found.line, side: found.side })
        return
      }
      setStack((current) => [...current, { path: found.path, line: found.line, side: found.side }])
    },
    [inPage],
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
      resolveNavigation(reviewId, revisionId, request, current, () => {
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
          if (result.symbol === null || (direct && inPage(direct))) {
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
    [reviewId, revisionId, reveal, inPage],
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
      {hint && <ServerHintNote hint={hint} onDismiss={() => { setHint(null) }} />}
    </>
  )

  return { navigate, target, element }
}
