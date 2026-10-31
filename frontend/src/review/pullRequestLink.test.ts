import { describe, expect, it } from 'vitest'

import { addRepositoryPath, addRepositoryRequestFromSearch, isPullRequestUrl, pullRequestRepositoryFromPath, pullRequestUrlFromPath } from './pullRequestLink'

describe('isPullRequestUrl', () => {
  it('accepts pull request links with or without scheme and suffix', () => {
    expect(isPullRequestUrl('https://github.com/acme/widgets/pull/7')).toBe(true)
    expect(isPullRequestUrl(' github.com/acme/widgets/pull/7/files ')).toBe(true)
    expect(isPullRequestUrl('https://github.com/acme/widgets/pull/7#discussion_r1')).toBe(true)
  })

  it('rejects other links', () => {
    expect(isPullRequestUrl('https://github.com/acme/widgets/issues/7')).toBe(false)
    expect(isPullRequestUrl('https://gitlab.com/acme/widgets/pull/7')).toBe(false)
  })
})

describe('pullRequestRepositoryFromPath', () => {
  it('reads the repository of a path that mirrors a pull request link', () => {
    expect(pullRequestRepositoryFromPath('/github.com/acme/widgets/pull/7/files')).toBe('acme/widgets')
    expect(pullRequestRepositoryFromPath('/github.com/acme/widgets/issues/7')).toBeNull()
  })
})

describe('pullRequestUrlFromPath', () => {
  it('turns an bussola path that mirrors a GitHub link into that link', () => {
    expect(pullRequestUrlFromPath('/github.com/acme/widgets/pull/7/files')).toBe('https://github.com/acme/widgets/pull/7/files')
  })

  it('ignores other paths', () => {
    expect(pullRequestUrlFromPath('/reviews/3')).toBeNull()
  })
})

describe('add repository request', () => {
  it('takes the repository from the pull request page to open next', () => {
    const then = '/github.com/acme/widgets/pull/7?path=src%2Fapp.py&line=4'
    const path = addRepositoryPath(then)

    expect(path.startsWith('/?')).toBe(true)
    expect(addRepositoryRequestFromSearch(path.slice(1))).toEqual({ repository: 'acme/widgets', then })
  })

  it('refuses anything but a pull request page to open next', () => {
    expect(addRepositoryRequestFromSearch('')).toBeNull()
    expect(addRepositoryRequestFromSearch('?add_repo=https://evil.example')).toBeNull()
    expect(addRepositoryRequestFromSearch('?add_repo=//evil.example/github.com/a/b/pull/1')).toBeNull()
    expect(addRepositoryRequestFromSearch('?add_repo=/github.com/acme/widgets/issues/7')).toBeNull()
  })
})
