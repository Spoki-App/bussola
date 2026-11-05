import type { ReactNode } from 'react'

import { navigate } from '../navigation'
import { AddRepoForm } from './AddRepoForm'
import { AiPanel } from './AiPanel'
import { AiPromptsPanel } from './AiPromptsPanel'
import { CodeFontPanel } from './CodeFontPanel'
import { DiffLayoutPanel } from './DiffLayoutPanel'
import { DiffWrapCheckbox } from './DiffWrapToggle'
import { OpenPullRequestForm } from './OpenPullRequestForm'

export const SETTING_CATEGORIES = ['Pull requests', 'Repositories', 'Appearance', 'Diff', 'AI'] as const

export type SettingCategory = (typeof SETTING_CATEGORIES)[number]

export interface Setting {
  category: SettingCategory
  name: string
  description: string
  render: (closeSettings: () => void) => ReactNode
}

export const SETTINGS: Setting[] = [
  {
    category: 'Pull requests',
    name: 'Open pull request',
    description: 'Paste a GitHub pull request link to start or continue its review.',
    render: (closeSettings) => <OpenPullRequestForm onOpened={closeSettings} />,
  },
  {
    category: 'Repositories',
    name: 'Add repository',
    description: 'Add a local git repository, by path or by browsing your folders.',
    render: (closeSettings) => (
      <AddRepoForm
        onAdded={() => {
          closeSettings()
          navigate('/')
        }}
      />
    ),
  },
  {
    category: 'Appearance',
    name: 'Code font',
    description: 'The font, size, ligatures and font features used for code.',
    render: () => <CodeFontPanel />,
  },
  {
    category: 'Diff',
    name: 'Diff layout',
    description: 'Split, unified or automatic, and the window width from which automatic splits.',
    render: () => <DiffLayoutPanel />,
  },
  {
    category: 'Diff',
    name: 'Line wrap',
    description: 'Wrap long lines in the diff, or keep them on one row and scroll sideways.',
    render: () => <DiffWrapCheckbox />,
  },
  {
    category: 'AI',
    name: 'AI provider',
    description: 'The provider, model, endpoint and key variable used by the AI features, and a connection test.',
    render: () => <AiPanel />,
  },
  {
    category: 'AI',
    name: 'AI prompts',
    description: 'The instructions given to the model for Describe, Rate impact and AI review.',
    render: () => <AiPromptsPanel />,
  },
]
