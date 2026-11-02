import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { AiConfig, AiStatus, AiTestResult } from '../api/types'
import { AiPanel } from './AiPanel'

const CONFIG_FILE = '/home/me/.config/bussola/config.toml'

const OFF: AiStatus = {
  configured: false,
  provider: null,
  label: null,
  model: null,
  endpoint: null,
  api_key_env: null,
  api_key_set: false,
  problem: null,
  config_file: CONFIG_FILE,
  target: null,
}

const ANTHROPIC: AiStatus = {
  ...OFF,
  configured: true,
  provider: 'anthropic',
  label: 'Anthropic API',
  model: 'claude-opus-5-5',
  endpoint: 'https://api.anthropic.com',
  api_key_env: 'ANTHROPIC_API_KEY',
  api_key_set: true,
  target: 'anthropic|claude-opus-5-5|https://api.anthropic.com',
}

const EMPTY_CONFIG: AiConfig = {
  provider: null,
  model: null,
  endpoint: null,
  api_key_env: null,
  timeout: 600,
  max_tokens: null,
  config_file: CONFIG_FILE,
  problem: null,
}

interface Api {
  status: AiStatus
  config?: AiConfig
  test?: AiTestResult
  save?: Response
}

function stubApi({ status, config = { ...EMPTY_CONFIG, provider: status.provider }, test, save }: Api) {
  const fetchMock = vi.fn((input: string, init?: RequestInit) => {
    if (input.endsWith('/ai/test')) {
      return Promise.resolve(Response.json(test))
    }
    if (input.endsWith('/ai/config')) {
      return Promise.resolve(init?.method === 'PUT' ? (save ?? Response.json(status)) : Response.json(config))
    }
    return Promise.resolve(Response.json(status))
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function savedBody(fetchMock: ReturnType<typeof stubApi>): unknown {
  const body = fetchMock.mock.calls.find(([, init]) => init?.method === 'PUT')?.[1]?.body
  return typeof body === 'string' ? JSON.parse(body) : null
}

function renderPanel() {
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <AiPanel />
    </QueryClientProvider>,
  )
}

function details(): string {
  return document.querySelector('.ai-details')?.textContent ?? ''
}

describe('AiPanel', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('shows AI as off, where it is saved, and no connection test', async () => {
    stubApi({ status: OFF })
    renderPanel()

    expect(await screen.findByLabelText('Provider')).toHaveValue('none')
    expect(screen.getByText(CONFIG_FILE)).toBeInTheDocument()
    expect(screen.queryByLabelText('Model')).toBeNull()
    expect(screen.queryByRole('button', { name: 'Test connection' })).toBeNull()
  })

  it('turns AI on with Claude Code and saves only the fields it uses', async () => {
    const fetchMock = stubApi({ status: OFF })
    renderPanel()

    fireEvent.change(await screen.findByLabelText('Provider'), { target: { value: 'claude-code' } })
    expect(screen.queryByLabelText('Endpoint')).toBeNull()
    expect(screen.queryByLabelText('API key environment variable')).toBeNull()
    fireEvent.change(screen.getByLabelText('Model'), { target: { value: 'claude-opus-5-5' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))

    expect(await screen.findByText('Saved')).toBeInTheDocument()
    expect(savedBody(fetchMock)).toEqual({ provider: 'claude-code', model: 'claude-opus-5-5', endpoint: null, api_key_env: null, timeout: 600, max_tokens: null })
  })

  it('asks for the endpoint, the key variable and the answer budget of an API provider', async () => {
    const fetchMock = stubApi({ status: OFF, config: { ...EMPTY_CONFIG, timeout: null } })
    renderPanel()

    fireEvent.change(await screen.findByLabelText('Provider'), { target: { value: 'openai-compatible' } })
    expect(screen.getByLabelText('Endpoint')).toHaveAttribute('placeholder', 'Required, for example http://localhost:11434/v1')
    fireEvent.change(screen.getByLabelText('Endpoint'), { target: { value: 'http://localhost:1234/v1' } })
    fireEvent.change(screen.getByLabelText('Model'), { target: { value: 'qwen2.5-coder' } })
    fireEvent.change(screen.getByLabelText('API key environment variable'), { target: { value: 'LM_KEY' } })
    fireEvent.change(screen.getByLabelText('Answer budget in tokens'), { target: { value: '4000' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))

    await waitFor(() => {
      expect(savedBody(fetchMock)).toEqual({ provider: 'openai-compatible', model: 'qwen2.5-coder', endpoint: 'http://localhost:1234/v1', api_key_env: 'LM_KEY', timeout: null, max_tokens: 4000 })
    })
  })

  it('fills the form with the saved settings and turns AI off with nothing else', async () => {
    const fetchMock = stubApi({ status: ANTHROPIC, config: { ...EMPTY_CONFIG, provider: 'anthropic', api_key_env: 'WORK_KEY', timeout: 120 } })
    renderPanel()

    expect(await screen.findByLabelText('API key environment variable')).toHaveValue('WORK_KEY')
    expect(screen.getByLabelText('Timeout in seconds')).toHaveValue(120)

    fireEvent.change(screen.getByLabelText('Provider'), { target: { value: 'none' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))

    await waitFor(() => {
      expect(savedBody(fetchMock)).toEqual({ provider: 'none', model: null, endpoint: null, api_key_env: null, timeout: null, max_tokens: null })
    })
  })

  it('shows why the settings could not be saved', async () => {
    stubApi({ status: OFF, save: Response.json({ detail: 'ai.endpoint: Value error, endpoint must start with http:// or https://' }, { status: 400 }) })
    renderPanel()

    fireEvent.change(await screen.findByLabelText('Provider'), { target: { value: 'anthropic' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('endpoint must start with http:// or https://')
    expect(screen.queryByText('Saved')).toBeNull()
  })

  it('shows a configuration problem once and offers to replace the settings', async () => {
    const problem = 'Invalid configuration in config.toml: ai.timout: Extra inputs are not permitted'
    stubApi({ status: { ...OFF, problem }, config: { ...EMPTY_CONFIG, problem } })
    renderPanel()

    expect(await screen.findByRole('alert')).toHaveTextContent('ai.timout: Extra inputs are not permitted')
    expect(screen.getAllByRole('alert')).toHaveLength(1)
    expect(screen.getByText(/Saving replaces the AI settings in that file/)).toBeInTheDocument()
  })

  it('shows the active provider and model and tests the connection', async () => {
    const fetchMock = stubApi({ status: ANTHROPIC, test: { ok: true, message: 'Anthropic API (claude-opus-5-5) answered', elapsed_ms: 420 } })
    renderPanel()

    expect(await screen.findByRole('button', { name: 'Test connection' })).toBeInTheDocument()
    expect(details()).toContain('Anthropic API')
    expect(details()).toContain('claude-opus-5-5')
    expect(details()).toContain('https://api.anthropic.com')
    expect(details()).toContain('ANTHROPIC_API_KEY is set')

    fireEvent.click(screen.getByRole('button', { name: 'Test connection' }))

    expect((await screen.findByRole('status')).textContent).toBe('Anthropic API (claude-opus-5-5) answered in 420 ms.')
    expect(fetchMock).toHaveBeenCalledWith('/api/ai/test', expect.objectContaining({ method: 'POST' }))
  })

  it('shows a failed test and a provider problem as errors', async () => {
    const message = 'Set the ANTHROPIC_API_KEY environment variable'
    stubApi({ status: { ...ANTHROPIC, api_key_set: false, problem: message }, test: { ok: false, message, elapsed_ms: 0 } })
    renderPanel()

    expect(await screen.findByRole('alert')).toHaveTextContent(message)
    expect(details()).toContain('ANTHROPIC_API_KEY is not set')

    fireEvent.click(screen.getByRole('button', { name: 'Test connection' }))

    await waitFor(() => {
      expect(screen.getAllByRole('alert')).toHaveLength(2)
    })
  })

  it('says the model is not set for other providers without one', async () => {
    stubApi({ status: { ...ANTHROPIC, provider: 'openai-compatible', label: 'OpenAI-compatible endpoint', model: null, problem: 'Set model in the [ai] section of the configuration' } })
    renderPanel()

    await screen.findByRole('button', { name: 'Test connection' })
    expect(details()).toContain('Not set')
    expect(details()).not.toContain('Default of the claude command')
  })

  it('shows the claude command default when no model is set', async () => {
    stubApi({ status: { ...ANTHROPIC, provider: 'claude-code', label: 'Claude Code CLI', model: null, endpoint: null, api_key_env: null } })
    renderPanel()

    await screen.findByRole('button', { name: 'Test connection' })
    expect(details()).toContain('Default of the claude command')
    expect(details()).not.toContain('API key')
  })
})
