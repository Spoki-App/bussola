import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { AiConfig, AiModels, AiOperation, AiPrompts, AiStatus } from '../api/types'
import { AiSettingsPanel } from './AiSettingsPanel'

const UNSET = { provider: null, label: null, model: null, effort: null, endpoint: null, api_key_env: null, problem: null }

const OPERATIONS: AiOperation[] = [
  { ...UNSET, key: 'describe', title: 'Describe' },
  { ...UNSET, key: 'impact', title: 'Rate impact', model: 'claude-haiku-4-5', effort: 'low' },
  { ...UNSET, key: 'review', title: 'AI review', effort: 'high' },
  { ...UNSET, key: 'chat', title: 'AI chat' },
]

const STATUS: AiStatus = {
  configured: true,
  provider: 'anthropic',
  label: 'Anthropic API',
  model: 'claude-opus-5-5',
  endpoint: 'https://api.anthropic.com',
  api_key_env: 'ANTHROPIC_API_KEY',
  api_key_set: true,
  problem: null,
  config_file: '/home/me/.config/bussola/config.toml',
  target: '["anthropic", "claude-opus-5-5", "https://api.anthropic.com"]',
  operations: OPERATIONS,
}

const CONFIG: AiConfig = {
  provider: 'anthropic',
  model: null,
  endpoint: null,
  api_key_env: null,
  timeout: 600,
  max_tokens: null,
  max_code_characters: null,
  config_file: STATUS.config_file,
  problem: null,
}

const PROMPTS: AiPrompts = {
  prompts: [
    { key: 'describe', default: 'Describe the unit.', custom: null },
    { key: 'impact', default: 'Rate the impact.', custom: null },
    { key: 'review', default: 'Report real problems.', custom: 'Only security problems.' },
    { key: 'chat', default: 'Answer briefly.', custom: null },
  ],
  problem: null,
}

const LISTED: AiModels = { models: [{ id: 'claude-opus-5-5', effort: true }, { id: 'claude-haiku-4-5', effort: false }], problem: null }

function renderPanel(status: AiStatus = STATUS, models: (url: string) => AiModels = () => LISTED) {
  const fetchMock = vi.fn<(url: string, init?: RequestInit) => Promise<Response>>((url, init) => {
    if (init?.method === 'PUT') {
      return Promise.resolve(Response.json(status))
    }
    if (url.startsWith('/api/ai/models')) {
      return Promise.resolve(Response.json(models(url)))
    }
    if (url === '/api/ai/prompts') {
      return Promise.resolve(Response.json(PROMPTS))
    }
    return Promise.resolve(Response.json(url === '/api/ai/config' ? CONFIG : status))
  })
  vi.stubGlobal('fetch', fetchMock)
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <AiSettingsPanel />
    </QueryClientProvider>,
  )
  return fetchMock
}

function openTab(name: string) {
  fireEvent.click(screen.getByRole('tab', { name }))
  return screen.getByRole('tabpanel', { name })
}

function savedRequest(fetchMock: ReturnType<typeof renderPanel>): [string, unknown] | undefined {
  const call = fetchMock.mock.calls.find(([, init]) => init?.method === 'PUT')
  const body = call?.[1]?.body
  return call && [call[0], JSON.parse(typeof body === 'string' ? body : '{}')]
}

describe('AiSettingsPanel', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('has a General tab with the provider and a tab for each AI feature', async () => {
    renderPanel()

    expect(screen.getAllByRole('tab').map((tab) => tab.textContent)).toEqual(['General', 'Describe', 'Rate impact', 'AI review', 'AI chat'])
    expect(screen.getByRole('tab', { name: 'General' })).toHaveAttribute('aria-selected', 'true')
    expect(await within(screen.getByRole('tabpanel', { name: 'General' })).findByLabelText('Provider')).toHaveValue('anthropic')
    expect(screen.queryByRole('tabpanel', { name: 'Describe' })).toBeNull()
  })

  it('shows the provider, model, effort and prompt of a feature, with General as the default', async () => {
    renderPanel()
    await screen.findByRole('tab', { name: 'AI review' })
    await waitFor(() => {
      expect(screen.getAllByRole('tabpanel', { hidden: true })).toHaveLength(5)
    })

    const review = within(openTab('AI review'))
    expect(review.getByLabelText('AI review provider')).toHaveValue('')
    expect(review.getByRole('option', { name: 'Same as General: Anthropic API' })).toBeInTheDocument()
    const model = await review.findByRole('combobox', { name: 'AI review model' })
    expect(Array.from(model.querySelectorAll('option'), (option) => option.textContent)).toEqual(['Same as General (claude-opus-5-5)', 'claude-opus-5-5', 'claude-haiku-4-5'])
    expect(review.getByLabelText('AI review effort')).toHaveValue('high')
    expect(review.getByLabelText(/AI review prompt/)).toHaveValue('Only security problems.')
    expect(review.getByText('Custom')).toBeInTheDocument()
    expect(within(openTab('Rate impact')).getByLabelText('Rate impact effort')).toBeDisabled()
  })

  it('saves the model, effort and prompt of one feature', async () => {
    const fetchMock = renderPanel()
    await screen.findByRole('tab', { name: 'AI review' })
    const review = within(await waitFor(() => openTab('AI review')))

    fireEvent.change(await review.findByRole('combobox', { name: 'AI review model' }), { target: { value: 'claude-opus-5-5' } })
    fireEvent.change(review.getByLabelText('AI review effort'), { target: { value: 'medium' } })
    fireEvent.click(review.getByRole('button', { name: 'Reset prompt to default' }))
    expect(review.getByLabelText(/AI review prompt/)).toHaveValue('Report real problems.')
    fireEvent.click(review.getByRole('button', { name: 'Save' }))

    expect(await review.findByText('Saved')).toBeInTheDocument()
    expect(savedRequest(fetchMock)).toEqual([
      '/api/ai/operations/review',
      { provider: null, model: 'claude-opus-5-5', effort: 'medium', endpoint: null, api_key_env: null, prompt: 'Report real problems.' },
    ])
  })

  it('lets a feature use its own provider and lists the models of that provider', async () => {
    const qwen: AiModels = { models: [{ id: 'qwen2.5-coder', effort: null }], problem: null }
    const fetchMock = renderPanel(STATUS, (url) => (url.includes('openai-compatible') ? qwen : LISTED))
    await screen.findByRole('tab', { name: 'AI chat' })
    const chat = within(await waitFor(() => openTab('AI chat')))

    fireEvent.change(chat.getByLabelText('AI chat provider'), { target: { value: 'openai-compatible' } })
    fireEvent.change(chat.getByLabelText('AI chat endpoint'), { target: { value: 'http://localhost:11434/v1' } })
    fireEvent.change(chat.getByLabelText('AI chat API key environment variable'), { target: { value: 'LM_KEY' } })
    const model = await chat.findByRole('option', { name: 'qwen2.5-coder' })
    fireEvent.change(chat.getByRole('combobox', { name: 'AI chat model' }), { target: { value: model.getAttribute('value') } })
    fireEvent.click(chat.getByRole('button', { name: 'Save' }))

    await waitFor(() => {
      expect(savedRequest(fetchMock)).toEqual([
        '/api/ai/operations/chat',
        { provider: 'openai-compatible', model: 'qwen2.5-coder', effort: null, endpoint: 'http://localhost:11434/v1', api_key_env: 'LM_KEY', prompt: 'Answer briefly.' },
      ])
    })
    expect(fetchMock).toHaveBeenCalledWith('/api/ai/models?provider=openai-compatible&operation=chat', expect.anything())
  })

  it('lists the models of a feature only once its tab is open', async () => {
    const operations = OPERATIONS.map((operation) => (operation.key === 'chat' ? { ...operation, provider: 'claude-code' as const, label: 'Claude Code CLI' } : operation))
    const fetchMock = renderPanel({ ...STATUS, operations })
    await screen.findByRole('tab', { name: 'AI chat' })
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith('/api/ai/models?provider=anthropic', expect.anything())
    })
    expect(fetchMock.mock.calls.some(([url]) => url.includes('operation='))).toBe(false)

    await waitFor(() => openTab('AI chat'))

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith('/api/ai/models?provider=claude-code&operation=chat', expect.anything())
    })
  })

  it('falls back to typing the model and shows why the provider did not list its models', async () => {
    renderPanel(STATUS, () => ({ models: [], problem: 'models answered HTTP 404' }))
    await screen.findByRole('tab', { name: 'Describe' })
    const describeTab = within(await waitFor(() => openTab('Describe')))

    expect(await describeTab.findByText('The provider did not list its models, so type the model name: models answered HTTP 404')).toBeInTheDocument()
    expect(describeTab.getByRole('textbox', { name: 'Describe model' })).toHaveAttribute('placeholder', 'Same as General (claude-opus-5-5)')
  })

  it('shows the problem of a feature provider and of a broken configuration', async () => {
    const operations = OPERATIONS.map((operation) =>
      operation.key === 'chat' ? { ...operation, provider: 'anthropic' as const, label: 'Anthropic API', problem: 'Set the MY_KEY environment variable' } : operation,
    )
    renderPanel({ ...STATUS, provider: 'claude-code', label: 'Claude Code CLI', model: null, operations })
    await screen.findByRole('tab', { name: 'AI chat' })

    expect(await within(await waitFor(() => openTab('AI chat'))).findByRole('alert')).toHaveTextContent('Set the MY_KEY environment variable')
  })

  it('shows why the features cannot be set when the configuration is broken', async () => {
    renderPanel({ ...STATUS, configured: false, provider: null, label: null, model: null, problem: 'Invalid configuration', operations: [] })

    fireEvent.click(screen.getByRole('tab', { name: 'Describe' }))

    expect(await screen.findAllByText('Invalid configuration')).not.toHaveLength(0)
  })
})
