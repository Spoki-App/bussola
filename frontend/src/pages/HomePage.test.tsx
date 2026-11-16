import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { PullSyncResult, Repo } from '../api/types'
import { HomePage } from './HomePage'

const repos: Repo[] = [
  { id: 1, path: '/code/api', name: 'api', missing: false },
  { id: 2, path: '/code/web', name: 'web', missing: false },
]

const synced: PullSyncResult = { updated: 2, closed: 1, failed: ['web #9: could not fetch'] }

function stubServer(repoList: Repo[]) {
  const fetch = vi.fn((url: string, init?: RequestInit) => {
    if (url === '/api/pulls/sync' && init?.method === 'POST') {
      return Promise.resolve(Response.json(synced))
    }
    return Promise.resolve(Response.json(url === '/api/repos' ? repoList : []))
  })
  vi.stubGlobal('fetch', fetch)
  return fetch
}

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <HomePage />
    </QueryClientProvider>,
  )
}

describe('HomePage Sync all', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('syncs the pull request reviews of every repository at once and shows the result', async () => {
    const fetch = stubServer(repos)
    renderPage()

    fireEvent.click(await screen.findByRole('button', { name: 'Sync all' }))

    expect(await screen.findByText('Pull request reviews synced: 2 updated, 1 closed or merged.')).toBeTruthy()
    expect(screen.getByText('web #9: could not fetch')).toBeTruthy()
    expect(fetch.mock.calls.filter(([url]) => url === '/api/pulls/sync')).toHaveLength(1)
    expect(fetch.mock.calls.some(([url]) => url.includes('/pulls/sync') && url !== '/api/pulls/sync')).toBe(false)
  })

  it('is not offered without repositories', async () => {
    stubServer([])
    renderPage()

    await screen.findByText(/No repositories yet/)
    expect(screen.queryByRole('button', { name: 'Sync all' })).toBeNull()
  })
})
