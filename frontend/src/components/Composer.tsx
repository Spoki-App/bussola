import { useRef, useState, type KeyboardEvent, type ReactNode } from 'react'
import { flushSync } from 'react-dom'

import { applyFormat, changedRange, type FormatAction } from '../markdown/format'
import { Markdown } from './Markdown'
import { Segmented } from './Segmented'

interface Props {
  placeholder?: string
  submitLabel: string
  initial?: string
  busy?: boolean
  autoFocus?: boolean
  onSubmit: (body: string, done: () => void) => void
  onCancel?: () => void
}

interface Tool {
  action: FormatAction
  label: string
  glyph: ReactNode
  shortcut?: string
}

const TOOL_GROUPS: Tool[][] = [
  [
    { action: 'h1', label: 'Heading 1', glyph: 'H1' },
    { action: 'h2', label: 'Heading 2', glyph: 'H2' },
    { action: 'h3', label: 'Heading 3', glyph: 'H3' },
  ],
  [
    { action: 'bold', label: 'Bold', glyph: <b>B</b>, shortcut: 'b' },
    { action: 'italic', label: 'Italic', glyph: <i>I</i>, shortcut: 'i' },
    { action: 'strike', label: 'Strikethrough', glyph: <s>S</s> },
  ],
  [
    { action: 'code', label: 'Inline code', glyph: '<>', shortcut: 'e' },
    { action: 'codeBlock', label: 'Code block', glyph: '{ }' },
    { action: 'quote', label: 'Quote', glyph: '❯' },
    { action: 'link', label: 'Link', glyph: 'Link', shortcut: 'k' },
  ],
  [
    { action: 'bullets', label: 'Bulleted list', glyph: '•' },
    { action: 'numbers', label: 'Numbered list', glyph: '1.' },
    { action: 'tasks', label: 'Task list', glyph: '☐' },
  ],
]

const SHORTCUTS = new Map(TOOL_GROUPS.flat().flatMap((tool) => (tool.shortcut ? [[tool.shortcut, tool.action] as const] : [])))

function replaceText(textarea: HTMLTextAreaElement, from: number, to: number, insert: string): boolean {
  if (from === to && !insert) {
    return true
  }
  textarea.focus()
  textarea.setSelectionRange(from, to)
  if (!('execCommand' in document)) {
    return false
  }
  // eslint-disable-next-line @typescript-eslint/no-deprecated -- the only way to edit a textarea and keep its native undo history
  return document.execCommand(insert ? 'insertText' : 'delete', false, insert)
}

export function Composer({ placeholder = 'Leave a comment (Markdown)', submitLabel, initial = '', busy = false, autoFocus = false, onSubmit, onCancel }: Props) {
  const [body, setBody] = useState(initial)
  const [previewing, setPreviewing] = useState(false)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const previewRef = useRef<HTMLDivElement>(null)
  const submit = () => {
    if (body.trim()) {
      onSubmit(body, () => { setBody('') })
    }
  }
  const showPreview = (show: boolean) => {
    flushSync(() => { setPreviewing(show) })
    if (show) {
      previewRef.current?.focus()
    } else {
      textareaRef.current?.focus()
    }
  }
  const format = (action: FormatAction) => {
    const textarea = textareaRef.current
    if (!textarea) {
      return
    }
    const next = applyFormat({ text: textarea.value, start: textarea.selectionStart, end: textarea.selectionEnd }, action)
    const { from, to, insert } = changedRange(textarea.value, next.text)
    if (!replaceText(textarea, from, to, insert)) {
      flushSync(() => { setBody(next.text) })
    }
    textarea.setSelectionRange(next.start, next.end)
  }
  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    const command = event.metaKey || event.ctrlKey
    const key = event.key.toLowerCase()
    if (command && event.shiftKey && key === 'p') {
      event.preventDefault()
      showPreview(!previewing)
      return
    }
    const action = command && !event.shiftKey && !event.altKey && !previewing ? SHORTCUTS.get(key) : undefined
    if (action) {
      event.preventDefault()
      format(action)
    } else if (event.key === 'Enter' && command) {
      event.preventDefault()
      submit()
    } else if (event.key === 'Escape' && onCancel) {
      onCancel()
    }
  }
  return (
    <div className="composer" onKeyDown={onKeyDown}>
      <div className="composer-bar">
        <Segmented label="Comment mode" labels={{ write: 'Write', preview: 'Preview' }} value={previewing ? 'preview' : 'write'} onChange={(mode) => { showPreview(mode === 'preview') }} />
        {!previewing && (
          <div className="composer-toolbar" role="toolbar" aria-label="Formatting">
            {TOOL_GROUPS.map((group) => (
              <span key={group[0].action} className="composer-tool-group">
                {group.map((tool) => (
                  <button
                    key={tool.action}
                    type="button"
                    className="composer-tool"
                    aria-label={tool.label}
                    title={tool.shortcut ? `${tool.label} (Ctrl/Cmd + ${tool.shortcut.toUpperCase()})` : tool.label}
                    onMouseDown={(event) => { event.preventDefault() }}
                    onClick={() => { format(tool.action) }}
                  >
                    {tool.glyph}
                  </button>
                ))}
              </span>
            ))}
          </div>
        )}
      </div>
      <textarea
        ref={textareaRef}
        aria-label={placeholder}
        hidden={previewing}
        value={body}
        placeholder={placeholder}
        autoFocus={autoFocus}
        rows={3}
        onChange={(event) => { setBody(event.target.value) }}
      />
      {previewing && (
        <div ref={previewRef} className="composer-preview" role="tabpanel" aria-label="Preview" tabIndex={0}>
          {body.trim() ? <Markdown text={body} /> : <p className="muted">Nothing to preview</p>}
        </div>
      )}
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
