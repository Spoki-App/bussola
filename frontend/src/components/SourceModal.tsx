import { useEffect, useMemo, useRef, type MouseEvent } from 'react'

import { describeError } from '../api/client'
import { useSourceFile, type CodeLocation } from '../api/navigation'
import { useModalDialog } from '../hooks/useModalDialog'
import { columnAt, isNavigationClick, type NavigationClick } from '../review/codeNavigation'
import { sourceLines, type SourceLine } from '../review/sourceLines'
import { ErrorNote } from './Badges'
import { ExternalLink } from './ExternalLink'

interface Props {
  reviewId: number
  revisionId: number | undefined
  stack: CodeLocation[]
  onBack: () => void
  onClose: () => void
  onNavigate: (click: NavigationClick) => void
}

function LineCode({ tokens }: { tokens: SourceLine }) {
  return tokens.map((token, index) =>
    token.className ? (
      <span key={index} className={token.className}>
        {token.text}
      </span>
    ) : (
      token.text
    ),
  )
}

export function SourceModal({ reviewId, revisionId, stack, onBack, onClose, onNavigate }: Props) {
  const { ref, close } = useModalDialog()
  const location = stack[stack.length - 1]
  const source = useSourceFile(reviewId, revisionId, location)
  const lines = useMemo(() => (source.data ? sourceLines(source.data.text, source.data.path) : []), [source.data])
  const body = useRef<HTMLDivElement>(null)

  useEffect(() => {
    body.current?.querySelector('.source-line.target')?.scrollIntoView({ block: 'center' })
  }, [lines, location])

  const onCodeMouseDown = (event: MouseEvent<HTMLElement>) => {
    if (isNavigationClick(event)) {
      event.preventDefault()
    }
  }
  const onCodeClick = (line: number, event: MouseEvent<HTMLElement>) => {
    if (!isNavigationClick(event)) {
      return
    }
    const column = columnAt(event.currentTarget, event.clientX, event.clientY)
    if (column !== null) {
      onNavigate({ path: location.path, side: location.side, line, column, point: { x: event.clientX, y: event.clientY } })
    }
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
      <div ref={body} className="source-view" role="region" aria-label={`Source of ${location.path}`}>
        {lines.map((tokens, index) => {
          const line = index + 1
          return (
            <div key={line} className={`source-line${line === location.line ? ' target' : ''}`}>
              <span className="source-number">{line}</span>
              <code onMouseDown={onCodeMouseDown} onClick={(event) => { onCodeClick(line, event) }}>
                <LineCode tokens={tokens} />
              </code>
            </div>
          )
        })}
      </div>
    </dialog>
  )
}
