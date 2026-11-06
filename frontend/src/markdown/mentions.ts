const MENTION_AT_CARET = /(?:^|[^\w`@/.-])@([A-Za-z0-9-]*)$/
const MAX_SUGGESTIONS = 8

export function mentionQuery(textBeforeCaret: string): string | null {
  return MENTION_AT_CARET.exec(textBeforeCaret)?.[1] ?? null
}

export function filterMentions(candidates: readonly string[], query: string): string[] {
  const needle = query.toLowerCase()
  const starting = candidates.filter((login) => login.toLowerCase().startsWith(needle))
  const containing = candidates.filter((login) => !login.toLowerCase().startsWith(needle) && login.toLowerCase().includes(needle))
  return [...starting, ...containing].slice(0, MAX_SUGGESTIONS)
}
