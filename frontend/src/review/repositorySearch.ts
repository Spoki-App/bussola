import type { FoundRepository } from '../api/types'
import { matchesWords } from './text'

export function filterRepositories(repositories: FoundRepository[], query: string): FoundRepository[] {
  return repositories.filter((repository) => matchesWords(repository.path, query))
}

export function displayPath(path: string, home: string): string {
  return path === home || path.startsWith(`${home}/`) ? `~${path.slice(home.length)}` : path
}
