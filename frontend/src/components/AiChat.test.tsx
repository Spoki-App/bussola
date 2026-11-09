import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { useState } from 'react'
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'

import type { AiChatMessage, AiStatus } from '../api/types'
import type { CodeTarget } from '../hooks/useCodeNavigation'
import type { ChatSnippetDraft } from '../review/askAi'
import { rememberAiConsent } from '../settings/aiConsent'
import { AiChat } from './AiChat'

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

const OFF: AiStatus = { ...AI, configured: false, provider: null, target: null }

const SELECTED: ChatSnippetDraft = { range: { unit_id: 7, side: 'head', line_offset: 1, line_count: 2 }, label: '2 lines of total' }

const QUESTION: AiChatMessage = {
  id: 1,
  role: 'user',
  body: 'Why 1.2?',
  snippets: [{ unit: 'app.py::total', path: 'app.py', side: 'after', first_line: 2, last_line: 3, code: '2:     return sum(items) * 1.2' }],
  lookups: [],
  comments: [],
  links: [],
  provider_label: null,
  model: null,
  created_at: '2026-11-09T10:00:00Z',
}

const ANSWER: AiChatMessage = {
  id: 2,
  role: 'assistant',
  body: 'It adds a [20% tax](#after:app.py:2).',
  snippets: [],
  lookups: [{ tool: 'read_file', arguments: { path: 'app.py', side: 'before', start_line: 2, end_line: 2 }, result: '2:     return sum(items)', error: false }],
  comments: [],
  links: [{ path: 'app.py', side: 'head', line: 2, unit_id: 7 }],
  provider_label: 'Anthropic API',
  model: 'claude-opus-5-5',
  created_at: '2026-11-09T10:00:05Z',
}

function Harness({ initial, onShowLine }: { initial: ChatSnippetDraft[]; onShowLine?: (target: CodeTarget) => void }) {
  const [snippets, setSnippets] = useState(initial)
  return <AiChat reviewId={1} repoId={3} snippets={snippets} onSnippetsChange={setSnippets} onShowLine={onShowLine} />
}

interface Server {
  status?: AiStatus
  history?: AiChatMessage[]
  answer?: () => Promise<Response>
}

function renderChat({ status = AI, history = [], answer }: Server, initial: ChatSnippetDraft[] = [], onShowLine?: (target: CodeTarget) => void) {
  const fetchMock = vi.fn<(url: string, init?: RequestInit) => Promise<Response>>((url, init) => {
    if (url === '/api/repos/3/ai') {
      return Promise.resolve(Response.json(status))
    }
    if (url === '/api/reviews/1/ai-chat') {
      if (init?.method === 'POST' && answer) {
        return answer()
      }
      return Promise.resolve(Response.json(init?.method === 'DELETE' ? [] : history))
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
      <Harness initial={initial} onShowLine={onShowLine} />
    </QueryClientProvider>,
  )
  return fetchMock
}

function sentBodies(fetchMock: ReturnType<typeof renderChat>): unknown[] {
  return fetchMock.mock.calls
    .filter(([url, init]) => url === '/api/reviews/1/ai-chat' && init?.method === 'POST')
    .map(([, init]) => JSON.parse(typeof init?.body === 'string' ? init.body : '{}') as unknown)
}

describe('AI chat', () => {
  beforeAll(() => {
    Element.prototype.scrollIntoView = vi.fn()
  })

  beforeEach(() => {
    window.localStorage.clear()
    if (AI.target) {
      rememberAiConsent(AI.target)
    }
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('sends the message with the selected code and shows the answer', async () => {
    const fetchMock = renderChat({ answer: () => Promise.resolve(Response.json([QUESTION, ANSWER])) }, [SELECTED])
    const input = await screen.findByRole('textbox', { name: 'Message to the AI' })
    expect(screen.getByText('2 lines of total')).toBeInTheDocument()

    fireEvent.change(input, { target: { value: '  Why 1.2?  ' } })
    fireEvent.keyDown(input, { key: 'Enter' })

    expect(await screen.findByText('20% tax')).toBeInTheDocument()
    expect(sentBodies(fetchMock)).toEqual([{ target: AI.target, call_id: expect.stringMatching(/^[0-9a-f]{32}$/) as unknown, message: 'Why 1.2?', snippets: [SELECTED.range] }])
    expect(input).toHaveValue('')
    expect(screen.queryByRole('list', { name: 'Selected code' })).not.toBeInTheDocument()
    expect(screen.getByText('app.py::total, lines 2-3 after')).toBeInTheDocument()
    expect(screen.getByText('Anthropic API (claude-opus-5-5)')).toBeInTheDocument()
    expect(screen.getByText('1 code lookup')).toBeInTheDocument()
  })

  it('opens the line an answer links to', async () => {
    const onShowLine = vi.fn<(target: CodeTarget) => void>()
    renderChat({ history: [QUESTION, ANSWER] }, [], onShowLine)

    fireEvent.click(await screen.findByText('20% tax'))

    expect(onShowLine).toHaveBeenCalledWith({ path: 'app.py', side: 'head', line: 2, unit_id: 7 })
  })

  it('lists the comments an answer added and opens their thread', async () => {
    const comment = { thread_id: 't1', place: 'app.py::total, line 2 after', body: 'The rate should come from the settings.' }
    renderChat({ answer: () => Promise.resolve(Response.json([QUESTION, { ...ANSWER, body: 'I added a comment.', comments: [comment] }])) })
    const input = await screen.findByRole('textbox', { name: 'Message to the AI' })
    fireEvent.change(input, { target: { value: 'Add a comment about the rate' } })
    fireEvent.click(screen.getByRole('button', { name: 'Send' }))

    expect(await screen.findByText('1 comment added to the review')).toBeInTheDocument()
    expect(screen.getByText('The rate should come from the settings.')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'app.py::total, line 2 after' }))

    expect(window.location.pathname).toBe('/reviews/1')
    expect(new URLSearchParams(window.location.search).get('thread')).toBe('t1')
  })

  it('keeps the message when the answer fails, and Shift+Enter does not send', async () => {
    const fetchMock = renderChat({ answer: () => Promise.resolve(Response.json({ detail: 'Cannot reach https://api.anthropic.com' }, { status: 502 })) }, [SELECTED])
    const input = await screen.findByRole('textbox', { name: 'Message to the AI' })
    fireEvent.change(input, { target: { value: 'Why?' } })

    fireEvent.keyDown(input, { key: 'Enter', shiftKey: true })
    expect(sentBodies(fetchMock)).toEqual([])
    fireEvent.click(screen.getByRole('button', { name: 'Send' }))

    expect(await screen.findByText('Cannot reach https://api.anthropic.com')).toBeInTheDocument()
    expect(input).toHaveValue('Why?')
    expect(screen.getByText('2 lines of total')).toBeInTheDocument()
  })

  it('can cancel a running answer', async () => {
    const fetchMock = renderChat({ answer: () => new Promise<Response>(() => undefined) })
    const input = await screen.findByRole('textbox', { name: 'Message to the AI' })
    fireEvent.change(input, { target: { value: 'Why?' } })
    fireEvent.click(screen.getByRole('button', { name: 'Send' }))

    expect(await screen.findByText('Thinking...')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))

    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url]) => url.startsWith('/api/ai/calls/'))).toBe(true)
    })
  })

  it('clears the conversation and removes selected code', async () => {
    const fetchMock = renderChat({ history: [QUESTION, ANSWER] }, [SELECTED])
    fireEvent.click(await screen.findByRole('button', { name: 'Remove 2 lines of total' }))
    expect(screen.queryByText('2 lines of total')).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Clear' }))

    expect(await screen.findByText(/Ask anything about this pull request/)).toBeInTheDocument()
    expect(fetchMock.mock.calls.some(([url, init]) => url === '/api/reviews/1/ai-chat' && init?.method === 'DELETE')).toBe(true)
  })

  it('asks for a provider when AI is turned off', async () => {
    renderChat({ status: OFF })

    expect(await screen.findByText('Choose an AI provider in Settings to chat about this pull request.')).toBeInTheDocument()
    expect(screen.queryByRole('textbox', { name: 'Message to the AI' })).not.toBeInTheDocument()
  })
})
