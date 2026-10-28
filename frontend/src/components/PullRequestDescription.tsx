import { useState } from 'react'

import type { ReviewPullRequest } from '../api/types'
import { Markdown } from './Markdown'

const LONG_DESCRIPTION_CHARS = 800
const LONG_DESCRIPTION_LINES = 15

function isLong(text: string): boolean {
  return text.length > LONG_DESCRIPTION_CHARS || text.split('\n').length > LONG_DESCRIPTION_LINES
}

export function PullRequestDescription({ pull }: { pull: ReviewPullRequest }) {
  const [open, setOpen] = useState(true)
  const [expanded, setExpanded] = useState(false)
  const text = (pull.description ?? '').trim()
  const long = isLong(text)

  return (
    <section className="pr-description" aria-label="Pull request description">
      <button type="button" className="pr-description-toggle" aria-expanded={open} onClick={() => { setOpen(!open) }}>
        <span aria-hidden="true">{open ? '\u25be' : '\u25b8'}</span> Description
        {pull.author && <span className="muted">{` by ${pull.author}`}</span>}
      </button>
      {open && (
        <div className={`pr-description-body${long && !expanded ? ' clamped' : ''}`}>
          {text ? <Markdown text={text} /> : <p className="muted">No description provided.</p>}
        </div>
      )}
      {open && long && (
        <button type="button" className="link" onClick={() => { setExpanded(!expanded) }}>
          {expanded ? 'Show less' : 'Show all'}
        </button>
      )}
    </section>
  )
}
