import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { AiPrompts } from '../api/types'
import { AiPromptsPanel } from './AiPromptsPanel'

const PROMPTS: AiPrompts = {
  prompts: [
    { key: 'describe', title: 'Describe', default: 'Describe the unit.', custom: null },
    { key: 'impact', title: 'Rate impact', default: 'Rate the impact.', custom: null },
    { key: 'review', title: 'AI review', default: 'Report real problems.', custom: 'Only security problems.' },
  ],
  config_file: '/home/me/.config/bussola/config.toml',
  problem: null,
}

function renderPanel() {
  const fetchMock = vi.fn<(url: string, init?: RequestInit) => Promise<Response>>((_url, init) => {
    if (init?.method === 'PUT') {
      return Promise.resolve(Response.json({ ...PROMPTS, prompts: PROMPTS.prompts.map((prompt) => ({ ...prompt, custom: prompt.key === 'impact' ? 'All high.' : null })) }))
    }
    return Promise.resolve(Response.json(PROMPTS))
  })
  vi.stubGlobal('fetch', fetchMock)
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <AiPromptsPanel />
    </QueryClientProvider>,
  )
  return fetchMock
}

describe('AiPromptsPanel', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('shows each prompt with its custom text or its default, and marks the custom ones', async () => {
    renderPanel()

    expect(await screen.findByLabelText('AI review instructions')).toHaveValue('Only security problems.')
    expect(screen.getByLabelText('Describe instructions')).toHaveValue('Describe the unit.')
    expect(screen.getAllByText('Custom')).toHaveLength(1)
  })

  it('resets a prompt to its default and saves every prompt', async () => {
    const fetchMock = renderPanel()

    fireEvent.change(await screen.findByLabelText('Rate impact instructions'), { target: { value: 'All high.' } })
    const [, , reviewReset] = screen.getAllByRole('button', { name: 'Reset to default' })
    fireEvent.click(reviewReset)
    expect(screen.getByLabelText('AI review instructions')).toHaveValue('Report real problems.')
    fireEvent.click(screen.getByRole('button', { name: 'Save prompts' }))

    expect(await screen.findByText('Saved')).toBeInTheDocument()
    const put = fetchMock.mock.calls.find(([, init]) => init?.method === 'PUT')
    expect(put?.[0]).toBe('/api/ai/prompts')
    const body = put?.[1]?.body
    expect(JSON.parse(typeof body === 'string' ? body : '{}')).toEqual({ describe: 'Describe the unit.', impact: 'All high.', review: 'Report real problems.' })
    await waitFor(() => { expect(screen.getByLabelText('Rate impact instructions')).toHaveValue('All high.') })
  })
})
