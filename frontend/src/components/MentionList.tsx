interface Props {
  options: string[]
  active: number
  onPick: (login: string) => void
  onHover: (index: number) => void
}

export function MentionList({ options, active, onPick, onHover }: Props) {
  return (
    <ul className="mention-list" role="listbox" aria-label="People to mention">
      {options.map((login, index) => (
        <li
          key={login}
          role="option"
          aria-selected={index === active}
          className={index === active ? 'active' : ''}
          onMouseDown={(event) => {
            event.preventDefault()
            onPick(login)
          }}
          onMouseEnter={() => { onHover(index) }}
        >
          @{login}
        </li>
      ))}
    </ul>
  )
}
