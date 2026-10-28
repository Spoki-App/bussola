import type { PublishOutcome, SyncResult } from '../api/types'
import { syncMessage } from '../review/sync'
import { ErrorNote } from './Badges'
import { ExternalLink } from './ExternalLink'

function failures(result: SyncResult): PublishOutcome[] {
  return result.published?.outcomes.filter((outcome) => outcome.status === 'failed' || outcome.status === 'skipped') ?? []
}

export function SyncSummary({ result }: { result: SyncResult }) {
  const reviewUrl = result.published?.review_url
  const problems = failures(result)
  return (
    <>
      <p className="notice">
        {syncMessage(result)}
        {reviewUrl && (
          <>
            {' '}
            <ExternalLink href={reviewUrl}>Open on GitHub</ExternalLink>
          </>
        )}
      </p>
      {problems.length > 0 && <ErrorNote message={problems.map((outcome) => `${outcome.status}: ${outcome.detail}`).join('; ')} />}
    </>
  )
}
