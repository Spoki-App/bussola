import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { ConversationSync } from '../api/types'
import { GitHubSyncStatus } from './GitHubSyncStatus'

function renderStatus(result: ConversationSync) {
  const fetchMock = vi.fn(() => Promise.resolve(Response.json(result)))
  vi.stubGlobal('fetch', fetchMock)
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <GitHubSyncStatus reviewId={3} headSha="abc" />
    </QueryClientProvider>,
  )
  return fetchMock
}

describe('GitHubSyncStatus', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('syncs the conversation when shown and says when it last did', async () => {
    const fetchMock = renderStatus({ changes: 0, new_commits: false, state: 'OPEN' })

    expect(await screen.findByText(/^Comments synced with GitHub at/)).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledWith('/api/reviews/3/forge/sync', expect.objectContaining({ method: 'POST' }))
    expect(screen.queryByText(/New commits/)).not.toBeInTheDocument()
  })

  it('points to Sync when the pull request moved on', async () => {
    renderStatus({ changes: 1, new_commits: true, state: 'OPEN' })

    expect(await screen.findByText(/New commits were pushed/)).toBeInTheDocument()
  })
})
