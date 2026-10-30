import { setDiffWrap, useDiffWrap } from '../settings/diffWrap'

const WRAP_TITLE = 'Wrap long lines in the diff. Continuation lines keep the indentation of their line and have no line number.'

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
    <button type="button" className="toggle" aria-pressed={wrap} title={WRAP_TITLE} onClick={() => { setDiffWrap(!wrap) }}>
      Wrap lines
    </button>
  )
}
