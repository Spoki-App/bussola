import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest'

import type { DirectoryListing } from '../api/types'
import { DirectoryPicker } from './DirectoryPicker'

const LISTINGS: Record<string, DirectoryListing> = {
  '/home/me': {
    path: '/home/me',
    parent: '/home',
    home: '/home/me',
    is_repo: false,
    entries: [
      { name: 'code', path: '/home/me/code', is_repo: false },
      { name: 'shop', path: '/home/me/shop', is_repo: true },
    ],
    truncated: false,
  },
  '/home/me/code': { path: '/home/me/code', parent: '/home/me', home: '/home/me', is_repo: false, entries: [], truncated: false },
}

function stubApi() {
  const fetchMock = vi.fn((input: string) => {
    const url = new URL(input, 'http://localhost')
    const listing = LISTINGS[url.searchParams.get('path') ?? '/home/me']
    return Promise.resolve(Response.json(listing))
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function renderPicker(onSelect = vi.fn()) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <DirectoryPicker busy={false} error={null} onSelect={onSelect} onClose={vi.fn()} />
    </QueryClientProvider>,
  )
  return onSelect
}

describe('DirectoryPicker', () => {
  beforeAll(() => {
    HTMLDialogElement.prototype.showModal = function showModal(this: HTMLDialogElement) {
      this.open = true
    }
    HTMLDialogElement.prototype.close = function close(this: HTMLDialogElement) {
      this.open = false
    }
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('starts at home and offers repositories for selection', async () => {
    stubApi()
    const onSelect = renderPicker()

    fireEvent.click(await screen.findByRole('button', { name: 'Add shop' }))

    expect(onSelect).toHaveBeenCalledWith('/home/me/shop')
    expect(screen.queryByRole('button', { name: 'Add code' })).toBeNull()
  })

  it('opens a folder when clicked', async () => {
    const fetchMock = stubApi()
    renderPicker()

    fireEvent.click(await screen.findByText('code'))

    expect(await screen.findByText('No folders here.')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenLastCalledWith('/api/directories?path=%2Fhome%2Fme%2Fcode', expect.anything())
  })
})
