import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { AiStatus, RateImpactResult } from '../api/types'
import { useRateImpact } from '../hooks/useRateImpact'
import { rememberAiConsent } from '../settings/aiConsent'
import { RateImpact } from './RateImpact'

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

function Harness() {
  return <RateImpact repoId={3} rating={useRateImpact(1)} />
}

function renderRating(answer: () => Promise<Response>) {
  const fetchMock = vi.fn<(url: string, init?: RequestInit) => Promise<Response>>((url) => {
    if (url === '/api/repos/3/ai') {
      return Promise.resolve(Response.json(AI))
    }
    if (url === '/api/reviews/1/impact') {
      return answer()
    }
    return Promise.resolve(Response.json({ cancelled: true }))
  })
  vi.stubGlobal('fetch', fetchMock)
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const page = (key: string) => (
    <QueryClientProvider client={client}>
      <Harness key={key} />
    </QueryClientProvider>
  )
  const view = render(page('first'))
  return Object.assign(fetchMock, { remount: () => { view.rerender(page('second')) } })
}

describe('Rate impact', () => {
  beforeEach(() => {
    window.localStorage.clear()
    if (AI.target) {
      rememberAiConsent(AI.target)
    }
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('rates every unit in one request and says what happened', async () => {
    const result: RateImpactResult = { rated: 4, failed: 1, cancelled: false, error: 'Timed out' }
    const fetchMock = renderRating(() => Promise.resolve(Response.json(result)))

    fireEvent.click(await screen.findByRole('button', { name: 'Rate impact' }))

    expect(await screen.findByText('4 units rated. 1 unit could not be rated: Timed out')).toBeInTheDocument()
    const requests = fetchMock.mock.calls.filter(([url]) => url === '/api/reviews/1/impact')
    expect(requests).toHaveLength(1)
    const body = requests[0][1]?.body
    expect(JSON.parse(typeof body === 'string' ? body : '{}')).toEqual({ target: AI.target, call_id: expect.stringMatching(/^[0-9a-f]{32}$/) as unknown })
  })

  it('shows that it is working and can be cancelled', async () => {
    let finish: (response: Response) => void = () => undefined
    const fetchMock = renderRating(() => new Promise<Response>((resolve) => { finish = resolve }))

    fireEvent.click(await screen.findByRole('button', { name: 'Rate impact' }))
    expect(await screen.findByRole('status')).toHaveTextContent('Rating the impact of each unit...')
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))

    await waitFor(() => { expect(fetchMock.mock.calls.some(([url]) => url.startsWith('/api/ai/calls/'))).toBe(true) })
    finish(Response.json({ rated: 1, failed: 0, cancelled: true, error: null }))
    expect(await screen.findByText('Cancelled, 1 unit rated.')).toBeInTheDocument()
  })

  it('still shows a running batch and its Cancel after the page is mounted again', async () => {
    const fetchMock = renderRating(() => new Promise<Response>(() => undefined))
    fireEvent.click(await screen.findByRole('button', { name: 'Rate impact' }))
    await screen.findByRole('status')

    fetchMock.remount()

    expect(await screen.findByRole('status')).toHaveTextContent('Rating the impact of each unit...')
    expect(screen.queryByRole('button', { name: 'Rate impact' })).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    await waitFor(() => { expect(fetchMock.mock.calls.some(([url]) => url.startsWith('/api/ai/calls/'))).toBe(true) })
    expect(fetchMock.mock.calls.filter(([url]) => url === '/api/reviews/1/impact')).toHaveLength(1)
  })
})
