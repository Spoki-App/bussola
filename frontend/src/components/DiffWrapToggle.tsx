import { setDiffWrap, useDiffWrap } from '../settings/diffWrap'

const WRAP_TITLE = 'Wrap long lines in the diff. Continuation lines keep the indentation of their line and have no line number. In split view each side then scrolls sideways on its own.'

export function DiffWrapCheckbox() {
  const wrap = useDiffWrap()
  return (
    <label className="checkbox" title={WRAP_TITLE}>
      <input type="checkbox" checked={wrap} onChange={(event) => { setDiffWrap(event.target.checked) }} />
      Wrap long lines
    </label>
  )
}

export function DiffWrapButton() {
  const wrap = useDiffWrap()
  return (
    <button type="button" className="wrap-toggle" aria-pressed={wrap} aria-label="Wrap long lines" title={WRAP_TITLE} onClick={() => { setDiffWrap(!wrap) }}>
      <svg className="wrap-icon" viewBox="0 0 24 24" aria-hidden="true">
        <path d="M4 6h16M4 12h12.5a3.5 3.5 0 0 1 0 7H12M4 19h4M14.5 16.5 12 19l2.5 2.5" />
      </svg>
    </button>
  )
}
