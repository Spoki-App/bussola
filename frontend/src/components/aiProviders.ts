import type { AiEffort, AiModel, AiProviderName } from '../api/types'

export type ProviderChoice = 'none' | AiProviderName

export const PROVIDERS: Record<ProviderChoice, string> = {
  none: 'Off',
  'claude-code': 'Claude Code CLI',
  anthropic: 'Anthropic API',
  'openai-compatible': 'OpenAI-compatible endpoint',
}

export const MODEL_DEFAULTS: Record<ProviderChoice, string> = {
  none: '',
  'claude-code': 'Default of the claude command',
  anthropic: 'Default: claude-opus-5-5',
  'openai-compatible': 'Required, for example qwen2.5-coder',
}

export const ENDPOINT_PLACEHOLDERS: Record<ProviderChoice, string> = {
  none: '',
  'claude-code': '',
  anthropic: 'https://api.anthropic.com',
  'openai-compatible': 'Required, for example http://localhost:11434/v1',
}

export const KEY_PLACEHOLDERS: Record<ProviderChoice, string> = {
  none: '',
  'claude-code': '',
  anthropic: 'ANTHROPIC_API_KEY',
  'openai-compatible': 'Optional, for a server that needs a key',
}

export const EFFORTS: Record<AiEffort, string> = { low: 'Low', medium: 'Medium', high: 'High' }

export function isRemote(provider: string): boolean {
  return provider === 'anthropic' || provider === 'openai-compatible'
}

export function takesEffort(models: AiModel[], model: string | null): boolean {
  return models.find((listed) => listed.id === model)?.effort !== false
}
