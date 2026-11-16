import { useState } from 'react'

import { useMe } from '../api/hooks'
import { Composer } from './Composer'

interface Props {
  reviewId: number
  busy: boolean
  onSubmit: (body: string, done: () => void) => void
}

export function ReplyBox({ reviewId, busy, onSubmit }: Props) {
  const [open, setOpen] = useState(false)
  const me = useMe()
  if (open) {
    return (
      <Composer
        reviewId={reviewId}
        submitLabel="Reply"
        placeholder="Reply (Markdown)"
        busy={busy}
        autoFocus
        onCancel={() => { setOpen(false) }}
        onSubmit={(body, done) => {
          onSubmit(body, () => {
            done()
            setOpen(false)
          })
        }}
      />
    )
  }
  return (
    <div className="reply-collapsed">
      <Avatar name={me.data?.name ?? ''} />
      <input type="text" readOnly aria-label="Reply" placeholder="Reply..." onFocus={() => { setOpen(true) }} />
    </div>
  )
}

function Avatar({ name }: { name: string }) {
  return (
    <span className="avatar" aria-hidden="true" title={name}>
      {name.trim().charAt(0).toUpperCase()}
    </span>
  )
}
