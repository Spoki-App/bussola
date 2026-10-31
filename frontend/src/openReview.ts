import { useCallback } from 'react'

import { isMissingClone, useOpenPullRequestLink } from './api/pulls'
import { showReview } from './navigation'

export interface OpenReviewOptions {
  search?: string
  replace?: boolean
  onOpened?: () => void
  onMissingClone?: () => void
}

export function useOpenReview() {
  const open = useOpenPullRequestLink()
  const { mutate } = open
  const start = useCallback(
    (url: string, { search = '', replace = true, onOpened, onMissingClone }: OpenReviewOptions = {}) => {
      mutate(url, {
        onSuccess: (review) => {
          onOpened?.()
          showReview(review.id, search, replace)
        },
        onError: (error) => {
          if (isMissingClone(error)) {
            onMissingClone?.()
          }
        },
      })
    },
    [mutate],
  )
  return { open, start }
}
