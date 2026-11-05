import { useState } from 'react'

import { useAiReviewRun, useAiReviewRuns } from '../api/aiReview'
import { describeError } from '../api/client'
import type { AiReviewFinding, AiReviewLookup, AiReviewPart, AiReviewRunDetail } from '../api/types'
import type { CodeTarget } from '../hooks/useCodeNavigation'
import { useModalDialog } from '../hooks/useModalDialog'
import type { LineLink } from '../markdown/lineLinks'
import { showReview } from '../navigation'
import { lookupCall, runHeadline, runLabel } from '../review/aiReview'
import { IMPACT_LABELS } from '../review/impact'
import { withoutLinkFocus } from '../review/linkFocus'
import { plural } from '../review/text'
import { ErrorNote } from './Badges'
import { Markdown } from './Markdown'
import { Spinner } from './Spinner'

interface Props {
  reviewId: number
  onClose: () => void
  onShowLine?: (target: CodeTarget) => void
}

export function AiReviewDetails({ reviewId, onClose, onShowLine }: Props) {
  const { ref, close } = useModalDialog()
  const runs = useAiReviewRuns(reviewId)
  const [chosen, setChosen] = useState<number | null>(null)
  const runId = chosen ?? runs.data?.at(0)?.id ?? null
  const detail = useAiReviewRun(reviewId, runId)
  const openThread = (threadId: string) => {
    const params = new URLSearchParams(withoutLinkFocus(window.location.search))
    params.set('thread', threadId)
    close()
    showReview(reviewId, `?${params.toString()}`, false)
  }
  const showLine = (link: LineLink) => {
    const path = link.path
    if (!onShowLine || path === undefined) {
      return
    }
    const found = detail.data?.links.find((candidate) => candidate.path === path && candidate.side === link.side && candidate.line === link.line)
    close()
    onShowLine({ path, side: link.side, line: link.line, unit_id: found?.unit_id ?? null })
  }
  const failure = runs.error ?? detail.error
  return (
    <dialog ref={ref} className="picker ai-review-details" aria-labelledby="ai-review-details-title" onClose={onClose}>
      <header className="picker-header">
        <h2 id="ai-review-details-title">AI review details</h2>
        <button type="button" className="link" onClick={close}>
          Close
        </button>
      </header>
      {runs.data && runs.data.length > 1 && runId !== null && (
        <label className="ai-run-picker">
          Run
          <select value={runId} onChange={(event) => { setChosen(Number(event.target.value)) }}>
            {runs.data.map((run) => (
              <option key={run.id} value={run.id}>
                {runLabel(run)}
              </option>
            ))}
          </select>
        </label>
      )}
      <div className="ai-review-details-body">
        {failure && <ErrorNote message={describeError(failure)} />}
        {detail.data ? (
          <RunDetail run={detail.data} onOpenThread={openThread} onLineLink={showLine} />
        ) : (
          !failure && (
            <p className="muted busy">
              <Spinner />
              Loading the AI review...
            </p>
          )
        )}
      </div>
    </dialog>
  )
}

interface Links {
  onOpenThread: (threadId: string) => void
  onLineLink: (link: LineLink) => void
}

function RunDetail({ run, onOpenThread, onLineLink }: { run: AiReviewRunDetail } & Links) {
  return (
    <>
      <p>{runHeadline(run)}</p>
      {run.error && <ErrorNote message={run.error} />}
      {run.rating && (
        <p className="muted">
          {`Impact rated for ${plural(run.rating.rated, 'unit')} before the review.`}
          {run.rating.failed.length > 0 && ` Not rated: ${run.rating.failed.join(', ')}${run.rating.error ? ` (${run.rating.error})` : ''}.`}
        </p>
      )}
      {run.parts.length === 0 && <p className="muted">No unit was reviewed in this run.</p>}
      {run.parts.map((part, index) => (
        <Part key={index} part={part} title={run.parts.length > 1 ? `Part ${String(index + 1)} of ${String(run.parts.length)}` : null} onOpenThread={onOpenThread} onLineLink={onLineLink} />
      ))}
    </>
  )
}

function Part({ part, title, onOpenThread, onLineLink }: { part: AiReviewPart; title: string | null } & Links) {
  return (
    <section className="ai-review-part">
      {title && <h3>{title}</h3>}
      {part.error && <ErrorNote message={part.error} />}
      {part.summary && <Markdown text={part.summary} media={false} onLineLink={onLineLink} />}
      {!part.error && (part.findings.length > 0 ? <Findings findings={part.findings} onOpenThread={onOpenThread} /> : <p className="muted">No findings in this part.</p>)}
      <details>
        <summary>{plural(part.lookups.length, 'code lookup')}</summary>
        {part.lookups.length > 0 && <Lookups lookups={part.lookups} />}
      </details>
      <details>
        <summary>{`${plural(part.units.length, 'unit')} reviewed`}</summary>
        <ul className="ai-review-units">
          {part.units.map((unit) => (
            <li key={unit.label}>
              <code>{unit.label}</code>
              {unit.impact && <span className={`badge impact-${unit.impact}`}>{`${IMPACT_LABELS[unit.impact]} impact`}</span>}
            </li>
          ))}
        </ul>
      </details>
    </section>
  )
}

function Findings({ findings, onOpenThread }: { findings: AiReviewFinding[]; onOpenThread: (threadId: string) => void }) {
  return (
    <ul className="ai-review-findings">
      {findings.map((finding) => (
        <li key={finding.thread_id}>
          <button type="button" className="link" title="Show this thread in the review" onClick={() => { onOpenThread(finding.thread_id) }}>
            {finding.place}
          </button>
          <Markdown text={finding.body} media={false} />
        </li>
      ))}
    </ul>
  )
}

function Lookups({ lookups }: { lookups: AiReviewLookup[] }) {
  return (
    <ol className="ai-review-lookups">
      {lookups.map((lookup, index) => (
        <li key={index} className={lookup.error ? 'failed' : undefined}>
          <code>{lookupCall(lookup)}</code>
          <pre>{lookup.result}</pre>
        </li>
      ))}
    </ol>
  )
}
