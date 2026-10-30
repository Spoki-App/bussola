import type { SyncResult } from '../api/types'
import { syncMessage } from '../review/sync'
import { ErrorNote } from './Badges'
import { ExternalLink } from './ExternalLink'

function failures(result: SyncResult): string[] {
  const outcomes = result.published?.outcomes.filter((outcome) => outcome.status === 'failed' || outcome.status === 'skipped') ?? []
  const notViewed = Object.entries(result.not_viewed).map(([path, reason]) => `not marked as viewed: ${path} (${reason})`)
  return [...outcomes.map((outcome) => `${outcome.status}: ${outcome.detail}`), ...notViewed]
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
      {problems.length > 0 && <ErrorNote message={problems.join('; ')} />}
    </>
  )
}
