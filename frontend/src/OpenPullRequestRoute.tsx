import { useEffect, useRef } from 'react'

import { describeError } from './api/client'
import { ErrorNote } from './components/Badges'
import { ExternalLink } from './components/ExternalLink'
import { Link } from './Link'
import { useOpenReview } from './openReview'

export function OpenPullRequestRoute({ url }: { url: string }) {
  const { start, visibleError } = useOpenReview()
  const started = useRef(false)

  useEffect(() => {
    if (started.current) {
      return
    }
    started.current = true
    start(url, { search: window.location.search, askToAddRepository: true })
  }, [start, url])

  return (
    <div className="page">
      <h1>Opening pull request</h1>
      <p>
        <ExternalLink href={url}>{url}</ExternalLink>
      </p>
      {visibleError ? (
        <>
          <ErrorNote message={describeError(visibleError)} />
          <Link to="/">Back to repositories</Link>
        </>
      ) : (
        <p className="muted">Finding the local clone and fetching the pull request...</p>
      )}
    </div>
  )
}
