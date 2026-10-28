import { describe, expect, it } from 'vitest'

import { isPullRequestUrl, pullRequestUrlFromPath } from './pullRequestLink'

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

describe('pullRequestUrlFromPath', () => {
  it('turns an rtool path that mirrors a GitHub link into that link', () => {
    expect(pullRequestUrlFromPath('/github.com/acme/widgets/pull/7/files')).toBe('https://github.com/acme/widgets/pull/7/files')
  })

  it('ignores other paths', () => {
    expect(pullRequestUrlFromPath('/reviews/3')).toBeNull()
  })
})
