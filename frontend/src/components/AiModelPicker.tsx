import type { AiModels } from '../api/types'

interface Props {
  id: string
  models: AiModels | undefined
  value: string
  fallback: string
  onChange: (model: string) => void
}

export function AiModelPicker({ id, models, value, fallback, onChange }: Props) {
  const listed = models?.models.map((model) => model.id) ?? []
  if (listed.length === 0) {
    return (
      <>
        <input id={id} value={value} placeholder={fallback} spellCheck={false} onChange={(event) => { onChange(event.target.value) }} />
        {models?.problem && <p className="muted">{`The provider did not list its models, so type the model name: ${models.problem}`}</p>}
      </>
    )
  }
  return (
    <select id={id} value={value} onChange={(event) => { onChange(event.target.value) }}>
      <option value="">{fallback}</option>
      {value !== '' && !listed.includes(value) && <option value={value}>{`${value} (not listed)`}</option>}
      {listed.map((model) => (
        <option key={model} value={model}>
          {model}
        </option>
      ))}
    </select>
  )
}
