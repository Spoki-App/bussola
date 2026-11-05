import type { AiReviewLookup, AiReviewResult, AiReviewRun, AiReviewRunStatus, AiReviewStatus } from '../api/types'
import { plural } from './text'

export function aiReviewProgress(status: AiReviewStatus | null): string {
  if (!status?.running || status.phase === null) {
    return 'Starting the AI review...'
  }
  const count = `${String(status.done)} of ${plural(status.total, 'unit')}`
  if (status.phase === 'rating') {
    return `Rating the impact first: ${count}...`
  }
  return status.lookups > 0 ? `AI review: ${count} reviewed, ${plural(status.lookups, 'code lookup')} so far...` : `AI review: ${count} reviewed...`
}

export function aiReviewSummary(result: AiReviewResult): string {
  const reviewed = `${plural(result.reviewed, 'unit')} reviewed, ${plural(result.findings, 'finding')} added as threads.`
  if (result.cancelled) {
    return `Cancelled, ${reviewed}`
  }
  if (result.reviewed === 0 && result.failed === 0) {
    return 'No unit changed since the last AI review.'
  }
  return result.failed === 0 ? reviewed : `${reviewed} ${plural(result.failed, 'unit')} could not be reviewed: ${result.error ?? 'unknown error'}`
}

export function aiReviewCoverage(status: AiReviewStatus | null): string | null {
  if (!status || status.reviewed_units === 0) {
    return null
  }
  return status.reviewed_units === status.units ? 'Every unit has an AI review.' : `${String(status.reviewed_units)} of ${plural(status.units, 'unit')} have an AI review.`
}

const RUN_STATUS_LABELS: Record<AiReviewRunStatus, string> = {
  running: 'Running',
  completed: 'Completed',
  cancelled: 'Cancelled',
  failed: 'Failed',
  interrupted: 'Interrupted, bussola stopped while it ran',
}

export function runLabel(run: AiReviewRun): string {
  return `${new Date(run.started_at).toLocaleString()}, ${RUN_STATUS_LABELS[run.status].toLowerCase()}`
}

export function runHeadline(run: AiReviewRun): string {
  const provider = run.model ? `${run.provider_label} (${run.model})` : run.provider_label
  const kind = run.again ? 'Review again' : 'AI review'
  const counts = `${plural(run.reviewed, 'unit')} reviewed, ${plural(run.findings, 'finding')}${run.failed > 0 ? `, ${plural(run.failed, 'unit')} not reviewed` : ''}.`
  return `${RUN_STATUS_LABELS[run.status]}: ${kind} with ${provider}, started ${new Date(run.started_at).toLocaleString()}. ${counts}`
}

export function lookupCall(lookup: AiReviewLookup): string {
  const values = Object.entries(lookup.arguments).map(([name, value]) => `${name}: ${typeof value === 'string' ? value : JSON.stringify(value)}`)
  return `${lookup.tool}(${values.join(', ')})`
}
