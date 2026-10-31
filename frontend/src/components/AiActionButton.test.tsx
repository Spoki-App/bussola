import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
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

function renderButton(status: AiStatus, onRun = vi.fn(), later: AiStatus | null = status) {
  let calls = 0
  vi.stubGlobal(
    'fetch',
    vi.fn(() => {
      calls += 1
      if (calls > 1 && later === null) {
        return Promise.resolve(Response.json({ detail: 'Server error' }, { status: 500 }))
      }
      return Promise.resolve(Response.json(calls === 1 ? status : later))
    }),
  )
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

  it('is disabled with the reason when the repository configuration is invalid', async () => {
    renderButton({ ...LOCAL, configured: false, provider: null, label: null, target: null, problem: 'Invalid configuration in /repo/.bussola.toml' })

    const button = await screen.findByRole('button', { name: 'Describe' })

    expect(button).toBeDisabled()
    expect(button).toHaveAttribute('title', 'Invalid configuration in /repo/.bussola.toml')
  })

  it('is disabled with the reason when the provider cannot be used', async () => {
    const onRun = renderButton({ ...LOCAL, problem: 'Set model in the [ai] section of the configuration' })

    const button = await screen.findByRole('button', { name: 'Describe' })

    expect(button).toBeDisabled()
    expect(button).toHaveAttribute('title', 'Set model in the [ai] section of the configuration')
    fireEvent.click(button)
    expect(screen.queryByRole('dialog')).toBeNull()
    expect(onRun).not.toHaveBeenCalled()
  })

  it('names the provider the first time and runs only after Send code', async () => {
    const onRun = renderButton(LOCAL)

    fireEvent.click(await screen.findByRole('button', { name: 'Describe' }))

    const notice = await screen.findByRole('dialog', { name: 'Send code to OpenAI-compatible endpoint?' })
    expect(notice).toHaveTextContent('This action sends the code it works on to OpenAI-compatible endpoint (model qwen2.5-coder) at http://localhost:11434/v1.')
    expect(notice).toHaveTextContent("This provider is set by the repository's .bussola.toml.")
    expect(onRun).not.toHaveBeenCalled()

    fireEvent.click(screen.getByRole('button', { name: 'Send code' }))

    expect(onRun).toHaveBeenCalledWith(LOCAL.target)
    expect(screen.queryByRole('dialog')).toBeNull()

    fireEvent.click(screen.getByRole('button', { name: 'Describe' }))

    await waitFor(() => {
      expect(onRun).toHaveBeenCalledTimes(2)
    })
    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('sends nothing when the notice is cancelled and asks again next time', async () => {
    const onRun = renderButton(LOCAL)

    fireEvent.click(await screen.findByRole('button', { name: 'Describe' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Cancel' }))

    expect(onRun).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: 'Describe' }))
    expect(await screen.findByRole('dialog')).toBeInTheDocument()
  })

  it('asks again when the provider, model or endpoint changes', async () => {
    window.localStorage.setItem('bussola.aiConsent', JSON.stringify(['openai-compatible|llama3|http://localhost:11434/v1']))
    const onRun = renderButton(LOCAL)

    fireEvent.click(await screen.findByRole('button', { name: 'Describe' }))

    expect(await screen.findByRole('dialog')).toBeInTheDocument()
    expect(onRun).not.toHaveBeenCalled()
  })

  it('checks the provider again at click time, so an approval for an older endpoint does not apply', async () => {
    window.localStorage.setItem('bussola.aiConsent', JSON.stringify([LOCAL.target]))
    const moved = { ...LOCAL, endpoint: 'http://other.example/v1', target: 'openai-compatible|qwen2.5-coder|http://other.example/v1' }
    const onRun = renderButton(LOCAL, vi.fn(), moved)

    fireEvent.click(await screen.findByRole('button', { name: 'Describe' }))

    expect(await screen.findByRole('dialog')).toHaveTextContent('at http://other.example/v1.')
    expect(onRun).not.toHaveBeenCalled()
  })

  it('does nothing when the status cannot be read again at click time', async () => {
    window.localStorage.setItem('bussola.aiConsent', JSON.stringify([LOCAL.target]))
    const onRun = renderButton(LOCAL, vi.fn(), null)

    fireEvent.click(await screen.findByRole('button', { name: 'Describe' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Could not check the AI provider: Server error')
    expect(onRun).not.toHaveBeenCalled()
    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('says why nothing happens when the provider broke after the page loaded', async () => {
    const broken = { ...LOCAL, problem: 'Set the ANTHROPIC_API_KEY environment variable' }
    const onRun = renderButton(LOCAL, vi.fn(), broken)

    fireEvent.click(await screen.findByRole('button', { name: 'Describe' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Set the ANTHROPIC_API_KEY environment variable')
    expect(onRun).not.toHaveBeenCalled()
  })

  it('runs once for a double click', async () => {
    window.localStorage.setItem('bussola.aiConsent', JSON.stringify([LOCAL.target]))
    const onRun = renderButton(LOCAL)

    const button = await screen.findByRole('button', { name: 'Describe' })
    fireEvent.click(button)
    fireEvent.click(button)

    await waitFor(() => {
      expect(onRun).toHaveBeenCalledTimes(1)
    })
    await new Promise((resolve) => setTimeout(resolve, 50))
    expect(onRun).toHaveBeenCalledTimes(1)
  })
})
