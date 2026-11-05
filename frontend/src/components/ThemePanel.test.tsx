import { fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { syncTheme } from '../settings/theme'
import { BUILTIN_PALETTES } from '../settings/themeMapping'
import { ThemeColorsPanel } from './ThemeColorsPanel'
import { ThemePanel } from './ThemePanel'

const THEME = `{
  // comments are allowed
  "name": "Paper",
  "type": "light",
  "colors": { "editor.background": "#f7f3e8", "editor.foreground": "#2b2b2b", },
  "tokenColors": [{ "scope": "keyword", "settings": { "foreground": "#8b1a4a" } }],
}`

function rootStyle(variable: string): string {
  return document.documentElement.style.getPropertyValue(variable)
}

function importTheme(text: string, name = 'paper.json') {
  fireEvent.change(screen.getByLabelText('VS Code theme file'), { target: { files: [new File([text], name, { type: 'application/json' })] } })
}

describe('ThemePanel', () => {
  beforeEach(() => {
    window.localStorage.clear()
    document.documentElement.removeAttribute('style')
    syncTheme()
  })

  afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  it('lists System, Light and Dark with System selected', () => {
    render(<ThemePanel />)

    const select = screen.getByLabelText<HTMLSelectElement>('Theme')
    expect([...select.options].map((option) => option.text)).toEqual(['System', 'Light', 'Dark'])
    expect(select.value).toBe('system')
  })

  it('imports a VS Code theme and applies it', async () => {
    render(<ThemePanel />)

    importTheme(THEME)

    expect(await screen.findByText('Imported "Paper".')).toBeInTheDocument()
    expect(screen.getByLabelText<HTMLSelectElement>('Theme').selectedOptions[0].text).toBe('Paper')
    expect(rootStyle('--bg')).toBe('#f7f3e8')
    expect(rootStyle('--hl-keyword')).toBe('#8b1a4a')
    expect(rootStyle('--accent')).toBe(BUILTIN_PALETTES.light['--accent'])

    fireEvent.click(screen.getByRole('button', { name: 'Remove "Paper"' }))

    expect(screen.getByLabelText<HTMLSelectElement>('Theme').value).toBe('system')
  })

  it('explains why a theme cannot be imported', async () => {
    render(<ThemePanel />)

    importTheme('{"include": "./base.json"}')

    expect(await screen.findByRole('status')).toHaveTextContent('This theme takes its colors from "./base.json" with include')
    expect(screen.getByLabelText<HTMLSelectElement>('Theme').options).toHaveLength(3)
  })

  it('exports the current colors as a VS Code theme', async () => {
    const createObjectURL = vi.fn<(blob: Blob) => string>(() => 'blob:theme')
    vi.stubGlobal('URL', Object.assign(class extends URL {}, { createObjectURL, revokeObjectURL: vi.fn() }))
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined)
    render(<ThemePanel />)
    fireEvent.change(screen.getByLabelText('Theme'), { target: { value: 'light' } })

    fireEvent.click(screen.getByRole('button', { name: 'Export as VS Code theme' }))

    const exported = JSON.parse(await createObjectURL.mock.calls[0][0].text()) as { name: string; type: string; colors: Record<string, string> }
    expect(exported).toMatchObject({ name: 'Light', type: 'light', colors: { 'editor.background': '#ffffff', 'editor.foreground': '#16213a' } })
  })
})

describe('ThemeColorsPanel', () => {
  beforeEach(() => {
    window.localStorage.clear()
    document.documentElement.removeAttribute('style')
    syncTheme()
  })

  it('overrides a color live and resets it', () => {
    render(<ThemeColorsPanel />)
    const background = screen.getByLabelText<HTMLInputElement>('Background')
    const row = background.closest('.theme-color') as HTMLElement

    fireEvent.focus(background)
    fireEvent.change(background, { target: { value: '#12' } })
    expect(background).toHaveAttribute('aria-invalid', 'true')
    expect(rootStyle('--bg')).toBe(BUILTIN_PALETTES.dark['--bg'])

    fireEvent.change(background, { target: { value: '#202020' } })
    expect(rootStyle('--bg')).toBe('#202020')

    fireEvent.change(within(row).getByLabelText('Background color picker'), { target: { value: '#303030' } })
    expect(rootStyle('--bg')).toBe('#303030')

    fireEvent.click(within(row).getByRole('button', { name: 'Reset' }))
    expect(rootStyle('--bg')).toBe(BUILTIN_PALETTES.dark['--bg'])
  })

  it('keeps the transparency of a color when picking a new one', () => {
    render(<ThemeColorsPanel />)

    fireEvent.change(screen.getByLabelText('Added line color picker'), { target: { value: '#00ff00' } })

    expect(rootStyle('--diff-insert')).toBe('#00ff001a')
  })

  it('warns about low contrast and resets every color of the theme', () => {
    render(<ThemeColorsPanel />)

    fireEvent.change(screen.getByLabelText('Text color picker'), { target: { value: '#0e1424' } })
    fireEvent.change(screen.getByLabelText('Keywords color picker'), { target: { value: '#ff0000' } })

    expect(screen.getByRole('alert')).toHaveTextContent('Text on the background: contrast 1.0:1, below the WCAG AA minimum of 4.5:1.')

    fireEvent.click(screen.getByRole('button', { name: 'Reset all colors of Dark' }))

    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(rootStyle('--text')).toBe(BUILTIN_PALETTES.dark['--text'])
    expect(rootStyle('--hl-keyword')).toBe(BUILTIN_PALETTES.dark['--hl-keyword'])
  })
})
