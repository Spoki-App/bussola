import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { ReviewDetail, SyncResult } from '../api/types'
import { ReviewPage } from './ReviewPage'

const revision = { id: 2, number: 1, head_sha: 'b', base_sha: 'a', merge_base_sha: 'a', created_at: '2026-11-04T10:00:00Z' }

function reviewWithTitle(title: string): ReviewDetail {
  return {
    id: 3,
    repo_id: 1,
    repo_name: 'bussola',
    head_ref: 'refs/bussola/pull/34',
    base_ref: 'origin/main',
    latest_revision: revision,
    counts: { approved: 0, approved_moved: 0, changed: 0, partial: 0, removed: 0, new: 0 },
    total: 0,
    approved: 0,
    open_threads: 0,
    total_threads: 0,
    last_session_at: null,
    pull_request: { number: 34, title, url: null, author: null, state: 'OPEN', description: null },
    pull_request_review: true,
    unsent_comments: 0,
  }
}

const synced: SyncResult = {
  refresh: { revision, created: false, warning: null },
  published: null,
  publish_error: null,
  unsent_comments: 0,
  marked_viewed: [],
  not_viewed: {},
  viewed_error: null,
}

function stubServer() {
  let title = 'feat: first title'
  vi.stubGlobal(
    'fetch',
    vi.fn((url: string) => {
      if (url === '/api/reviews/3/sync') {
        title = 'feat: renamed on GitHub'
        return Promise.resolve(Response.json(synced))
      }
      if (url === '/api/reviews/3/forge/sync') {
        return Promise.resolve(Response.json({ changes: 0, new_commits: false, state: 'OPEN' }))
      }
      return Promise.resolve(Response.json(url === '/api/reviews/3' ? reviewWithTitle(title) : []))
    }),
  )
}

describe('ReviewPage window title', () => {
  beforeEach(() => {
    document.title = 'bussola'
    stubServer()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('names the pull request, follows its title after a sync and goes back to the default when left', async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const { unmount } = render(
      <QueryClientProvider client={client}>
        <ReviewPage reviewId={3} />
      </QueryClientProvider>,
    )

    await waitFor(() => {
      expect(document.title).toBe('bussola#34 feat: first title')
    })

    fireEvent.click(screen.getByRole('button', { name: 'Sync' }))

    await waitFor(() => {
      expect(document.title).toBe('bussola#34 feat: renamed on GitHub')
    })

    unmount()

    expect(document.title).toBe('bussola')
  })
})
