import { useState } from 'react'

import { describeError } from '../api/client'
import { useCreateThread } from '../api/threads'
import { ErrorNote } from './Badges'
import { Composer } from './Composer'

export function FileCommentButton({ reviewId, path }: { reviewId: number; path: string }) {
  const [open, setOpen] = useState(false)
  const create = useCreateThread(reviewId)
  if (!open) {
    return (
      <button type="button" onClick={() => { setOpen(true) }}>
        Comment on file
      </button>
    )
  }
  return (
    <div className="file-composer">
      <Composer
        submitLabel="Comment"
        placeholder={`Comment on ${path} (Markdown)`}
        busy={create.isPending}
        autoFocus
        onCancel={() => { setOpen(false) }}
        onSubmit={(body) => { create.mutate({ scope: 'file', path, body }, { onSuccess: () => { setOpen(false) } }) }}
      />
      {create.error && <ErrorNote message={describeError(create.error)} />}
    </div>
  )
}
