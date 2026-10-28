import { useState } from 'react'

import {
  DEFAULT_CODE_FONT,
  MAX_CODE_SIZE,
  MIN_CODE_SIZE,
  applyCodeFont,
  canListSystemFonts,
  clampSize,
  featureSettings,
  fontStack,
  installedCommonFonts,
  isInstalled,
  ligatureVariant,
  loadCodeFont,
  saveCodeFont,
  systemMonospaceFonts,
  type CodeFont,
} from '../settings/codeFont'

const PREVIEW = 'def total(items: list[int]) -> int:\n    return sum(i for i in items if i != 0 and i >= -1)  # => === 0O1lI'

export function CodeFontSettings() {
  const [open, setOpen] = useState(false)
  return (
    <div className="popover-anchor">
      <button type="button" aria-expanded={open} title="Choose the font used to show code" onClick={() => { setOpen(!open) }}>
        Code font
      </button>
      {open && (
        <div className="popover" role="dialog" aria-label="Code font">
          <CodeFontPanel />
        </div>
      )}
    </div>
  )
}

function CodeFontPanel() {
  const [font, setFont] = useState<CodeFont>(loadCodeFont)
  const [sizeText, setSizeText] = useState(() => String(font.size))
  const [families, setFamilies] = useState<string[]>(installedCommonFonts)
  const [source, setSource] = useState<'common' | 'system'>('common')
  const [error, setError] = useState<string | null>(null)

  const update = (next: CodeFont) => {
    setFont(next)
    applyCodeFont(next)
    saveCodeFont(next)
  }
  const listSystemFonts = () => {
    setError(null)
    systemMonospaceFonts().then(
      (found) => {
        setFamilies(found)
        setSource('system')
      },
      () => { setError('The browser did not allow reading the installed fonts.') },
    )
  }
  const changeSize = (text: string) => {
    setSizeText(text)
    const size = Number(text)
    if (text !== '' && size >= MIN_CODE_SIZE && size <= MAX_CODE_SIZE) {
      update({ ...font, size: clampSize(size) })
    }
  }
  const reset = () => {
    update(DEFAULT_CODE_FONT)
    setSizeText(String(DEFAULT_CODE_FONT.size))
  }
  const missing = font.family.trim() !== '' && !isInstalled(font.family)

  return (
    <div className="stack code-font-panel">
      <label htmlFor="code-font-family">Font</label>
      <input
        id="code-font-family"
        list="code-font-families"
        value={font.family}
        placeholder="Default (SF Mono, Menlo...)"
        onChange={(event) => { update({ ...font, family: event.target.value }) }}
      />
      <datalist id="code-font-families">
        {families.map((family) => (
          <option key={family} value={family} />
        ))}
      </datalist>
      <p className="muted">
        {source === 'system' ? `${String(families.length)} monospaced fonts installed on this computer.` : `${String(families.length)} common coding fonts found. You can also type any installed font.`}
      </p>
      {canListSystemFonts() && source === 'common' && (
        <button type="button" onClick={listSystemFonts}>
          List all installed monospaced fonts
        </button>
      )}
      {missing && <p className="muted">{`"${font.family}" is not installed, so the default font is used.`}</p>}
      {error && <p className="muted">{error}</p>}
      <label htmlFor="code-font-size">Size</label>
      <input
        id="code-font-size"
        type="number"
        min={MIN_CODE_SIZE}
        max={MAX_CODE_SIZE}
        value={sizeText}
        onChange={(event) => { changeSize(event.target.value) }}
        onBlur={() => { setSizeText(String(font.size)) }}
      />
      <label className="checkbox">
        <input type="checkbox" checked={font.ligatures} onChange={(event) => { update({ ...font, ligatures: event.target.checked }) }} />
        Ligatures (for fonts that have them, like Fira Code or JetBrains Mono)
      </label>
      <label htmlFor="code-font-features">Font features</label>
      <input
        id="code-font-features"
        value={font.features}
        placeholder="e.g. ss01 ss02 zero"
        title="OpenType features to turn on, separated by spaces. Some fonts keep ligatures or alternate glyphs in stylistic sets (Monaspace: ss01 to ss08) or in dlig."
        onChange={(event) => { update({ ...font, features: event.target.value }) }}
      />
      <pre
        className="code-font-preview"
        style={{ fontFamily: fontStack(font), fontSize: `${String(font.size)}px`, fontVariantLigatures: ligatureVariant(font), fontFeatureSettings: featureSettings(font) }}
      >
        {PREVIEW}
      </pre>
      <button type="button" onClick={reset}>
        Reset to default
      </button>
    </div>
  )
}
