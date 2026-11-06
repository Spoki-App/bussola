import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { MergeOptions, MergeResult } from '../api/types'
import { MergePullRequest } from './MergePullRequest'

const HEAD = 'a'.repeat(40)

const OPTIONS: MergeOptions = {
  head_sha: HEAD,
  methods: ['merge', 'squash', 'rebase'],
  default_method: 'squash',
  commit_texts: {
    merge: { title: 'Merge pull request #7 from bob/sum-items', message: 'Sum the items' },
    squash: { title: 'Sum the items (#7)', message: '* contribution' },
  },
  blockers: [],
  branch_deletion: 'optional',
}

const MERGED: MergeResult = { state: 'MERGED', branch_deleted: true, branch_error: null }

function renderMerge(options: Partial<MergeOptions> = {}) {
  const fetchMock = vi.fn((_url: string, init?: RequestInit) => Promise.resolve(Response.json(init?.method === 'POST' ? MERGED : { ...OPTIONS, ...options })))
  vi.stubGlobal('fetch', fetchMock)
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <MergePullRequest reviewId={3} />
    </QueryClientProvider>,
  )
  return fetchMock
}

function sentBody(fetchMock: ReturnType<typeof renderMerge>): unknown {
  const call = fetchMock.mock.calls.find(([, init]) => init?.method === 'POST')
  return JSON.parse(call?.[1]?.body as string)
}

describe('MergePullRequest', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('offers only the allowed methods and selects the default one', async () => {
    renderMerge({ methods: ['squash', 'rebase'] })

    expect(await screen.findByRole('tab', { name: 'Squash and merge' })).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByRole('tab', { name: 'Rebase and merge' })).toHaveAttribute('aria-selected', 'false')
    expect(screen.queryByRole('tab', { name: 'Create a merge commit' })).not.toBeInTheDocument()
    expect(screen.getByLabelText('Commit title')).toHaveValue('Sum the items (#7)')
  })

  it('prefills the commit text of each method and hides it for rebase', async () => {
    renderMerge()

    fireEvent.click(await screen.findByRole('tab', { name: 'Create a merge commit' }))
    expect(screen.getByLabelText('Commit title')).toHaveValue('Merge pull request #7 from bob/sum-items')
    expect(screen.getByLabelText('Commit message')).toHaveValue('Sum the items')

    fireEvent.click(screen.getByRole('tab', { name: 'Rebase and merge' }))
    expect(screen.queryByLabelText('Commit title')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Confirm rebase and merge' })).toBeEnabled()
  })

  it('merges with the edited text and deletes the branch when asked', async () => {
    const fetchMock = renderMerge()

    fireEvent.change(await screen.findByLabelText('Commit title'), { target: { value: 'Sum the totals (#7)' } })
    fireEvent.click(screen.getByLabelText('Delete the branch after merging'))
    fireEvent.click(screen.getByRole('button', { name: 'Confirm squash and merge' }))

    expect(await screen.findByText('Pull request merged and its branch deleted.')).toBeInTheDocument()
    expect(sentBody(fetchMock)).toEqual({ method: 'squash', head_sha: HEAD, title: 'Sum the totals (#7)', message: '* contribution', delete_branch: true })
  })

  it('shows why merging is blocked and does not allow it', async () => {
    renderMerge({ blockers: ['Some checks are failing.', 'An approving review is required.'] })

    expect(await screen.findByText('Some checks are failing.')).toBeInTheDocument()
    expect(screen.getByText('An approving review is required.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Confirm squash and merge' })).toBeDisabled()
  })

  it('says when GitHub deletes the branch by itself', async () => {
    renderMerge({ branch_deletion: 'automatic' })

    expect(await screen.findByText(/GitHub deletes the branch after merging/)).toBeInTheDocument()
    expect(screen.queryByLabelText('Delete the branch after merging')).not.toBeInTheDocument()
  })
})
