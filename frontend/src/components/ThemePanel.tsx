import { useRef, useState, type ChangeEvent } from 'react'

import { SYSTEM_THEME, activeTheme, addTheme, allThemes, removeTheme, resolvePalette, selectTheme, useThemeState } from '../settings/theme'
import { exportVscodeTheme, parseVscodeTheme } from '../settings/vscodeTheme'

function download(fileName: string, text: string): void {
  const url = URL.createObjectURL(new Blob([text], { type: 'application/json' }))
  const link = document.createElement('a')
  link.href = url
  link.download = fileName
  link.click()
  URL.revokeObjectURL(url)
}

function fileNameOf(name: string): string {
  return `${name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'bussola'}-color-theme.json`
}

export function ThemePanel() {
  const state = useThemeState()
  const [messages, setMessages] = useState<string[]>([])
  const fileInput = useRef<HTMLInputElement>(null)
  const theme = activeTheme(state)
  const imported = state.themes.some((candidate) => candidate.id === state.selected)

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
    const overrides = state.overrides[theme.id] ?? {}
    const name = Object.keys(overrides).length > 0 ? `${theme.name} (customized)` : theme.name
    download(fileNameOf(name), exportVscodeTheme(name, theme.type, resolvePalette(theme, overrides)))
  }

  return (
    <div className="stack theme-panel">
      <label htmlFor="theme-select">Theme</label>
      <select id="theme-select" value={state.selected} onChange={(event) => { selectTheme(event.target.value) }}>
        <option value={SYSTEM_THEME}>System</option>
        {allThemes(state).map((candidate) => (
          <option key={candidate.id} value={candidate.id}>
            {candidate.name}
          </option>
        ))}
      </select>
      {state.selected === SYSTEM_THEME && <p className="muted">{`Follows the system setting, now ${theme.name}.`}</p>}
      <button type="button" onClick={() => fileInput.current?.click()}>
        Import VS Code theme (.json)
      </button>
      <input ref={fileInput} hidden aria-label="VS Code theme file" type="file" accept=".json,.jsonc,application/json" onChange={importFile} />
      <p className="muted">Pick the theme file inside a VS Code theme extension, usually in its themes folder. Only its colors are read, and themes stay in this browser.</p>
      {messages.length > 0 && (
        <div role="status" className="theme-messages">
          {messages.map((message) => (
            <p key={message}>{message}</p>
          ))}
        </div>
      )}
      <button type="button" onClick={exportTheme}>
        Export as VS Code theme
      </button>
      {imported && (
        <button type="button" onClick={() => { removeTheme(theme.id) }}>
          {`Remove "${theme.name}"`}
        </button>
      )}
    </div>
  )
}
