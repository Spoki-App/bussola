import { describeError } from '../api/client'
import { usePullRequests, useReviewPullRequest, useSyncPullRequests } from '../api/pulls'
import type { PullSyncResult } from '../api/types'
import { Link } from '../Link'
import { navigate } from '../navigation'
import { ErrorNote } from './Badges'
import { CommentCount } from './CommentCount'

function syncSummary(result: PullSyncResult): string {
  const parts = [`${String(result.updated)} updated`, `${String(result.closed)} closed or merged`]
  return `Pull request reviews synced: ${parts.join(', ')}.`
}

export function PullRequestsPanel({ repoId }: { repoId: number }) {
  const pulls = usePullRequests(repoId)
  const start = useReviewPullRequest(repoId)
  const sync = useSyncPullRequests(repoId)

  if (pulls.isPending) {
    return <p className="muted">Loading pull requests from GitHub...</p>
  }
  if (pulls.error) {
    return <ErrorNote message={describeError(pulls.error)} />
  }
  const data = pulls.data
  if (!data.status.authenticated) {
    return <p className="muted">{data.status.message}</p>
  }
  if (data.repository === null) {
    return <p className="muted">This repository has no GitHub remote.</p>
  }
  return (
    <div className="pulls">
      <div className="pulls-header">
        <span className="muted">{`Open pull requests in ${data.repository}`}</span>
        <span className="spacer" />
        <button type="button" disabled={pulls.isFetching} onClick={() => { void pulls.refetch() }}>
          Reload
        </button>
        <button type="button" disabled={sync.isPending} title="Fetch the latest commits of every reviewed pull request" onClick={() => { sync.mutate() }}>
          {sync.isPending ? 'Syncing...' : 'Sync reviews'}
        </button>
      </div>
      {sync.data && <p className="notice">{syncSummary(sync.data)}</p>}
      {sync.data?.failed.map((failure) => <ErrorNote key={failure} message={failure} />)}
      {(sync.error ?? start.error) && <ErrorNote message={describeError(sync.error ?? start.error)} />}
      {data.pulls.length === 0 && <p className="muted">No open pull requests.</p>}
      <ul className="pull-list">
        {data.pulls.map(({ pull, review_id: reviewId }) => (
          <li key={pull.number}>
            <div className="pull-info">
              <a href={pull.url} target="_blank" rel="noreferrer">
                <span className="pr-number">{`#${String(pull.number)}`}</span> {pull.title}
              </a>
              <span className="muted">
                {`${pull.author} · `}
                <code>{pull.head_ref}</code>
                {' into '}
                <code>{pull.base_ref}</code>
              </span>
            </div>
            {pull.is_draft && <span className="badge kind">draft</span>}
            <CommentCount total={pull.comment_count} unresolved={pull.unresolved_threads} totalLabel="comment" />
            {reviewId === null ? (
              <button
                type="button"
                className="primary"
                disabled={start.isPending}
                onClick={() => { start.mutate(pull.number, { onSuccess: (review) => { navigate(`/reviews/${String(review.id)}`) } }) }}
              >
                {start.isPending && start.variables === pull.number ? 'Fetching...' : 'Review'}
              </button>
            ) : (
              <Link to={`/reviews/${String(reviewId)}`} className="button-link">
                Open review
              </Link>
            )}
          </li>
        ))}
      </ul>
    </div>
  )
}
