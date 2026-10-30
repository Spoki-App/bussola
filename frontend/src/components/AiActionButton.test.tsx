import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'

import type { AiStatus } from '../api/types'
import { AiActionButton } from './AiActionButton'

const LOCAL: AiStatus = {
  configured: true,
  provider: 'openai-compatible',
  label: 'OpenAI-compatible endpoint',
  model: 'qwen2.5-coder',
  endpoint: 'http://localhost:11434/v1',
  source: 'repository',
  api_key_env: null,
  api_key_set: false,
  problem: null,
  config_file: null,
  target: 'openai-compatible|qwen2.5-coder|http://localhost:11434/v1',
}

function renderButton(status: AiStatus, onRun = vi.fn()) {
  vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(Response.json(status))))
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <AiActionButton repoId={3} label="Describe" onRun={onRun} />
    </QueryClientProvider>,
  )
  return onRun
}

describe('AiActionButton', () => {
  beforeAll(() => {
    HTMLDialogElement.prototype.showModal = function showModal(this: HTMLDialogElement) {
      this.open = true
    }
    HTMLDialogElement.prototype.close = function close(this: HTMLDialogElement) {
      this.open = false
      this.dispatchEvent(new Event('close'))
    }
  })

  beforeEach(() => {
    window.localStorage.clear()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('is hidden when no provider is configured', async () => {
    renderButton({ ...LOCAL, configured: false, provider: null, label: null, target: null })

    await new Promise((resolve) => setTimeout(resolve, 0))

    expect(screen.queryByRole('button', { name: 'Describe' })).toBeNull()
  })

  it('names the provider the first time and runs only after Send code', async () => {
    const onRun = renderButton(LOCAL)

    fireEvent.click(await screen.findByRole('button', { name: 'Describe' }))

    const notice = screen.getByRole('dialog', { name: 'Send code to OpenAI-compatible endpoint?' })
    expect(notice).toHaveTextContent('This action sends the code it works on to OpenAI-compatible endpoint (model qwen2.5-coder) at http://localhost:11434/v1.')
    expect(notice).toHaveTextContent("This provider is set by the repository's .bussola.toml.")
    expect(onRun).not.toHaveBeenCalled()

    fireEvent.click(screen.getByRole('button', { name: 'Send code' }))

    expect(onRun).toHaveBeenCalledTimes(1)
    expect(screen.queryByRole('dialog')).toBeNull()

    fireEvent.click(screen.getByRole('button', { name: 'Describe' }))

    expect(onRun).toHaveBeenCalledTimes(2)
    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('sends nothing when the notice is cancelled and asks again next time', async () => {
    const onRun = renderButton(LOCAL)

    fireEvent.click(await screen.findByRole('button', { name: 'Describe' }))
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))

    expect(onRun).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: 'Describe' }))
    expect(screen.getByRole('dialog')).toBeInTheDocument()
  })

  it('asks again when the provider, model or endpoint changes', async () => {
    window.localStorage.setItem('bussola.aiConsent', JSON.stringify(['openai-compatible|llama3|http://localhost:11434/v1']))
    const onRun = renderButton(LOCAL)

    fireEvent.click(await screen.findByRole('button', { name: 'Describe' }))

    expect(screen.getByRole('dialog')).toBeInTheDocument()
    expect(onRun).not.toHaveBeenCalled()
  })
})
