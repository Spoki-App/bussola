import { useState } from 'react'

import { setDiffLayout, useDiffLayout } from '../hooks/useDiffLayout'
import { DIFF_LAYOUT_LABELS, MAX_SPLIT_THRESHOLD, MIN_SPLIT_THRESHOLD } from '../settings/diffLayout'
import { Segmented } from './Segmented'

export function DiffLayoutSwitch() {
  const settings = useDiffLayout()
  return <Segmented label="Diff layout" labels={DIFF_LAYOUT_LABELS} value={settings.layout} onChange={(layout) => { setDiffLayout({ ...settings, layout }) }} />
}

export function DiffLayoutPanel() {
  const settings = useDiffLayout()
  const [thresholdText, setThresholdText] = useState(() => String(settings.threshold))

  const changeThreshold = (text: string) => {
    setThresholdText(text)
    const threshold = Number(text)
    if (text !== '' && Number.isInteger(threshold) && threshold >= MIN_SPLIT_THRESHOLD && threshold <= MAX_SPLIT_THRESHOLD) {
      setDiffLayout({ ...settings, threshold })
    }
  }

  return (
    <div className="stack diff-layout-panel">
      <DiffLayoutSwitch />
      <p className="muted">Automatic shows old and new code side by side for units that rewrite lines when the window is wide enough, and one column otherwise.</p>
      <label htmlFor="diff-split-threshold">Automatic split from window width (px)</label>
      <input
        id="diff-split-threshold"
        type="number"
        min={MIN_SPLIT_THRESHOLD}
        max={MAX_SPLIT_THRESHOLD}
        value={thresholdText}
        onChange={(event) => { changeThreshold(event.target.value) }}
        onBlur={() => { setThresholdText(String(settings.threshold)) }}
      />
    </div>
  )
}
