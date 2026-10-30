import { useState } from 'react'

import { describeError } from '../api/client'
import { useForge, useLinkPullRequest } from '../api/forge'
import type { ForgeOverview } from '../api/types'
import { ErrorNote } from './Badges'

interface Props {
  reviewId: number
  unsent: number
  onLinked: () => void
}

export function LinkPullRequest({ reviewId, unsent, onLinked }: Props) {
  const forge = useForge(reviewId)
  if (forge.isPending) {
    return <p className="muted">Checking GitHub...</p>
  }
  if (forge.error) {
    return <ErrorNote message={describeError(forge.error)} />
  }
  const overview = forge.data
  if (!overview.status.authenticated) {
    return <p>{`Your comments were not sent to GitHub. ${overview.status.message}`}</p>
  }
  if (overview.repository === null) {
    return <p className="muted">This branch has no GitHub remote, so your comments stay in bussola.</p>
  }
  return <LinkForm reviewId={reviewId} unsent={unsent} overview={overview} onLinked={onLinked} />
}

function LinkForm({ reviewId, unsent, overview, onLinked }: Props & { overview: ForgeOverview }) {
  const [manual, setManual] = useState('')
  const linkPr = useLinkPullRequest(reviewId)
  const link = (number: number) => {
    linkPr.mutate(number, { onSuccess: onLinked })
  }
  return (
    <div className="stack link-pull-request">
      <p>{`${String(unsent)} comment${unsent === 1 ? ' is' : 's are'} not sent yet. Link this review to a pull request in ${overview.repository ?? ''} to send ${unsent === 1 ? 'it' : 'them'}:`}</p>
      {overview.error && <ErrorNote message={overview.error} />}
      {overview.candidates.length === 0 && <p className="muted">No open pull request matches these branches.</p>}
      {overview.candidates.map((candidate) => (
        <button key={candidate.number} type="button" disabled={linkPr.isPending} onClick={() => { link(candidate.number) }}>
          {`Link #${String(candidate.number)} ${candidate.title} and send`}
        </button>
      ))}
      <form
        className="inline-form"
        onSubmit={(event) => {
          event.preventDefault()
          link(Number(manual))
        }}
      >
        <label htmlFor="pr-number">PR number</label>
        <input id="pr-number" inputMode="numeric" value={manual} onChange={(event) => { setManual(event.target.value.replace(/\D/g, '')) }} />
        <button type="submit" disabled={!manual || linkPr.isPending}>
          Link and send
        </button>
      </form>
      {linkPr.error && <ErrorNote message={describeError(linkPr.error)} />}
    </div>
  )
}
