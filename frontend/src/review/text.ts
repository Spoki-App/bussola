export function plural(count: number, word: string): string {
  return `${String(count)} ${word}${count === 1 ? '' : 's'}`
}

export function matchesWords(haystack: string, query: string): boolean {
  const text = haystack.toLowerCase()
  return query.toLowerCase().split(/\s+/).filter(Boolean).every((word) => text.includes(word))
}
