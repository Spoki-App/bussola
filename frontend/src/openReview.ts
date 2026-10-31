import { useCallback } from 'react'

import { isMissingClone, useOpenPullRequestLink } from './api/pulls'
import { showReview } from './navigation'

export function useOpenReview() {
  const open = useOpenPullRequestLink()
  const { mutate } = open
  const start = useCallback(
    (url: string, search: string, onMissingClone?: () => void) => {
      mutate(url, {
        onSuccess: (review) => { showReview(review.id, search) },
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
