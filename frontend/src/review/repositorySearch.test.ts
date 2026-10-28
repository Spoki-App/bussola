import { describe, expect, it } from 'vitest'

import type { FoundRepository } from '../api/types'
import { displayPath, filterRepositories } from './repositorySearch'

const repositories: FoundRepository[] = [
  { name: 'shop', path: '/home/me/Projects/shop', registered: false },
  { name: 'api', path: '/home/me/work/acme/api', registered: true },
]

describe('filterRepositories', () => {
  it('matches every word against the path, ignoring case', () => {
    expect(filterRepositories(repositories, 'ACME api').map((repository) => repository.name)).toEqual(['api'])
    expect(filterRepositories(repositories, 'projects').map((repository) => repository.name)).toEqual(['shop'])
  })

  it('keeps everything for an empty query', () => {
    expect(filterRepositories(repositories, '  ')).toHaveLength(2)
  })
})

describe('displayPath', () => {
  it('shortens paths inside home with a tilde', () => {
    expect(displayPath('/home/me/Projects/shop', '/home/me')).toBe('~/Projects/shop')
    expect(displayPath('/home/meow/x', '/home/me')).toBe('/home/meow/x')
  })
})
