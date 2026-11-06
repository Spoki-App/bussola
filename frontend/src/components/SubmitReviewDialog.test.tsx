import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { useState } from 'react'
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest'

import type { ForgeOverview, ReviewSubmitResult } from '../api/types'
import { SubmitReviewDialog } from './SubmitReviewDialog'

const PULL = {
  number: 7,
  title: 'Sum the items',
  url: 'https://github.com/acme/widgets/pull/7',
  head_sha: 'abc',
  head_ref: 'sum-items',
  base_ref: 'main',
  author: 'bob',
  state: 'OPEN',
  is_draft: false,
  comment_count: 0,
  unresolved_threads: 0,
  body: '',
}

function overview(viewer: string): ForgeOverview {
  return {
    status: { available: true, authenticated: true, message: 'gh is ready' },
    repository: 'acme/widgets',
    link: { provider: 'github', repository: 'acme/widgets', pr_number: 7 },
    pull_request: PULL,
    candidates: [],
    head_matches: true,
    error: null,
    viewer,
  }
}

const SUBMITTED: ReviewSubmitResult = {
  event: 'APPROVE',
  published: { review_url: 'https://github.com/acme/widgets/pull/7#pullrequestreview-1', outcomes: [] },
  unsent_comments: 0,
}

function Harness({ pending, onSubmitted, onClose }: { pending: number; onSubmitted: (result: ReviewSubmitResult) => void; onClose: () => void }) {
  const [summary, setSummary] = useState('')
  return <SubmitReviewDialog reviewId={1} pendingComments={pending} summary={summary} onSummaryChange={setSummary} onSubmitted={onSubmitted} onClose={onClose} />
}

function renderDialog({ viewer = 'alice', pending = 0, answer = () => Promise.resolve(Response.json(SUBMITTED)) } = {}) {
  const fetchMock = vi.fn<(url: string, init?: RequestInit) => Promise<Response>>((url, init) => {
    if (url === '/api/reviews/1/forge/review' && init?.method === 'POST') {
      return answer()
    }
    if (url === '/api/reviews/1/forge') {
      return Promise.resolve(Response.json(overview(viewer)))
    }
    return Promise.resolve(Response.json([]))
  })
  vi.stubGlobal('fetch', fetchMock)
  const onSubmitted = vi.fn()
  const onClose = vi.fn()
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <Harness pending={pending} onSubmitted={onSubmitted} onClose={onClose} />
    </QueryClientProvider>,
  )
  return { fetchMock, onSubmitted, onClose }
}

function posted(fetchMock: ReturnType<typeof renderDialog>['fetchMock']): unknown[] {
  return fetchMock.mock.calls.filter(([url, init]) => url === '/api/reviews/1/forge/review' && init?.method === 'POST').map(([, init]) => JSON.parse(typeof init?.body === 'string' ? init.body : '{}') as unknown)
}

const submitButton = () => screen.getByRole('button', { name: 'Submit review' })

describe('SubmitReviewDialog', () => {
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

  it('offers a summary with Write and Preview and the three review types', () => {
    renderDialog()

    fireEvent.change(screen.getByLabelText('Review summary'), { target: { value: 'Looks **good**' } })
    fireEvent.click(screen.getByRole('tab', { name: 'Preview' }))

    expect(screen.getByText('good').tagName).toBe('STRONG')
    expect(screen.getByRole('radio', { name: /^Comment/ })).toBeChecked()
    expect(screen.getByRole('radio', { name: /^Approve/ })).toBeEnabled()
    expect(screen.getByRole('radio', { name: /^Request changes/ })).toBeEnabled()
    fireEvent.click(screen.getByRole('tab', { name: 'Write' }))
    expect(screen.getByLabelText('Review summary')).toHaveValue('Looks **good**')
  })

  it('approves without a summary and closes', async () => {
    const { fetchMock, onSubmitted, onClose } = renderDialog()

    fireEvent.click(screen.getByRole('radio', { name: /^Approve/ }))
    fireEvent.click(submitButton())

    await waitFor(() => { expect(onSubmitted).toHaveBeenCalledWith(SUBMITTED) })
    expect(onClose).toHaveBeenCalled()
    expect(posted(fetchMock)).toEqual([{ event: 'APPROVE', body: '' }])
  })

  it('needs a summary to request changes, and to comment without pending comments', () => {
    renderDialog()

    expect(submitButton()).toBeDisabled()
    fireEvent.click(screen.getByRole('radio', { name: /^Request changes/ }))
    expect(submitButton()).toBeDisabled()
    expect(screen.getByText('Write a summary to request changes.')).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('Review summary'), { target: { value: 'Please rename it' } })
    expect(submitButton()).toBeEnabled()
  })

  it('comments with only the pending comments', () => {
    renderDialog({ pending: 2 })

    expect(submitButton()).toBeEnabled()
    expect(screen.getByText('2 pending comments will be sent with this review.')).toBeInTheDocument()
  })

  it('allows only Comment on your own pull request', async () => {
    renderDialog({ viewer: 'bob' })

    await waitFor(() => { expect(screen.getByRole('radio', { name: /^Approve/ })).toBeDisabled() })
    expect(screen.getByRole('radio', { name: /^Request changes/ })).toBeDisabled()
    expect(screen.getByRole('radio', { name: /^Comment/ })).toBeEnabled()
    expect(screen.getByText('You cannot approve or request changes on your own pull request.')).toBeInTheDocument()
  })

  it('shows the error and keeps the summary when GitHub refuses', async () => {
    const answer = () => Promise.resolve(Response.json({ detail: 'HTTP 422: Unprocessable Entity' }, { status: 502 }))
    const { onSubmitted, onClose } = renderDialog({ answer })

    fireEvent.change(screen.getByLabelText('Review summary'), { target: { value: 'Please rename it' } })
    fireEvent.click(screen.getByRole('radio', { name: /^Request changes/ }))
    fireEvent.click(submitButton())

    expect(await screen.findByRole('alert')).toHaveTextContent('HTTP 422: Unprocessable Entity')
    expect(screen.getByLabelText('Review summary')).toHaveValue('Please rename it')
    expect(onSubmitted).not.toHaveBeenCalled()
    expect(onClose).not.toHaveBeenCalled()
  })
})
