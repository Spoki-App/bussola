import { useState, type KeyboardEvent } from 'react'

interface Props {
  placeholder?: string
  submitLabel: string
  initial?: string
  busy?: boolean
  autoFocus?: boolean
  onSubmit: (body: string, done: () => void) => void
  onCancel?: () => void
}

export function Composer({ placeholder = 'Leave a comment (Markdown)', submitLabel, initial = '', busy = false, autoFocus = false, onSubmit, onCancel }: Props) {
  const [body, setBody] = useState(initial)
  const submit = () => {
    if (body.trim()) {
      onSubmit(body, () => { setBody('') })
    }
  }
  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && (event.metaKey || event.ctrlKey)) {
      event.preventDefault()
      submit()
    } else if (event.key === 'Escape' && onCancel) {
      onCancel()
    }
  }
  return (
    <div className="composer">
      <textarea
        aria-label={placeholder}
        value={body}
        placeholder={placeholder}
        autoFocus={autoFocus}
        rows={3}
        onChange={(event) => { setBody(event.target.value) }}
        onKeyDown={onKeyDown}
      />
      <div className="composer-actions">
        <span className="muted">Ctrl/Cmd + Enter to send</span>
        {onCancel && (
          <button type="button" onClick={onCancel}>
            Cancel
          </button>
        )}
        <button type="button" className="primary" disabled={busy || !body.trim()} onClick={submit}>
          {submitLabel}
        </button>
      </div>
    </div>
  )
}
