import { describe, expect, it } from 'vitest'

import {
  addRepositoryPath,
  addRepositoryRequestFromSearch,
  isPullRequestUrl,
  pullRequestTargetFromUrl,
  pullRequestRepositoryFromPath,
  pullRequestUrlFromPath,
} from './pullRequestLink'

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

describe('pullRequestTargetFromUrl', () => {
  it('turns a pasted pull request link into its page and link, keeping a comment anchor', () => {
    expect(pullRequestTargetFromUrl(' https://github.com/acme/widgets/pull/7/files ')).toEqual({
      url: 'https://github.com/acme/widgets/pull/7/files',
      pathname: '/github.com/acme/widgets/pull/7/files',
      search: '',
    })
    expect(pullRequestTargetFromUrl('www.github.com/acme/widgets/pull/7?w=1').pathname).toBe('/github.com/acme/widgets/pull/7')
    expect(pullRequestTargetFromUrl('https://github.com/acme/widgets/pull/7#discussion_r501').search).toBe('?comment=501')
    expect(pullRequestTargetFromUrl('https://github.com/acme/widgets/pull/7/files#r502').search).toBe('?comment=502')
    expect(pullRequestTargetFromUrl('https://github.com/acme/widgets/pull/7#issuecomment-503').search).toBe('?comment=503')
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
  it('takes the repository, link and focus from the pull request page to open next', () => {
    const path = addRepositoryPath('/github.com/acme/widgets/pull/7/files?path=src%2Fapp.py&line=4')

    expect(path.startsWith('/?')).toBe(true)
    expect(addRepositoryRequestFromSearch(path.slice(1))).toEqual({
      repository: 'acme/widgets',
      url: 'https://github.com/acme/widgets/pull/7/files',
      search: '?path=src%2Fapp.py&line=4',
    })
    expect(addRepositoryRequestFromSearch(addRepositoryPath('/github.com/acme/widgets/pull/7').slice(1))?.search).toBe('')
    expect(addRepositoryRequestFromSearch(addRepositoryPath('/github.com/acme/widgets/pull/7?line=4#top').slice(1))?.search).toBe('?line=4')
  })

  it('refuses anything but a pull request page to open next', () => {
    expect(addRepositoryRequestFromSearch('')).toBeNull()
    expect(addRepositoryRequestFromSearch('?add_repo=https://evil.example')).toBeNull()
    expect(addRepositoryRequestFromSearch('?add_repo=//evil.example/github.com/a/b/pull/1')).toBeNull()
    expect(addRepositoryRequestFromSearch('?add_repo=/github.com/acme/widgets/issues/7')).toBeNull()
    expect(addRepositoryRequestFromSearch('?add_repo=http://%5B')).toBeNull()
  })
})
