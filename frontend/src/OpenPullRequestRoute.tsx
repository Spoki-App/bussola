import { useEffect, useRef } from 'react'

import { describeError } from './api/client'
import { ErrorNote } from './components/Badges'
import { ExternalLink } from './components/ExternalLink'
import { Link } from './Link'
import { navigate } from './navigation'
import { useOpenReview } from './openReview'
import { addRepositoryPath } from './review/pullRequestLink'

export function OpenPullRequestRoute({ url }: { url: string }) {
  const { open, start } = useOpenReview()
  const started = useRef(false)

  useEffect(() => {
    if (started.current) {
      return
    }
    started.current = true
    const { pathname, search } = window.location
    start(url, { search, onMissingClone: () => { navigate(addRepositoryPath(`${pathname}${search}`), { replace: true }) } })
  }, [start, url])

  return (
    <div className="page">
      <h1>Opening pull request</h1>
      <p>
        <ExternalLink href={url}>{url}</ExternalLink>
      </p>
      {open.error ? (
        <>
          <ErrorNote message={describeError(open.error)} />
          <Link to="/">Back to repositories</Link>
        </>
      ) : (
        <p className="muted">Finding the local clone and fetching the pull request...</p>
      )}
    </div>
  )
}
