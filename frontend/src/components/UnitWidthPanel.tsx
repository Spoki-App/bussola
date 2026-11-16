import type { LineLength } from '../api/lineLength'
import { UNIT_WIDTH_LABELS, lineLengthOrigin, nextUnitWidth, setUnitWidth, unitColumns, useUnitWidth, type UnitWidth } from '../settings/unitWidth'
import { Segmented } from './Segmented'

function widthTitle(width: UnitWidth, lineLength: LineLength | undefined): string {
  if (width === 'auto') {
    return `Unit width: Auto, ${lineLengthOrigin(lineLength)}`
  }
  return width === 'full' ? 'Unit width: Full, all the available space' : `Unit width: ${UNIT_WIDTH_LABELS[width]} columns`
}

export function UnitWidthPanel() {
  const width = useUnitWidth()
  return (
    <div className="stack">
      <Segmented label="Unit width" labels={UNIT_WIDTH_LABELS} value={width} onChange={setUnitWidth} />
      <p className="muted">The width of the unit box in columns of code, plus the line numbers. Auto uses the line length of the repository under review (.editorconfig, Ruff, Black or Prettier), or 120 when it sets none. In split layout the width applies to each side. A box never gets wider than the window.</p>
    </div>
  )
}

export function UnitWidthButton({ lineLength }: { lineLength: LineLength | undefined }) {
  const width = useUnitWidth()
  const label = width === 'auto' ? `Auto ${String(unitColumns(width, lineLength))}` : UNIT_WIDTH_LABELS[width]
  return (
    <button type="button" className="unit-width-button" title={`${widthTitle(width, lineLength)}. Click for the next width.`} onClick={() => { setUnitWidth(nextUnitWidth(width)) }}>
      {`Width ${label}`}
    </button>
  )
}
