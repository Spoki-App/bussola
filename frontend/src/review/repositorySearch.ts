import type { FoundRepository } from '../api/types'

export function filterRepositories(repositories: FoundRepository[], query: string): FoundRepository[] {
  const words = query.toLowerCase().split(/\s+/).filter(Boolean)
  return repositories.filter((repository) => {
    const haystack = repository.path.toLowerCase()
    return words.every((word) => haystack.includes(word))
  })
}

export function displayPath(path: string, home: string): string {
  return path === home || path.startsWith(`${home}/`) ? `~${path.slice(home.length)}` : path
}
