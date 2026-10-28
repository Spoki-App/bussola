import { useState } from 'react'

import { describeError } from '../api/client'
import { useDeleteComment, useEditComment, useReply, useSetThreadStatus } from '../api/threads'
import type { Comment, Thread } from '../api/types'
import { ErrorNote } from './Badges'
import { Composer } from './Composer'
import { Markdown } from './Markdown'

interface Props {
  reviewId: number
  thread: Thread
  showSnippet?: boolean
}

export function ThreadView({ reviewId, thread, showSnippet = false }: Props) {
  const [collapsed, setCollapsed] = useState(thread.status === 'resolved')
  const reply = useReply(reviewId)
  const setStatus = useSetThreadStatus(reviewId)
  const failure = reply.error ?? setStatus.error
  const resolved = thread.status === 'resolved'

  return (
    <div className={`thread${resolved ? ' resolved' : ''}${thread.anchor?.outdated ? ' outdated' : ''}`} data-testid="thread">
      <div className="thread-header">
        <button type="button" className="disclosure" aria-expanded={!collapsed} onClick={() => { setCollapsed(!collapsed) }}>
          {collapsed ? '▸' : '▾'}
        </button>
        <strong>{thread.comments.at(0)?.author.name ?? thread.created_by.name}</strong>
        {resolved && <span className="badge state-approved">Resolved</span>}
        {thread.anchor?.outdated && <span className="badge state-changed">Outdated</span>}
        {thread.line_count > 1 && thread.anchor?.file_line != null && thread.anchor.end_file_line != null && (
          <span className="muted">{`lines ${String(thread.anchor.file_line)}-${String(thread.anchor.end_file_line)}`}</span>
        )}
        <span className="muted">{`${String(thread.comments.length)} comment${thread.comments.length === 1 ? '' : 's'}`}</span>
        <span className="spacer" />
        <button type="button" disabled={setStatus.isPending} onClick={() => { setStatus.mutate({ threadId: thread.id, status: resolved ? 'open' : 'resolved' }) }}>
          {resolved ? 'Reopen' : 'Resolve'}
        </button>
      </div>
      {!collapsed && (
        <>
          {showSnippet && thread.line_text !== null && <Snippet thread={thread} />}
          {thread.comments.map((comment) => (
            <CommentItem key={comment.id} reviewId={reviewId} comment={comment} />
          ))}
          <Composer
            submitLabel="Reply"
            placeholder="Reply (Markdown)"
            busy={reply.isPending}
            onSubmit={(body, done) => { reply.mutate({ threadId: thread.id, body }, { onSuccess: done }) }}
          />
        </>
      )}
      {failure && <ErrorNote message={describeError(failure)} />}
    </div>
  )
}

function Snippet({ thread }: { thread: Thread }) {
  return (
    <pre className="snippet">
      {thread.context_before.map((line, index) => (
        <div key={`b${String(index)}`} className="muted">
          {line || ' '}
        </div>
      ))}
      {(thread.line_text ?? '').split('\n').map((line, index) => (
        <div key={`t${String(index)}`} className="snippet-target">
          {line || ' '}
        </div>
      ))}
      {thread.context_after.map((line, index) => (
        <div key={`a${String(index)}`} className="muted">
          {line || ' '}
        </div>
      ))}
    </pre>
  )
}

function CommentItem({ reviewId, comment }: { reviewId: number; comment: Comment }) {
  const [editing, setEditing] = useState(false)
  const edit = useEditComment(reviewId)
  const remove = useDeleteComment(reviewId)
  if (comment.deleted) {
    return <p className="comment muted">This comment was deleted.</p>
  }
  return (
    <div className="comment">
      <div className="comment-meta">
        <strong>{comment.author.name}</strong>
        <span className="muted">{new Date(comment.created_at).toLocaleString()}</span>
        {comment.edited_at && <span className="muted">(edited)</span>}
        <span className="spacer" />
        {comment.mine && !editing && (
          <>
            <button type="button" className="link" onClick={() => { setEditing(true) }}>
              Edit
            </button>
            <button type="button" className="link" disabled={remove.isPending} onClick={() => { remove.mutate(comment.id) }}>
              Delete
            </button>
          </>
        )}
      </div>
      {editing ? (
        <Composer
          submitLabel="Save"
          initial={comment.body}
          busy={edit.isPending}
          autoFocus
          onCancel={() => { setEditing(false) }}
          onSubmit={(body) => { edit.mutate({ commentId: comment.id, body }, { onSuccess: () => { setEditing(false) } }) }}
        />
      ) : (
        <Markdown text={comment.body} />
      )}
      {(edit.error ?? remove.error) && <ErrorNote message={describeError(edit.error ?? remove.error)} />}
    </div>
  )
}
