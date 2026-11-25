import { useEffect, useEffectEvent } from 'react'

import type { Thread } from '../api/types'
import { targetsThread, useLinkedTarget } from '../review/linkFocus'
import { plural } from '../review/text'

interface Props {
  threads: Thread[]
  expanded: boolean
  onShow: (shown: boolean) => void
}

export function ResolvedThreadsMarker({ threads, expanded, onShow }: Props) {
  const target = useLinkedTarget()
  const linked = threads.some((thread) => targetsThread(target, thread))
  const reveal = useEffectEvent(() => { onShow(true) })
  useEffect(() => {
    if (linked) {
      reveal()
    }
  }, [linked])
  const label = plural(threads.length, 'resolved thread')
  return (
    <button
      type="button"
      className="resolved-marker"
      aria-label={label}
      aria-expanded={expanded}
      title={label}
      onMouseDown={(event) => { event.stopPropagation() }}
      onClick={() => { onShow(!expanded) }}
    >
      <svg className="resolved-marker-icon" viewBox="0 0 16 16" aria-hidden="true">
        <path d="M2.5 3h11v7.5h-6L4.5 13v-2.5h-2z" />
        <path d="M5.5 6.8l1.7 1.7 3.3-3.3" />
      </svg>
      {threads.length > 1 && <span className="resolved-marker-count">{threads.length}</span>}
    </button>
  )
}
