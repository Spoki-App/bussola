import { useState } from 'react'

import { opaqueHex, parseColor } from '../settings/colors'
import { activePalette, contrastWarnings, resetOverrides, setOverride, useThemeState } from '../settings/theme'
import { COLOR_GROUPS, COLOR_SLOTS, type ColorSlot } from '../settings/themeMapping'

interface ColorRowProps {
  themeId: string
  slot: ColorSlot
  value: string
  overridden: boolean
}

function ColorRow({ themeId, slot, value, overridden }: ColorRowProps) {
  const [text, setText] = useState<string | null>(null)
  const color = parseColor(value) ?? value
  const id = `theme-color-${slot.variable.slice(2)}`

  const changeText = (next: string) => {
    setText(next)
    setOverride(themeId, slot.variable, next)
  }
  const pick = (hex: string) => {
    setOverride(themeId, slot.variable, `${hex}${color.slice(7, 9)}`)
  }

  return (
    <div className="theme-color">
      <label htmlFor={id}>{slot.label}</label>
      <input type="color" aria-label={`${slot.label} color picker`} value={opaqueHex(color)} onChange={(event) => { pick(event.target.value) }} />
      <input
        id={id}
        className="theme-color-hex"
        spellCheck={false}
        value={text ?? color}
        aria-invalid={text !== null && parseColor(text) === null}
        onFocus={() => { setText(color) }}
        onBlur={() => { setText(null) }}
        onChange={(event) => { changeText(event.target.value) }}
      />
      <button type="button" className="link" disabled={!overridden} onClick={() => { resetOverrides(themeId, slot.variable) }}>
        Reset
      </button>
    </div>
  )
}

function ThemePreview() {
  return (
    <div className="theme-preview" aria-label="Preview">
      <p>
        Text, <span className="muted">secondary text</span> and <span className="theme-preview-link">a link</span>
      </p>
      <pre>
        <code>
          <span className="hljs-keyword">def</span> <span className="hljs-title">total</span>(<span className="hljs-params">items</span>):{'\n'}
          <span style={{ background: 'var(--diff-delete)', display: 'block' }}>
            {'-     '}
            <span className="hljs-keyword">return</span> <span style={{ background: 'var(--diff-delete-word)' }}>len</span>(items)
          </span>
          <span style={{ background: 'var(--diff-insert)', display: 'block' }}>
            {'+     '}
            <span className="hljs-keyword">return</span> <span style={{ background: 'var(--diff-insert-word)' }}>sum</span>(items, <span className="hljs-number">0</span>) <span className="hljs-comment"># all items</span>
          </span>
          {'      log('}
          <span className="hljs-string">{'"done"'}</span>
          {')'}
        </code>
      </pre>
    </div>
  )
}

export function ThemeColorsPanel() {
  const { theme, overrides, palette } = activePalette(useThemeState())
  const warnings = contrastWarnings(palette)

  return (
    <div className="stack theme-colors-panel">
      <p className="muted">{`Changes apply to ${theme.name} at once and are kept on top of it.`}</p>
      <ThemePreview />
      {warnings.length > 0 && (
        <div role="alert" className="notice warning">
          {warnings.map((warning) => (
            <p key={warning}>{warning}</p>
          ))}
        </div>
      )}
      {COLOR_GROUPS.map((group) => (
        <fieldset key={group} className="theme-color-group">
          <legend>{group}</legend>
          {COLOR_SLOTS.filter((slot) => slot.group === group).map((slot) => (
            <ColorRow key={`${theme.id}${slot.variable}`} themeId={theme.id} slot={slot} value={palette[slot.variable]} overridden={slot.variable in overrides} />
          ))}
        </fieldset>
      ))}
      <button type="button" disabled={Object.keys(overrides).length === 0} onClick={() => { resetOverrides(theme.id) }}>
        {`Reset all colors of ${theme.name}`}
      </button>
    </div>
  )
}
