import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { useState } from 'react'
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest'

import type { AiReviewRun, AiReviewRunDetail, ForgeOverview, ReviewSubmitResult } from '../api/types'
import { SubmitReview, SubmitReviewDialog } from './SubmitReviewDialog'

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
    viewer_reviewed_at: null,
  }
}

const SUBMITTED: ReviewSubmitResult = {
  event: 'APPROVE',
  published: { review_url: 'https://github.com/acme/widgets/pull/7#pullrequestreview-1', outcomes: [] },
  unsent_comments: 0,
}

function Harness({ pending, onSubmitted, onClose }: { pending: number; onSubmitted: (result: ReviewSubmitResult) => void; onClose: () => void }) {
  const [summary, setSummary] = useState('')
  const [open, setOpen] = useState(true)
  const close = () => {
    setOpen(false)
    onClose()
  }
  return open && <SubmitReviewDialog reviewId={1} pendingComments={pending} summary={summary} onSummaryChange={setSummary} onSubmitted={onSubmitted} onClose={close} />
}

function deferred(): { promise: Promise<Response>; resolve: (response: Response) => void } {
  let resolve: (response: Response) => void = () => undefined
  const promise = new Promise<Response>((done) => {
    resolve = done
  })
  return { promise, resolve }
}

function renderDialog({
  viewer = 'alice',
  pending = 0,
  answer = () => Promise.resolve(Response.json(SUBMITTED)),
  forge = () => Promise.resolve(Response.json(overview(viewer))),
} = {}) {
  const fetchMock = vi.fn<(url: string, init?: RequestInit) => Promise<Response>>((url, init) => {
    if (url === '/api/reviews/1/forge/review' && init?.method === 'POST') {
      return answer()
    }
    if (url === '/api/reviews/1/forge') {
      return forge()
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

const SUMMARY = 'Review summary (Markdown)'

const submitButton = () => screen.getByRole('button', { name: 'Submit review' })

beforeAll(() => {
  HTMLDialogElement.prototype.showModal = function showModal(this: HTMLDialogElement) {
    this.open = true
  }
  HTMLDialogElement.prototype.close = function close(this: HTMLDialogElement) {
    this.open = false
    this.dispatchEvent(new Event('close'))
  }
})
describe('SubmitReviewDialog', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('offers a summary with Write and Preview and the three review types', () => {
    renderDialog()

    fireEvent.change(screen.getByLabelText(SUMMARY), { target: { value: 'Looks **good**' } })
    fireEvent.click(screen.getByRole('tab', { name: 'Preview' }))

    expect(screen.getByText('good').tagName).toBe('STRONG')
    expect(screen.getByRole('radio', { name: /^Comment/ })).toBeChecked()
    expect(screen.getByRole('radio', { name: /^Approve/ })).toBeEnabled()
    expect(screen.getByRole('radio', { name: /^Request changes/ })).toBeEnabled()
    fireEvent.click(screen.getByRole('tab', { name: 'Write' }))
    expect(screen.getByLabelText(SUMMARY)).toHaveValue('Looks **good**')
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
    fireEvent.change(screen.getByLabelText(SUMMARY), { target: { value: 'Please rename it' } })
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

  it('falls back to Comment when the pull request turns out to be your own', async () => {
    const pendingForge = deferred()
    const { fetchMock } = renderDialog({ pending: 1, forge: () => pendingForge.promise })

    fireEvent.click(screen.getByRole('radio', { name: /^Approve/ }))
    pendingForge.resolve(Response.json(overview('bob')))

    await waitFor(() => { expect(screen.getByRole('radio', { name: /^Approve/ })).toBeDisabled() })
    expect(screen.getByRole('radio', { name: /^Approve/ })).not.toBeChecked()
    expect(screen.getByRole('radio', { name: /^Comment/ })).toBeChecked()
    fireEvent.click(submitButton())
    await waitFor(() => { expect(posted(fetchMock)).toEqual([{ event: 'COMMENT', body: '' }]) })
  })

  it('reports the review submitted after the dialog was closed', async () => {
    const pendingAnswer = deferred()
    const { onSubmitted, onClose } = renderDialog({ answer: () => pendingAnswer.promise })

    fireEvent.click(screen.getByRole('radio', { name: /^Approve/ }))
    fireEvent.click(submitButton())
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(onClose).toHaveBeenCalled()
    pendingAnswer.resolve(Response.json(SUBMITTED))

    await waitFor(() => { expect(onSubmitted).toHaveBeenCalledWith(SUBMITTED) })
  })

  it('shows the error and keeps the summary when GitHub refuses', async () => {
    const answer = () => Promise.resolve(Response.json({ detail: 'HTTP 422: Unprocessable Entity' }, { status: 502 }))
    const { onSubmitted, onClose } = renderDialog({ answer })

    fireEvent.change(screen.getByLabelText(SUMMARY), { target: { value: 'Please rename it' } })
    fireEvent.click(screen.getByRole('radio', { name: /^Request changes/ }))
    fireEvent.click(submitButton())

    expect(await screen.findByRole('alert')).toHaveTextContent('HTTP 422: Unprocessable Entity')
    expect(screen.getByLabelText(SUMMARY)).toHaveValue('Please rename it')
    expect(onSubmitted).not.toHaveBeenCalled()
    expect(onClose).not.toHaveBeenCalled()
  })
})

const RUN: AiReviewRun = {
  id: 5,
  status: 'completed',
  again: false,
  provider: 'claude-code',
  provider_label: 'Claude Code',
  model: null,
  effort: null,
  reviewed: 2,
  findings: 1,
  failed: 0,
  error: null,
  started_at: '2026-11-12T10:00:00Z',
  finished_at: '2026-11-12T10:05:00Z',
}

const DETAIL: AiReviewRunDetail = {
  ...RUN,
  rating: null,
  links: [],
  rules: [],
  rules_error: null,
  parts: [{ units: [], summary: 'Needs work before merging.\n\n- [the total](#after:app.py:3) skips refunds', findings: [{ thread_id: 't1', place: 'app.py:3', body: 'Refunds' }], lookups: [], error: null }],
}

const AI_SUMMARY = 'Needs work before merging.\n\n- the total skips refunds'

function renderSubmitReview({ reviewedAt = null as string | null, runs = [RUN], threadStatus = 'open' } = {}) {
  const state = { runs }
  const fetchMock = vi.fn<(url: string) => Promise<Response>>((url) => {
    const answers: Record<string, unknown> = {
      '/api/reviews/1/forge': { ...overview('alice'), viewer_reviewed_at: reviewedAt },
      '/api/reviews/1/ai-review/runs': state.runs,
      '/api/reviews/1/ai-review/runs/5': DETAIL,
      '/api/reviews/1/threads?revision_id=3': [{ id: 't1', status: threadStatus, resolvable: true, created_at: '2026-11-12T10:04:00Z', created_by: { id: 2, email: '', name: 'Claude Code', ai: true } }],
    }
    return Promise.resolve(Response.json(answers[url] ?? []))
  })
  vi.stubGlobal('fetch', fetchMock)
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <SubmitReview reviewId={1} revisionId={3} pendingComments={0} onSubmitted={vi.fn()} />
    </QueryClientProvider>,
  )
  const loaded = () =>
    waitFor(() => {
      expect(fetchMock.mock.calls.some(([url]) => url === '/api/reviews/1/threads?revision_id=3')).toBe(true)
      expect(client.isFetching()).toBe(0)
    })
  const setRuns = async (next: AiReviewRun[]) => {
    state.runs = next
    await act(() => client.invalidateQueries())
    await waitFor(() => { expect(fetchMock.mock.calls.some(([url]) => url === '/api/reviews/1/ai-review/runs/5')).toBe(true) })
    await loaded()
  }
  return { loaded, setRuns }
}

const open = () => { fireEvent.click(screen.getAllByRole('button', { name: 'Submit review' })[0]) }
const cancel = () => { fireEvent.click(screen.getByRole('button', { name: 'Cancel' })) }

describe('SubmitReview', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('starts from a new AI review that left open comments, with Request changes', async () => {
    const { loaded } = renderSubmitReview({ reviewedAt: '2026-11-11T09:00:00Z' })
    await loaded()

    open()

    expect(screen.getByLabelText(SUMMARY)).toHaveValue(AI_SUMMARY)
    expect(screen.getByRole('radio', { name: /^Request changes/ })).toBeChecked()
    fireEvent.click(screen.getByRole('radio', { name: /^Comment/ }))
    expect(screen.getByRole('radio', { name: /^Comment/ })).toBeChecked()
  })

  it('keeps the summary cleared after the AI review was used once', async () => {
    const { loaded } = renderSubmitReview()
    await loaded()

    open()
    fireEvent.change(screen.getByLabelText(SUMMARY), { target: { value: '' } })
    cancel()
    open()

    expect(screen.getByLabelText(SUMMARY)).toHaveValue('')
  })

  it('keeps Comment when the AI review comments are resolved', async () => {
    const { loaded } = renderSubmitReview({ threadStatus: 'resolved' })
    await loaded()

    open()

    expect(screen.getByLabelText(SUMMARY)).toHaveValue(AI_SUMMARY)
    expect(screen.getByRole('radio', { name: /^Comment/ })).toBeChecked()
  })

  it('starts empty when the AI review is older than the last submitted review', async () => {
    const { loaded } = renderSubmitReview({ reviewedAt: '2026-11-12T11:00:00Z' })
    await loaded()

    open()

    expect(screen.getByLabelText(SUMMARY)).toHaveValue('')
    expect(screen.getByRole('radio', { name: /^Comment/ })).toBeChecked()
  })

  it('is not hidden by a later AI review that had nothing to review', async () => {
    const { loaded } = renderSubmitReview({ runs: [{ ...RUN, id: 6, reviewed: 0, findings: 0, finished_at: '2026-11-12T11:00:00Z' }, RUN] })
    await loaded()

    open()

    expect(screen.getByLabelText(SUMMARY)).toHaveValue(AI_SUMMARY)
    expect(screen.getByRole('radio', { name: /^Request changes/ })).toBeChecked()
  })

  it('keeps the review type while the dialog is open', async () => {
    const { loaded, setRuns } = renderSubmitReview({ runs: [] })
    await loaded()
    open()

    await setRuns([RUN])

    expect(screen.getByRole('radio', { name: /^Comment/ })).toBeChecked()
  })

  it('never replaces a summary already written', async () => {
    const { loaded, setRuns } = renderSubmitReview({ runs: [] })
    await loaded()
    open()
    fireEvent.change(screen.getByLabelText(SUMMARY), { target: { value: 'My own words' } })
    cancel()

    await setRuns([RUN])
    open()

    expect(screen.getByLabelText(SUMMARY)).toHaveValue('My own words')
    expect(screen.getByRole('radio', { name: /^Request changes/ })).toBeChecked()
  })
})
