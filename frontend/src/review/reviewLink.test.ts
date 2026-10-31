import { describe, expect, it } from 'vitest'

import { reviewLinkMaker } from './reviewLink'

describe('reviewLinkMaker', () => {
  const makeLink = reviewLinkMaker('https://github.com/acme/widgets/pull/42')

  it('links to the review, a line of a file and a thread', () => {
    expect(makeLink?.()).toBe('bussola://review?repo=acme/widgets&pr=42')
    expect(makeLink?.({ path: 'src/app.py', line: 7 })).toBe('bussola://review?repo=acme/widgets&pr=42&path=src/app.py&line=7')
    expect(makeLink?.({ thread: '0123456789abcdef0123456789abcdef' })).toBe('bussola://review?repo=acme/widgets&pr=42&thread=0123456789abcdef0123456789abcdef')
  })

  it('escapes file paths that would end the parameter', () => {
    expect(makeLink?.({ path: 'docs/a&b #1.md', line: 1 })).toBe('bussola://review?repo=acme/widgets&pr=42&path=docs/a%26b+%231.md&line=1')
  })

  it('makes no links without a GitHub pull request', () => {
    expect(reviewLinkMaker(null)).toBeNull()
    expect(reviewLinkMaker(undefined)).toBeNull()
    expect(reviewLinkMaker('https://gitlab.com/acme/widgets/-/merge_requests/42')).toBeNull()
  })
})
