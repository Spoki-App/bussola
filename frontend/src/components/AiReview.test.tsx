import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'

import type { AiReviewResult, AiReviewRunDetail, AiReviewStatus, AiStatus } from '../api/types'
import { useAiReview } from '../hooks/useAiReview'
import type { CodeTarget } from '../hooks/useCodeNavigation'
import { rememberAiConsent } from '../settings/aiConsent'
import { AiReview } from './AiReview'

const AI: AiStatus = {
  configured: true,
  provider: 'anthropic',
  label: 'Anthropic API',
  model: 'claude-opus-5-5',
  endpoint: 'https://api.anthropic.com',
  api_key_env: 'ANTHROPIC_API_KEY',
  api_key_set: true,
  problem: null,
  config_file: null,
  target: '["anthropic", "claude-opus-5-5", "https://api.anthropic.com"]',
}

const IDLE: AiReviewStatus = { running: false, phase: null, done: 0, total: 0, lookups: 0, units: 5, reviewed_units: 0, runs: 0 }

function Harness({ onShowLine }: { onShowLine?: (target: CodeTarget) => void }) {
  return <AiReview reviewId={1} repoId={3} review={useAiReview(1)} onShowLine={onShowLine} />
}

function renderReview(answer: () => Promise<Response>, status: () => AiReviewStatus = () => IDLE) {
  const fetchMock = vi.fn<(url: string, init?: RequestInit) => Promise<Response>>((url, init) => {
    if (url === '/api/repos/3/ai') {
      return Promise.resolve(Response.json(AI))
    }
    if (url === '/api/reviews/1/ai-review') {
      return init?.method === 'POST' ? answer() : Promise.resolve(Response.json(status()))
    }
    if (url.startsWith('/api/ai/calls/')) {
      return Promise.resolve(Response.json({ cancelled: true }))
    }
    return Promise.resolve(Response.json([]))
  })
  vi.stubGlobal('fetch', fetchMock)
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <Harness />
    </QueryClientProvider>,
  )
  return fetchMock
}

describe('AI review', () => {
  beforeEach(() => {
    window.localStorage.clear()
    if (AI.target) {
      rememberAiConsent(AI.target)
    }
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('reviews the pull request in one request and says what it found', async () => {
    const result: AiReviewResult = { reviewed: 5, findings: 3, failed: 1, cancelled: false, error: 'Timed out' }
    const fetchMock = renderReview(() => Promise.resolve(Response.json(result)))

    fireEvent.click(await screen.findByRole('button', { name: 'AI review' }))

    expect(await screen.findByText('5 units reviewed, 3 findings added as threads. 1 unit could not be reviewed: Timed out')).toBeInTheDocument()
    const posts = fetchMock.mock.calls.filter(([url, init]) => url === '/api/reviews/1/ai-review' && init?.method === 'POST')
    expect(posts).toHaveLength(1)
    const body = posts[0][1]?.body
    expect(JSON.parse(typeof body === 'string' ? body : '{}')).toEqual({ target: AI.target, call_id: expect.stringMatching(/^[0-9a-f]{32}$/) as unknown, again: false })
  })

  it('shows the progress and can be cancelled, keeping what was found', async () => {
    const request: { finish?: (response: Response) => void; done?: boolean } = {}
    const running: AiReviewStatus = { running: true, phase: 'reviewing', done: 2, total: 5, lookups: 3, units: 5, reviewed_units: 2, runs: 1 }
    const fetchMock = renderReview(
      () => new Promise<Response>((resolve) => { request.finish = resolve }),
      () => (request.finish && !request.done ? running : IDLE),
    )

    fireEvent.click(await screen.findByRole('button', { name: 'AI review' }))
    expect(await screen.findByText('AI review: 2 of 5 units reviewed, 3 code lookups so far...', undefined, { timeout: 3000 })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))

    await waitFor(() => { expect(fetchMock.mock.calls.some(([url]) => url.startsWith('/api/ai/calls/'))).toBe(true) })
    request.done = true
    request.finish?.(Response.json({ reviewed: 2, findings: 1, failed: 0, cancelled: true, error: null }))
    expect(await screen.findByText('Cancelled, 2 units reviewed, 1 finding added as threads.')).toBeInTheDocument()
  })

  it('says how much of the pull request already has an AI review and offers both reviews', async () => {
    renderReview(() => new Promise<Response>(() => undefined), () => ({ ...IDLE, reviewed_units: 3 }))

    expect(await screen.findByText('3 of 5 units have an AI review.')).toBeInTheDocument()
    expect(await screen.findByRole('button', { name: 'AI review' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Review again' })).toBeInTheDocument()
  })

  it('reviews the whole pull request again once every unit has an AI review', async () => {
    const fetchMock = renderReview(
      () => Promise.resolve(Response.json({ reviewed: 5, findings: 2, failed: 0, cancelled: false, error: null })),
      () => ({ ...IDLE, reviewed_units: 5 }),
    )

    expect(await screen.findByText('Every unit has an AI review.')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'AI review' })).toBeNull()
    fireEvent.click(await screen.findByRole('button', { name: 'Review again' }))

    expect(await screen.findByText('5 units reviewed, 2 findings added as threads.')).toBeInTheDocument()
    const post = fetchMock.mock.calls.find(([url, init]) => url === '/api/reviews/1/ai-review' && init?.method === 'POST')
    const body = post?.[1]?.body
    expect(JSON.parse(typeof body === 'string' ? body : '{}')).toMatchObject({ again: true })
  })

  it('follows and cancels a review started in another tab', async () => {
    let calls = 0
    const fetchMock = renderReview(
      () => new Promise<Response>(() => undefined),
      () => {
        calls += 1
        return calls < 3 ? { ...IDLE, running: true, phase: 'reviewing', done: 0, total: 5, lookups: calls } : IDLE
      },
    )

    expect(await screen.findByText('AI review: 0 of 5 units reviewed, 1 code lookup so far...')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'AI review' })).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    await waitFor(() => { expect(fetchMock.mock.calls.some(([url]) => url === '/api/reviews/1/ai-review/cancel')).toBe(true) })
    expect(await screen.findByRole('button', { name: 'AI review' }, { timeout: 4000 })).toBeInTheDocument()
  })
})

describe('AI review start', () => {
  beforeEach(() => {
    window.localStorage.clear()
    if (AI.target) {
      rememberAiConsent(AI.target)
    }
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('shows that it is starting while it checks the provider', async () => {
    let answer: (response: Response) => void = () => undefined
    let checks = 0
    vi.stubGlobal(
      'fetch',
      vi.fn((url: string) => {
        if (url === '/api/repos/3/ai') {
          checks += 1
          return checks === 1 ? Promise.resolve(Response.json(AI)) : new Promise<Response>((resolve) => { answer = resolve })
        }
        return Promise.resolve(Response.json(url === '/api/reviews/1/ai-review' ? IDLE : []))
      }),
    )
    render(
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <Harness />
      </QueryClientProvider>,
    )

    fireEvent.click(await screen.findByRole('button', { name: 'AI review' }))

    await waitFor(() => { expect(screen.getByRole('button', { name: 'AI review' })).toHaveAttribute('aria-busy', 'true') })
    answer(Response.json({ ...AI, configured: false, problem: 'AI is off' }))
    await waitFor(() => { expect(screen.getByRole('button', { name: 'AI review' })).toHaveAttribute('aria-busy', 'false') })
  })
})

const RUN: AiReviewRunDetail = {
  id: 7,
  status: 'completed',
  again: false,
  provider: 'anthropic',
  provider_label: 'Anthropic API',
  model: 'claude-opus-5-5',
  reviewed: 2,
  findings: 1,
  failed: 0,
  error: null,
  started_at: '2026-11-05T10:00:00Z',
  finished_at: '2026-11-05T10:02:00Z',
  rating: { rated: 2, failed: [], error: null },
  parts: [
    {
      units: [{ label: 'app.py::total', impact: 'high' }],
      summary: 'Checked the **callers** of `total`, such as [the cart](#after:shop.py:5), and [the old sum](#before:app.py:1).',
      findings: [{ thread_id: 't9', place: 'app.py::total, line 2 after', body: 'The rate is hard-coded.' }],
      lookups: [{ tool: 'find_usages', arguments: { path: 'app.py', line: 1, name: 'total' }, result: 'shop.py:5: total(cart)', error: false }],
      error: null,
    },
  ],
  links: [
    { path: 'app.py', side: 'base', line: 1, unit_id: 4 },
    { path: 'shop.py', side: 'head', line: 5, unit_id: null },
  ],
}

function renderDetails(onShowLine?: (target: CodeTarget) => void) {
  vi.stubGlobal(
    'fetch',
    vi.fn((url: string) => {
      const answers: Record<string, unknown> = {
        '/api/repos/3/ai': AI,
        '/api/reviews/1/ai-review': { ...IDLE, reviewed_units: 2, runs: 1 },
        '/api/reviews/1/ai-review/runs': [RUN],
        '/api/reviews/1/ai-review/runs/7': RUN,
      }
      return Promise.resolve(Response.json(answers[url] ?? []))
    }),
  )
  window.history.replaceState(null, '', '/reviews/1')
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <Harness onShowLine={onShowLine} />
    </QueryClientProvider>,
  )
}

describe('AI review details', () => {
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
    window.history.replaceState(null, '', '/')
  })

  it('shows what the last run checked, found and looked up, and opens a finding in the review', async () => {
    renderDetails()

    fireEvent.click(await screen.findByRole('button', { name: 'Details' }))

    const dialog = await screen.findByRole('dialog', { name: 'AI review details' })
    expect(await within(dialog).findByText(/^Completed: AI review with Anthropic API \(claude-opus-5-5\)/)).toBeInTheDocument()
    expect(within(dialog).getByText('callers')).toBeInTheDocument()
    expect(within(dialog).getByText('1 code lookup')).toBeInTheDocument()
    expect(within(dialog).getByText('find_usages(path: app.py, line: 1, name: total)')).toBeInTheDocument()
    fireEvent.click(within(dialog).getByRole('button', { name: 'app.py::total, line 2 after' }))
    expect(window.location.search).toBe('?thread=t9')
  })

  it('shows a line linked from the summary in the review and closes the details', async () => {
    const onShowLine = vi.fn<(target: CodeTarget) => void>()
    renderDetails(onShowLine)

    fireEvent.click(await screen.findByRole('button', { name: 'Details' }))
    const dialog = await screen.findByRole('dialog', { name: 'AI review details' })
    const old = await within(dialog).findByRole('link', { name: 'the old sum' })
    expect(old).toHaveAttribute('title', 'Show old line 1 of app.py')
    fireEvent.click(old)

    expect(onShowLine).toHaveBeenCalledWith({ path: 'app.py', side: 'base', line: 1, unit_id: 4 })
    expect(screen.queryByRole('dialog', { name: 'AI review details' })).toBeNull()

    fireEvent.click(screen.getByRole('button', { name: 'Details' }))
    fireEvent.click(await screen.findByRole('link', { name: 'the cart' }))
    expect(onShowLine).toHaveBeenLastCalledWith({ path: 'shop.py', side: 'head', line: 5, unit_id: null })
  })
})
