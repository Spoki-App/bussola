export interface Rgba {
  r: number
  g: number
  b: number
  a: number
}

const HEX = /^#([0-9a-f]{3,4}|[0-9a-f]{6}|[0-9a-f]{8})$/i
const RGB = /^rgba?\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*(?:,\s*(\d*\.?\d+)(%?)\s*)?\)$/i

export const AA_CONTRAST = 4.5

function rgbaOf(value: string): Rgba | null {
  const text = value.trim()
  const hex = HEX.exec(text)?.[1]
  if (hex) {
    const full = hex.length <= 4 ? hex.replace(/./g, '$&$&') : hex
    const channel = (index: number) => parseInt(full.slice(index * 2, index * 2 + 2) || 'ff', 16)
    return { r: channel(0), g: channel(1), b: channel(2), a: channel(3) / 255 }
  }
  const rgb = RGB.exec(text)
  if (!rgb) {
    return null
  }
  const [r, g, b] = [rgb[1], rgb[2], rgb[3]].map(Number)
  const alpha = rgb[4] ? Number(rgb[4]) / (rgb[5] ? 100 : 1) : 1
  if (r > 255 || g > 255 || b > 255 || alpha > 1) {
    return null
  }
  return { r, g, b, a: alpha }
}

function pair(channel: number): string {
  return Math.round(channel).toString(16).padStart(2, '0')
}

function hexOf({ r, g, b, a }: Rgba): string {
  const alpha = Math.round(a * 255)
  return `#${pair(r)}${pair(g)}${pair(b)}${alpha === 255 ? '' : pair(alpha)}`
}

export function parseColor(value: unknown): string | null {
  if (typeof value !== 'string') {
    return null
  }
  const rgba = rgbaOf(value)
  return rgba ? hexOf(rgba) : null
}

export function opaqueHex(color: string): string {
  return (parseColor(color) ?? '#000000').slice(0, 7)
}

export function withAlpha(color: string, alpha: number): string {
  const rgba = rgbaOf(color)
  return rgba ? hexOf({ ...rgba, a: alpha }) : color
}

function over(top: Rgba, bottom: Rgba): Rgba {
  const mix = (front: number, back: number) => front * top.a + back * (1 - top.a)
  return { r: mix(top.r, bottom.r), g: mix(top.g, bottom.g), b: mix(top.b, bottom.b), a: 1 }
}

function luminance({ r, g, b }: Rgba): number {
  const linear = (channel: number) => {
    const value = channel / 255
    return value <= 0.03928 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4
  }
  return 0.2126 * linear(r) + 0.7152 * linear(g) + 0.0722 * linear(b)
}

export function isDark(color: string): boolean {
  const rgba = rgbaOf(color)
  return rgba !== null && luminance(rgba) < 0.2
}

export function contrastRatio(foreground: string, background: string, base = '#ffffff'): number {
  const page = over(rgbaOf(base) ?? { r: 255, g: 255, b: 255, a: 1 }, { r: 255, g: 255, b: 255, a: 1 })
  const back = over(rgbaOf(background) ?? page, page)
  const front = over(rgbaOf(foreground) ?? back, back)
  const [light, dark] = [luminance(front), luminance(back)].sort((left, right) => right - left)
  return (light + 0.05) / (dark + 0.05)
}
