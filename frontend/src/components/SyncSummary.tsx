import type { PublishResult, SyncResult } from '../api/types'
import { syncMessage } from '../review/sync'
import { ErrorNote } from './Badges'
import { ExternalLink } from './ExternalLink'

interface Props {
  message: string
  published: PublishResult | null
  problems?: string[]
}

export function PublishSummary({ message, published, problems = [] }: Props) {
  const reviewUrl = published?.review_url
  const outcomes = published?.outcomes.filter((outcome) => outcome.status === 'failed' || outcome.status === 'skipped') ?? []
  const failures = [...outcomes.map((outcome) => `${outcome.status}: ${outcome.detail}`), ...problems]
  return (
    <>
      <p className="notice">
        {message}
        {reviewUrl && (
          <>
            {' '}
            <ExternalLink href={reviewUrl}>Open on GitHub</ExternalLink>
          </>
        )}
      </p>
      {failures.length > 0 && <ErrorNote message={failures.join('; ')} />}
    </>
  )
}

export function SyncSummary({ result }: { result: SyncResult }) {
  const notViewed = Object.entries(result.not_viewed).map(([path, reason]) => `not marked as viewed: ${path} (${reason})`)
  return <PublishSummary message={syncMessage(result)} published={result.published} problems={notViewed} />
}
