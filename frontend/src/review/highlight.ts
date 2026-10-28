import { common, createLowlight } from 'lowlight'
import { tokenize, type HunkData, type HunkTokens } from 'react-diff-view'

const lowlight = createLowlight(common)

const EXTENSION_LANGUAGES: Record<string, string> = {
  pyi: 'python',
  vue: 'xml',
  svelte: 'xml',
  mdx: 'markdown',
  gradle: 'kotlin',
}

const refractor = {
  highlight: (value: string, language: string) => lowlight.highlight(language, value).children,
}

export function languageFor(path: string): string | null {
  const name = path.split('/').at(-1)?.toLowerCase() ?? ''
  const extension = name.includes('.') ? (name.split('.').at(-1) ?? '') : name
  const language = EXTENSION_LANGUAGES[extension] ?? extension
  return language && lowlight.registered(language) ? language : null
}

export function highlightTokens(hunks: HunkData[], language: string | null): HunkTokens | undefined {
  if (language === null || hunks.length === 0) {
    return undefined
  }
  try {
    return tokenize(hunks, { highlight: true, refractor, language })
  } catch {
    return undefined
  }
}
