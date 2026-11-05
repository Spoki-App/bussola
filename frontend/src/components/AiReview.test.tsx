import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { AiReviewResult, AiReviewStatus, AiStatus } from '../api/types'
import { useAiReview } from '../hooks/useAiReview'
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

const IDLE: AiReviewStatus = { running: false, phase: null, done: 0, total: 0, lookups: 0, units: 5, reviewed_units: 0 }

function Harness() {
  return <AiReview repoId={3} review={useAiReview(1)} />
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
    expect(JSON.parse(typeof body === 'string' ? body : '{}')).toEqual({ target: AI.target, call_id: expect.stringMatching(/^[0-9a-f]{32}$/) as unknown })
  })

  it('shows the progress and can be cancelled, keeping what was found', async () => {
    const request: { finish?: (response: Response) => void; done?: boolean } = {}
    const running: AiReviewStatus = { running: true, phase: 'reviewing', done: 2, total: 5, lookups: 3, units: 5, reviewed_units: 2 }
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

  it('says how much of the pull request already has an AI review', async () => {
    renderReview(() => new Promise<Response>(() => undefined), () => ({ ...IDLE, reviewed_units: 3 }))

    expect(await screen.findByText('3 of 5 units have an AI review.')).toBeInTheDocument()
  })

  it('follows and cancels a review started in another tab', async () => {
    let calls = 0
    const fetchMock = renderReview(
      () => new Promise<Response>(() => undefined),
      () => {
        calls += 1
        return calls < 3 ? { ...IDLE, running: true, phase: 'rating', done: calls, total: 5 } : IDLE
      },
    )

    expect(await screen.findByText('Rating the impact first: 1 of 5 units...')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'AI review' })).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    await waitFor(() => { expect(fetchMock.mock.calls.some(([url]) => url === '/api/reviews/1/ai-review/cancel')).toBe(true) })
    expect(await screen.findByRole('button', { name: 'AI review' }, { timeout: 4000 })).toBeInTheDocument()
  })
})
