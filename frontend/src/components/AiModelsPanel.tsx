import { useId, useState } from 'react'

import { useAiModels, useAiOperations, useAiStatus, useSaveAiOperations } from '../api/ai'
import { describeError } from '../api/client'
import type { AiEffort, AiModel, AiOperation, AiOperationChoice, AiOperationKey, AiOperations, AiStatus } from '../api/types'
import { ErrorNote } from './Badges'

const EFFORTS: Record<AiEffort, string> = { low: 'Low', medium: 'Medium', high: 'High' }

const OPERATION_USES: Record<AiOperationKey, string> = {
  describe: 'Describe on a unit card.',
  impact: 'Rate impact on the whole pull request.',
  review: 'AI review and Review again.',
  chat: 'Questions in the AI chat panel.',
}

interface Row {
  model: string
  effort: AiEffort | ''
}

type Rows = Record<AiOperationKey, Row>

function rowsOf(operations: AiOperation[]): Rows {
  return Object.fromEntries(operations.map((operation) => [operation.key, { model: operation.model ?? '', effort: operation.effort ?? '' }])) as Rows
}

function choicesOf(rows: Rows): Record<AiOperationKey, AiOperationChoice> {
  return Object.fromEntries(
    Object.entries(rows).map(([key, row]) => [key, { model: row.model.trim() || null, effort: row.effort === '' ? null : row.effort }]),
  ) as Record<AiOperationKey, AiOperationChoice>
}

function takesEffort(models: AiModel[], model: string | null): boolean {
  return models.find((listed) => listed.id === model)?.effort !== false
}

export function AiModelsPanel() {
  const status = useAiStatus()
  const operations = useAiOperations()
  const error = status.error ?? operations.error
  if (error) {
    return <ErrorNote message={describeError(error)} />
  }
  if (status.data === undefined || operations.data === undefined) {
    return <p className="muted">Loading...</p>
  }
  return <ModelsForm ai={status.data} operations={operations.data} />
}

function ModelsForm({ ai, operations }: { ai: AiStatus; operations: AiOperations }) {
  const id = useId()
  const [rows, setRows] = useState(() => rowsOf(operations.operations))
  const [saved, setSaved] = useState(false)
  const save = useSaveAiOperations()
  const models = useAiModels()
  const listed = models.data?.models ?? []
  const update = (key: AiOperationKey, change: Partial<Row>) => {
    setRows({ ...rows, [key]: { ...rows[key], ...change } })
    setSaved(false)
  }
  const fallback = ai.model ?? (ai.provider === 'claude-code' ? 'Default of the claude command' : 'Model of the provider')
  return (
    <form
      className="stack ai-form"
      onSubmit={(event) => {
        event.preventDefault()
        save.mutate(choicesOf(rows), { onSuccess: (answer) => { setRows(rowsOf(answer.operations)); setSaved(true) } })
      }}
    >
      <p className="muted">
        Choose a model and an effort for each AI action. Leave the model empty to use the model of the AI provider. A higher effort lets the model think
        more, which costs more and takes longer.
      </p>
      {!ai.configured && <p className="muted">Choose an AI provider first to see the models it offers.</p>}
      {operations.problem && <ErrorNote message={operations.problem} />}
      <datalist id={`${id}-models`}>
        {listed.map((model) => (
          <option key={model.id} value={model.id} />
        ))}
      </datalist>
      {operations.operations.map((operation) => {
        const row = rows[operation.key]
        const effort = takesEffort(listed, row.model.trim() || ai.model)
        return (
          <fieldset key={operation.key} className="stack ai-operation">
            <legend>{operation.title}</legend>
            <p className="muted">{OPERATION_USES[operation.key]}</p>
            <label htmlFor={`${id}-${operation.key}-model`}>{`${operation.title} model`}</label>
            <input
              id={`${id}-${operation.key}-model`}
              list={`${id}-models`}
              value={row.model}
              placeholder={fallback}
              spellCheck={false}
              onChange={(event) => { update(operation.key, { model: event.target.value }) }}
            />
            <label htmlFor={`${id}-${operation.key}-effort`}>{`${operation.title} effort`}</label>
            <select
              id={`${id}-${operation.key}-effort`}
              value={effort ? row.effort : ''}
              disabled={!effort}
              onChange={(event) => { update(operation.key, { effort: event.target.value as AiEffort | '' }) }}
            >
              <option value="">Default of the model</option>
              {Object.entries(EFFORTS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
            {!effort && <p className="muted">This model does not take an effort.</p>}
          </fieldset>
        )
      })}
      {models.data?.problem && <p className="muted">{`The provider did not list its models, so type the model name: ${models.data.problem}`}</p>}
      <div className="ai-form-actions">
        <button type="submit" className="primary" disabled={save.isPending}>
          {save.isPending ? 'Saving...' : 'Save models'}
        </button>
        {saved && <span role="status">Saved</span>}
      </div>
      {save.error && <ErrorNote message={describeError(save.error)} />}
      <p className="muted">
        Saved in the <code>[ai.operations]</code> sections of <code>{operations.config_file ?? 'config.toml'}</code>. A repository cannot change them.
      </p>
    </form>
  )
}
