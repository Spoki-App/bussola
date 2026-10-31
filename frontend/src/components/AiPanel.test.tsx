import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { AiStatus, AiTestResult } from '../api/types'
import { AiPanel } from './AiPanel'

const OFF: AiStatus = {
  configured: false,
  provider: null,
  label: null,
  model: null,
  endpoint: null,
  source: null,
  api_key_env: null,
  api_key_set: false,
  problem: null,
  config_file: '/home/me/.config/bussola/config.toml',
  target: null,
}

const ANTHROPIC: AiStatus = {
  ...OFF,
  configured: true,
  provider: 'anthropic',
  label: 'Anthropic API',
  model: 'claude-opus-5-5',
  endpoint: 'https://api.anthropic.com',
  source: 'user',
  api_key_env: 'ANTHROPIC_API_KEY',
  api_key_set: true,
  target: 'anthropic|claude-opus-5-5|https://api.anthropic.com',
}

function stubApi(status: AiStatus, test?: AiTestResult) {
  const fetchMock = vi.fn((input: string) => Promise.resolve(Response.json(input.endsWith('/ai/test') ? test : status)))
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function renderPanel() {
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <AiPanel />
    </QueryClientProvider>,
  )
}

describe('AiPanel', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('says AI is off and where to configure it when no provider is set', async () => {
    stubApi(OFF)
    renderPanel()

    expect(await screen.findByText(/AI features are off/)).toBeInTheDocument()
    expect(screen.getByText('/home/me/.config/bussola/config.toml')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Test connection' })).toBeNull()
  })

  it('asks to fix the configuration instead of adding one when it has a problem', async () => {
    stubApi({ ...OFF, problem: 'Invalid configuration in config.toml: ai.timout: Extra inputs are not permitted' })
    renderPanel()

    expect(await screen.findByText(/the AI configuration has a problem/)).toBeInTheDocument()
    expect(screen.queryByText(/To turn them on/)).toBeNull()
    expect(screen.getByRole('alert')).toHaveTextContent('ai.timout: Extra inputs are not permitted')
  })

  it('shows the active provider and model and tests the connection', async () => {
    const fetchMock = stubApi(ANTHROPIC, { ok: true, message: 'Anthropic API (claude-opus-5-5) answered', elapsed_ms: 420 })
    renderPanel()

    expect(await screen.findByText('Anthropic API')).toBeInTheDocument()
    expect(screen.getByText('claude-opus-5-5')).toBeInTheDocument()
    expect(screen.getByText('https://api.anthropic.com')).toBeInTheDocument()
    expect(screen.getByText('ANTHROPIC_API_KEY').parentElement?.textContent).toBe('ANTHROPIC_API_KEY is set')

    fireEvent.click(screen.getByRole('button', { name: 'Test connection' }))

    expect((await screen.findByRole('status')).textContent).toBe('Anthropic API (claude-opus-5-5) answered in 420 ms.')
    expect(fetchMock).toHaveBeenCalledWith('/api/ai/test', expect.objectContaining({ method: 'POST' }))
  })

  it('shows a failed test and a configuration problem as errors', async () => {
    stubApi({ ...ANTHROPIC, api_key_set: false, problem: 'Set the ANTHROPIC_API_KEY environment variable' }, { ok: false, message: 'Set the ANTHROPIC_API_KEY environment variable', elapsed_ms: 0 })
    renderPanel()

    expect(await screen.findByRole('alert')).toHaveTextContent('Set the ANTHROPIC_API_KEY environment variable')
    expect(screen.getByText('ANTHROPIC_API_KEY').parentElement?.textContent).toBe('ANTHROPIC_API_KEY is not set')

    fireEvent.click(screen.getByRole('button', { name: 'Test connection' }))

    await waitFor(() => {
      expect(screen.getAllByRole('alert')).toHaveLength(2)
    })
  })

  it('says the model is not set for other providers without one', async () => {
    stubApi({ ...ANTHROPIC, provider: 'openai-compatible', label: 'OpenAI-compatible endpoint', model: null, problem: 'Set model in the [ai] section of the configuration' })
    renderPanel()

    expect(await screen.findByText('Not set')).toBeInTheDocument()
    expect(screen.queryByText('Default of the claude command')).toBeNull()
  })

  it('says the configuration file is not set when the server does not know it', async () => {
    stubApi({ ...ANTHROPIC, config_file: null })
    renderPanel()

    expect(await screen.findByText('Configuration')).toBeInTheDocument()
    expect(screen.getByText('Configuration').nextElementSibling?.textContent).toBe('Not set')
  })

  it('shows the claude command default when no model is set', async () => {
    stubApi({ ...ANTHROPIC, provider: 'claude-code', label: 'Claude Code CLI', model: null, endpoint: null, api_key_env: null })
    renderPanel()

    expect(await screen.findByText('Default of the claude command')).toBeInTheDocument()
    expect(screen.queryByText('API key')).toBeNull()
  })
})
