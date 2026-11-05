import { useSyncExternalStore } from 'react'

import { AA_CONTRAST, contrastRatio, parseColor, withAlpha } from './colors'
import { readStored, writeStored } from './storage'
import { BUILTIN_PALETTES, COLOR_SLOTS, DERIVED_COLORS, type ThemeType } from './themeMapping'
import type { ParsedTheme, ThemeColors } from './vscodeTheme'

export interface Theme {
  id: string
  name: string
  type: ThemeType
  colors: ThemeColors
}

export interface ThemeState {
  selected: string
  themes: Theme[]
  overrides: Record<string, ThemeColors>
}

export const SYSTEM_THEME = 'system'
export const BUILTIN_THEMES: Theme[] = [
  { id: 'light', name: 'Light', type: 'light', colors: {} },
  { id: 'dark', name: 'Dark', type: 'dark', colors: {} },
]

const SELECTED_KEY = 'bussola.theme'
const THEMES_KEY = 'bussola.themes'
const OVERRIDES_KEY = 'bussola.themeOverrides'
const SLOT_VARIABLES = new Set(COLOR_SLOTS.map((slot) => slot.variable))
const CONTRAST_PAIRS = [
  ['--text', '--bg', 'Text on the background'],
  ['--muted', '--bg', 'Secondary text on the background'],
  ['--text', '--bg-subtle', 'Text on panels'],
  ['--accent', '--bg', 'Links on the background'],
  ['--accent-text', '--accent', 'Text on accent buttons'],
] as const

function readJson(key: string): unknown {
  try {
    return JSON.parse(readStored(key) ?? 'null')
  } catch {
    return null
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

export function cleanColors(value: unknown): ThemeColors {
  const colors: ThemeColors = {}
  if (!isRecord(value)) {
    return colors
  }
  for (const [variable, raw] of Object.entries(value)) {
    const color = parseColor(raw)
    if (SLOT_VARIABLES.has(variable) && color) {
      colors[variable] = color
    }
  }
  return colors
}

function cleanTheme(value: unknown): Theme | null {
  if (!isRecord(value) || typeof value.id !== 'string' || typeof value.name !== 'string') {
    return null
  }
  return { id: value.id, name: value.name, type: value.type === 'light' ? 'light' : 'dark', colors: cleanColors(value.colors) }
}

export function loadThemeState(): ThemeState {
  const storedThemes = readJson(THEMES_KEY)
  const themes = Array.isArray(storedThemes) ? storedThemes.map(cleanTheme).filter((theme): theme is Theme => theme !== null) : []
  const storedOverrides = readJson(OVERRIDES_KEY)
  const overrides = isRecord(storedOverrides) ? Object.fromEntries(Object.entries(storedOverrides).map(([id, colors]) => [id, cleanColors(colors)])) : {}
  return { selected: readStored(SELECTED_KEY) ?? SYSTEM_THEME, themes, overrides }
}

function prefersDark(): boolean {
  return typeof window.matchMedia === 'function' && window.matchMedia('(prefers-color-scheme: dark)').matches
}

export function allThemes(state: ThemeState): Theme[] {
  return [...BUILTIN_THEMES, ...state.themes]
}

export function activeTheme(state: ThemeState, dark = prefersDark()): Theme {
  const systemTheme = BUILTIN_THEMES[dark ? 1 : 0]
  return state.selected === SYSTEM_THEME ? systemTheme : (allThemes(state).find((theme) => theme.id === state.selected) ?? systemTheme)
}

export function resolvePalette(theme: Theme, overrides: ThemeColors = {}): Record<string, string> {
  const explicit = { ...theme.colors, ...overrides }
  const palette = { ...BUILTIN_PALETTES[theme.type], ...explicit }
  for (const derived of DERIVED_COLORS) {
    const source = explicit[derived.from]
    if (source && !(derived.variable in explicit)) {
      palette[derived.variable] = derived.alpha === undefined ? source : withAlpha(source, derived.alpha)
    }
  }
  return palette
}

export function contrastWarnings(palette: Record<string, string>): string[] {
  return CONTRAST_PAIRS.flatMap(([foreground, background, label]) => {
    const ratio = contrastRatio(palette[foreground], palette[background], palette['--bg'])
    return ratio < AA_CONTRAST ? [`${label}: contrast ${ratio.toFixed(1)}:1, below the WCAG AA minimum of ${String(AA_CONTRAST)}:1.`] : []
  })
}

function applyTheme(state: ThemeState): void {
  const theme = activeTheme(state)
  const style = document.documentElement.style
  for (const [variable, value] of Object.entries(resolvePalette(theme, state.overrides[theme.id]))) {
    style.setProperty(variable, value)
  }
  style.colorScheme = theme.type
}

const listeners = new Set<() => void>()
let current: ThemeState | undefined

function snapshot(): ThemeState {
  current ??= loadThemeState()
  return current
}

function update(next: ThemeState): void {
  current = next
  applyTheme(next)
  for (const listener of listeners) {
    listener()
  }
}

function commit(next: ThemeState): void {
  writeStored(SELECTED_KEY, next.selected)
  writeStored(THEMES_KEY, JSON.stringify(next.themes))
  writeStored(OVERRIDES_KEY, JSON.stringify(next.overrides))
  update(next)
}

export function selectTheme(id: string): void {
  commit({ ...snapshot(), selected: id })
}

export function addTheme(parsed: ParsedTheme): Theme {
  const theme: Theme = { id: `imported-${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`, name: parsed.name, type: parsed.type, colors: cleanColors(parsed.colors) }
  const state = snapshot()
  commit({ ...state, selected: theme.id, themes: [...state.themes, theme] })
  return theme
}

export function removeTheme(id: string): void {
  const state = snapshot()
  const overrides = Object.fromEntries(Object.entries(state.overrides).filter(([themeId]) => themeId !== id))
  commit({ selected: state.selected === id ? SYSTEM_THEME : state.selected, themes: state.themes.filter((theme) => theme.id !== id), overrides })
}

export function setOverride(themeId: string, variable: string, value: string): boolean {
  const color = parseColor(value)
  if (!color || !SLOT_VARIABLES.has(variable)) {
    return false
  }
  const state = snapshot()
  commit({ ...state, overrides: { ...state.overrides, [themeId]: { ...state.overrides[themeId], [variable]: color } } })
  return true
}

export function resetOverrides(themeId: string, variable?: string): void {
  const state = snapshot()
  const remaining = variable ? Object.fromEntries(Object.entries(state.overrides[themeId] ?? {}).filter(([name]) => name !== variable)) : {}
  commit({ ...state, overrides: { ...state.overrides, [themeId]: remaining } })
}

export function syncTheme(): void {
  update(loadThemeState())
  window.addEventListener('storage', (event) => {
    if (event.key === null || [SELECTED_KEY, THEMES_KEY, OVERRIDES_KEY].includes(event.key)) {
      update(loadThemeState())
    }
  })
  if (typeof window.matchMedia === 'function') {
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
      update({ ...snapshot() })
    })
  }
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener)
  return () => {
    listeners.delete(listener)
  }
}

export function useThemeState(): ThemeState {
  return useSyncExternalStore(subscribe, snapshot)
}
