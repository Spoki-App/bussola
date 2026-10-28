import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { Thread } from '../api/types'
import { ThreadView } from './ThreadView'

function thread(canDelete: boolean): Thread {
  return {
    id: 't1',
    scope: 'review',
    path: null,
    kind: null,
    qualified_name: null,
    side: null,
    status: 'open',
    created_by: { id: 1, email: 'a@b.c', name: 'Alice' },
    created_at: '2026-10-28T10:00:00Z',
    line_text: null,
    line_count: 1,
    context_before: [],
    context_after: [],
    anchor: null,
    comments: [],
    can_delete: canDelete,
  }
}

function renderThread(canDelete: boolean) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <ThreadView reviewId={1} thread={thread(canDelete)} />
    </QueryClientProvider>,
  )
}

describe('ThreadView deletion', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('asks for confirmation before deleting', async () => {
    const fetchMock = vi.fn(() => Promise.resolve(Response.json({ id: 't1', deleted: true })))
    vi.stubGlobal('fetch', fetchMock)
    renderThread(true)

    fireEvent.click(screen.getByRole('button', { name: 'Delete' }))
    expect(fetchMock).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: 'Delete thread' }))

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith('/api/threads/t1', expect.objectContaining({ method: 'DELETE' }))
    })
  })

  it('hides the delete button when the thread cannot be deleted', () => {
    renderThread(false)

    expect(screen.queryByRole('button', { name: 'Delete' })).toBeNull()
  })
})
