import { useRef, useState, type ChangeEvent } from 'react'

import { describeError, getJson } from '../api/client'
import { useEditorThemes } from '../api/hooks'
import type { EditorTheme } from '../api/types'
import { SYSTEM_THEME, activePalette, addTheme, removeTheme, selectTheme, useThemeState } from '../settings/theme'
import { exportVscodeTheme, parseVscodeTheme, themeFromJson } from '../settings/vscodeTheme'

const BUILTIN_OPTIONS = [
  { id: 'light', name: 'Light' },
  { id: 'dark', name: 'Dark' },
]

function download(fileName: string, text: string): void {
  const url = URL.createObjectURL(new Blob([text], { type: 'application/json' }))
  const link = document.createElement('a')
  link.href = url
  link.download = fileName
  link.click()
  setTimeout(() => {
    URL.revokeObjectURL(url)
  })
}

function fileNameOf(name: string): string {
  return `${name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'bussola'}-color-theme.json`
}

function editorThemeId(theme: EditorTheme): string {
  return `editor-${theme.id}`
}

function byEditor(themes: EditorTheme[]): [string, EditorTheme[]][] {
  const groups = new Map<string, EditorTheme[]>()
  for (const theme of themes) {
    groups.set(theme.editor, [...(groups.get(theme.editor) ?? []), theme])
  }
  return [...groups]
}

export function ThemePanel() {
  const state = useThemeState()
  const editorThemes = useEditorThemes()
  const [messages, setMessages] = useState<string[]>([])
  const fileInput = useRef<HTMLInputElement>(null)
  const { theme, overrides, palette } = activePalette(state)
  const installed = editorThemes.data ?? []
  const installedIds = new Set(installed.map(editorThemeId))
  const imported = state.themes.filter((candidate) => !installedIds.has(candidate.id))

  const applyEditorTheme = (editorTheme: EditorTheme) => {
    getJson<unknown>(`/editor-themes/${editorTheme.id}`).then(
      (content) => {
        try {
          const parsed = themeFromJson(content, editorTheme.label)
          addTheme(parsed, editorThemeId(editorTheme))
          setMessages([`Using "${parsed.name}" from ${editorTheme.editor}.`, ...parsed.notes])
        } catch (error) {
          setMessages([error instanceof Error ? error.message : String(error)])
        }
      },
      (error: unknown) => { setMessages([describeError(error)]) },
    )
  }

  const choose = (id: string) => {
    const editorTheme = installed.find((candidate) => editorThemeId(candidate) === id)
    if (editorTheme) {
      applyEditorTheme(editorTheme)
    } else {
      selectTheme(id)
    }
  }

  const importFile = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) {
      return
    }
    file.text().then(
      (text) => {
        try {
          const parsed = parseVscodeTheme(text, file.name)
          addTheme(parsed)
          setMessages([`Imported "${parsed.name}".`, ...parsed.notes])
        } catch (error) {
          setMessages([error instanceof Error ? error.message : String(error)])
        }
      },
      () => { setMessages([`Could not read ${file.name}.`]) },
    )
  }

  const exportTheme = () => {
    const name = Object.keys(overrides).length > 0 ? `${theme.name} (customized)` : theme.name
    download(fileNameOf(name), exportVscodeTheme(name, theme.type, palette))
  }

  return (
    <div className="stack theme-panel">
      <label htmlFor="theme-select">Theme</label>
      <select id="theme-select" value={state.selected} onChange={(event) => { choose(event.target.value) }}>
        <option value={SYSTEM_THEME}>System</option>
        {BUILTIN_OPTIONS.map((option) => (
          <option key={option.id} value={option.id}>
            {option.name}
          </option>
        ))}
        {imported.length > 0 && (
          <optgroup label="Imported">
            {imported.map((candidate) => (
              <option key={candidate.id} value={candidate.id}>
                {candidate.name}
              </option>
            ))}
          </optgroup>
        )}
        {byEditor(installed).map(([editor, themes]) => (
          <optgroup key={editor} label={`Installed in ${editor}`}>
            {themes.map((candidate) => (
              <option key={candidate.id} value={editorThemeId(candidate)} title={candidate.extension}>
                {candidate.label}
              </option>
            ))}
          </optgroup>
        ))}
      </select>
      {state.selected === SYSTEM_THEME && <p className="muted">{`Follows the system setting, now ${theme.name}.`}</p>}
      {installed.length > 0 && <p className="muted">{`${String(installed.length)} ${installed.length === 1 ? 'theme' : 'themes'} found in VS Code and similar editors on this computer.`}</p>}
      <button type="button" onClick={() => fileInput.current?.click()}>
        Import VS Code theme (.json)
      </button>
      <input ref={fileInput} hidden aria-label="VS Code theme file" type="file" accept=".json,.jsonc,application/json" onChange={importFile} />
      <p className="muted">Pick the theme file inside a VS Code theme extension, usually in its themes folder. Only its colors are read, and themes stay in this browser.</p>
      {messages.length > 0 && (
        <div role="status" className="notice">
          {messages.map((message) => (
            <p key={message}>{message}</p>
          ))}
        </div>
      )}
      <button type="button" onClick={exportTheme}>
        Export as VS Code theme
      </button>
      {imported.includes(theme) && (
        <button type="button" onClick={() => { removeTheme(theme.id) }}>
          {`Remove "${theme.name}"`}
        </button>
      )}
    </div>
  )
}
