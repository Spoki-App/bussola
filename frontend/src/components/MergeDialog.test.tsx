import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest'

import type { MergeOptions, MergeResult } from '../api/types'
import { MergeDialog } from './MergeDialog'

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

function renderMerge(options: Partial<MergeOptions> = {}, merged: Response | (() => Response) = () => Response.json(MERGED)) {
  const fetchMock = vi.fn((_url: string, init?: RequestInit) =>
    Promise.resolve(init?.method === 'POST' ? (typeof merged === 'function' ? merged() : merged) : Response.json({ ...OPTIONS, ...options })),
  )
  vi.stubGlobal('fetch', fetchMock)
  const onMerged = vi.fn()
  const onClose = vi.fn()
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <MergeDialog reviewId={3} onMerged={onMerged} onClose={onClose} />
    </QueryClientProvider>,
  )
  return { fetchMock, onMerged, onClose }
}

function sentBody(fetchMock: ReturnType<typeof renderMerge>['fetchMock']): unknown {
  const call = fetchMock.mock.calls.find(([, init]) => init?.method === 'POST')
  return JSON.parse(call?.[1]?.body as string)
}

const mergeButton = () => screen.getByRole('button', { name: 'Merge' })

describe('MergeDialog', () => {
  beforeAll(() => {
    HTMLDialogElement.prototype.showModal = function showModal(this: HTMLDialogElement) {
      this.open = true
    }
    HTMLDialogElement.prototype.close = function close(this: HTMLDialogElement) {
      this.open = false
      this.dispatchEvent(new Event('close'))
    }
  })

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
    expect(mergeButton()).toBeEnabled()
  })

  it('opens as a modal dialog with Cancel', async () => {
    const { onClose } = renderMerge()

    expect(screen.getByRole('dialog', { name: 'Merge pull request' })).toHaveAttribute('open')
    expect(screen.getByText('Checking whether the pull request can be merged...')).toBeInTheDocument()
    expect(await screen.findByLabelText('Commit title')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(onClose).toHaveBeenCalled()
  })

  it('merges with the edited text, deletes the branch when asked and closes', async () => {
    const { fetchMock, onMerged, onClose } = renderMerge()

    fireEvent.change(await screen.findByLabelText('Commit title'), { target: { value: 'Sum the totals (#7)' } })
    fireEvent.click(screen.getByLabelText('Delete the branch after merging'))
    fireEvent.click(mergeButton())

    await waitFor(() => { expect(onMerged).toHaveBeenCalledWith(MERGED) })
    expect(onClose).toHaveBeenCalled()
    expect(sentBody(fetchMock)).toEqual({ method: 'squash', head_sha: HEAD, title: 'Sum the totals (#7)', message: '* contribution', delete_branch: true })
  })

  it('shows why merging is blocked and does not allow it', async () => {
    renderMerge({ blockers: ['Some checks are failing.', 'An approving review is required.'] })

    expect(await screen.findByText('Some checks are failing.')).toBeInTheDocument()
    expect(screen.getByText('An approving review is required.')).toBeInTheDocument()
    expect(mergeButton()).toBeDisabled()
  })

  it('keeps the dialog open with the reason when GitHub refuses the merge', async () => {
    const { onMerged, onClose } = renderMerge({}, () => Response.json({ detail: 'Head branch was modified.' }, { status: 409 }))

    fireEvent.click(await screen.findByRole('button', { name: 'Merge' }))

    expect(await screen.findByText(/Head branch was modified/)).toBeInTheDocument()
    expect(onMerged).not.toHaveBeenCalled()
    expect(onClose).not.toHaveBeenCalled()
    expect(screen.getByLabelText('Commit title')).toHaveValue('Sum the items (#7)')
  })

  it('falls back to the default method when the chosen one is no longer allowed', async () => {
    const { fetchMock } = renderMerge()

    fireEvent.click(await screen.findByRole('tab', { name: 'Rebase and merge' }))
    fetchMock.mockImplementation(() => Promise.resolve(Response.json({ ...OPTIONS, methods: ['merge', 'squash'] })))
    fireEvent.focus(window)
    window.dispatchEvent(new Event('visibilitychange'))

    await waitFor(() => { expect(screen.getByRole('tab', { name: 'Squash and merge' })).toHaveAttribute('aria-selected', 'true') })
  })

  it('says when GitHub deletes the branch by itself', async () => {
    renderMerge({ branch_deletion: 'automatic' })

    expect(await screen.findByText(/GitHub deletes the branch after merging/)).toBeInTheDocument()
    expect(screen.queryByLabelText('Delete the branch after merging')).not.toBeInTheDocument()
  })
})
