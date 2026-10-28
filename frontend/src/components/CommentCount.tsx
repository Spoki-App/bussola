interface Props {
  total: number
  unresolved: number
  totalLabel: string
}

function plural(count: number, word: string): string {
  return `${String(count)} ${word}${count === 1 ? '' : 's'}`
}

export function CommentCount({ total, unresolved, totalLabel }: Props) {
  if (total === 0) {
    return <span className="comment-count empty" />
  }
  const label = unresolved > 0 ? `${plural(total, totalLabel)}, ${String(unresolved)} unresolved` : plural(total, totalLabel)
  return (
    <span className="comment-count" title={label} aria-label={label}>
      <svg viewBox="0 0 16 16" width="16" height="16" aria-hidden="true" focusable="false">
        <path
          fill="currentColor"
          d="M1 2.75C1 1.78 1.78 1 2.75 1h10.5c.97 0 1.75.78 1.75 1.75v7.5A1.75 1.75 0 0 1 13.25 12H9.06l-2.57 2.57A1.46 1.46 0 0 1 4 13.54V12H2.75A1.75 1.75 0 0 1 1 10.25Zm1.75-.25a.25.25 0 0 0-.25.25v7.5c0 .14.11.25.25.25h2a.75.75 0 0 1 .75.75v2.19l2.72-2.72a.75.75 0 0 1 .53-.22h4.5a.25.25 0 0 0 .25-.25v-7.5a.25.25 0 0 0-.25-.25Z"
        />
      </svg>
      <span aria-hidden="true">{total}</span>
      {unresolved > 0 && (
        <span className="unresolved" aria-hidden="true">
          {`${String(unresolved)} unresolved`}
        </span>
      )}
    </span>
  )
}
