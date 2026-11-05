import { useId, useState } from 'react'

import { useAiPrompts, useSaveAiPrompts } from '../api/ai'
import { describeError } from '../api/client'
import type { AiPrompt, AiPromptKey, AiPrompts } from '../api/types'
import { ErrorNote } from './Badges'

const PROMPT_USES: Record<AiPromptKey, string> = {
  describe: 'Describe on a unit card: what the description says and how the impact is rated.',
  impact: 'Rate impact, and the first step of the AI review: what Low, Medium and High impact mean.',
  review: 'AI review and Review again: what to report, how to anchor and word a finding, and what the summary says.',
}

type Texts = Record<AiPromptKey, string>

function textsOf(prompts: AiPrompt[]): Texts {
  return Object.fromEntries(prompts.map((prompt) => [prompt.key, prompt.custom ?? prompt.default])) as Texts
}

export function AiPromptsPanel() {
  const prompts = useAiPrompts()
  if (prompts.error) {
    return <ErrorNote message={describeError(prompts.error)} />
  }
  if (prompts.data === undefined) {
    return <p className="muted">Loading...</p>
  }
  return <PromptsForm prompts={prompts.data} />
}

function PromptsForm({ prompts }: { prompts: AiPrompts }) {
  const id = useId()
  const [texts, setTexts] = useState(() => textsOf(prompts.prompts))
  const [saved, setSaved] = useState(false)
  const save = useSaveAiPrompts()
  const update = (key: AiPromptKey, text: string) => {
    setTexts({ ...texts, [key]: text })
    setSaved(false)
  }
  return (
    <form
      className="stack ai-prompts"
      onSubmit={(event) => {
        event.preventDefault()
        save.mutate(texts, { onSuccess: (answer) => { setTexts(textsOf(answer.prompts)); setSaved(true) } })
      }}
    >
      <p className="muted">
        bussola always tells the model what it gets, never to follow instructions written in the code, which tools it has and the format of the answer.
        These instructions come after that: what to look for, how to rate and how to write. Leave a prompt as it is, or reset it, to use the default.
      </p>
      {prompts.problem && <ErrorNote message={prompts.problem} />}
      {prompts.prompts.map((prompt) => {
        const text = texts[prompt.key]
        const custom = text.trim() !== prompt.default.trim()
        return (
          <details key={prompt.key} className="ai-prompt">
            <summary>
              {prompt.title}
              {custom && <span className="label">Custom</span>}
            </summary>
            <p className="muted">{PROMPT_USES[prompt.key]}</p>
            <textarea
              id={`${id}-${prompt.key}`}
              aria-label={`${prompt.title} instructions`}
              rows={10}
              value={text}
              spellCheck={false}
              onChange={(event) => { update(prompt.key, event.target.value) }}
            />
            <div>
              <button type="button" disabled={!custom} onClick={() => { update(prompt.key, prompt.default) }}>
                Reset to default
              </button>
            </div>
          </details>
        )
      })}
      <div className="ai-form-actions">
        <button type="submit" className="primary" disabled={save.isPending}>
          {save.isPending ? 'Saving...' : 'Save prompts'}
        </button>
        {saved && <span role="status">Saved</span>}
      </div>
      {save.error && <ErrorNote message={describeError(save.error)} />}
      <p className="muted">
        Saved in the <code>[ai.prompts]</code> section of <code>{prompts.config_file ?? 'config.toml'}</code>. A repository cannot change them.
      </p>
    </form>
  )
}
