import { useEffect, type KeyboardEvent, type MouseEvent } from 'react'

import type { NavigationResult, NavigationTarget } from '../api/navigation'
import { useModalDialog } from '../hooks/useModalDialog'
import { emptyMessage, groupTargets, titleOf, type ScreenPoint } from '../review/codeNavigation'
import { plural } from '../review/text'
import { ErrorNote } from './Badges'

export type PopupState = { status: 'loading'; building: boolean } | { status: 'ready'; result: NavigationResult } | { status: 'error'; message: string }

interface Props {
  state: PopupState
  point: ScreenPoint
  onChoose: (target: NavigationTarget) => void
  onClose: () => void
}

const POPUP_WIDTH = 560
const POPUP_MAX_HEIGHT = 420
const VIEWPORT_MARGIN = 8
const CURSOR_GAP = 14
const ENTRY_SELECTOR = 'button.navigation-entry'
const STEPS: Record<string, number> = { ArrowDown: 1, ArrowUp: -1 }

function verticalPlacement(y: number, viewportHeight: number) {
  const below = viewportHeight - y - CURSOR_GAP - VIEWPORT_MARGIN
  const above = y - CURSOR_GAP - VIEWPORT_MARGIN
  if (below >= POPUP_MAX_HEIGHT || below >= above) {
    return { top: y + CURSOR_GAP, maxHeight: Math.min(POPUP_MAX_HEIGHT, below) }
  }
  return { top: 'auto', bottom: viewportHeight - y + CURSOR_GAP, maxHeight: Math.min(POPUP_MAX_HEIGHT, above) }
}

function clickedOutside(event: MouseEvent<HTMLDialogElement>): boolean {
  const box = event.currentTarget.getBoundingClientRect()
  return event.target === event.currentTarget && (event.clientX < box.left || event.clientX > box.right || event.clientY < box.top || event.clientY > box.bottom)
}

function moveFocus(dialog: HTMLDialogElement, step: number) {
  const entries = [...dialog.querySelectorAll<HTMLButtonElement>(ENTRY_SELECTOR)]
  if (entries.length === 0) {
    return
  }
  const current = entries.indexOf(document.activeElement as HTMLButtonElement)
  const next = current < 0 ? (step > 0 ? 0 : entries.length - 1) : (current + step + entries.length) % entries.length
  entries[next].focus()
}

function Entry({ target, onChoose }: { target: NavigationTarget; onChoose: (target: NavigationTarget) => void }) {
  return (
    <li>
      <button type="button" className="navigation-entry" onClick={() => { onChoose(target) }}>
        <span className="navigation-location">
          <span>{`${target.path}:${String(target.line)}`}</span>
          {target.side === 'base' && <span className="label">base</span>}
          {target.unit_id !== null && <span className="label in-review">in review</span>}
        </span>
        <code className="navigation-preview">{target.preview}</code>
      </button>
    </li>
  )
}

function Results({ result, onChoose }: { result: NavigationResult; onChoose: (target: NavigationTarget) => void }) {
  if (result.targets.length === 0) {
    return <p className="muted">{emptyMessage(result)}</p>
  }
  const groups = groupTargets(result.targets)
  return (
    <div className="navigation-results">
      {groups.definitions.length > 0 && (
        <section aria-label="Definitions">
          <h3>Definitions</h3>
          <ul>
            {groups.definitions.map((target) => (
              <Entry key={`${target.path}:${String(target.line)}:${String(target.column)}`} target={target} onChoose={onChoose} />
            ))}
          </ul>
        </section>
      )}
      {groups.files.map((file) => (
        <section key={file.path} aria-label={`Usages in ${file.path}`}>
          <h3>
            {file.path}
            <span className="muted">{plural(file.targets.length, 'usage')}</span>
          </h3>
          <ul>
            {file.targets.map((target) => (
              <Entry key={`${target.path}:${String(target.line)}:${String(target.column)}`} target={target} onChoose={onChoose} />
            ))}
          </ul>
        </section>
      ))}
    </div>
  )
}

function heading(state: PopupState): string {
  if (state.status === 'ready') {
    return titleOf(state.result)
  }
  return state.status === 'error' ? 'Navigation failed' : 'Finding the symbol'
}

export function NavigationPopup({ state, point, onChoose, onClose }: Props) {
  const { ref, close } = useModalDialog()

  useEffect(() => {
    if (state.status === 'ready') {
      ref.current?.querySelector<HTMLButtonElement>(ENTRY_SELECTOR)?.focus()
    }
  }, [state, ref])

  const onKeyDown = (event: KeyboardEvent<HTMLDialogElement>) => {
    const step = STEPS[event.key] as number | undefined
    if (step !== undefined && ref.current) {
      event.preventDefault()
      moveFocus(ref.current, step)
    }
  }

  const left = Math.max(VIEWPORT_MARGIN, Math.min(point.x, window.innerWidth - POPUP_WIDTH - VIEWPORT_MARGIN))
  const vertical = verticalPlacement(point.y, window.innerHeight)
  const title = heading(state)

  return (
    <dialog
      ref={ref}
      className="navigation-popup"
      style={{ left, ...vertical }}
      aria-label={title}
      onClose={onClose}
      onKeyDown={onKeyDown}
      onClick={(event) => {
        if (clickedOutside(event)) {
          close()
        }
      }}
    >
      <h2>{title}</h2>
      {state.status === 'loading' && <p className="muted" role="status">{state.building ? 'Indexing the repository, this happens once per commit...' : 'Searching...'}</p>}
      {state.status === 'error' && <ErrorNote message={state.message} />}
      {state.status === 'ready' && <Results result={state.result} onChoose={onChoose} />}
    </dialog>
  )
}
