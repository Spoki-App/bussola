import { describeError } from '../api/client'
import { GITHUB_SYNC_INTERVAL_MS, useGitHubSync } from '../api/forge'

const SYNC_TITLE = `Comments, replies, edits and resolved threads are synced with GitHub every ${String(GITHUB_SYNC_INTERVAL_MS / 60000)} minutes while this page is open, and when you come back to it.`

export function GitHubSyncStatus({ reviewId, headSha }: { reviewId: number; headSha: string | undefined }) {
  const sync = useGitHubSync(reviewId, headSha)
  const syncedAt = sync.dataUpdatedAt ? new Date(sync.dataUpdatedAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : null

  return (
    <>
      <p className="muted sync-status" title={SYNC_TITLE}>
        {sync.isFetching && 'Syncing comments with GitHub...'}
        {!sync.isFetching && sync.isError && `Could not sync comments with GitHub: ${describeError(sync.error)}`}
        {!sync.isFetching && !sync.isError && syncedAt && `Comments synced with GitHub at ${syncedAt}`}
      </p>
      {sync.data?.new_commits && <p className="notice">New commits were pushed to this pull request. Use Sync to review them.</p>}
    </>
  )
}
