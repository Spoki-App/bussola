import type { FileGroup } from '../review/logic'

interface Props {
  groups: FileGroup[]
  onSelect: (path: string) => void
}

function splitPath(path: string): [string, string] {
  const slash = path.lastIndexOf('/')
  return slash < 0 ? ['', path] : [path.slice(0, slash + 1), path.slice(slash + 1)]
}

export function FileTree({ groups, onSelect }: Props) {
  if (groups.length === 0) {
    return <p className="muted">No files.</p>
  }
  return (
    <nav aria-label="Changed files">
      <ul className="file-tree">
        {groups.map((group) => {
          const [directory, name] = splitPath(group.path)
          return (
            <li key={group.path} className={group.complete ? 'complete' : ''}>
              <button type="button" onClick={() => { onSelect(group.path) }} title={group.path}>
                <span className="file-dir">
                  <bdi dir="ltr">{directory}</bdi>
                </span>
                <span className="file-name">{name}</span>
                {group.complete ? <span className="check" aria-label="All approved">{'✓'}</span> : <span className="count">{group.todo}</span>}
              </button>
            </li>
          )
        })}
      </ul>
    </nav>
  )
}
