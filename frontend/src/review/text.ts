export function plural(count: number, word: string): string {
  return `${String(count)} ${word}${count === 1 ? '' : 's'}`
}

export function matchesWords(haystack: string, query: string): boolean {
  const text = haystack.toLowerCase()
  return query.toLowerCase().split(/\s+/).filter(Boolean).every((word) => text.includes(word))
}

export function aiSource(label: string, model: string | null, effort?: string | null): string {
  const details = [model, effort ? `${effort} effort` : null].filter((part) => part !== null && part !== '')
  return details.length > 0 ? `${label} (${details.join(', ')})` : label
}
