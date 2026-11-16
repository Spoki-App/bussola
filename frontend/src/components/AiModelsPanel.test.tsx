import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { AiModels, AiStatus } from '../api/types'
import { AiModelsPanel } from './AiModelsPanel'

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
  operations: [
    { key: 'describe', title: 'Describe', model: null, effort: null },
    { key: 'impact', title: 'Rate impact', model: 'claude-haiku-5-5', effort: 'low' },
    { key: 'review', title: 'AI review', model: null, effort: 'high' },
    { key: 'chat', title: 'AI chat', model: null, effort: null },
  ],
}

function renderPanel(models: AiModels) {
  const fetchMock = vi.fn<(url: string, init?: RequestInit) => Promise<Response>>((url) => {
    return Promise.resolve(Response.json(url === '/api/ai/models' ? models : STATUS))
  })
  vi.stubGlobal('fetch', fetchMock)
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <AiModelsPanel />
    </QueryClientProvider>,
  )
  return fetchMock
}

describe('AiModelsPanel', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('shows the model and effort of each operation, with the global model as the fallback', async () => {
    renderPanel({ models: [], problem: null })

    expect(await screen.findByLabelText('Rate impact model')).toHaveValue('claude-haiku-5-5')
    expect(screen.getByLabelText('Rate impact effort')).toHaveValue('low')
    expect(screen.getByLabelText('AI review effort')).toHaveValue('high')
    expect(screen.getByLabelText('AI chat model')).toHaveAttribute('placeholder', 'claude-opus-5-5')
  })

  it('offers the models the provider lists and disables the effort for a model that does not take one', async () => {
    renderPanel({ models: [{ id: 'claude-opus-5-5', effort: true }, { id: 'claude-haiku-4-5', effort: false }], problem: null })

    const chatModel = await screen.findByLabelText('AI chat model')
    await waitFor(() => {
      expect(document.querySelectorAll('datalist option')).toHaveLength(2)
    })
    fireEvent.change(chatModel, { target: { value: 'claude-haiku-4-5' } })

    expect(screen.getByLabelText('AI chat effort')).toBeDisabled()
    expect(screen.getByText('This model does not take an effort.')).toBeInTheDocument()
    expect(screen.getByLabelText('Describe effort')).toBeEnabled()
  })

  it('does not save an effort for a model that does not take one', async () => {
    const fetchMock = renderPanel({ models: [{ id: 'claude-haiku-4-5', effort: false }], problem: null })

    const impactModel = await screen.findByLabelText('Rate impact model')
    await waitFor(() => {
      expect(document.querySelectorAll('datalist option')).toHaveLength(1)
    })
    fireEvent.change(impactModel, { target: { value: 'claude-haiku-4-5' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save models' }))

    expect(await screen.findByText('Saved')).toBeInTheDocument()
    const put = fetchMock.mock.calls.find(([, init]) => init?.method === 'PUT')
    const body = put?.[1]?.body
    expect(JSON.parse(typeof body === 'string' ? body : '{}')).toMatchObject({ impact: { model: 'claude-haiku-4-5', effort: null } })
  })

  it('saves every operation, with blank models left to the global model', async () => {
    const fetchMock = renderPanel({ models: [], problem: 'models answered HTTP 404' })

    fireEvent.change(await screen.findByLabelText('Describe effort'), { target: { value: 'medium' } })
    fireEvent.change(screen.getByLabelText('Rate impact model'), { target: { value: '  ' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save models' }))

    expect(await screen.findByText('Saved')).toBeInTheDocument()
    expect(screen.getByText(/did not list its models, so type the model name/)).toBeInTheDocument()
    const put = fetchMock.mock.calls.find(([, init]) => init?.method === 'PUT')
    expect(put?.[0]).toBe('/api/ai/operations')
    const body = put?.[1]?.body
    expect(JSON.parse(typeof body === 'string' ? body : '{}')).toEqual({
      describe: { model: null, effort: 'medium' },
      impact: { model: null, effort: 'low' },
      review: { model: null, effort: 'high' },
      chat: { model: null, effort: null },
    })
  })
})
