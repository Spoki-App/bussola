import { readStored, writeStored } from './storage'

export interface CodeFont {
  family: string
  size: number
  ligatures: boolean
  features: string
}

export const DEFAULT_CODE_FONT: CodeFont = { family: '', size: 12, ligatures: true, features: '' }
export const MIN_CODE_SIZE = 9
export const MAX_CODE_SIZE = 24

const STORAGE_KEY = 'rtool.codeFont'
const FALLBACK_STACK = "ui-monospace, 'SF Mono', Menlo, Consolas, monospace"
const PROBE_TEXT = 'mmmmmmmmmmlliWW@#0O'
const PROBE_SIZE = '72px'
const BASE_FAMILIES = ['monospace', 'serif', 'sans-serif']
const FEATURE_TAG = /^[a-zA-Z0-9]{4}$/

export const COMMON_CODE_FONTS = [
  'SF Mono',
  'Menlo',
  'Monaco',
  'JetBrains Mono',
  'Fira Code',
  'Fira Mono',
  'Cascadia Code',
  'Cascadia Mono',
  'Source Code Pro',
  'IBM Plex Mono',
  'Hack',
  'Iosevka',
  'Inconsolata',
  'Ubuntu Mono',
  'DejaVu Sans Mono',
  'Roboto Mono',
  'Victor Mono',
  'Operator Mono',
  'Input Mono',
  'Geist Mono',
  'Monaspace Neon',
  'Berkeley Mono',
  'Consolas',
  'Courier New',
  'Andale Mono',
  'PT Mono',
]

export function cleanFamily(family: string): string {
  return family.replace(/["\\;{}]/g, '').trim()
}

export function fontStack(font: CodeFont): string {
  const family = cleanFamily(font.family)
  return family ? `"${family}", ${FALLBACK_STACK}` : FALLBACK_STACK
}

export function featureTags(features: string): string[] {
  return [...new Set(features.split(/[\s,]+/).filter((tag) => FEATURE_TAG.test(tag)))]
}

export function featureSettings(font: CodeFont): string {
  const tags = featureTags(font.features).map((tag) => `"${tag}" 1`)
  if (!font.ligatures) {
    tags.push('"liga" 0', '"calt" 0', '"dlig" 0')
  }
  return tags.length > 0 ? tags.join(', ') : 'normal'
}

export function ligatureVariant(font: CodeFont): string {
  return font.ligatures ? 'normal' : 'none'
}

export function clampSize(size: number): number {
  return Number.isFinite(size) ? Math.min(MAX_CODE_SIZE, Math.max(MIN_CODE_SIZE, Math.round(size))) : DEFAULT_CODE_FONT.size
}

export function loadCodeFont(): CodeFont {
  try {
    const stored: unknown = JSON.parse(readStored(STORAGE_KEY) ?? 'null')
    if (stored && typeof stored === 'object' && 'family' in stored && 'size' in stored && typeof stored.family === 'string' && typeof stored.size === 'number') {
      const ligatures = 'ligatures' in stored && typeof stored.ligatures === 'boolean' ? stored.ligatures : DEFAULT_CODE_FONT.ligatures
      const features = 'features' in stored && typeof stored.features === 'string' ? stored.features : DEFAULT_CODE_FONT.features
      return { family: cleanFamily(stored.family), size: clampSize(stored.size), ligatures, features }
    }
  } catch {
    return DEFAULT_CODE_FONT
  }
  return DEFAULT_CODE_FONT
}

export function saveCodeFont(font: CodeFont): void {
  writeStored(STORAGE_KEY, JSON.stringify(font))
}

export function applyCodeFont(font: CodeFont): void {
  const style = document.documentElement.style
  style.setProperty('--mono', fontStack(font))
  style.setProperty('--code-size', `${String(clampSize(font.size))}px`)
  style.setProperty('--code-ligatures', ligatureVariant(font))
  style.setProperty('--code-features', featureSettings(font))
}

function textWidth(context: CanvasRenderingContext2D, family: string): number {
  context.font = `${PROBE_SIZE} ${family}`
  return context.measureText(PROBE_TEXT).width
}

function probeContext(): CanvasRenderingContext2D | null {
  try {
    return document.createElement('canvas').getContext('2d')
  } catch {
    return null
  }
}

export function isInstalled(family: string, context = probeContext()): boolean {
  const name = cleanFamily(family)
  if (!context || !name) {
    return false
  }
  return BASE_FAMILIES.some((base) => textWidth(context, `"${name}", ${base}`) !== textWidth(context, base))
}

export function isMonospace(family: string, context = probeContext()): boolean {
  if (!context) {
    return false
  }
  context.font = `${PROBE_SIZE} "${cleanFamily(family)}", monospace`
  return context.measureText('iiiii').width === context.measureText('WWWWW').width
}

interface LocalFontData {
  family: string
}

type QueryLocalFonts = () => Promise<LocalFontData[]>

export function canListSystemFonts(): boolean {
  return 'queryLocalFonts' in window
}

export async function systemMonospaceFonts(): Promise<string[]> {
  const query = (window as unknown as { queryLocalFonts: QueryLocalFonts }).queryLocalFonts
  const fonts = await query()
  const context = probeContext()
  const families = [...new Set(fonts.map((font) => font.family))]
  return families.filter((family) => isMonospace(family, context)).sort((left, right) => left.localeCompare(right))
}

export function installedCommonFonts(): string[] {
  const context = probeContext()
  return COMMON_CODE_FONTS.filter((family) => isInstalled(family, context))
}
