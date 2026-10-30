import type { UnitState } from '../api/types'
import { STATE_LABELS } from '../review/logic'

const COURSE_ORDER: UnitState[] = ['approved', 'approved_moved', 'partial', 'changed', 'removed', 'new']
const TICK_LIMIT = 80

export function StateBadge({ state }: { state: UnitState }) {
  return <span className={`badge state-${state}`}>{STATE_LABELS[state]}</span>
}

export function KindBadge({ kind }: { kind: string }) {
  return <span className="kind">{kind}</span>
}

interface CourseProps {
  counts: Record<UnitState, number>
  percent: number
  label: string
}

export function CourseStrip({ counts, percent, label }: CourseProps) {
  const states = COURSE_ORDER.filter((state) => counts[state] > 0)
  const total = states.reduce((sum, state) => sum + counts[state], 0)
  const ticks = total <= TICK_LIMIT
  return (
    <div
      className={`course${ticks ? ' ticks' : ''}`}
      role="progressbar"
      aria-valuenow={percent}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label={label}
      title={states.map((state) => `${STATE_LABELS[state]}: ${String(counts[state])}`).join('\n')}
    >
      {ticks
        ? states.flatMap((state) => Array.from({ length: counts[state] }, (_, index) => <span key={`${state}-${String(index)}`} className={`state-${state}`} />))
        : states.map((state) => <span key={state} className={`state-${state}`} style={{ flexGrow: counts[state] }} />)}
    </div>
  )
}

export function ErrorNote({ message }: { message: string }) {
  return (
    <p className="error-note" role="alert">
      {message}
    </p>
  )
}
