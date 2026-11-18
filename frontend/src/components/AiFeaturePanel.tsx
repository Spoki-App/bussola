import { useId, useState } from 'react'

import { useAiModels, useSaveAiOperation } from '../api/ai'
import { describeError } from '../api/client'
import type { AiEffort, AiOperation, AiOperationKey, AiPrompt, AiProviderName, AiStatus } from '../api/types'
import { AiModelPicker } from './AiModelPicker'
import { EFFORTS, ENDPOINT_PLACEHOLDERS, isRemote, KEY_PLACEHOLDERS, MODEL_DEFAULTS, PROVIDERS, takesEffort } from './aiProviders'
import { ErrorNote } from './Badges'

const USES: Record<AiOperationKey, string> = {
  describe: 'Describe on a unit card: what the description says and how the impact is rated.',
  impact: 'Rate impact on the whole pull request, and the impact the AI review gives each unit: what Low, Medium and High impact mean.',
  review: 'AI review and Review again: what to report, how to anchor and word a finding, and what the summary says. The impact scale comes from Rate impact.',
  chat: 'Questions in the AI chat panel: how to write the answer.',
}

const OWN_PROVIDERS: AiProviderName[] = ['claude-code', 'anthropic', 'openai-compatible']

interface Form {
  provider: AiProviderName | ''
  model: string
  effort: AiEffort | ''
  endpoint: string
  apiKeyEnv: string
  prompt: string
}

function formOf(operation: AiOperation, prompt: AiPrompt): Form {
  return {
    provider: operation.provider ?? '',
    model: operation.model ?? '',
    effort: operation.effort ?? '',
    endpoint: operation.endpoint ?? '',
    apiKeyEnv: operation.api_key_env ?? '',
    prompt: prompt.custom ?? prompt.default,
  }
}

interface Props {
  ai: AiStatus
  operation: AiOperation
  prompt: AiPrompt
}

export function AiFeaturePanel({ ai, operation, prompt }: Props) {
  const id = useId()
  const [form, setForm] = useState(() => formOf(operation, prompt))
  const [saved, setSaved] = useState(false)
  const save = useSaveAiOperation(operation.key)
  const global = ai.configured ? ai.provider : null
  const own = form.provider !== '' && form.provider !== global
  const ownRemote = own && isRemote(form.provider)
  const provider = form.provider === '' ? global : form.provider
  const models = useAiModels(provider, own ? operation.key : undefined)
  const listing = models.data && { ...models.data, problem: models.data.problem === operation.problem ? null : models.data.problem }
  const effort = takesEffort(models.data?.models ?? [], form.model || (own ? null : ai.model))
  const customPrompt = form.prompt.trim() !== prompt.default.trim()
  const update = (change: Partial<Form>) => {
    setForm({ ...form, ...change })
    setSaved(false)
  }
  const fallback = form.provider !== '' && own ? MODEL_DEFAULTS[form.provider] : `Same as General (${ai.model ?? (global === 'claude-code' ? 'default of the claude command' : 'not set')})`
  return (
    <form
      className="stack ai-form"
      onSubmit={(event) => {
        event.preventDefault()
        save.mutate(
          {
            provider: form.provider || null,
            model: form.model || null,
            effort: effort ? form.effort || null : null,
            endpoint: ownRemote ? form.endpoint : null,
            api_key_env: ownRemote ? form.apiKeyEnv : null,
            prompt: form.prompt,
          },
          { onSuccess: () => { setSaved(true) } },
        )
      }}
    >
      {!ai.configured && <p className="muted">AI is off. Choose a provider in General to use {operation.title}.</p>}
      <label htmlFor={`${id}-provider`}>{`${operation.title} provider`}</label>
      <select id={`${id}-provider`} value={form.provider} onChange={(event) => { update({ provider: event.target.value as AiProviderName | '', model: '' }) }}>
        <option value="">{`Same as General${ai.label ? `: ${ai.label}` : ''}`}</option>
        {OWN_PROVIDERS.map((value) => (
          <option key={value} value={value}>
            {PROVIDERS[value]}
          </option>
        ))}
      </select>
      {ownRemote && form.provider !== '' && (
        <>
          <label htmlFor={`${id}-endpoint`}>{`${operation.title} endpoint`}</label>
          <input id={`${id}-endpoint`} value={form.endpoint} placeholder={ENDPOINT_PLACEHOLDERS[form.provider]} onChange={(event) => { update({ endpoint: event.target.value }) }} />
          <label htmlFor={`${id}-key`}>{`${operation.title} API key environment variable`}</label>
          <input id={`${id}-key`} value={form.apiKeyEnv} placeholder={KEY_PLACEHOLDERS[form.provider]} spellCheck={false} onChange={(event) => { update({ apiKeyEnv: event.target.value }) }} />
        </>
      )}
      {operation.problem && <ErrorNote message={operation.problem} />}
      <label htmlFor={`${id}-model`}>{`${operation.title} model`}</label>
      <AiModelPicker id={`${id}-model`} models={listing} value={form.model} fallback={fallback} onChange={(model) => { update({ model }) }} />
      <label htmlFor={`${id}-effort`}>{`${operation.title} effort`}</label>
      <select id={`${id}-effort`} value={effort ? form.effort : ''} disabled={!effort} onChange={(event) => { update({ effort: event.target.value as AiEffort | '' }) }}>
        <option value="">Default of the model</option>
        {Object.entries(EFFORTS).map(([value, label]) => (
          <option key={value} value={value}>
            {label}
          </option>
        ))}
      </select>
      {!effort && (
        <p className="muted">{form.effort === '' ? 'This model does not take an effort.' : 'This model does not take an effort. Save to stop sending the effort saved for it.'}</p>
      )}
      <label htmlFor={`${id}-prompt`}>
        {`${operation.title} prompt`} {customPrompt && <span className="label">Custom</span>}
      </label>
      <p className="muted">{USES[operation.key]}</p>
      <textarea id={`${id}-prompt`} className="ai-prompt" rows={10} value={form.prompt} spellCheck={false} onChange={(event) => { update({ prompt: event.target.value }) }} />
      <div className="ai-form-actions">
        <button type="submit" className="primary" disabled={save.isPending}>
          {save.isPending ? 'Saving...' : 'Save'}
        </button>
        <button type="button" disabled={!customPrompt} onClick={() => { update({ prompt: prompt.default }) }}>
          Reset prompt to default
        </button>
        {saved && <span role="status">Saved</span>}
      </div>
      {save.error && <ErrorNote message={describeError(save.error)} />}
    </form>
  )
}
