import { useEffect, useRef, useState, type ClipboardEvent, type DragEvent, type KeyboardEvent } from 'react'

import { IMAGE_TYPES, imageProblem, uploadImage } from '../api/attachments'
import { describeError } from '../api/client'
import { useMentionCandidates } from '../api/mentions'
import { imageAlt, insertRichImage, replaceRange, runCommand, replaceRichBeforeCaret, replaceRichImage, richTextBeforeCaret, uploadingImage } from '../markdown/editing'
import { filterMentions, mentionQuery } from '../markdown/mentions'
import { richHtmlFor, richToMarkdown } from '../markdown/richText'
import { readStored, writeStored } from '../settings/storage'
import { ErrorNote } from './Badges'
import { MentionList } from './MentionList'
import { Segmented } from './Segmented'

type Mode = 'write' | 'rich'
type Placeholder = ReturnType<typeof uploadingImage>

const MODE_KEY = 'bussola.commentEditor'
const MODES: Record<Mode, string> = { write: 'Write', rich: 'Rich text' }
const NOT_KEPT = 'This comment uses Markdown that rich text cannot keep exactly, so it stays in Write mode.'
const RICH_ACTIONS = [
  { label: 'Bold', text: 'B', command: 'bold' },
  { label: 'Italic', text: 'I', command: 'italic' },
  { label: 'Strikethrough', text: 'S', command: 'strikeThrough' },
  { label: 'Bulleted list', text: '•', command: 'insertUnorderedList' },
  { label: 'Numbered list', text: '1.', command: 'insertOrderedList' },
  { label: 'Quote', text: '❝', command: 'formatBlock', value: 'blockquote' },
]

interface Props {
  reviewId: number
  placeholder?: string
  submitLabel: string
  initial?: string
  busy?: boolean
  autoFocus?: boolean
  onSubmit: (body: string, done: () => void) => void
  onCancel?: () => void
}

function initialState(initial: string): { mode: Mode; html: string; notice: string | null } {
  const html = readStored(MODE_KEY) === 'rich' ? richHtmlFor(initial) : null
  if (html === null) {
    return { mode: 'write', html: '', notice: readStored(MODE_KEY) === 'rich' ? NOT_KEPT : null }
  }
  return { mode: 'rich', html, notice: null }
}

function imageFiles(files: FileList | null | undefined): File[] {
  return Array.from(files ?? []).filter((file) => file.type.startsWith('image/'))
}

export function Composer({ reviewId, placeholder = 'Leave a comment (Markdown)', submitLabel, initial = '', busy = false, autoFocus = false, onSubmit, onCancel }: Props) {
  const [body, setBody] = useState(initial)
  const [start] = useState(() => initialState(initial))
  const [mode, setMode] = useState(start.mode)
  const [rich, setRich] = useState({ html: start.html, version: 0 })
  const [notice, setNotice] = useState(start.notice)
  const [mention, setMention] = useState<{ query: string; active: number } | null>(null)
  const textarea = useRef<HTMLTextAreaElement>(null)
  const editor = useRef<HTMLDivElement>(null)
  const candidates = useMentionCandidates(reviewId, mention !== null)
  useEffect(() => {
    if (autoFocus) {
      editor.current?.focus()
    }
  }, [autoFocus])
  const options = mention ? filterMentions(candidates.data ?? [], mention.query) : []

  const showRich = (html: string) => {
    setRich((current) => ({ html, version: current.version + 1 }))
  }
  const changeMode = (next: Mode) => {
    setMention(null)
    const html = next === 'rich' ? richHtmlFor(body) : ''
    if (html === null) {
      setNotice(NOT_KEPT)
      return
    }
    setNotice(null)
    showRich(html)
    setMode(next)
    writeStored(MODE_KEY, next)
  }
  const syncRich = () => {
    if (editor.current) {
      setBody(richToMarkdown(editor.current))
    }
  }
  const submit = () => {
    if (body.trim()) {
      onSubmit(body, () => {
        setBody('')
        showRich('')
      })
    }
  }

  const updateMention = (before: string | null) => {
    const query = before === null ? null : mentionQuery(before)
    setMention((current) => (query === null ? null : current?.query === query ? current : { query, active: 0 }))
  }
  const updateWriteMention = () => {
    const element = textarea.current
    updateMention(element && element.selectionStart === element.selectionEnd ? element.value.slice(0, element.selectionStart) : null)
  }
  const updateRichMention = () => {
    updateMention(editor.current ? richTextBeforeCaret(editor.current) : null)
  }
  const pickMention = (login: string) => {
    if (!mention) {
      return
    }
    const length = mention.query.length + 1
    setMention(null)
    if (editor.current) {
      replaceRichBeforeCaret(editor.current, length, `@${login} `)
      syncRich()
      return
    }
    const element = textarea.current
    if (element) {
      const edit = replaceRange(body, element.selectionStart - length, element.selectionStart, `@${login} `)
      setBody(edit.text)
      requestAnimationFrame(() => { element.setSelectionRange(edit.caret, edit.caret) })
    }
  }

  const insertPlaceholder = ({ alt, markdown }: Placeholder) => {
    if (editor.current) {
      insertRichImage(editor.current, alt)
      syncRich()
      return
    }
    const element = textarea.current
    const start = element?.selectionStart ?? body.length
    const end = element?.selectionEnd ?? body.length
    setBody((current) => replaceRange(current, start, end, markdown).text)
  }
  const replacePlaceholder = ({ alt, markdown }: Placeholder, image: { alt: string; src: string } | null) => {
    if (editor.current) {
      replaceRichImage(editor.current, alt, image)
      syncRich()
      return
    }
    setBody((current) => current.replace(markdown, image ? `![${image.alt}](${image.src})` : ''))
  }
  const attach = (files: File[]) => {
    setNotice(null)
    for (const file of files) {
      const problem = imageProblem(file)
      if (problem) {
        setNotice(problem)
        continue
      }
      const placeholder = uploadingImage(file.name)
      insertPlaceholder(placeholder)
      uploadImage(file).then(
        (src) => { replacePlaceholder(placeholder, { alt: imageAlt(file.name), src }) },
        (error: unknown) => {
          replacePlaceholder(placeholder, null)
          setNotice(`${file.name} could not be uploaded: ${describeError(error)}`)
        },
      )
    }
  }
  const attachFrom = (event: ClipboardEvent | DragEvent) => {
    const files = imageFiles('clipboardData' in event ? event.clipboardData.files : event.dataTransfer.files)
    if (files.length) {
      event.preventDefault()
      attach(files)
    }
  }

  const onKeyDown = (event: KeyboardEvent) => {
    if (options.length && mention) {
      const step = { ArrowDown: 1, ArrowUp: -1 }[event.key]
      if (step) {
        event.preventDefault()
        setMention({ ...mention, active: (mention.active + step + options.length) % options.length })
        return
      }
      if ((event.key === 'Enter' || event.key === 'Tab') && !event.metaKey && !event.ctrlKey && !event.shiftKey) {
        event.preventDefault()
        pickMention(options[mention.active])
        return
      }
      if (event.key === 'Escape') {
        event.preventDefault()
        event.stopPropagation()
        setMention(null)
        return
      }
    }
    if (event.key === 'Enter' && (event.metaKey || event.ctrlKey)) {
      event.preventDefault()
      submit()
    } else if (event.key === 'Escape' && onCancel) {
      onCancel()
    }
  }

  return (
    <div className="composer" onPaste={attachFrom} onDrop={attachFrom} onDragOver={(event) => { event.preventDefault() }}>
      <div className="composer-toolbar">
        <Segmented label="Editor mode" labels={MODES} value={mode} onChange={changeMode} />
        {mode === 'rich' &&
          RICH_ACTIONS.map((action) => (
            <button
              key={action.label}
              type="button"
              className="icon"
              aria-label={action.label}
              title={action.label}
              onMouseDown={(event) => {
                event.preventDefault()
                runCommand(action.command, action.value)
                syncRich()
              }}
            >
              {action.text}
            </button>
          ))}
        <label className="composer-attach" title="Attach an image (PNG, JPEG, GIF or WebP). Images are stored by bussola on this machine.">
          Attach image
          <input
            type="file"
            accept={IMAGE_TYPES.join(',')}
            multiple
            hidden
            onChange={(event) => {
              attach(imageFiles(event.target.files))
              event.target.value = ''
            }}
          />
        </label>
      </div>
      <div className="composer-input">
        {mode === 'rich' ? (
          <div
            key={rich.version}
            ref={editor}
            className="rich-text markdown"
            contentEditable
            role="textbox"
            aria-multiline
            aria-label={placeholder}
            data-placeholder={placeholder}
            dangerouslySetInnerHTML={{ __html: rich.html }}
            onFocus={() => { runCommand('defaultParagraphSeparator', 'p') }}
            onInput={() => {
              syncRich()
              updateRichMention()
            }}
            onKeyDown={onKeyDown}
            onKeyUp={updateRichMention}
            onBlur={() => { setMention(null) }}
          />
        ) : (
          <textarea
            ref={textarea}
            aria-label={placeholder}
            value={body}
            placeholder={placeholder}
            autoFocus={autoFocus}
            rows={3}
            onChange={(event) => { setBody(event.target.value) }}
            onSelect={updateWriteMention}
            onKeyDown={onKeyDown}
            onBlur={() => { setMention(null) }}
          />
        )}
        {mention && options.length > 0 && (
          <MentionList options={options} active={mention.active} onPick={pickMention} onHover={(active) => { setMention({ ...mention, active }) }} />
        )}
      </div>
      {notice && <ErrorNote message={notice} />}
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
