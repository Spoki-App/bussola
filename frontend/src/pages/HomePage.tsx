import { useState, type SubmitEvent } from 'react'

import { describeError } from '../api/client'
import { useAddRepo, useCreateReview, useRefs, useRepos, useReviews } from '../api/hooks'
import type { Refs, Repo } from '../api/types'
import { ErrorNote, ProgressBar } from '../components/Badges'
import { DirectoryPicker } from '../components/DirectoryPicker'
import { Link } from '../Link'
import { navigate } from '../navigation'
import { progressPercent } from '../review/logic'

const BASE_FALLBACKS = ['develop', 'main', 'master']

export function HomePage() {
  const repos = useRepos()
  return (
    <div className="page">
      <h1>Repositories</h1>
      <AddRepoForm />
      {repos.error && <ErrorNote message={describeError(repos.error)} />}
      {repos.data?.length === 0 && <p className="muted">No repositories yet. Add one with Browse, or run `rtool serve` inside a repository.</p>}
      {repos.data?.map((repo) => <RepoSection key={repo.id} repo={repo} />)}
    </div>
  )
}

function AddRepoForm() {
  const [path, setPath] = useState('')
  const [browsing, setBrowsing] = useState(false)
  const addRepo = useAddRepo()
  const add = (target: string, done: () => void) => {
    addRepo.mutate(target.trim(), { onSuccess: done })
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
      <label htmlFor="repo-path">Add repository</label>
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
          busy={addRepo.isPending}
          error={addRepo.error}
          onSelect={(target) => { add(target, () => { setBrowsing(false) }) }}
          onClose={() => { setBrowsing(false) }}
        />
      )}
    </form>
  )
}

function RepoSection({ repo }: { repo: Repo }) {
  const reviews = useReviews(repo.id)
  const [creating, setCreating] = useState(false)
  return (
    <section className="repo">
      <div className="repo-header">
        <h2>{repo.name}</h2>
        <span className="muted">{repo.path}</span>
        <span className="spacer" />
        {!repo.missing && (
          <button type="button" onClick={() => { setCreating(!creating) }}>
            New review
          </button>
        )}
      </div>
      {repo.missing && <ErrorNote message="This repository is no longer at this path. Add it again from its new location; its reviews will follow it." />}
      {creating && <NewReviewForm repoId={repo.id} />}
      {reviews.error && <ErrorNote message={describeError(reviews.error)} />}
      <ul className="review-list">
        {reviews.data?.map((review) => (
          <li key={review.id}>
            <Link to={`/reviews/${String(review.id)}`} className="review-link">
              <code>{review.head_ref}</code> <span className="muted">into</span> <code>{review.base_ref}</code>
            </Link>
            <ProgressBar percent={progressPercent(review)} label={`Progress of ${review.head_ref}`} />
            <span className="muted">{`${String(review.approved)}/${String(review.total)} approved`}</span>
            <span className="muted">{`${String(review.total - review.approved)} to review`}</span>
            {review.open_threads > 0 && <span className="muted">{`${String(review.open_threads)} open thread${review.open_threads === 1 ? '' : 's'}`}</span>}
          </li>
        ))}
      </ul>
    </section>
  )
}

function defaultBase(refs: Refs): string {
  return refs.default_base ?? BASE_FALLBACKS.find((name) => refs.local.includes(name)) ?? refs.local.at(0) ?? ''
}

function NewReviewForm({ repoId }: { repoId: number }) {
  const refs = useRefs(repoId, true)
  const create = useCreateReview(repoId)
  const [head, setHead] = useState<string | null>(null)
  const [base, setBase] = useState<string | null>(null)
  if (refs.isPending) {
    return <p className="muted">Loading branches...</p>
  }
  if (refs.error) {
    return <ErrorNote message={describeError(refs.error)} />
  }
  const options = [...refs.data.local, ...refs.data.remote]
  const chosenBase = base ?? defaultBase(refs.data)
  const chosenHead = head ?? refs.data.local.find((name) => name !== chosenBase) ?? ''
  const submit = (event: SubmitEvent) => {
    event.preventDefault()
    create.mutate({ head_ref: chosenHead, base_ref: chosenBase }, { onSuccess: (review) => { navigate(`/reviews/${String(review.id)}`) } })
  }
  return (
    <form className="inline-form" onSubmit={submit}>
      <BranchSelect id={`head-${String(repoId)}`} label="Branch" value={chosenHead} refs={refs.data} onChange={setHead} />
      <BranchSelect id={`base-${String(repoId)}`} label="against" value={chosenBase} refs={refs.data} onChange={setBase} />
      <button type="submit" className="primary" disabled={!chosenHead || !chosenBase || create.isPending || !options.includes(chosenHead)}>
        {create.isPending ? 'Creating...' : 'Start review'}
      </button>
      {create.error && <ErrorNote message={describeError(create.error)} />}
    </form>
  )
}

function BranchSelect({ id, label, value, refs, onChange }: { id: string; label: string; value: string; refs: Refs; onChange: (value: string) => void }) {
  return (
    <>
      <label htmlFor={id}>{label}</label>
      <select id={id} value={value} onChange={(event) => { onChange(event.target.value) }}>
        <optgroup label="Local">
          {refs.local.map((name) => (
            <option key={name}>{name}</option>
          ))}
        </optgroup>
        <optgroup label="Remote">
          {refs.remote.map((name) => (
            <option key={name}>{name}</option>
          ))}
        </optgroup>
      </select>
    </>
  )
}
