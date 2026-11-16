import { describe, expect, it } from 'vitest'

import { aiSource } from './text'

describe('aiSource', () => {
  it('names the provider with the model and the effort it used', () => {
    expect(aiSource('Anthropic API', 'claude-haiku-5-5', 'low')).toBe('Anthropic API (claude-haiku-5-5, low effort)')
    expect(aiSource('Anthropic API', 'claude-opus-5-5', null)).toBe('Anthropic API (claude-opus-5-5)')
    expect(aiSource('Claude Code CLI', null, 'high')).toBe('Claude Code CLI (high effort)')
    expect(aiSource('Claude Code CLI', null, null)).toBe('Claude Code CLI')
  })
})
