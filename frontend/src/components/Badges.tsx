import type { UnitState } from '../api/types'
import { STATE_LABELS } from '../review/logic'

export function StateBadge({ state }: { state: UnitState }) {
  return <span className={`badge state-${state}`}>{STATE_LABELS[state]}</span>
}

export function KindBadge({ kind }: { kind: string }) {
  return <span className="badge kind">{kind}</span>
}

export function ProgressBar({ percent, label }: { percent: number; label?: string }) {
  return (
    <div className="progress" role="progressbar" aria-valuenow={percent} aria-valuemin={0} aria-valuemax={100} aria-label={label ?? 'Review progress'}>
      <div className="progress-fill" style={{ width: `${String(percent)}%` }} />
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
