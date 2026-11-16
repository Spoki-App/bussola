import { useState } from 'react'

import { describeError } from '../api/client'
import { useCreateThread } from '../api/threads'
import type { Thread } from '../api/types'
import { showThread, threadElementId, useLinkedElementId } from '../review/linkFocus'
import { isInline, isOpen, isResolved } from '../review/threadPlacement'
import { readStored, writeStored } from '../settings/storage'
import { ErrorNote } from './Badges'
import { Composer } from './Composer'
import { QualifiedName } from './QualifiedName'
import { Segmented } from './Segmented'
import { ThreadView } from './ThreadView'

interface Props {
  reviewId: number
  threads: Thread[]
}

type Kind = 'all' | 'general' | 'code'

const KINDS: Record<Kind, string> = { all: 'All', general: 'General', code: 'Code' }
const KIND_KEY = 'bussola.conversationFilter'
const RESOLVED_KEY = 'bussola.conversationShowResolved'

function storedKind(): Kind {
  const stored = readStored(KIND_KEY)
  return stored === 'general' || stored === 'code' ? stored : 'all'
}

function inlineLabel(thread: Thread): string {
  const line = thread.anchor?.file_line
  const path = thread.path ?? ''
  const place = line == null ? path : `${path}:${String(line)}`
  return thread.qualified_name ? `${thread.qualified_name} (${place})` : place
}

function inlineSummary(thread: Thread): string {
  const first = thread.comments.find((comment) => !comment.deleted)
  const author = first?.author.name ?? thread.created_by.name
  const text = first?.body.trim().split('\n')[0] ?? ''
  return text ? `${author}: ${text}` : author
}

function Location({ thread }: { thread: Thread }) {
  if (!thread.qualified_name) {
    return <p className="thread-location">{thread.path}</p>
  }
  return (
    <p className="thread-location">
      <QualifiedName module={thread.module} name={thread.qualified_name} />
      {thread.path && <span className="muted">{` in ${thread.path}`}</span>}
    </p>
  )
}

export function ThreadPanel({ reviewId, threads }: Props) {
  const create = useCreateThread(reviewId)
  const [kind, setKind] = useState(storedKind)
  const [showResolved, setShowResolved] = useState(() => readStored(RESOLVED_KEY) === 'true')
  const linkedId = useLinkedElementId()
  const linked = threads.find((thread) => threadElementId(thread.id) === linkedId && !isInline(thread))
  if (linked && !showResolved && isResolved(linked)) {
    setShowResolved(true)
  }
  if (linked && kind !== 'all' && (linked.scope === 'review') !== (kind === 'general')) {
    setKind('all')
  }
  const showGeneral = kind !== 'code'
  const shown = showResolved ? threads : threads.filter((thread) => !isResolved(thread))
  const code = kind === 'general' ? [] : shown
  const general = shown.filter((thread) => thread.scope === 'review')
  const files = code.filter((thread) => thread.scope === 'file')
  const inline = code.filter(isInline)
  const elsewhere = code.filter((thread) => thread.scope === 'unit' && !isInline(thread))
  const resolvedCount = threads.filter(isResolved).length
  const open = threads.filter(isOpen).length

  return (
    <div className="thread-panel">
      <h2>{`Conversation (${String(open)} open)`}</h2>
      <div className="thread-filters">
        <Segmented
          label="Show comments"
          labels={KINDS}
          value={kind}
          onChange={(next) => {
            setKind(next)
            writeStored(KIND_KEY, next)
          }}
        />
        <label>
          <input
            type="checkbox"
            checked={showResolved}
            onChange={(event) => {
              setShowResolved(event.target.checked)
              writeStored(RESOLVED_KEY, String(event.target.checked))
            }}
          />
          {`Show resolved (${String(resolvedCount)})`}
        </label>
      </div>
      {showGeneral && (
        <section>
          <h3>Review</h3>
          {general.map((thread) => (
            <ThreadView key={thread.id} reviewId={reviewId} thread={thread} />
          ))}
          <Composer
            reviewId={reviewId}
            submitLabel="Comment"
            placeholder="Comment on the whole review (Markdown)"
            busy={create.isPending}
            onSubmit={(body, done) => { create.mutate({ scope: 'review', body }, { onSuccess: done }) }}
          />
          {create.error && <ErrorNote message={describeError(create.error)} />}
        </section>
      )}
      {inline.length > 0 && (
        <section>
          <h3>In the code</h3>
          <ul className="thread-jumps">
            {inline.map((thread) => (
              <li key={thread.id}>
                <button type="button" className="link" onClick={() => { showThread(reviewId, thread.id) }}>
                  {inlineLabel(thread)}
                </button>
                <span className="muted">{inlineSummary(thread)}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
      {files.length > 0 && (
        <section>
          <h3>Files</h3>
          {files.map((thread) => (
            <div key={thread.id}>
              <p className="thread-location">{thread.path}</p>
              <ThreadView reviewId={reviewId} thread={thread} />
            </div>
          ))}
        </section>
      )}
      {elsewhere.length > 0 && (
        <section>
          <h3>Outdated or not shown</h3>
          {elsewhere.map((thread) => (
            <div key={thread.id}>
              <Location thread={thread} />
              <ThreadView reviewId={reviewId} thread={thread} showSnippet />
            </div>
          ))}
        </section>
      )}
      {!showGeneral && inline.length + files.length + elsewhere.length === 0 && <p className="muted">No comments on code</p>}
    </div>
  )
}
