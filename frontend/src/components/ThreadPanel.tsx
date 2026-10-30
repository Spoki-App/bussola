import { describeError } from '../api/client'
import { useCreateThread } from '../api/threads'
import type { Thread } from '../api/types'
import { isInline, isOpen } from '../review/threadPlacement'
import { ErrorNote } from './Badges'
import { Composer } from './Composer'
import { QualifiedName } from './QualifiedName'
import { ThreadView } from './ThreadView'

interface Props {
  reviewId: number
  threads: Thread[]
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
  const general = threads.filter((thread) => thread.scope === 'review')
  const files = threads.filter((thread) => thread.scope === 'file')
  const elsewhere = threads.filter((thread) => thread.scope === 'unit' && !isInline(thread))
  const open = threads.filter(isOpen).length

  return (
    <div className="thread-panel">
      <h2>{`Conversation (${String(open)} open)`}</h2>
      <section>
        <h3>Review</h3>
        {general.map((thread) => (
          <ThreadView key={thread.id} reviewId={reviewId} thread={thread} />
        ))}
        <Composer
          submitLabel="Comment"
          placeholder="Comment on the whole review (Markdown)"
          busy={create.isPending}
          onSubmit={(body, done) => { create.mutate({ scope: 'review', body }, { onSuccess: done }) }}
        />
        {create.error && <ErrorNote message={describeError(create.error)} />}
      </section>
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
    </div>
  )
}
