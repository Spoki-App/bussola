import type { SyncResult } from '../api/types'

function plural(count: number, word: string): string {
  return `${String(count)} ${word}${count === 1 ? '' : 's'}`
}

export function syncMessage(result: SyncResult): string {
  const { refresh, published, publish_error: publishError } = result
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
  return parts.join(' ')
}
