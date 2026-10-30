import { useState, type SubmitEvent } from 'react'

import { describeError } from '../api/client'
import { useAddRepo } from '../api/hooks'
import { ErrorNote } from './Badges'
import { DirectoryPicker } from './DirectoryPicker'

export function AddRepoForm({ onAdded, filter }: { onAdded: () => void; filter?: string }) {
  const [path, setPath] = useState('')
  const [browsing, setBrowsing] = useState(filter !== undefined)
  const addRepo = useAddRepo()
  const add = (target: string, done: () => void) => {
    addRepo.mutate(target.trim(), {
      onSuccess: () => {
        done()
        onAdded()
      },
    })
  }
  const submit = (event: SubmitEvent) => {
    event.preventDefault()
    add(path, () => { setPath('') })
  }
  const openPicker = () => {
    addRepo.reset()
    setBrowsing(true)
  }
  return (
    <form className="inline-form" onSubmit={submit}>
      <label htmlFor="repo-path">Path</label>
      <input id="repo-path" value={path} onChange={(event) => { setPath(event.target.value) }} placeholder="/path/to/repository" />
      <button type="submit" disabled={!path.trim() || addRepo.isPending}>
        Add
      </button>
      <button type="button" className="primary" onClick={openPicker}>
        Browse...
      </button>
      {!browsing && addRepo.error && <ErrorNote message={describeError(addRepo.error)} />}
      {browsing && (
        <DirectoryPicker
          filter={filter}
          busy={addRepo.isPending}
          error={addRepo.error}
          onSelect={(target) => { add(target, () => { setBrowsing(false) }) }}
          onClose={() => { setBrowsing(false) }}
        />
      )}
    </form>
  )
}
