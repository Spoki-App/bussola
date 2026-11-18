import { useState } from 'react'

import { useAiPrompts, useAiStatus } from '../api/ai'
import { describeError } from '../api/client'
import type { AiOperationKey } from '../api/types'
import { AiFeaturePanel } from './AiFeaturePanel'
import { AiPanel } from './AiPanel'
import { ErrorNote } from './Badges'
import { Segmented } from './Segmented'

type Tab = 'general' | AiOperationKey

const TABS: Record<Tab, string> = { general: 'General', describe: 'Describe', impact: 'Rate impact', review: 'AI review', chat: 'AI chat' }

export function AiSettingsPanel() {
  const [tab, setTab] = useState<Tab>('general')
  return (
    <div className="stack">
      <Segmented label="AI settings" labels={TABS} value={tab} onChange={setTab} />
      <div role="tabpanel" aria-label={TABS.general} hidden={tab !== 'general'}>
        <AiPanel active={tab === 'general'} />
      </div>
      <AiFeatures tab={tab} />
    </div>
  )
}

function AiFeatures({ tab }: { tab: Tab }) {
  const status = useAiStatus()
  const prompts = useAiPrompts()
  const error = status.error ?? prompts.error
  if (tab !== 'general' && error) {
    return <ErrorNote message={describeError(error)} />
  }
  if (status.data === undefined || prompts.data === undefined) {
    return tab === 'general' ? null : <p className="muted">Loading...</p>
  }
  const ai = status.data
  const loaded = prompts.data
  const problem = ai.operations.length === 0 ? ai.problem : loaded.problem
  return (
    <>
      {ai.operations.map((operation) => {
        const prompt = loaded.prompts.find((candidate) => candidate.key === operation.key)
        return (
          prompt && (
            <div key={operation.key} role="tabpanel" aria-label={operation.title} hidden={tab !== operation.key}>
              <AiFeaturePanel ai={ai} operation={operation} prompt={prompt} active={tab === operation.key} />
            </div>
          )
        )
      })}
      {tab !== 'general' && (
        <>
          <p className="muted">
            Saved in the <code>[ai.operations]</code> and <code>[ai.prompts]</code> sections of <code>{ai.config_file ?? 'config.toml'}</code>. A repository cannot change them.
          </p>
          {problem && <ErrorNote message={problem} />}
        </>
      )}
    </>
  )
}
