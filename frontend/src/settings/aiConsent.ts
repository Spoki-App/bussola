import { readStored, writeStored } from './storage'

const STORAGE_KEY = 'bussola.aiConsent'

function acceptedTargets(): string[] {
  try {
    const stored: unknown = JSON.parse(readStored(STORAGE_KEY) ?? '[]')
    return Array.isArray(stored) ? stored.filter((item): item is string => typeof item === 'string') : []
  } catch {
    return []
  }
}

export function hasAiConsent(target: string): boolean {
  return acceptedTargets().includes(target)
}

export function rememberAiConsent(target: string): void {
  if (!hasAiConsent(target)) {
    writeStored(STORAGE_KEY, JSON.stringify([...acceptedTargets(), target]))
  }
}
