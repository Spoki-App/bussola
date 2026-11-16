import { useEffect, useRef, useState } from 'react'

import { useMe } from '../api/hooks'
import { Composer } from './Composer'

interface Props {
  reviewId: number
  busy: boolean
  onSubmit: (body: string, done: () => void) => void
}

const EDITOR = 'textarea:not([hidden]), [contenteditable="true"]'

export function ReplyBox({ reviewId, busy, onSubmit }: Props) {
  const [open, setOpen] = useState(false)
  const [started, setStarted] = useState(false)
  const box = useRef<HTMLDivElement>(null)
  const me = useMe()
  useEffect(() => {
    if (open) {
      box.current?.querySelector<HTMLElement>(EDITOR)?.focus()
    }
  }, [open])
  return (
    <>
      {!open && (
        <div className="reply-collapsed">
          <Avatar name={me.data?.name ?? ''} />
          <input
            type="text"
            readOnly
            aria-label="Reply"
            placeholder="Reply..."
            onFocus={() => {
              setStarted(true)
              setOpen(true)
            }}
          />
        </div>
      )}
      {started && (
        <div ref={box} hidden={!open}>
          <Composer
            reviewId={reviewId}
            submitLabel="Reply"
            placeholder="Reply (Markdown)"
            busy={busy}
            onCancel={() => { setOpen(false) }}
            onSubmit={(body, done) => {
              onSubmit(body, () => {
                done()
                setOpen(false)
                setStarted(false)
              })
            }}
          />
        </div>
      )}
    </>
  )
}

function Avatar({ name }: { name: string }) {
  return (
    <span className="avatar" aria-hidden="true" title={name}>
      {name.trim().charAt(0).toUpperCase()}
    </span>
  )
}
