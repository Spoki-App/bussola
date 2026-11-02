import { useId, useState } from 'react'

import { useAiConfig, useAiStatus, useSaveAiConfig, useTestAiConnection } from '../api/ai'
import { describeError } from '../api/client'
import type { AiConfig, AiConfigFields, AiStatus } from '../api/types'
import { ErrorNote } from './Badges'

type ProviderChoice = 'none' | 'claude-code' | 'anthropic' | 'openai-compatible'

const PROVIDERS: Record<ProviderChoice, string> = {
  none: 'Off',
  'claude-code': 'Claude Code CLI',
  anthropic: 'Anthropic API',
  'openai-compatible': 'OpenAI-compatible endpoint',
}

const MODEL_PLACEHOLDERS: Record<ProviderChoice, string> = {
  none: '',
  'claude-code': 'Default of the claude command',
  anthropic: 'claude-opus-5-5',
  'openai-compatible': 'Required, for example qwen2.5-coder',
}

const ENDPOINT_PLACEHOLDERS: Record<ProviderChoice, string> = {
  none: '',
  'claude-code': '',
  anthropic: 'https://api.anthropic.com',
  'openai-compatible': 'Required, for example http://localhost:11434/v1',
}

const KEY_PLACEHOLDERS: Record<ProviderChoice, string> = {
  none: '',
  'claude-code': '',
  anthropic: 'ANTHROPIC_API_KEY',
  'openai-compatible': 'Optional, for a server that needs a key',
}

interface Form {
  provider: ProviderChoice
  model: string
  endpoint: string
  apiKeyEnv: string
  timeout: string
  maxTokens: string
}

function isProvider(value: string | null): value is ProviderChoice {
  return value !== null && value in PROVIDERS
}

function formOf(config: AiConfig): Form {
  return {
    provider: isProvider(config.provider) ? config.provider : 'none',
    model: config.model ?? '',
    endpoint: config.endpoint ?? '',
    apiKeyEnv: config.api_key_env ?? '',
    timeout: config.timeout === null ? '' : String(config.timeout),
    maxTokens: config.max_tokens === null ? '' : String(config.max_tokens),
  }
}

function numberOrNull(text: string): number | null {
  return text.trim() === '' ? null : Number(text)
}

function fieldsOf(form: Form): AiConfigFields {
  const off = form.provider === 'none'
  const remote = !off && form.provider !== 'claude-code'
  return {
    provider: form.provider,
    model: off ? null : form.model,
    endpoint: remote ? form.endpoint : null,
    api_key_env: remote ? form.apiKeyEnv : null,
    timeout: off ? null : numberOrNull(form.timeout),
    max_tokens: remote ? numberOrNull(form.maxTokens) : null,
  }
}

export function AiPanel() {
  const status = useAiStatus()
  const config = useAiConfig()
  const error = status.error ?? config.error
  if (error) {
    return <ErrorNote message={describeError(error)} />
  }
  if (status.data === undefined || config.data === undefined) {
    return <p className="muted">Loading...</p>
  }
  return (
    <div className="stack">
      <ProviderForm config={config.data} />
      {status.data.configured && <ActiveProvider ai={status.data} />}
    </div>
  )
}

function ProviderForm({ config }: { config: AiConfig }) {
  const id = useId()
  const [form, setForm] = useState(() => formOf(config))
  const [saved, setSaved] = useState(false)
  const save = useSaveAiConfig()
  const update = (change: Partial<Form>) => {
    setForm({ ...form, ...change })
    setSaved(false)
  }
  const remote = form.provider === 'anthropic' || form.provider === 'openai-compatible'
  const file = config.config_file ?? 'config.toml'
  return (
    <form
      className="stack ai-form"
      onSubmit={(event) => {
        event.preventDefault()
        save.mutate(fieldsOf(form), { onSuccess: () => { setSaved(true) } })
      }}
    >
      <label htmlFor={`${id}-provider`}>Provider</label>
      <select id={`${id}-provider`} value={form.provider} onChange={(event) => { update({ provider: event.target.value as ProviderChoice }) }}>
        {Object.entries(PROVIDERS).map(([value, label]) => (
          <option key={value} value={value}>
            {label}
          </option>
        ))}
      </select>
      {form.provider === 'claude-code' && <p className="muted">Runs the claude command signed in on this computer, so no key is needed.</p>}
      {form.provider !== 'none' && (
        <>
          <label htmlFor={`${id}-model`}>Model</label>
          <input id={`${id}-model`} value={form.model} placeholder={MODEL_PLACEHOLDERS[form.provider]} onChange={(event) => { update({ model: event.target.value }) }} />
        </>
      )}
      {remote && (
        <>
          <label htmlFor={`${id}-endpoint`}>Endpoint</label>
          <input id={`${id}-endpoint`} value={form.endpoint} placeholder={ENDPOINT_PLACEHOLDERS[form.provider]} onChange={(event) => { update({ endpoint: event.target.value }) }} />
          <label htmlFor={`${id}-key`}>API key environment variable</label>
          <input id={`${id}-key`} value={form.apiKeyEnv} placeholder={KEY_PLACEHOLDERS[form.provider]} spellCheck={false} onChange={(event) => { update({ apiKeyEnv: event.target.value }) }} />
          <p className="muted">Set the key in the environment bussola runs in. bussola saves only the name of the variable, never the key.</p>
          <label htmlFor={`${id}-max-tokens`}>Answer budget in tokens</label>
          <input id={`${id}-max-tokens`} type="number" min={1} step={1} value={form.maxTokens} placeholder="16000" onChange={(event) => { update({ maxTokens: event.target.value }) }} />
        </>
      )}
      {form.provider !== 'none' && (
        <>
          <label htmlFor={`${id}-timeout`}>Timeout in seconds</label>
          <input id={`${id}-timeout`} type="number" min={1} max={3600} value={form.timeout} placeholder="600" onChange={(event) => { update({ timeout: event.target.value }) }} />
        </>
      )}
      {config.problem && (
        <>
          <ErrorNote message={config.problem} />
          <p className="muted">AI features are off until this is fixed. Saving replaces the AI settings in that file.</p>
        </>
      )}
      <div className="ai-form-actions">
        <button type="submit" className="primary" disabled={save.isPending}>
          {save.isPending ? 'Saving...' : 'Save'}
        </button>
        {saved && <span role="status">Saved</span>}
      </div>
      {save.error && <ErrorNote message={describeError(save.error)} />}
      <p className="muted">
        Saved in <code>{file}</code>, which you can also edit by hand. Saving rewrites the file, so comments in it are not kept.
      </p>
    </form>
  )
}

function ActiveProvider({ ai }: { ai: AiStatus }) {
  const test = useTestAiConnection()
  return (
    <div className="stack">
      <dl className="ai-details">
        <dt>Provider</dt>
        <dd>{ai.label}</dd>
        <dt>Model</dt>
        <dd>{ai.model ?? (ai.provider === 'claude-code' ? 'Default of the claude command' : 'Not set')}</dd>
        {ai.endpoint && (
          <>
            <dt>Endpoint</dt>
            <dd>
              <code>{ai.endpoint}</code>
            </dd>
          </>
        )}
        {ai.api_key_env && (
          <>
            <dt>API key</dt>
            <dd>
              <code>{ai.api_key_env}</code> {ai.api_key_set ? 'is set' : 'is not set'}
            </dd>
          </>
        )}
      </dl>
      {ai.problem && <ErrorNote message={ai.problem} />}
      <button type="button" disabled={test.isPending} onClick={() => { test.mutate() }}>
        {test.isPending ? 'Testing...' : 'Test connection'}
      </button>
      {test.data?.ok && <p role="status">{`${test.data.message} in ${String(test.data.elapsed_ms)} ms.`}</p>}
      {test.data && !test.data.ok && <ErrorNote message={test.data.message} />}
      {test.error && <ErrorNote message={describeError(test.error)} />}
      <p className="muted">Test connection sends a short fixed prompt and no code. Code is sent only when you start an AI action.</p>
    </div>
  )
}
