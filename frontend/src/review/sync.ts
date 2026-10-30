import type { SyncResult } from '../api/types'
import { plural } from './text'

export function syncMessage(result: SyncResult): string {
  const { refresh, published, publish_error: publishError, viewed_files: viewedFiles, viewed_error: viewedError } = result
  const parts = [refresh.created ? `New commits found: revision ${String(refresh.revision.number)} recorded.` : 'No new commits.']
  if (refresh.warning) {
    parts.push(refresh.warning)
  }
  const sent = published?.outcomes.filter((outcome) => outcome.status === 'published' || outcome.status === 'updated') ?? []
  if (sent.length > 0) {
    parts.push(`Sent ${plural(sent.length, 'comment')} to GitHub.`)
  }
  if (publishError) {
    parts.push(`Comments not sent: ${publishError}`)
  }
  const marked = viewedFiles.filter((file) => file.status === 'marked')
  if (marked.length > 0) {
    parts.push(`Marked ${plural(marked.length, 'approved file')} as viewed on GitHub.`)
  }
  const failed = viewedFiles.filter((file) => file.status === 'failed')
  if (failed.length > 0) {
    parts.push(`Not marked as viewed: ${failed.map((file) => `${file.path} (${file.detail})`).join(', ')}.`)
  }
  if (viewedError) {
    parts.push(`Files not marked as viewed: ${viewedError}`)
  }
  return parts.join(' ')
}
