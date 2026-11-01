import { useEffect, useState, type MouseEvent } from 'react'

interface Props {
  link: string
  label: string
  text?: string
  className?: string
  focusable?: boolean
}

const FEEDBACK_MS = 1500

type CopyState = 'idle' | 'copied' | 'failed'

const FEEDBACK: Record<Exclude<CopyState, 'idle'>, string> = { copied: 'Link copied', failed: 'Copy failed' }

export function CopyLinkButton({ link, label, text, className, focusable = true }: Props) {
  const [copyState, setCopyState] = useState<CopyState>('idle')
  useEffect(() => {
    if (copyState === 'idle') {
      return undefined
    }
    const timer = window.setTimeout(() => { setCopyState('idle') }, FEEDBACK_MS)
    return () => { window.clearTimeout(timer) }
  }, [copyState])
  const feedback = copyState === 'idle' ? null : FEEDBACK[copyState]

  const copy = (event: MouseEvent) => {
    event.stopPropagation()
    navigator.clipboard.writeText(link).then(
      () => { setCopyState('copied') },
      () => { setCopyState('failed') },
    )
  }

  return (
    <button
      type="button"
      className={['copy-link', className, copyState === 'idle' ? '' : copyState].filter(Boolean).join(' ')}
      aria-label={label}
      title={feedback ?? label}
      tabIndex={focusable ? undefined : -1}
      onMouseDown={(event) => { event.stopPropagation() }}
      onClick={copy}
    >
      {copyState === 'copied' ? <CheckIcon /> : <LinkIcon />}
      {text && <span>{feedback ?? text}</span>}
    </button>
  )
}

function LinkIcon() {
  return (
    <svg className="copy-link-icon" viewBox="0 0 16 16" aria-hidden="true">
      <path d="M6.5 9.5a3 3 0 0 0 4.2 0l2.3-2.3a3 3 0 0 0-4.2-4.2l-1 1" />
      <path d="M9.5 6.5a3 3 0 0 0-4.2 0L3 8.8a3 3 0 0 0 4.2 4.2l1-1" />
    </svg>
  )
}

function CheckIcon() {
  return (
    <svg className="copy-link-icon" viewBox="0 0 16 16" aria-hidden="true">
      <path d="M3 8.5l3.2 3L13 4.5" />
    </svg>
  )
}
