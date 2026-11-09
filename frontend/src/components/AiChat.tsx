import { useEffect, useRef, useState, type KeyboardEvent } from 'react'

import { newCallId, useAiStatus, useCancelAiCall } from '../api/ai'
import { useAiChat, useClearAiChat, usePendingAiChat, useSendAiChat } from '../api/aiChat'
import { describeError } from '../api/client'
import type { AiChatMessage } from '../api/types'
import type { CodeTarget } from '../hooks/useCodeNavigation'
import type { LineLink } from '../markdown/lineLinks'
import { snippetPlace, type ChatSnippetDraft } from '../review/askAi'
import { showThread } from '../review/linkFocus'
import { plural } from '../review/text'
import { AiActionButton } from './AiActionButton'
import { Findings, Lookups } from './AiReviewDetails'
import { ErrorNote } from './Badges'
import { Markdown } from './Markdown'
import { Spinner } from './Spinner'

interface Props {
  reviewId: number
  repoId: number
  snippets: ChatSnippetDraft[]
  onSnippetsChange: (snippets: ChatSnippetDraft[]) => void
  onShowLine?: (target: CodeTarget) => void
}

interface QuotedCode {
  place: string
  code?: string
}

const EMPTY_HINT =
  'Ask anything about this pull request. The AI sees its description and changed units, and can look up definitions, usages and files like during the AI review. To ask about specific code, click or drag over line numbers and choose Ask AI.'

function snippetKey(snippet: ChatSnippetDraft): string {
  const { unit_id, side, line_offset, line_count } = snippet.range
  return `${String(unit_id)}:${side}:${String(line_offset)}:${String(line_count)}`
}

export function AiChat({ reviewId, repoId, snippets, onSnippetsChange, onShowLine }: Props) {
  const ai = useAiStatus(repoId)
  const chat = useAiChat(reviewId)
  const send = useSendAiChat(reviewId)
  const pending = usePendingAiChat(reviewId)
  const clear = useClearAiChat(reviewId)
  const cancelCall = useCancelAiCall()
  const [message, setMessage] = useState('')
  const sendButton = useRef<HTMLButtonElement>(null)
  const end = useRef<HTMLDivElement>(null)
  const messages = chat.data ?? []
  const asking = pending.at(0)
  const turnedOff = ai.data !== undefined && !ai.data.configured && ai.data.problem === null

  useEffect(() => {
    end.current?.scrollIntoView({ block: 'nearest' })
  }, [messages.length, asking])

  const run = (target: string) => {
    const text = message.trim()
    if (!text || asking) {
      return
    }
    cancelCall.reset()
    send.mutate(
      { target, call_id: newCallId(), message: text, snippets: snippets.map((snippet) => snippet.range) },
      {
        onSuccess: () => {
          setMessage('')
          onSnippetsChange([])
        },
      },
    )
  }
  const cancel = () => {
    send.reset()
    for (const request of pending) {
      cancelCall.mutate(request.call_id)
    }
  }
  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault()
      sendButton.current?.click()
    }
  }
  const showLine = (answer: AiChatMessage) => (link: LineLink) => {
    const path = link.path
    if (!onShowLine || path === undefined) {
      return
    }
    const known = answer.links.find((candidate) => candidate.path === path && candidate.side === link.side && candidate.line === link.line)
    onShowLine({ path, side: link.side, line: link.line, unit_id: known?.unit_id ?? null })
  }
  const failure = chat.error ?? send.error ?? clear.error ?? cancelCall.error

  return (
    <div className="ai-chat">
      <header className="ai-chat-header">
        <h2>AI chat</h2>
        {messages.length > 0 && !asking && (
          <button type="button" className="link" title="Delete this conversation and start a new one" disabled={clear.isPending} onClick={() => { clear.mutate() }}>
            Clear
          </button>
        )}
      </header>
      {turnedOff ? (
        <p className="muted">Choose an AI provider in Settings to chat about this pull request.</p>
      ) : (
        messages.length === 0 && !asking && !chat.isPending && <p className="muted">{EMPTY_HINT}</p>
      )}
      <ol className="ai-chat-messages">
        {messages.map((item) => (
          <li key={item.id} className={`ai-chat-message ${item.role}`}>
            {item.role === 'user' ? (
              <Question body={item.body} quoted={item.snippets.map((snippet) => ({ place: snippetPlace(snippet), code: snippet.code }))} />
            ) : (
              <Answer message={item} onLineLink={showLine(item)} onOpenThread={(threadId) => { showThread(reviewId, threadId) }} />
            )}
          </li>
        ))}
        {asking && (
          <>
            <li className="ai-chat-message user">
              <Question body={asking.message} quoted={snippets.map((snippet) => ({ place: snippet.label }))} />
            </li>
            <li className="ai-chat-message assistant">
              <span className="muted busy" role="status">
                <Spinner />
                Thinking...
              </span>
              <button type="button" className="link" onClick={cancel}>
                Cancel
              </button>
            </li>
          </>
        )}
      </ol>
      <div ref={end} />
      {failure && <ErrorNote message={describeError(failure)} />}
      {!turnedOff && (
        <div className="ai-chat-compose">
          {snippets.length > 0 && (
            <ul className="ai-chat-snippets" aria-label="Selected code">
              {snippets.map((snippet) => (
                <li key={snippetKey(snippet)}>
                  <span>{snippet.label}</span>
                  <button
                    type="button"
                    className="link"
                    aria-label={`Remove ${snippet.label}`}
                    disabled={asking !== undefined}
                    onClick={() => { onSnippetsChange(snippets.filter((other) => other !== snippet)) }}
                  >
                    ×
                  </button>
                </li>
              ))}
            </ul>
          )}
          <textarea
            aria-label="Message to the AI"
            placeholder="Ask about this pull request. Enter sends, Shift+Enter starts a new line."
            rows={3}
            value={message}
            disabled={asking !== undefined}
            onChange={(event) => { setMessage(event.target.value) }}
            onKeyDown={onKeyDown}
          />
          <div className="ai-chat-actions">
            <AiActionButton
              ref={sendButton}
              repoId={repoId}
              label="Send"
              title="Send the message, with the selected code, to the AI provider"
              disabled={asking !== undefined || !message.trim()}
              onRun={run}
            />
          </div>
        </div>
      )}
    </div>
  )
}

function Question({ body, quoted }: { body: string; quoted: QuotedCode[] }) {
  return (
    <>
      {quoted.map(({ place, code }, index) =>
        code === undefined ? (
          <p key={index} className="ai-chat-snippet muted">
            {place}
          </p>
        ) : (
          <details key={index} className="ai-chat-snippet">
            <summary>{place}</summary>
            <pre>{code}</pre>
          </details>
        ),
      )}
      <p className="ai-chat-text">{body}</p>
    </>
  )
}

interface AnswerProps {
  message: AiChatMessage
  onLineLink: (link: LineLink) => void
  onOpenThread: (threadId: string) => void
}

function Answer({ message, onLineLink, onOpenThread }: AnswerProps) {
  const author = message.model ? `${message.provider_label ?? 'AI'} (${message.model})` : message.provider_label
  return (
    <>
      <Markdown text={message.body} media={false} onLineLink={onLineLink} />
      {message.comments.length > 0 && (
        <section className="ai-chat-comments" aria-label="Comments added to the review">
          <h3>{plural(message.comments.length, 'comment')} added to the review</h3>
          <Findings findings={message.comments} onOpenThread={onOpenThread} />
        </section>
      )}
      <div className="ai-chat-meta muted">
        {author}
        {message.lookups.length > 0 && (
          <details>
            <summary>{plural(message.lookups.length, 'code lookup')}</summary>
            <Lookups lookups={message.lookups} />
          </details>
        )}
      </div>
    </>
  )
}
