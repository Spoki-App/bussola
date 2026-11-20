import { useMemo, useState } from 'react'

import type { Thread } from '../api/types'
import { compactPreview, previewLines } from '../review/codePreview'
import { plural } from '../review/text'
import { LineCode } from './LineCode'

interface Props {
  thread: Thread
  onShow?: () => void
  showTitle?: string
}

export function CodePreview({ thread, onShow, showTitle }: Props) {
  const [expanded, setExpanded] = useState(false)
  const lines = useMemo(() => previewLines(thread), [thread])
  const compact = useMemo(() => compactPreview(lines), [lines])
  if (lines.length === 0) {
    return null
  }
  const hidden = lines.length - compact.length
  return (
    <div className="code-preview">
      <pre>
        {(expanded ? lines : compact).map((line, index) => (
          <div key={index} className={line.target ? 'code-preview-line target' : 'code-preview-line'}>
            {line.tokens.length > 0 ? <LineCode tokens={line.tokens} /> : ' '}
          </div>
        ))}
      </pre>
      {(hidden > 0 || onShow) && (
        <div className="code-preview-actions">
          {hidden > 0 && (
            <button type="button" className="link" aria-expanded={expanded} onClick={() => { setExpanded(!expanded) }}>
              {expanded ? 'Show less' : `Show ${plural(hidden, 'more line')}`}
            </button>
          )}
          {onShow && (
            <button type="button" className="link" title={showTitle} onClick={onShow}>
              Go to code
            </button>
          )}
        </div>
      )}
    </div>
  )
}
