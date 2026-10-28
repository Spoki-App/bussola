import { describe, expect, it } from 'vitest'

import type { Refs } from '../api/types'
import { defaultReviewRefs, reviewFormProblem } from './newReview'

function refs(local: string[], remote: string[] = [], defaultBase: string | null = null): Refs {
  return { local, remote, default_base: defaultBase }
}

describe('defaultReviewRefs', () => {
  it('compares the first other local branch with the default base', () => {
    expect(defaultReviewRefs(refs(['feature', 'main'], [], 'main'))).toEqual({ head: 'feature', base: 'main' })
  })

  it('falls back to develop, main or master as base', () => {
    expect(defaultReviewRefs(refs(['main', 'topic']))).toEqual({ head: 'topic', base: 'main' })
  })

  it('uses a remote branch when there is no other local one', () => {
    expect(defaultReviewRefs(refs(['main'], ['origin/main', 'origin/fix']))).toEqual({ head: 'origin/fix', base: 'main' })
  })

  it('leaves head equal to base when there is only one branch', () => {
    expect(defaultReviewRefs(refs(['main'], ['origin/main']))).toEqual({ head: 'main', base: 'main' })
  })
})

describe('reviewFormProblem', () => {
  it('accepts two different refs, including typed commits', () => {
    expect(reviewFormProblem(refs(['main']), { head: 'main', base: 'main~5' })).toBeNull()
  })

  it('explains how to review a repository with a single branch', () => {
    expect(reviewFormProblem(refs(['main'], ['origin/main']), { head: 'main', base: 'main' })).toContain('type an earlier commit as the base, for example main~5')
  })

  it('reports identical refs when other branches exist', () => {
    expect(reviewFormProblem(refs(['main', 'feature']), { head: 'feature', base: 'feature' })).toBe('The branch and the base are the same, so there is nothing to review.')
  })

  it('asks for both refs', () => {
    expect(reviewFormProblem(refs(['main']), { head: ' ', base: 'main' })).toBe('Choose the branch to review and the base to compare it with.')
  })
})
