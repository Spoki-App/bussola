import { useEffect, useRef, useState } from 'react'

import { plural } from '../review/text'
import { ErrorNote } from './Badges'

interface Props {
  title: string
  lineCount: number
  onCompareSelection?: () => void
  onCompareClipboard: (pasted: string) => void
  onCancel: () => void
}

function readClipboard(): Promise<string> {
  try {
    return navigator.clipboard.readText()
  } catch (error) {
    return Promise.reject(error instanceof Error ? error : new Error(String(error)))
  }
}

export function CompareBar({ title, lineCount, onCompareSelection, onCompareClipboard, onCancel }: Props) {
  const hasSelection = onCompareSelection !== undefined
  const [error, setError] = useState<string | null>(null)
  const open = useRef(true)
  useEffect(() => {
    open.current = true
    return () => {
      open.current = false
    }
  }, [])
  const compareClipboard = () => {
    setError(null)
    readClipboard().then(
      (pasted) => {
        if (!open.current) {
          return
        }
        if (pasted.trim()) {
          onCompareClipboard(pasted)
        } else {
          setError('The clipboard has no text to compare.')
        }
      },
      () => {
        setError('The clipboard could not be read. Allow this page to see the clipboard and try again.')
      },
    )
  }
  return (
    <section className="compare-bar" role="status" aria-label="Compare ranges">
      <span className="compare-bar-label">First range</span>
      <span className="move-link compare-chip" title={title}>
        <code>{title}</code>
        {plural(lineCount, 'line')}
      </span>
      <span className="compare-bar-hint muted">
        {hasSelection ? 'Compare it with the selected lines or the clipboard.' : 'Select a second range by its line numbers, or compare with the clipboard.'}
      </span>
      <div className="compare-bar-actions">
        <button type="button" className="primary" disabled={!hasSelection} title={hasSelection ? 'Compare the first range with the selected lines' : 'Select a second range first'} onClick={onCompareSelection}>
          Compare with selection
        </button>
        <button type="button" className="compare-clipboard" aria-label="Compare with clipboard" title="Compare with clipboard" onClick={compareClipboard}>
          <ClipboardIcon />
        </button>
        <button type="button" onClick={onCancel}>
          Cancel
        </button>
      </div>
      {error && <ErrorNote message={error} />}
    </section>
  )
}

function ClipboardIcon() {
  return (
    <svg className="copy-link-icon" viewBox="0 0 16 16" aria-hidden="true">
      <rect x="3.5" y="3" width="9" height="11" rx="1.5" />
      <path d="M6 3V2.5A.5.5 0 0 1 6.5 2h3a.5.5 0 0 1 .5.5V3a.5.5 0 0 1-.5.5h-3A.5.5 0 0 1 6 3Z" />
    </svg>
  )
}
