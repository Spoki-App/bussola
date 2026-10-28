import { useState } from 'react'

import { describeError } from '../api/client'
import { useForge, useLinkPullRequest, usePublish } from '../api/forge'
import type { ForgeOverview, PublishResult } from '../api/types'
import { ErrorNote } from './Badges'

export function GitHubButton({ reviewId }: { reviewId: number }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="popover-anchor">
      <button type="button" aria-expanded={open} title="Link this review to a GitHub pull request and send your comments there." onClick={() => { setOpen(!open) }}>
        GitHub comments
      </button>
      {open && (
        <div className="popover" role="dialog" aria-label="Send comments to GitHub">
          <GitHubPanel reviewId={reviewId} />
        </div>
      )}
    </div>
  )
}

function GitHubPanel({ reviewId }: { reviewId: number }) {
  const forge = useForge(reviewId, true)
  if (forge.isPending) {
    return <p className="muted">Checking GitHub...</p>
  }
  if (forge.error) {
    return <ErrorNote message={describeError(forge.error)} />
  }
  const overview = forge.data
  if (!overview.status.authenticated) {
    return <p>{overview.status.message}</p>
  }
  if (overview.repository === null) {
    return <p>This branch has no GitHub remote, so there is nowhere to send comments.</p>
  }
  return (
    <>
      {overview.error && <ErrorNote message={overview.error} />}
      {overview.link ? <PublishSection reviewId={reviewId} overview={overview} /> : <LinkSection reviewId={reviewId} overview={overview} />}
    </>
  )
}

function LinkSection({ reviewId, overview }: { reviewId: number; overview: ForgeOverview }) {
  const [manual, setManual] = useState('')
  const linkPr = useLinkPullRequest(reviewId)
  return (
    <div className="stack">
      <p>{`Link this review to a pull request in ${overview.repository ?? ''}.`}</p>
      {overview.candidates.length === 0 && <p className="muted">No open pull request matches these branches.</p>}
      {overview.candidates.map((candidate) => (
        <button key={candidate.number} type="button" disabled={linkPr.isPending} onClick={() => { linkPr.mutate(candidate.number) }}>
          {`Link #${String(candidate.number)} ${candidate.title}`}
        </button>
      ))}
      <form
        className="inline-form"
        onSubmit={(event) => {
          event.preventDefault()
          linkPr.mutate(Number(manual))
        }}
      >
        <label htmlFor="pr-number">PR number</label>
        <input id="pr-number" inputMode="numeric" value={manual} onChange={(event) => { setManual(event.target.value.replace(/\D/g, '')) }} />
        <button type="submit" disabled={!manual || linkPr.isPending}>
          Link
        </button>
      </form>
      {linkPr.error && <ErrorNote message={describeError(linkPr.error)} />}
    </div>
  )
}

function PublishSection({ reviewId, overview }: { reviewId: number; overview: ForgeOverview }) {
  const [draft, setDraft] = useState(false)
  const publish = usePublish(reviewId)
  const pull = overview.pull_request
  const pending = overview.pending_comments
  return (
    <div className="stack">
      {pull ? (
        <p>
          <a href={pull.url} target="_blank" rel="noreferrer">{`#${String(pull.number)} ${pull.title}`}</a>
        </p>
      ) : (
        <p>{`Linked to #${String(overview.link?.pr_number ?? 0)}`}</p>
      )}
      {overview.head_matches === false && (
        <ErrorNote message="The pull request head differs from the reviewed commit. Push the branch or refresh the review before sending." />
      )}
      <label className="checkbox">
        <input type="checkbox" checked={draft} onChange={(event) => { setDraft(event.target.checked) }} />
        Keep the review as a draft on GitHub
      </label>
      {draft && <p className="muted">File-level comments are posted right away; GitHub cannot keep them in a draft review.</p>}
      <button type="button" className="primary" disabled={pending === 0 || publish.isPending || overview.head_matches === false} onClick={() => { publish.mutate(draft) }}>
        {publish.isPending ? 'Sending...' : pending === 0 ? 'Nothing new to send' : `Send ${String(pending)} comment${pending === 1 ? '' : 's'}`}
      </button>
      {publish.error && <ErrorNote message={describeError(publish.error)} />}
      {publish.data && <PublishSummary result={publish.data} />}
    </div>
  )
}

function PublishSummary({ result }: { result: PublishResult }) {
  return (
    <div className="stack">
      {result.review_url && (
        <a href={result.review_url} target="_blank" rel="noreferrer">
          Open the review on GitHub
        </a>
      )}
      <ul className="outcomes">
        {result.outcomes.map((outcome) => (
          <li key={outcome.comment_ids.join(',')} className={`outcome-${outcome.status}`}>
            <strong>{outcome.status}</strong> {outcome.detail}
            {outcome.url && (
              <>
                {' '}
                <a href={outcome.url} target="_blank" rel="noreferrer">
                  view
                </a>
              </>
            )}
          </li>
        ))}
      </ul>
    </div>
  )
}
