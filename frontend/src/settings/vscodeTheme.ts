import { isDark, parseColor } from './colors'
import { isRecord } from './storage'
import { COLOR_SLOTS, type ThemeType } from './themeMapping'

export type ThemeColors = Record<string, string>

export interface ParsedTheme {
  name: string
  type: ThemeType
  colors: ThemeColors
  notes: string[]
}

interface TokenRule {
  selectors: string[]
  foreground: string
}

const LIGHT_TYPES = new Set(['light', 'hcLight', 'hc-light', 'vs'])
const DARK_TYPES = new Set(['dark', 'hc', 'hcDark', 'hc-black', 'vs-dark'])

function scan(text: string, onCode: (index: number) => number | undefined): string {
  let output = ''
  let index = 0
  while (index < text.length) {
    const char = text[index]
    if (char === '"') {
      let end = index + 1
      while (end < text.length && text[end] !== '"') {
        end += text[end] === '\\' ? 2 : 1
      }
      output += text.slice(index, end + 1)
      index = end + 1
      continue
    }
    const skipTo = onCode(index)
    if (skipTo === undefined) {
      output += char
      index += 1
    } else {
      index = skipTo
    }
  }
  return output
}

export function stripJsonc(text: string): string {
  const withoutComments = scan(text, (index) => {
    if (text.startsWith('//', index)) {
      const end = text.indexOf('\n', index)
      return end === -1 ? text.length : end
    }
    if (text.startsWith('/*', index)) {
      const end = text.indexOf('*/', index + 2)
      return end === -1 ? text.length : end + 2
    }
    return undefined
  })
  return scan(withoutComments, (index) => (withoutComments[index] === ',' && /^\s*[}\]]/.test(withoutComments.slice(index + 1)) ? index + 1 : undefined))
}

function selectorsOf(scope: unknown): string[] {
  const parts = typeof scope === 'string' ? [scope] : Array.isArray(scope) ? scope.filter((part): part is string => typeof part === 'string') : []
  return parts
    .flatMap((part) => part.split(','))
    .map((selector) => selector.trim())
    .filter((selector) => /^[\w.-]+$/.test(selector) && !selector.startsWith('-'))
}

function tokenRules(tokenColors: unknown): TokenRule[] {
  if (!Array.isArray(tokenColors)) {
    return []
  }
  return tokenColors.flatMap((entry) => {
    if (!isRecord(entry) || !isRecord(entry.settings)) {
      return []
    }
    const foreground = parseColor(entry.settings.foreground)
    return foreground ? [{ selectors: selectorsOf(entry.scope), foreground }] : []
  })
}

function scopeColor(rules: TokenRule[], scope: string): string | null {
  let best: { specificity: number; color: string } | null = null
  for (const rule of rules) {
    for (const selector of rule.selectors) {
      if (scope === selector || scope.startsWith(`${selector}.`)) {
        const specificity = selector.split('.').length
        if (!best || specificity >= best.specificity) {
          best = { specificity, color: rule.foreground }
        }
      }
    }
  }
  return best?.color ?? null
}

function globalSettings(tokenColors: unknown): Record<string, unknown> {
  const global: unknown = Array.isArray(tokenColors) ? tokenColors.find((entry) => isRecord(entry) && entry.scope === undefined && isRecord(entry.settings)) : undefined
  return isRecord(global) && isRecord(global.settings) ? global.settings : {}
}

export function mapThemeColors(colors: unknown, tokenColors: unknown): ThemeColors {
  const workbench = isRecord(colors) ? colors : {}
  const rules = tokenRules(tokenColors)
  const global = globalSettings(tokenColors)
  const fallbacks: Record<string, unknown> = { '--text': global.foreground, '--bg': global.background }
  const mapped: ThemeColors = {}
  for (const slot of COLOR_SLOTS) {
    const fromWorkbench = (slot.workbench ?? []).map((key) => parseColor(workbench[key])).find((color) => color !== null)
    const fromScopes = (slot.scopes ?? []).map((scope) => scopeColor(rules, scope)).find((color) => color !== null)
    const color = fromWorkbench ?? fromScopes ?? parseColor(fallbacks[slot.variable])
    if (color) {
      mapped[slot.variable] = color
    }
  }
  return mapped
}

function themeType(type: unknown, colors: ThemeColors): ThemeType {
  if (typeof type === 'string' && LIGHT_TYPES.has(type)) {
    return 'light'
  }
  if (typeof type === 'string' && DARK_TYPES.has(type)) {
    return 'dark'
  }
  return colors['--bg'] && !isDark(colors['--bg']) ? 'light' : 'dark'
}

function themeName(name: unknown, fileName: string): string {
  const text = typeof name === 'string' ? name.trim() : ''
  return (text || fileName.replace(/\.jsonc?$/i, '') || 'Imported theme').slice(0, 80)
}

export function parseVscodeTheme(text: string, fileName = ''): ParsedTheme {
  let parsed: unknown
  try {
    parsed = JSON.parse(stripJsonc(text))
  } catch {
    throw new Error('This file is not a VS Code color theme: it is not valid JSON.')
  }
  if (!isRecord(parsed)) {
    throw new Error('This file is not a VS Code color theme: it has no colors or tokenColors.')
  }
  const include = typeof parsed.include === 'string' ? parsed.include : typeof parsed.tokenColors === 'string' ? parsed.tokenColors : null
  const colors = mapThemeColors(parsed.colors, parsed.tokenColors)
  const count = Object.keys(colors).length
  if (count === 0) {
    throw new Error(
      include
        ? `This theme takes its colors from "${include}" with include, which bussola does not read. Import that file instead.`
        : 'No colors found: the file has no hex or rgb colors that bussola uses.',
    )
  }
  const type = themeType(parsed.type, colors)
  const typeName = type === 'light' ? 'Light' : 'Dark'
  const notes = [`${String(count)} of ${String(COLOR_SLOTS.length)} colors come from the theme, the others from the built in ${typeName} palette.`]
  if (include) {
    notes.unshift(`This theme also takes colors from "${include}" with include, which bussola does not read: those colors use the built in ${typeName} palette.`)
  }
  return { name: themeName(parsed.name, fileName), type, colors, notes }
}

export function exportVscodeTheme(name: string, type: ThemeType, palette: ThemeColors): string {
  const colors: ThemeColors = {}
  const tokenColors: { name: string; scope: string[]; settings: { foreground: string } }[] = []
  for (const slot of COLOR_SLOTS) {
    const color = parseColor(palette[slot.variable])
    if (!color) {
      continue
    }
    if (slot.workbench) {
      colors[slot.workbench[0]] = color
    }
    if (slot.scopes) {
      tokenColors.push({ name: slot.label, scope: slot.scopes, settings: { foreground: color } })
    }
  }
  return `${JSON.stringify({ $schema: 'vscode://schemas/color-theme', name, type, colors, tokenColors }, null, 2)}\n`
}
