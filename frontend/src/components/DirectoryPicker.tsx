import { useState } from 'react'

import { describeError } from '../api/client'
import { useDirectories, useRepositoryScan } from '../api/hooks'
import { displayPath, filterRepositories } from '../review/repositorySearch'
import { ErrorNote } from './Badges'
import { useModalDialog } from '../hooks/useModalDialog'
import { Segmented } from './Segmented'

interface Props {
  busy: boolean
  error: unknown
  onSelect: (path: string) => void
  onClose: () => void
}

type PickerTab = 'found' | 'browse'

const TAB_LABELS: Record<PickerTab, string> = { found: 'Found in your home folder', browse: 'Browse folders' }

export function DirectoryPicker({ busy, error, onSelect, onClose }: Props) {
  const { ref: dialog, close } = useModalDialog()
  const [tab, setTab] = useState<PickerTab>('found')

  return (
    <dialog ref={dialog} className="picker" aria-labelledby="picker-title" onClose={onClose}>
      <header className="picker-header">
        <h2 id="picker-title">Add a repository</h2>
        <button type="button" className="link" onClick={close}>
          Close
        </button>
      </header>
      <Segmented label="How to find the repository" labels={TAB_LABELS} value={tab} onChange={setTab} />
      {tab === 'found' ? <FoundRepositories busy={busy} onSelect={onSelect} /> : <FolderBrowser busy={busy} onSelect={onSelect} />}
      {error ? <ErrorNote message={describeError(error)} /> : null}
    </dialog>
  )
}

function FoundRepositories({ busy, onSelect }: { busy: boolean; onSelect: (path: string) => void }) {
  const [query, setQuery] = useState('')
  const scan = useRepositoryScan()
  const home = useDirectories(undefined).data?.home ?? ''
  const matches = filterRepositories(scan.data?.repositories ?? [], query)

  return (
    <>
      <div className="picker-path">
        <input
          className="picker-filter"
          aria-label="Filter repositories"
          placeholder="Filter by name or path"
          value={query}
          autoFocus
          onChange={(event) => { setQuery(event.target.value) }}
        />
        <button type="button" disabled={scan.isFetching} onClick={() => { void scan.refetch() }}>
          Scan again
        </button>
      </div>
      {scan.error && <ErrorNote message={describeError(scan.error)} />}
      <ul className="picker-list" aria-label="Repositories found" aria-busy={scan.isFetching}>
        {scan.isPending && <li className="muted">Looking for git repositories in your home folder...</li>}
        {matches.map((repository) => (
          <li key={repository.path}>
            <div className="picker-entry static">
              <span className="picker-name">
                <strong>{repository.name}</strong>
                <span className="picker-detail muted">
                  <bdi dir="ltr">{displayPath(repository.path, home)}</bdi>
                </span>
              </span>
            </div>
            {repository.registered ? (
              <span className="muted picker-added">Added</span>
            ) : (
              <button type="button" disabled={busy} aria-label={`Add ${repository.name}`} onClick={() => { onSelect(repository.path) }}>
                Add
              </button>
            )}
          </li>
        ))}
        {scan.data && matches.length === 0 && (
          <li className="muted">{query ? 'No repository matches the filter.' : 'No git repositories found. Try Browse folders.'}</li>
        )}
      </ul>
      {scan.data?.truncated && <p className="muted">The search stopped early. If a repository is missing, use Browse folders.</p>}
    </>
  )
}

function FolderBrowser({ busy, onSelect }: { busy: boolean; onSelect: (path: string) => void }) {
  const [path, setPath] = useState<string | undefined>(undefined)
  const listing = useDirectories(path)
  const data = listing.data

  return (
    <>
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
    </>
  )
}
