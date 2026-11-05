import { describe, expect, it } from 'vitest'

import { COLOR_SLOTS } from './themeMapping'
import { exportVscodeTheme, mapThemeColors, parseVscodeTheme, scopeColor, stripJsonc } from './vscodeTheme'

const JSONC_THEME = `{
  // Exported from a VS Code extension
  "name": "Night Owl Test",
  "type": "dark",
  /* workbench colors */
  "colors": {
    "editor.background": "#011627",
    "editor.foreground": "#d6deeb",
    "textLink.foreground": "#82AAFF",
    "diffEditor.insertedLineBackground": "rgba(173, 219, 103, 0.13)",
    "focusBorder": "#122d42",
  },
  "tokenColors": [
    { "scope": "comment", "settings": { "foreground": "#637777", "fontStyle": "italic" } },
    { "scope": ["string", "string.quoted"], "settings": { "foreground": "#ecc48d" } },
  ],
}`

describe('stripJsonc', () => {
  it('removes comments and trailing commas but keeps them inside strings', () => {
    const text = '{"url": "https://example.com/*x*/", // note\n "list": [1, 2,], /* gone */ "a": {"b": "c,}",},}'

    expect(JSON.parse(stripJsonc(text))).toEqual({ url: 'https://example.com/*x*/', list: [1, 2], a: { b: 'c,}' } })
  })

  it('keeps escaped quotes inside strings', () => {
    expect(JSON.parse(stripJsonc('{"a": "say \\"hi\\" // not a comment",}'))).toEqual({ a: 'say "hi" // not a comment' })
  })
})

describe('parseVscodeTheme', () => {
  it('reads a JSONC theme and maps workbench colors and token colors', () => {
    const theme = parseVscodeTheme(JSONC_THEME, 'night-owl.json')

    expect(theme.name).toBe('Night Owl Test')
    expect(theme.type).toBe('dark')
    expect(theme.colors).toMatchObject({
      '--bg': '#011627',
      '--text': '#d6deeb',
      '--accent': '#82aaff',
      '--focus': '#122d42',
      '--diff-insert': '#addb6721',
      '--hl-comment': '#637777',
      '--hl-string': '#ecc48d',
    })
  })

  it('leaves out missing colors so they fall back to the built in palette', () => {
    const theme = parseVscodeTheme(JSONC_THEME)

    expect(theme.colors).not.toHaveProperty('--border')
    expect(theme.colors).not.toHaveProperty('--hl-keyword')
    expect(theme.notes.at(-1)).toBe(`7 of ${String(COLOR_SLOTS.length)} colors come from the theme, the others from the built in Dark palette.`)
  })

  it('accepts only hex and rgb colors and ignores everything else', () => {
    const colors = mapThemeColors(
      {
        'editor.background': 'red',
        'editor.foreground': '#fff; background: url(javascript:alert(1))',
        foreground: '#abc',
        focusBorder: 'var(--text)',
        'panel.border': 'rgba(300, 0, 0, 1)',
        'sideBar.border': 'rgb(1, 2, 3)',
        'input.border': 42,
        descriptionForeground: '#12',
        'textLink.foreground': { color: '#ffffff' },
      },
      [{ scope: 'keyword', settings: { foreground: 'expression(alert(1))' } }, { scope: 'string', settings: 'nope' }, 'junk'],
    )

    expect(colors).toEqual({ '--text': '#aabbcc', '--border': '#010203' })
  })

  it('takes the type from the background when the file has none', () => {
    expect(parseVscodeTheme('{"colors": {"editor.background": "#fdf6e3"}}').type).toBe('light')
    expect(parseVscodeTheme('{"colors": {"editor.background": "#002b36"}}').type).toBe('dark')
    expect(parseVscodeTheme('{"type": "hcLight", "colors": {"editor.background": "#000000"}}').type).toBe('light')
  })

  it('uses the file name when the theme has no name', () => {
    expect(parseVscodeTheme('{"colors": {"editor.background": "#000000"}}', 'dracula.json').name).toBe('dracula')
  })

  it('explains themes that rely on include', () => {
    expect(() => parseVscodeTheme('{"include": "./dark_vs.json"}')).toThrow('This theme takes its colors from "./dark_vs.json" with include, which bussola does not read. Import that file instead.')

    const theme = parseVscodeTheme('{"include": "./dark_plus.json", "colors": {"editor.background": "#1e1e1e"}}')
    expect(theme.notes[0]).toBe('This theme also takes colors from "./dark_plus.json" with include, which bussola does not read: those colors use the built in Dark palette.')
  })

  it('rejects files that are not JSON or have no usable colors', () => {
    expect(() => parseVscodeTheme('<theme/>')).toThrow('not valid JSON')
    expect(() => parseVscodeTheme('[]')).toThrow('has no colors or tokenColors')
    expect(() => parseVscodeTheme('{"colors": {"editor.background": "blue"}}')).toThrow('No colors found')
  })
})

describe('scope mapping', () => {
  const rule = (scope: string | string[], foreground: string) => ({ scope, settings: { foreground } })

  it('matches a selector against longer scopes on a dot boundary', () => {
    const colors = mapThemeColors({}, [rule('keyword', '#111111'), rule('constant', '#222222'), rule('entity.name', '#333333'), rule('key', '#999999')])

    expect(colors['--hl-keyword']).toBe('#111111')
    expect(colors['--hl-constant']).toBe('#222222')
    expect(colors['--hl-title']).toBe('#333333')
    expect(colors['--hl-tag']).toBe('#333333')
  })

  it('prefers the most specific selector and then the later rule', () => {
    const rules = [rule('entity.name', '#333333'), rule('entity.name.tag', '#444444'), rule('entity.name.tag', '#555555'), rule('entity', '#666666')]

    expect(mapThemeColors({}, rules)['--hl-tag']).toBe('#555555')
    expect(mapThemeColors({}, rules)['--hl-title']).toBe('#333333')
  })

  it('reads comma separated and array scopes and skips selectors it cannot match alone', () => {
    const colors = mapThemeColors({}, [rule('markup.inserted, markup.deleted', '#777777'), rule(['source.python string', 'comment'], '#888888'), rule('-string', '#999999')])

    expect(colors['--hl-addition']).toBe('#777777')
    expect(colors['--hl-deletion']).toBe('#777777')
    expect(colors['--hl-comment']).toBe('#888888')
    expect(colors).not.toHaveProperty('--hl-string')
  })

  it('tries the scopes of a color in order', () => {
    expect(mapThemeColors({}, [rule('storage.type', '#aaaaaa')])['--hl-keyword']).toBe('#aaaaaa')
    expect(mapThemeColors({}, [rule('storage.type', '#aaaaaa'), rule('keyword.control.flow', '#bbbbbb'), rule('keyword.control', '#cccccc')])['--hl-keyword']).toBe('#cccccc')
  })

  it('ignores rules without a foreground color', () => {
    expect(scopeColor([], 'comment')).toBeNull()
    expect(mapThemeColors({}, [rule('comment', '#123456'), { scope: 'comment', settings: { fontStyle: 'italic' } }])['--hl-comment']).toBe('#123456')
  })

  it('uses the global token settings when the workbench has no editor colors', () => {
    expect(mapThemeColors({}, [{ settings: { foreground: '#f8f8f2', background: '#272822' } }])).toEqual({ '--text': '#f8f8f2', '--bg': '#272822' })
  })
})

describe('exportVscodeTheme', () => {
  it('writes a theme that imports back to the same colors', () => {
    const palette = Object.fromEntries(COLOR_SLOTS.map((slot, index) => [slot.variable, `#${index.toString(16).padStart(2, '0')}20${(255 - index).toString(16)}`]))
    palette['--diff-insert'] = 'rgba(18, 134, 106, 0.08)'

    const exported = exportVscodeTheme('Custom', 'light', palette)
    const theme = parseVscodeTheme(exported)

    expect(theme.name).toBe('Custom')
    expect(theme.type).toBe('light')
    expect(theme.colors).toEqual({ ...palette, '--diff-insert': '#12866a14' })
  })

  it('names each workbench color of a slot once', () => {
    const keys = COLOR_SLOTS.flatMap((slot) => slot.workbench ?? [])
    expect(new Set(keys).size).toBe(keys.length)
  })
})
