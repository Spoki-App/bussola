import { useEffect, useRef } from 'react'

import { ApiError, describeError } from './api/client'
import { useOpenPullRequestLink } from './api/pulls'
import { ErrorNote } from './components/Badges'
import { ExternalLink } from './components/ExternalLink'
import { Link } from './Link'
import { navigate, reviewPath } from './navigation'
import { addRepositoryPath } from './review/linkFocus'

const NO_LOCAL_CLONE = 'no_local_clone'

export function OpenPullRequestRoute({ url }: { url: string }) {
  const open = useOpenPullRequestLink()
  const started = useRef(false)

  useEffect(() => {
    if (started.current) {
      return
    }
    started.current = true
    const { pathname, search } = window.location
    open.mutate(url, {
      onSuccess: (review) => { navigate(`${reviewPath(review.id)}${search}`, { replace: true }) },
      onError: (error) => {
        if (error instanceof ApiError && error.code === NO_LOCAL_CLONE) {
          navigate(addRepositoryPath(`${pathname}${search}`), { replace: true })
        }
      },
    })
  }, [open, url])

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
