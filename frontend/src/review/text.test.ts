import { describe, expect, it } from 'vitest'

import type { ReviewPullRequest } from '../api/types'
import { projectName, reviewDocumentTitle } from './text'

function pull(number: number, title: string | null): ReviewPullRequest {
  return { number, title, url: null, author: null, state: 'OPEN', description: null }
}

describe('reviewDocumentTitle', () => {
  it('names a pull request review by project, number and title', () => {
    const review = { repo_path: '/home/me/code/bussola', head_ref: 'ai-description', pull_request: pull(34, 'feat: AI description and impact rating of a unit, on demand') }

    expect(reviewDocumentTitle(review)).toBe('bussola#34 feat: AI description and impact rating of a unit, on demand')
  })

  it('falls back to a generic label when the pull request has no title yet', () => {
    expect(reviewDocumentTitle({ repo_path: '/code/bussola', head_ref: 'x', pull_request: pull(7, null) })).toBe('bussola#7 Pull request')
  })

  it('names a branch review by project and branch', () => {
    expect(reviewDocumentTitle({ repo_path: '/code/bussola', head_ref: 'feature/window-title', pull_request: null })).toBe('bussola feature/window-title')
  })
})

describe('projectName', () => {
  it.each([
    ['/home/me/code/bussola', 'bussola'],
    ['/home/me/code/bussola/', 'bussola'],
    ['C:\\Users\\me\\code\\bussola', 'bussola'],
    ['bussola', 'bussola'],
  ])('takes the last folder of %s', (path, name) => {
    expect(projectName(path)).toBe(name)
  })
})
