const MENTION_AT_CARET = /(?:^|[^\w`@/.-])@([A-Za-z0-9-]*)$/
const MAX_SUGGESTIONS = 8

export function mentionQuery(textBeforeCaret: string): string | null {
  return MENTION_AT_CARET.exec(textBeforeCaret)?.[1] ?? null
}

export function filterMentions(candidates: readonly string[], query: string): string[] {
  const needle = query.toLowerCase()
  const matching = candidates.filter((login) => login.toLowerCase().includes(needle))
  const starts = (login: string) => (login.toLowerCase().startsWith(needle) ? 0 : 1)
  return matching.sort((left, right) => starts(left) - starts(right)).slice(0, MAX_SUGGESTIONS)
}
