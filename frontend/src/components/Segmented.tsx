interface Props<T extends string> {
  label: string
  labels: Record<T, string>
  value: T | undefined
  onChange: (value: T) => void
}

export function Segmented<T extends string>({ label, labels, value, onChange }: Props<T>) {
  return (
    <div className="segmented" role="tablist" aria-label={label}>
      {(Object.keys(labels) as T[]).map((option) => (
        <button key={option} type="button" role="tab" aria-selected={value === option} className={value === option ? 'active' : ''} onClick={() => { onChange(option) }}>
          {labels[option]}
        </button>
      ))}
    </div>
  )
}
