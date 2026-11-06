import { useState } from 'react'

import { describeError } from '../api/client'
import { useMerge, useMergeOptions } from '../api/forge'
import type { CommitText, MergeMethod, MergeOptions } from '../api/types'
import { ErrorNote } from './Badges'
import { Segmented } from './Segmented'

const METHOD_LABELS: Record<MergeMethod, string> = {
  merge: 'Create a merge commit',
  squash: 'Squash and merge',
  rebase: 'Rebase and merge',
}

const CONFIRM_LABELS: Record<MergeMethod, string> = {
  merge: 'Confirm merge',
  squash: 'Confirm squash and merge',
  rebase: 'Confirm rebase and merge',
}

export function MergePullRequest({ reviewId }: { reviewId: number }) {
  const options = useMergeOptions(reviewId)
  const merge = useMerge(reviewId)
  const result = merge.data
  if (result) {
    return (
      <div className="notice merge-result">
        <p>{result.branch_deleted ? 'Pull request merged and its branch deleted.' : 'Pull request merged.'}</p>
        {result.branch_error && <ErrorNote message={result.branch_error} />}
      </div>
    )
  }
  if (options.isPending) {
    return <p className="muted">Checking whether the pull request can be merged...</p>
  }
  if (options.error) {
    return <ErrorNote message={describeError(options.error)} />
  }
  return <MergeForm options={options.data} merge={merge} />
}

function MergeForm({ options, merge }: { options: MergeOptions; merge: ReturnType<typeof useMerge> }) {
  const [choice, setChoice] = useState<MergeMethod | null>(null)
  const [edits, setEdits] = useState<Partial<Record<MergeMethod, CommitText>>>({})
  const [deleteBranch, setDeleteBranch] = useState(false)
  const method = choice ?? options.default_method
  if (method === null) {
    return <ErrorNote message="This repository allows no merge method. Enable one in its settings on GitHub." />
  }
  const prefilled = options.commit_texts[method]
  const text = edits[method] ?? prefilled
  const blocked = options.blockers.length > 0
  const edit = (change: Partial<CommitText>) => {
    if (text) {
      setEdits({ ...edits, [method]: { ...text, ...change } })
    }
  }
  const submit = () => {
    const request = { method, head_sha: options.head_sha, title: text?.title ?? '', message: text?.message ?? '', delete_branch: deleteBranch }
    merge.mutate(request)
  }

  return (
    <form
      className="stack merge-pull-request"
      onSubmit={(event) => {
        event.preventDefault()
        submit()
      }}
    >
      {blocked && (
        <div className="notice warning">
          <p>Merging is blocked:</p>
          <ul>
            {options.blockers.map((blocker) => (
              <li key={blocker}>{blocker}</li>
            ))}
          </ul>
        </div>
      )}
      <Segmented
        label="Merge method"
        labels={Object.fromEntries(options.methods.map((item) => [item, METHOD_LABELS[item]])) as Record<MergeMethod, string>}
        value={method}
        onChange={setChoice}
      />
      {text && (
        <>
          <label>
            Commit title
            <input value={text.title} onChange={(event) => { edit({ title: event.target.value }) }} />
          </label>
          <label>
            Commit message
            <textarea rows={6} value={text.message} onChange={(event) => { edit({ message: event.target.value }) }} />
          </label>
        </>
      )}
      {options.branch_deletion === 'optional' && (
        <label className="checkbox">
          <input type="checkbox" checked={deleteBranch} onChange={(event) => { setDeleteBranch(event.target.checked) }} />
          Delete the branch after merging
        </label>
      )}
      {options.branch_deletion === 'automatic' && <p className="muted">GitHub deletes the branch after merging, as set in the repository settings.</p>}
      <button type="submit" className="primary" disabled={blocked || merge.isPending || text?.title.trim() === ''}>
        {merge.isPending ? 'Merging...' : CONFIRM_LABELS[method]}
      </button>
      {merge.error && <ErrorNote message={describeError(merge.error)} />}
    </form>
  )
}
