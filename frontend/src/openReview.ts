import { useCallback } from 'react'

import { isMissingClone, useOpenPullRequestLink } from './api/pulls'
import { navigate, showReview } from './navigation'
import { addRepositoryPath, pullRequestTargetFromUrl } from './review/pullRequestLink'

export interface OpenReviewOptions {
  search?: string
  replace?: boolean
  askToAddRepository?: boolean
  onOpened?: () => void
}

export function useOpenReview() {
  const open = useOpenPullRequestLink()
  const { mutate } = open
  const start = useCallback(
    (url: string, { search = '', replace = true, askToAddRepository = false, onOpened }: OpenReviewOptions = {}) => {
      mutate(url, {
        onSuccess: (review) => {
          onOpened?.()
          showReview(review.id, search, replace)
        },
        onError: (error) => {
          if (askToAddRepository && isMissingClone(error)) {
            onOpened?.()
            navigate(addRepositoryPath(`${pullRequestTargetFromUrl(url).pathname}${search}`), { replace })
          }
        },
      })
    },
    [mutate],
  )
  const visibleError = open.error && !isMissingClone(open.error) ? open.error : null
  return { open, start, visibleError }
}
