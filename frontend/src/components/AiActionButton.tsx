import { useRef, useState, type ButtonHTMLAttributes, type ReactNode, type Ref } from 'react'

import { useAiStatus } from '../api/ai'
import { describeError } from '../api/client'
import type { AiStatus } from '../api/types'
import { useModalDialog } from '../hooks/useModalDialog'
import { hasAiConsent, rememberAiConsent } from '../settings/aiConsent'
import { ErrorNote } from './Badges'
import { IconButton } from './IconButton'
import { Spinner } from './Spinner'

interface AiActionButtonProps {
  repoId: number
  label: string
  title?: string
  icon?: ReactNode
  disabled?: boolean
  ref?: Ref<HTMLButtonElement>
  onRun: (target: string) => void
}

export function AiActionButton({ repoId, label, title, icon, disabled = false, ref, onRun }: AiActionButtonProps) {
  const status = useAiStatus(repoId)
  const [asking, setAsking] = useState<AiStatus | null>(null)
  const starting = useRef(false)
  const [checking, setChecking] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)
  const ai = status.data
  const button = (description: string | undefined, props: ButtonHTMLAttributes<HTMLButtonElement> & { ref?: Ref<HTMLButtonElement> }) =>
    icon ? (
      <IconButton label={label} description={description} icon={checking ? <Spinner /> : icon} {...props} />
    ) : (
      <button type="button" title={description} {...props}>
        {checking && <Spinner />}
        {label}
      </button>
    )
  if (status.isError && ai === undefined) {
    return button(`Could not check the AI provider: ${describeError(status.error)}`, { disabled: true })
  }
  if (ai === undefined || (!ai.configured && ai.problem === null)) {
    return notice ? <ErrorNote message={notice} /> : null
  }
  const start = async () => {
    if (starting.current) {
      return
    }
    starting.current = true
    setChecking(true)
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
      setChecking(false)
    }
  }
  return (
    <>
      {button(ai.problem ?? title, {
        ref,
        className: checking ? 'busy' : undefined,
        'aria-busy': checking,
        disabled: disabled || ai.problem !== null || ai.target === null,
        onClick: () => { void start() },
      })}
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
  const overrides = ai.operations.flatMap((operation) => (operation.uses ? [{ ...operation.uses, key: operation.key, title: operation.title }] : []))
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
      {overrides.length > 0 && (
        <ul>
          {overrides.map((operation) => (
            <li key={operation.key}>
              {operation.title} uses <strong>{operation.label}</strong>
              {operation.model && (
                <>
                  {' '}
                  with the model <code>{operation.model}</code>
                </>
              )}
              {operation.endpoint && (
                <>
                  {' '}
                  at <code>{operation.endpoint}</code>
                </>
              )}
              .
            </li>
          ))}
        </ul>
      )}
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
