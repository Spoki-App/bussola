import { memo, useEffect, useMemo, useRef, type MouseEvent } from 'react'

import { describeError } from '../api/client'
import { useSourceFile, type CodeLocation, type NavigationRequest } from '../api/navigation'
import { useModalDialog } from '../hooks/useModalDialog'
import { useSymbolLink } from '../hooks/useSymbolLink'
import { isNavigationClick, navigationColumn, type NavigationClick } from '../review/codeNavigation'
import { sourceLines, type SourceLine } from '../review/sourceLines'
import { ErrorNote } from './Badges'
import { ExternalLink } from './ExternalLink'
import { LineCode } from './LineCode'

interface Props {
  reviewId: number
  revisionId: number | undefined
  stack: CodeLocation[]
  onBack: () => void
  onClose: () => void
  onNavigate: (click: NavigationClick) => void
  canNavigate: (request: NavigationRequest) => Promise<boolean>
}

const SourceLines = memo(function SourceLines({ lines, target }: { lines: SourceLine[]; target: number }) {
  return lines.map((tokens, index) => {
    const line = index + 1
    return (
      <div key={line} className={`source-line${line === target ? ' target' : ''}`} data-line={line}>
        <span className="source-number">{line}</span>
        <code>
          <LineCode tokens={tokens} />
        </code>
      </div>
    )
  })
})

function codeAt(event: MouseEvent<HTMLElement>): { code: Element; line: number } | null {
  const code = event.target instanceof Element ? event.target.closest('.source-line code') : null
  const line = Number(code?.parentElement?.dataset.line)
  return code && line > 0 ? { code, line } : null
}

export function SourceModal({ reviewId, revisionId, stack, onBack, onClose, onNavigate, canNavigate }: Props) {
  const { ref, close } = useModalDialog()
  const location = stack[stack.length - 1]
  const source = useSourceFile(reviewId, revisionId, location)
  const lines = useMemo(() => (source.data ? sourceLines(source.data.text, source.data.path) : []), [source.data])
  const body = useRef<HTMLDivElement>(null)
  const link = useSymbolLink()

  useEffect(() => {
    body.current?.querySelector('.source-line.target')?.scrollIntoView({ block: 'center' })
  }, [lines, location])

  const navigable = !location.library
  const onMouseDown = (event: MouseEvent<HTMLElement>) => {
    if (navigable && isNavigationClick(event)) {
      event.preventDefault()
    }
  }
  const onClick = (event: MouseEvent<HTMLElement>) => {
    const clicked = navigable && isNavigationClick(event) ? codeAt(event) : null
    const column = clicked ? navigationColumn(clicked.code, event.clientX, event.clientY) : null
    if (clicked && column !== null) {
      onNavigate({ path: location.path, side: location.side, line: clicked.line, column, point: { x: event.clientX, y: event.clientY } })
    }
  }
  const onMouseMove = (event: MouseEvent<HTMLElement>) => {
    const hovered = navigable ? codeAt(event) : null
    if (!hovered) {
      link.leave()
      return
    }
    link.hover(event, hovered.code, (column) => canNavigate({ path: location.path, side: location.side, line: hovered.line, column }))
  }
  const githubUrl = source.data?.url ? `${source.data.url}#L${String(location.line)}` : null

  return (
    <dialog ref={ref} className="picker source-dialog" aria-labelledby="source-dialog-title" onClose={onClose}>
      <header className="picker-header">
        <div className="source-title">
          <button type="button" disabled={stack.length < 2} onClick={onBack} title="Back to the previous location">
            Back
          </button>
          <h2 id="source-dialog-title">
            <code>{`${location.path}:${String(location.line)}`}</code>
          </h2>
          {location.side === 'base' && <span className="label">base</span>}
          {location.library && <span className="label">installed library</span>}
        </div>
        <div className="source-actions">
          {githubUrl && <ExternalLink href={githubUrl}>View on GitHub</ExternalLink>}
          <button type="button" className="link" onClick={close}>
            Close
          </button>
        </div>
      </header>
      {source.isPending && <p className="muted">Loading file...</p>}
      {source.error && <ErrorNote message={describeError(source.error)} />}
      <div ref={body} className="source-view" role="region" aria-label={`Source of ${location.path}`} onMouseDown={onMouseDown} onClick={onClick} onMouseMove={onMouseMove} onMouseLeave={link.leave}>
        <SourceLines lines={lines} target={location.line} />
      </div>
    </dialog>
  )
}
