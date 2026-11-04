import { describe, expect, it } from 'vitest'

import type { ReviewPullRequest } from '../api/types'
import { reviewDocumentTitle } from './reviewName'

function pull(number: number, title: string | null): ReviewPullRequest {
  return { number, title, url: null, author: null, state: 'OPEN', description: null }
}

describe('reviewDocumentTitle', () => {
  it('names a pull request review by project, number and title', () => {
    const review = { repo_name: 'bussola', head_ref: 'ai-description', pull_request: pull(34, 'feat: AI description and impact rating of a unit, on demand') }

    expect(reviewDocumentTitle(review)).toBe('bussola#34 feat: AI description and impact rating of a unit, on demand')
  })

  it.each([null, '', '  '])('falls back to a generic label when the pull request title is %j', (title) => {
    expect(reviewDocumentTitle({ repo_name: 'bussola', head_ref: 'x', pull_request: pull(7, title) })).toBe('bussola#7 Pull request')
  })

  it('names a branch review by project and branch', () => {
    expect(reviewDocumentTitle({ repo_name: 'bussola', head_ref: 'feature/window-title', pull_request: null })).toBe('bussola feature/window-title')
  })
})
