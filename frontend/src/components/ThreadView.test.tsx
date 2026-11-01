import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { Thread } from '../api/types'
import { LinkScrollContext, createLinkScroll } from '../review/linkFocus'
import { ThreadView } from './ThreadView'

function thread(canDelete: boolean, resolvable: boolean): Thread {
  return {
    id: 't1',
    scope: 'review',
    path: null,
    module: null,
    kind: null,
    qualified_name: null,
    side: null,
    status: 'open',
    resolvable,
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

function renderThread(canDelete: boolean, resolvable = false) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <ThreadView reviewId={1} thread={thread(canDelete, resolvable)} />
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

describe('ThreadView resolution', () => {
  it('offers Resolve on a thread that can be resolved', () => {
    renderThread(false, true)

    expect(screen.getByRole('button', { name: 'Resolve' })).toBeTruthy()
  })

  it('hides Resolve on a comment on the whole review', () => {
    renderThread(false, false)

    expect(screen.queryByRole('button', { name: 'Resolve' })).toBeNull()
  })
})

describe('ThreadView links', () => {
  it('opens a resolved thread that a link points at', () => {
    Element.prototype.scrollIntoView = () => undefined
    const link = createLinkScroll()
    const resolved = { ...thread(false, true), status: 'resolved' as const }
    render(
      <QueryClientProvider client={new QueryClient()}>
        <LinkScrollContext value={link}>
          <ThreadView reviewId={1} thread={resolved} />
        </LinkScrollContext>
      </QueryClientProvider>,
    )
    expect(screen.getByRole('button', { name: '▸' })).toHaveAttribute('aria-expanded', 'false')

    act(() => { link.start({ unitId: null, elementId: 'thread-t1' }) })

    expect(screen.getByRole('button', { name: '▾' })).toHaveAttribute('aria-expanded', 'true')
    Reflect.deleteProperty(Element.prototype, 'scrollIntoView')
  })
})
