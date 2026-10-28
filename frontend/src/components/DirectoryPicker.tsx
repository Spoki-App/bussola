import { useEffect, useRef, useState } from 'react'

import { describeError } from '../api/client'
import { useDirectories } from '../api/hooks'
import { ErrorNote } from './Badges'

interface Props {
  busy: boolean
  error: unknown
  onSelect: (path: string) => void
  onClose: () => void
}

export function DirectoryPicker({ busy, error, onSelect, onClose }: Props) {
  const dialog = useRef<HTMLDialogElement>(null)
  const [path, setPath] = useState<string | undefined>(undefined)
  const listing = useDirectories(path)
  const data = listing.data

  useEffect(() => {
    const element = dialog.current
    if (element && !element.open) {
      element.showModal()
    }
    return () => {
      element?.close()
    }
  }, [])

  const close = () => {
    dialog.current?.close()
  }

  return (
    <dialog ref={dialog} className="picker" aria-labelledby="picker-title" onClose={onClose}>
      <header className="picker-header">
        <h2 id="picker-title">Choose a repository</h2>
        <button type="button" className="link" onClick={close}>
          Close
        </button>
      </header>
      <div className="picker-path">
        <button type="button" disabled={!data?.parent} onClick={() => { setPath(data?.parent ?? undefined) }}>
          Up
        </button>
        <button type="button" disabled={!data || data.path === data.home} onClick={() => { setPath(data?.home) }}>
          Home
        </button>
        <code title={data?.path}>
          <bdi dir="ltr">{data?.path ?? '...'}</bdi>
        </code>
      </div>
      {listing.error && <ErrorNote message={describeError(listing.error)} />}
      {data?.is_repo && (
        <div className="picker-current">
          <span>This folder is a git repository.</span>
          <button type="button" className="primary" disabled={busy} onClick={() => { onSelect(data.path) }}>
            Add this repository
          </button>
        </div>
      )}
      <ul className="picker-list" aria-label="Folders" aria-busy={listing.isFetching}>
        {data?.entries.map((entry) => (
          <li key={entry.path}>
            <button type="button" className="picker-entry" onClick={() => { setPath(entry.path) }}>
              <span className="picker-name">{entry.name}</span>
              {entry.is_repo && <span className="badge kind">git</span>}
              <span className="muted" aria-hidden="true">
                {'›'}
              </span>
            </button>
            {entry.is_repo && (
              <button type="button" disabled={busy} aria-label={`Add ${entry.name}`} onClick={() => { onSelect(entry.path) }}>
                Add
              </button>
            )}
          </li>
        ))}
        {data?.entries.length === 0 && <li className="muted">No folders here.</li>}
      </ul>
      {data?.truncated && <p className="muted">Only the first folders are shown. Paste the path in the form for others.</p>}
      {error ? <ErrorNote message={describeError(error)} /> : null}
    </dialog>
  )
}
