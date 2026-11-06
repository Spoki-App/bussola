import { useEffect, useRef, useState, type ClipboardEvent, type DragEvent, type KeyboardEvent, type ReactNode } from 'react'
import { flushSync } from 'react-dom'

import { IMAGE_TYPES, imageProblem, uploadImage } from '../api/attachments'
import { describeError } from '../api/client'
import { useMentionCandidates } from '../api/mentions'
import { imageAlt, insertRichImage, replaceRange, replaceRichBeforeCaret, replaceRichImage, richTextBeforeCaret, runCommand, uploadingImage } from '../markdown/editing'
import { applyFormat, changedRange, type FormatAction } from '../markdown/format'
import { filterMentions, mentionQuery } from '../markdown/mentions'
import { richHtmlFor, richToMarkdown } from '../markdown/richText'
import { readStored, writeStored } from '../settings/storage'
import { ErrorNote } from './Badges'
import { Markdown } from './Markdown'
import { MentionList } from './MentionList'
import { Segmented } from './Segmented'

type Mode = 'write' | 'preview' | 'rich'
type Placeholder = ReturnType<typeof uploadingImage>

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

const RICH_ACTIONS = [
  { label: 'Bold', glyph: <b>B</b>, command: 'bold' },
  { label: 'Italic', glyph: <i>I</i>, command: 'italic' },
  { label: 'Strikethrough', glyph: <s>S</s>, command: 'strikeThrough' },
  { label: 'Quote', glyph: '❯', command: 'formatBlock', value: 'blockquote' },
  { label: 'Bulleted list', glyph: '•', command: 'insertUnorderedList' },
  { label: 'Numbered list', glyph: '1.', command: 'insertOrderedList' },
]

const MAC = /Mac|iPhone|iPad/.test(navigator.userAgent)

const SHORTCUTS = new Map(TOOL_GROUPS.flat().flatMap((tool) => (tool.shortcut ? [[tool.shortcut, tool.action] as const] : [])))

const MODE_KEY = 'bussola.commentEditor'
const MODES: Record<Mode, string> = { write: 'Write', preview: 'Preview', rich: 'Rich text' }
const NOT_KEPT = 'This comment uses Markdown that rich text cannot keep exactly, so it stays in Write mode.'

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

function editingMode(): Mode {
  return readStored(MODE_KEY) === 'rich' ? 'rich' : 'write'
}

function initialState(initial: string): { mode: Mode; html: string; notice: string | null } {
  const html = editingMode() === 'rich' ? richHtmlFor(initial) : null
  if (html === null) {
    return { mode: 'write', html: '', notice: editingMode() === 'rich' ? NOT_KEPT : null }
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
  const [uploading, setUploading] = useState(0)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const previewRef = useRef<HTMLDivElement>(null)
  const editor = useRef<HTMLDivElement>(null)
  const candidates = useMentionCandidates(reviewId, mention !== null)
  useEffect(() => {
    if (autoFocus) {
      editor.current?.focus()
    }
  }, [autoFocus])
  const options = mention ? filterMentions(candidates.data ?? [], mention.query) : []
  const canSubmit = !busy && uploading === 0 && body.trim() !== ''

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
    if (next === 'rich') {
      showRich(html)
    }
    if (next !== 'preview') {
      writeStored(MODE_KEY, next)
    }
    flushSync(() => { setMode(next) })
    const focused = { write: textareaRef.current, preview: previewRef.current, rich: editor.current }[next]
    focused?.focus()
  }
  const syncRich = () => {
    if (editor.current) {
      setBody(richToMarkdown(editor.current))
    }
  }
  const submit = () => {
    if (canSubmit) {
      onSubmit(body, () => {
        setBody('')
        showRich('')
        setMode((current) => (current === 'preview' ? editingMode() : current))
      })
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

  const updateMention = (before: string | null) => {
    const query = before === null ? null : mentionQuery(before)
    setMention((current) => (query === null ? null : current?.query === query ? current : { query, active: 0 }))
  }
  const updateWriteMention = () => {
    const element = textareaRef.current
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
    const element = textareaRef.current
    if (element) {
      const edit = replaceRange(body, element.selectionStart - length, element.selectionStart, `@${login} `)
      setBody(edit.text)
      requestAnimationFrame(() => { element.setSelectionRange(edit.caret, edit.caret) })
    }
  }

  const insertPlaceholders = (placeholders: Placeholder[]) => {
    const root = editor.current
    if (root) {
      placeholders.forEach(({ alt }) => { insertRichImage(root, alt) })
      syncRich()
      return
    }
    const element = textareaRef.current
    const from = element?.selectionStart ?? body.length
    const to = element?.selectionEnd ?? body.length
    setBody((current) => replaceRange(current, from, to, placeholders.map(({ markdown }) => markdown).join('\n')).text)
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
    const problems = files.map(imageProblem)
    const accepted = files.filter((_, index) => problems[index] === null)
    setNotice(problems.findLast((problem) => problem !== null) ?? null)
    if (!accepted.length) {
      return
    }
    const placeholders = accepted.map((file) => uploadingImage(file.name))
    insertPlaceholders(placeholders)
    setUploading((count) => count + accepted.length)
    accepted.forEach((file, index) => {
      uploadImage(file)
        .then(
          (src) => { replacePlaceholder(placeholders[index], { alt: imageAlt(file.name), src }) },
          (error: unknown) => {
            replacePlaceholder(placeholders[index], null)
            setNotice(`${file.name} could not be uploaded: ${describeError(error)}`)
          },
        )
        .finally(() => { setUploading((count) => count - 1) })
    })
  }
  const attachFrom = (event: ClipboardEvent | DragEvent) => {
    const files = imageFiles('clipboardData' in event ? event.clipboardData.files : event.dataTransfer.files)
    if (files.length && mode !== 'preview') {
      event.preventDefault()
      attach(files)
    }
  }

  const onMentionKey = (event: KeyboardEvent): boolean => {
    if (!mention || !options.length) {
      return false
    }
    const step = { ArrowDown: 1, ArrowUp: -1 }[event.key]
    if (step) {
      setMention({ ...mention, active: (mention.active + step + options.length) % options.length })
    } else if ((event.key === 'Enter' || event.key === 'Tab') && !event.metaKey && !event.ctrlKey && !event.shiftKey) {
      pickMention(options[mention.active])
    } else if (event.key === 'Escape') {
      event.stopPropagation()
      setMention(null)
    } else {
      return false
    }
    event.preventDefault()
    return true
  }
  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (onMentionKey(event)) {
      return
    }
    const command = MAC ? event.metaKey : event.ctrlKey
    const key = event.key.toLowerCase()
    if (command && event.shiftKey && key === 'p') {
      event.preventDefault()
      changeMode(mode === 'preview' ? editingMode() : 'preview')
      return
    }
    const action = command && !event.shiftKey && !event.altKey && mode === 'write' ? SHORTCUTS.get(key) : undefined
    if (action) {
      event.preventDefault()
      format(action)
    } else if (event.key === 'Enter' && (event.metaKey || event.ctrlKey)) {
      event.preventDefault()
      submit()
    } else if (event.key === 'Escape' && onCancel) {
      onCancel()
    }
  }

  return (
    <div className="composer" onKeyDown={onKeyDown} onPaste={attachFrom} onDrop={attachFrom} onDragOver={(event) => { event.preventDefault() }}>
      <div className="composer-bar">
        <Segmented label="Comment mode" labels={MODES} value={mode} onChange={changeMode} />
        {mode === 'write' && (
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
        {mode === 'rich' && (
          <div className="composer-toolbar" role="toolbar" aria-label="Formatting">
            <span className="composer-tool-group">
              {RICH_ACTIONS.map((action) => (
                <button
                  key={action.label}
                  type="button"
                  className="composer-tool"
                  aria-label={action.label}
                  title={action.label}
                  onMouseDown={(event) => {
                    event.preventDefault()
                    runCommand(action.command, action.value)
                  }}
                >
                  {action.glyph}
                </button>
              ))}
            </span>
          </div>
        )}
        {mode !== 'preview' && (
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
        )}
      </div>
      <div className="composer-input">
        <textarea
          ref={textareaRef}
          aria-label={placeholder}
          hidden={mode !== 'write'}
          value={body}
          placeholder={placeholder}
          autoFocus={autoFocus && mode === 'write'}
          rows={3}
          onChange={(event) => { setBody(event.target.value) }}
          onSelect={updateWriteMention}
          onBlur={() => { setMention(null) }}
        />
        {mode === 'rich' && (
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
            onKeyUp={(event) => {
              if (event.key !== 'Escape') {
                updateRichMention()
              }
            }}
            onBlur={() => { setMention(null) }}
          />
        )}
        {mode === 'preview' && (
          <div ref={previewRef} className="composer-preview" role="tabpanel" aria-label="Preview" tabIndex={0}>
            {body.trim() ? <Markdown text={body} /> : <p className="muted">Nothing to preview</p>}
          </div>
        )}
        {mention && options.length > 0 && (
          <MentionList options={options} active={mention.active} onPick={pickMention} onHover={(active) => { setMention({ ...mention, active }) }} />
        )}
      </div>
      {notice && <ErrorNote message={notice} />}
      <div className="composer-actions">
        <span className="muted">{uploading ? 'Uploading images...' : 'Ctrl/Cmd + Enter to send'}</span>
        {onCancel && (
          <button type="button" onClick={onCancel}>
            Cancel
          </button>
        )}
        <button type="button" className="primary" disabled={!canSubmit} onClick={submit}>
          {submitLabel}
        </button>
      </div>
    </div>
  )
}
