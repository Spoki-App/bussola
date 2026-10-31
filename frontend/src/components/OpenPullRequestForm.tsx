import { useState, type SubmitEvent } from 'react'

import { describeError } from '../api/client'
import { isMissingClone } from '../api/pulls'
import { navigate } from '../navigation'
import { useOpenReview } from '../openReview'
import { addRepositoryPath, isPullRequestUrl, pullRequestTargetFromUrl } from '../review/pullRequestLink'
import { ErrorNote } from './Badges'

export function OpenPullRequestForm({ onOpened }: { onOpened: () => void }) {
  const [url, setUrl] = useState('')
  const { open, start } = useOpenReview()
  const submit = (event: SubmitEvent) => {
    event.preventDefault()
    const target = pullRequestTargetFromUrl(url)
    start(target.url, {
      search: target.search,
      replace: false,
      onOpened,
      onMissingClone: () => {
        onOpened()
        navigate(addRepositoryPath(`${target.pathname}${target.search}`))
      },
    })
  }
  return (
    <form className="inline-form" onSubmit={submit}>
      <label htmlFor="pull-request-url">GitHub link</label>
      <input
        id="pull-request-url"
        value={url}
        onChange={(event) => { setUrl(event.target.value) }}
        placeholder="https://github.com/owner/repository/pull/123"
        title="Paste a GitHub pull request link. bussola finds your local clone of that repository (adding it if it is under your home folder) and opens the pull request review."
      />
      <button type="submit" className="primary" disabled={!isPullRequestUrl(url) || open.isPending}>
        {open.isPending ? 'Opening...' : 'Open'}
      </button>
      {open.error && !isMissingClone(open.error) && <ErrorNote message={describeError(open.error)} />}
    </form>
  )
}
