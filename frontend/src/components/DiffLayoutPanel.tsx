import { useState } from 'react'

import { setDiffLayout, useDiffLayout } from '../hooks/useDiffLayout'
import { DIFF_LAYOUT_LABELS, MAX_SPLIT_THRESHOLD, MIN_SPLIT_THRESHOLD, clampThreshold } from '../settings/diffLayout'
import { Segmented } from './Segmented'

export function DiffLayoutSwitch() {
  const settings = useDiffLayout()
  return <Segmented label="Diff layout" labels={DIFF_LAYOUT_LABELS} value={settings.layout} onChange={(layout) => { setDiffLayout({ ...settings, layout }) }} />
}

export function DiffLayoutPanel() {
  const settings = useDiffLayout()
  const [thresholdText, setThresholdText] = useState(() => String(settings.threshold))

  const commitThreshold = () => {
    const typed = Number(thresholdText)
    const threshold = thresholdText.trim() === '' || !Number.isFinite(typed) ? settings.threshold : clampThreshold(typed)
    setThresholdText(String(threshold))
    setDiffLayout({ ...settings, threshold })
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
        onChange={(event) => { setThresholdText(event.target.value) }}
        onBlur={commitThreshold}
        onKeyDown={(event) => {
          if (event.key === 'Enter') {
            commitThreshold()
          }
        }}
      />
    </div>
  )
}
