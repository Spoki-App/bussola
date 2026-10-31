import { useState, type SubmitEvent } from 'react'

import { describeError } from '../api/client'
import { useCreateReview, useRefs, useRepos, useReviews } from '../api/hooks'
import { isMissingClone, useOpenPullRequestLink } from '../api/pulls'
import type { Repo } from '../api/types'
import { AddRepoForm } from '../components/AddRepoForm'
import { CourseStrip, ErrorNote } from '../components/Badges'
import { CommentCount } from '../components/CommentCount'
import { PullRequestsPanel } from '../components/PullRequestsPanel'
import { ReviewTitle } from '../components/ReviewTitle'
import { Link } from '../Link'
import { navigate, reviewPath, useSearch } from '../navigation'
import { addRepositoryRequestFromSearch, type AddRepositoryRequest } from '../review/pullRequestLink'
import { progressPercent } from '../review/logic'
import { REVIEW_FILTER_LABELS, loadReviewFilter, matchesReviewFilter, saveReviewFilter, type ReviewFilter } from '../review/reviewFilter'
import { defaultReviewRefs, reviewFormProblem } from '../review/newReview'
import { Segmented } from '../components/Segmented'
import { plural } from '../review/text'


export function HomePage() {
  const repos = useRepos()
  const addRequest = addRepositoryRequestFromSearch(useSearch())
  const [filter, setFilter] = useState<ReviewFilter>(loadReviewFilter)
  const choose = (option: ReviewFilter) => {
    setFilter(option)
    saveReviewFilter(option)
  }
  return (
    <div className="page">
      <div className="home-header">
        <h1>Repositories</h1>
        <Segmented label="Show reviews" labels={REVIEW_FILTER_LABELS} value={filter} onChange={choose} />
      </div>
      {addRequest && <AddRepositoryPrompt request={addRequest} />}
      {repos.error && <ErrorNote message={describeError(repos.error)} />}
      {repos.data?.length === 0 && <p className="muted">No repositories yet. Add one from Settings (top right), or run `bussola serve` inside a repository.</p>}
      {repos.data?.map((repo) => <RepoSection key={repo.id} repo={repo} filter={filter} />)}
    </div>
  )
}

function AddRepositoryPrompt({ request }: { request: AddRepositoryRequest }) {
  const name = request.repository.slice(request.repository.indexOf('/') + 1)
  const open = useOpenPullRequestLink()
  const openPullRequest = () => {
    open.mutate(request.url, { onSuccess: (review) => { navigate(`${reviewPath(review.id)}${request.search}`, { replace: true }) } })
  }
  return (
    <section className="repo" aria-labelledby="add-repository-title">
      <h2 id="add-repository-title">{`Add ${request.repository}`}</h2>
      <p className="muted">
        {`No local clone of github.com/${request.repository} was found. Clone it if you have not yet (`}
        <code>{`git clone https://github.com/${request.repository}.git`}</code>
        {'), then add its folder here. The pull request opens once it is added.'}
      </p>
      <AddRepoForm filter={name} onAdded={openPullRequest} />
      {open.isPending && <p className="muted">Opening the pull request...</p>}
      {open.error && (
        <ErrorNote
          message={isMissingClone(open.error) ? `The folder you added is not a clone of github.com/${request.repository}. Add the folder of a clone of it.` : describeError(open.error)}
        />
      )}
    </section>
  )
}

function RepoSection({ repo, filter }: { repo: Repo; filter: ReviewFilter }) {
  const reviews = useReviews(repo.id)
  const all = reviews.data ?? []
  const shown = all.filter((review) => matchesReviewFilter(review, filter))
  const hidden = all.length - shown.length
  const [creating, setCreating] = useState(false)
  const [showPulls, setShowPulls] = useState(false)
  return (
    <section className="repo">
      <div className="repo-header">
        <h2>{repo.name}</h2>
        <span className="repo-path">{repo.path}</span>
        <span className="spacer" />
        {!repo.missing && (
          <>
            <button type="button" aria-expanded={showPulls} onClick={() => { setShowPulls(!showPulls) }}>
              Pull requests
            </button>
            <button type="button" aria-expanded={creating} onClick={() => { setCreating(!creating) }}>
              New review
            </button>
          </>
        )}
      </div>
      {repo.missing && <ErrorNote message="This repository is no longer at this path. Add it again from its new location; its reviews will follow it." />}
      {showPulls && <PullRequestsPanel repoId={repo.id} />}
      {creating && <NewReviewForm repoId={repo.id} />}
      {reviews.error && <ErrorNote message={describeError(reviews.error)} />}
      <ul className="review-list">
        {shown.map((review) => (
          <li key={review.id}>
            <Link to={reviewPath(review.id)} className="review-link">
              <ReviewTitle review={review} />
            </Link>
            <CourseStrip counts={review.counts} percent={progressPercent(review)} label={`Progress of ${review.head_ref}`} />
            <span className="review-count">
              <strong>{review.approved}</strong>
              {`/${String(review.total)}`}
            </span>
            <span className="muted review-todo">{review.total === review.approved ? 'done' : `${String(review.total - review.approved)} to review`}</span>
            <CommentCount total={review.total_threads} unresolved={review.open_threads} totalLabel="thread" />
          </li>
        ))}
      </ul>
      {hidden > 0 && <p className="muted hidden-reviews">{`${plural(hidden, 'review')} hidden by the filter.`}</p>}
    </section>
  )
}

function NewReviewForm({ repoId }: { repoId: number }) {
  const refs = useRefs(repoId)
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
    create.mutate({ head_ref: choice.head.trim(), base_ref: choice.base.trim() }, { onSuccess: (review) => { navigate(reviewPath(review.id)) } })
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
