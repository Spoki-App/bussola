import { useRef, useState } from 'react'

import { useAiStatus } from '../api/ai'
import { describeError } from '../api/client'
import type { AiStatus } from '../api/types'
import { useModalDialog } from '../hooks/useModalDialog'
import { hasAiConsent, rememberAiConsent } from '../settings/aiConsent'
import { ErrorNote } from './Badges'

interface AiActionButtonProps {
  repoId: number
  label: string
  title?: string
  disabled?: boolean
  onRun: (target: string) => void
}

export function AiActionButton({ repoId, label, title, disabled = false, onRun }: AiActionButtonProps) {
  const status = useAiStatus(repoId)
  const [asking, setAsking] = useState<AiStatus | null>(null)
  const starting = useRef(false)
  const [notice, setNotice] = useState<string | null>(null)
  const ai = status.data
  if (status.isError && ai === undefined) {
    const reason = `Could not check the AI provider: ${describeError(status.error)}`
    return (
      <button type="button" title={reason} disabled>
        {label}
      </button>
    )
  }
  if (ai === undefined || (!ai.configured && ai.problem === null)) {
    return null
  }
  const start = async () => {
    if (starting.current) {
      return
    }
    starting.current = true
    setNotice(null)
    try {
      const result = await status.refetch()
      if (result.isError) {
        setNotice(`Could not check the AI provider: ${describeError(result.error)}`)
        return
      }
      const fresh = result.data
      if (!fresh?.configured || fresh.problem !== null || fresh.target === null) {
        setNotice(fresh?.problem ?? 'AI is turned off for this repository')
        return
      }
      if (hasAiConsent(fresh.target)) {
        onRun(fresh.target)
      } else {
        setAsking(fresh)
      }
    } finally {
      starting.current = false
    }
  }
  return (
    <>
      <button type="button" title={ai.problem ?? title} disabled={disabled || ai.problem !== null || ai.target === null} onClick={() => { void start() }}>
        {label}
      </button>
      {notice && <ErrorNote message={notice} />}
      {asking?.target && (
        <AiNoticeDialog
          ai={asking}
          onAnswer={(accepted) => {
            setAsking(null)
            if (accepted && asking.target !== null) {
              rememberAiConsent(asking.target)
              onRun(asking.target)
            }
          }}
        />
      )}
    </>
  )
}

function AiNoticeDialog({ ai, onAnswer }: { ai: AiStatus; onAnswer: (accepted: boolean) => void }) {
  const { ref: dialog, close } = useModalDialog()
  const accepted = useRef(false)
  const answered = useRef(false)
  const finish = () => {
    if (!answered.current) {
      answered.current = true
      onAnswer(accepted.current)
    }
  }
  return (
    <dialog ref={dialog} className="picker ai-notice" aria-labelledby="ai-notice-title" onClose={finish}>
      <h2 id="ai-notice-title">Send code to {ai.label}?</h2>
      <p>
        This action sends the code it works on to <strong>{ai.label}</strong>
        {ai.model && (
          <>
            {' '}
            (model <code>{ai.model}</code>)
          </>
        )}
        {ai.endpoint && (
          <>
            {' '}
            at <code>{ai.endpoint}</code>
          </>
        )}
        .
      </p>
      {ai.source === 'repository' && <p className="muted">This provider is set by the repository's .bussola.toml.</p>}
      <p className="muted">bussola asks once for each provider, model and endpoint. Nothing is sent until you choose Send code.</p>
      <div className="ai-notice-actions">
        <button type="button" onClick={close}>
          Cancel
        </button>
        <button
          type="button"
          className="primary"
          onClick={() => {
            accepted.current = true
            close()
          }}
        >
          Send code
        </button>
      </div>
    </dialog>
  )
}
