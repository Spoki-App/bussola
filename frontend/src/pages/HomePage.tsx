import { useState, type SubmitEvent } from 'react'

import { describeError } from '../api/client'
import { useAddRepo, useCreateReview, useRefs, useRepos, useReviews } from '../api/hooks'
import type { Repo } from '../api/types'
import { ErrorNote, ProgressBar } from '../components/Badges'
import { DirectoryPicker } from '../components/DirectoryPicker'
import { Link } from '../Link'
import { navigate } from '../navigation'
import { progressPercent } from '../review/logic'
import { defaultReviewRefs, reviewFormProblem } from '../review/newReview'


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
  const defaults = defaultReviewRefs(refs.data)
  const choice = { head: head ?? defaults.head, base: base ?? defaults.base }
  const problem = reviewFormProblem(refs.data, choice)
  const suggestions = `refs-${String(repoId)}`
  const submit = (event: SubmitEvent) => {
    event.preventDefault()
    create.mutate({ head_ref: choice.head.trim(), base_ref: choice.base.trim() }, { onSuccess: (review) => { navigate(`/reviews/${String(review.id)}`) } })
  }
  return (
    <form className="inline-form" onSubmit={submit}>
      <datalist id={suggestions}>
        {[...refs.data.local, ...refs.data.remote].map((name) => (
          <option key={name} value={name} />
        ))}
      </datalist>
      <RefInput id={`head-${String(repoId)}`} label="Branch" value={choice.head} suggestions={suggestions} onChange={setHead} />
      <RefInput id={`base-${String(repoId)}`} label="against" value={choice.base} suggestions={suggestions} onChange={setBase} />
      <button type="submit" className="primary" disabled={problem !== null || create.isPending}>
        {create.isPending ? 'Creating...' : 'Start review'}
      </button>
      {problem && <p className="form-hint">{problem}</p>}
      {create.error && <ErrorNote message={describeError(create.error)} />}
    </form>
  )
}

interface RefInputProps {
  id: string
  label: string
  value: string
  suggestions: string
  onChange: (value: string) => void
}

function RefInput({ id, label, value, suggestions, onChange }: RefInputProps) {
  return (
    <>
      <label htmlFor={id}>{label}</label>
      <input
        id={id}
        className="ref-input"
        list={suggestions}
        value={value}
        spellCheck={false}
        autoComplete="off"
        placeholder="branch or commit"
        onChange={(event) => { onChange(event.target.value) }}
      />
    </>
  )
}
