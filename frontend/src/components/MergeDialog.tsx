import { useState } from 'react'

import { describeError } from '../api/client'
import { useMerge, useMergeOptions } from '../api/forge'
import type { CommitText, MergeMethod, MergeOptions, MergeResult } from '../api/types'
import { useModalDialog } from '../hooks/useModalDialog'
import { ErrorNote } from './Badges'
import { Segmented } from './Segmented'

const METHOD_LABELS: Record<MergeMethod, string> = {
  merge: 'Create a merge commit',
  squash: 'Squash and merge',
  rebase: 'Rebase and merge',
}

interface Props {
  reviewId: number
  onMerged: (result: MergeResult) => void
  onClose: () => void
}

export function MergeDialog({ reviewId, onMerged, onClose }: Props) {
  const { ref, close } = useModalDialog()
  const options = useMergeOptions(reviewId)
  const cancel = (
    <div className="composer-actions">
      <button type="button" onClick={close}>
        Cancel
      </button>
    </div>
  )

  return (
    <dialog ref={ref} className="picker merge-dialog" aria-labelledby="merge-dialog-title" onClose={onClose}>
      <header className="picker-header">
        <h2 id="merge-dialog-title">Merge pull request</h2>
      </header>
      {options.data ? (
        <MergeForm reviewId={reviewId} options={options.data} onMerged={onMerged} close={close} />
      ) : (
        <>
          {options.error ? <ErrorNote message={describeError(options.error)} /> : <p className="muted">Checking whether the pull request can be merged...</p>}
          {cancel}
        </>
      )}
    </dialog>
  )
}

export function MergeResultNotice({ result }: { result: MergeResult }) {
  return (
    <div className="notice merge-result">
      <p>{result.branch_deleted ? 'Pull request merged and its branch deleted.' : 'Pull request merged.'}</p>
      {result.branch_error && <ErrorNote message={result.branch_error} />}
    </div>
  )
}

interface FormProps {
  reviewId: number
  options: MergeOptions
  onMerged: (result: MergeResult) => void
  close: () => void
}

function MergeForm({ reviewId, options, onMerged, close }: FormProps) {
  const merge = useMerge(reviewId)
  const [choice, setChoice] = useState<MergeMethod | null>(null)
  const [edits, setEdits] = useState<Partial<Record<MergeMethod, CommitText>>>({})
  const [deleteBranch, setDeleteBranch] = useState(false)
  const method = choice !== null && options.methods.includes(choice) ? choice : options.default_method
  const prefilled = method && options.commit_texts[method]
  const text = (method && edits[method]) ?? prefilled
  const blocked = options.blockers.length > 0
  const disabled = method === null || blocked || merge.isPending || text?.title.trim() === ''
  const edit = (change: Partial<CommitText>) => {
    if (method && text) {
      setEdits({ ...edits, [method]: { ...text, ...change } })
    }
  }
  const submit = () => {
    if (method === null || disabled) {
      return
    }
    const request = { method, head_sha: options.head_sha, title: text?.title ?? '', message: text?.message ?? '', delete_branch: deleteBranch }
    merge.mutateAsync(request).then(
      (result) => {
        onMerged(result)
        close()
      },
      () => undefined,
    )
  }

  return (
    <form
      className="stack"
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
      {method === null ? (
        <ErrorNote message="This repository allows no merge method. Enable one in its settings on GitHub." />
      ) : (
        <Segmented
          label="Merge method"
          labels={Object.fromEntries(options.methods.map((item) => [item, METHOD_LABELS[item]])) as Record<MergeMethod, string>}
          value={method}
          onChange={setChoice}
        />
      )}
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
      {merge.error && <ErrorNote message={describeError(merge.error)} />}
      <div className="composer-actions">
        <button type="button" onClick={close}>
          Cancel
        </button>
        <button type="submit" className="primary" disabled={disabled}>
          {merge.isPending ? 'Merging...' : 'Merge'}
        </button>
      </div>
    </form>
  )
}
