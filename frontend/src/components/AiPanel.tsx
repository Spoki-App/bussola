import { useAiStatus, useTestAiConnection } from '../api/ai'
import { describeError } from '../api/client'
import type { AiStatus } from '../api/types'
import { ErrorNote } from './Badges'

export function AiPanel() {
  const status = useAiStatus()
  if (status.error) {
    return <ErrorNote message={describeError(status.error)} />
  }
  if (status.data === undefined) {
    return <p className="muted">Loading...</p>
  }
  return status.data.configured ? <ActiveProvider ai={status.data} /> : <NoProvider ai={status.data} />
}

function NoProvider({ ai }: { ai: AiStatus }) {
  return (
    <div className="stack">
      <p className="muted">
        AI features are off. To turn them on, add an <code>[ai]</code> section to <code>{ai.config_file ?? 'config.toml'}</code> choosing Claude Code, the Anthropic API or an
        OpenAI-compatible endpoint (see the README).
      </p>
      {ai.problem && <ErrorNote message={ai.problem} />}
    </div>
  )
}

function ActiveProvider({ ai }: { ai: AiStatus }) {
  const test = useTestAiConnection()
  return (
    <div className="stack">
      <dl className="ai-details">
        <dt>Provider</dt>
        <dd>{ai.label}</dd>
        <dt>Model</dt>
        <dd>{ai.model ?? 'Default of the claude command'}</dd>
        {ai.endpoint && (
          <>
            <dt>Endpoint</dt>
            <dd>
              <code>{ai.endpoint}</code>
            </dd>
          </>
        )}
        {ai.api_key_env && (
          <>
            <dt>API key</dt>
            <dd>
              <code>{ai.api_key_env}</code> {ai.api_key_set ? 'is set' : 'is not set'}
            </dd>
          </>
        )}
        <dt>Configuration</dt>
        <dd>
          <code>{ai.config_file}</code>
        </dd>
      </dl>
      {ai.problem && <ErrorNote message={ai.problem} />}
      <button type="button" disabled={test.isPending} onClick={() => { test.mutate() }}>
        {test.isPending ? 'Testing...' : 'Test connection'}
      </button>
      {test.data?.ok && <p role="status">{`${test.data.message} in ${String(test.data.elapsed_ms)} ms.`}</p>}
      {test.data && !test.data.ok && <ErrorNote message={test.data.message} />}
      {test.error && <ErrorNote message={describeError(test.error)} />}
      <p className="muted">Test connection sends a short fixed prompt and no code. Code is sent only when you start an AI action.</p>
    </div>
  )
}
