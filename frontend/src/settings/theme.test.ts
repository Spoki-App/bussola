import { beforeEach, describe, expect, it } from 'vitest'

import css from '../index.css?raw'
import { contrastRatio, parseColor, withAlpha } from './colors'
import { activeTheme, addTheme, contrastWarnings, loadThemeState, removeTheme, resetOverrides, resolvePalette, selectTheme, setOverride, syncTheme } from './theme'
import { BUILTIN_PALETTES } from './themeMapping'

function cssVariables(block: string): Record<string, string> {
  return Object.fromEntries([...block.matchAll(/(--[\w-]+):\s*([^;]+);/g)].map((match) => [match[1], match[2].trim()]))
}

function rootStyle(variable: string): string {
  return document.documentElement.style.getPropertyValue(variable)
}

describe('colors', () => {
  it('normalizes hex and rgb colors and rejects the rest', () => {
    expect(parseColor('#ABC')).toBe('#aabbcc')
    expect(parseColor('#abcd')).toBe('#aabbccdd')
    expect(parseColor('#112233ff')).toBe('#112233')
    expect(parseColor(' rgb(1, 2, 3) ')).toBe('#010203')
    expect(parseColor('rgba(255, 0, 0, 50%)')).toBe('#ff000080')
    expect(parseColor('transparent')).toBeNull()
    expect(parseColor('#12345')).toBeNull()
    expect(parseColor('rgba(0, 0, 0, 2)')).toBeNull()
    expect(withAlpha('#3cc79c', 0.14)).toBe('#3cc79c24')
  })

  it('computes the WCAG contrast ratio, blending translucent colors', () => {
    expect(contrastRatio('#000000', '#ffffff')).toBeCloseTo(21)
    expect(contrastRatio('#ffffff', '#ffffff')).toBeCloseTo(1)
    expect(contrastRatio('#00000000', '#ffffff')).toBeCloseTo(1)
  })
})

describe('built in palettes', () => {
  it('match the variables in index.css', () => {
    const light = cssVariables(/^:root \{([^}]*)\}/m.exec(css)?.[1] ?? '')
    const dark = cssVariables(/@media \(prefers-color-scheme: dark\) \{\s*:root \{([^}]*)\}/.exec(css)?.[1] ?? '')

    expect(Object.keys(BUILTIN_PALETTES.dark).sort()).toEqual(Object.keys(dark).sort())
    expect(BUILTIN_PALETTES.dark).toEqual(dark)
    for (const variable of Object.keys(BUILTIN_PALETTES.light)) {
      expect([variable, light[variable]]).toEqual([variable, BUILTIN_PALETTES.light[variable]])
    }
  })
})

describe('resolvePalette', () => {
  it('fills the colors a theme lacks from the built in palette of the same type', () => {
    const palette = resolvePalette({ id: 'x', name: 'X', type: 'light', colors: { '--bg': '#fdf6e3' } })

    expect(palette['--bg']).toBe('#fdf6e3')
    expect(palette['--text']).toBe(BUILTIN_PALETTES.light['--text'])
    expect(palette['--hl-keyword']).toBe(BUILTIN_PALETTES.light['--hl-keyword'])
  })

  it('derives tinted backgrounds from the colors they follow', () => {
    const palette = resolvePalette({ id: 'x', name: 'X', type: 'dark', colors: { '--sea': '#00ff00', '--muted': '#888888' } }, { '--accent': '#0000ff' })

    expect(palette['--sea-bg']).toBe('#00ff0024')
    expect(palette['--info-bg']).toBe('#0000ff21')
    expect(palette['--hl-comment']).toBe('#888888')
    expect(palette['--amber-bg']).toBe(BUILTIN_PALETTES.dark['--amber-bg'])
  })

  it('warns about text below WCAG AA contrast', () => {
    expect(contrastWarnings(resolvePalette({ id: 'light', name: 'Light', type: 'light', colors: {} }))).toEqual([])
    expect(contrastWarnings(resolvePalette({ id: 'x', name: 'X', type: 'light', colors: { '--text': '#bbbbbb' } }))).toEqual([
      'Text on the background: contrast 1.9:1, below the WCAG AA minimum of 4.5:1.',
      'Text on panels: contrast 1.8:1, below the WCAG AA minimum of 4.5:1.',
    ])
  })
})

describe('theme store', () => {
  beforeEach(() => {
    window.localStorage.clear()
    document.documentElement.removeAttribute('style')
    syncTheme()
  })

  it('starts with System and applies the system palette', () => {
    expect(loadThemeState().selected).toBe('system')
    expect(rootStyle('--bg')).toBe(BUILTIN_PALETTES.dark['--bg'])
    expect(document.documentElement.style.colorScheme).toBe('dark')
  })

  it('applies the chosen built in theme whatever the system setting', () => {
    selectTheme('light')

    expect(rootStyle('--bg')).toBe('#ffffff')
    expect(rootStyle('--diff-insert')).toBe(BUILTIN_PALETTES.light['--diff-insert'])
    expect(document.documentElement.style.colorScheme).toBe('light')
    expect(window.localStorage.getItem('bussola.theme')).toBe('light')
  })

  it('adds an imported theme, selects it and removes it', () => {
    const theme = addTheme({ name: 'Solarized', type: 'light', colors: { '--bg': '#fdf6e3', '--evil': '#000000', '--text': 'red' }, notes: [] })

    expect(activeTheme(loadThemeState())).toEqual(theme)
    expect(theme.colors).toEqual({ '--bg': '#fdf6e3' })
    expect(rootStyle('--bg')).toBe('#fdf6e3')
    expect(rootStyle('--text')).toBe(BUILTIN_PALETTES.light['--text'])

    removeTheme(theme.id)

    expect(loadThemeState()).toEqual({ selected: 'system', themes: [], overrides: {} })
  })

  it('overrides single colors and resets one or all of them', () => {
    selectTheme('dark')

    expect(setOverride('dark', '--accent', '#FF0000')).toBe(true)
    expect(setOverride('dark', '--hl-string', 'rgb(0, 128, 0)')).toBe(true)
    expect(setOverride('dark', '--text', 'url(x)')).toBe(false)
    expect(setOverride('dark', '--shadow-dialog', '#000000')).toBe(false)
    expect(rootStyle('--accent')).toBe('#ff0000')
    expect(rootStyle('--info-bg')).toBe('#ff000021')
    expect(rootStyle('--hl-string')).toBe('#008000')
    expect(loadThemeState().overrides).toEqual({ dark: { '--accent': '#ff0000', '--hl-string': '#008000' } })

    resetOverrides('dark', '--accent')

    expect(rootStyle('--accent')).toBe(BUILTIN_PALETTES.dark['--accent'])
    expect(rootStyle('--info-bg')).toBe(BUILTIN_PALETTES.dark['--info-bg'])
    expect(loadThemeState().overrides).toEqual({ dark: { '--hl-string': '#008000' } })

    resetOverrides('dark')

    expect(rootStyle('--hl-string')).toBe(BUILTIN_PALETTES.dark['--hl-string'])
    expect(loadThemeState().overrides).toEqual({ dark: {} })
  })

  it('keeps overrides per theme', () => {
    setOverride('light', '--bg', '#eeeeee')
    selectTheme('light')
    expect(rootStyle('--bg')).toBe('#eeeeee')

    selectTheme('dark')
    expect(rootStyle('--bg')).toBe(BUILTIN_PALETTES.dark['--bg'])
  })

  it('ignores stored values that are not colors', () => {
    window.localStorage.setItem('bussola.themes', JSON.stringify([{ id: 'x', name: 'X', type: 'light', colors: { '--bg': '#fff', '--text': '1px solid red' } }, 'junk']))
    window.localStorage.setItem('bussola.themeOverrides', '{"x": {"--accent": "expression(1)"}}')

    expect(loadThemeState()).toEqual({ selected: 'system', themes: [{ id: 'x', name: 'X', type: 'light', colors: { '--bg': '#ffffff' } }], overrides: { x: {} } })
  })
})
