import type { Refs } from '../api/types'

const BASE_FALLBACKS = ['develop', 'main', 'master']
const EXAMPLE_ANCESTOR = '~5'

export interface ReviewRefs {
  head: string
  base: string
}

export function defaultReviewRefs(refs: Refs): ReviewRefs {
  const base = refs.default_base ?? BASE_FALLBACKS.find((name) => refs.local.includes(name)) ?? refs.local.at(0) ?? ''
  const head = refs.local.find((name) => name !== base) ?? refs.remote.find((name) => name !== base && !name.endsWith(`/${base}`)) ?? base
  return { head, base }
}

export function reviewFormProblem(refs: Refs, choice: ReviewRefs): string | null {
  const head = choice.head.trim()
  const base = choice.base.trim()
  if (!head || !base) {
    return 'Choose the branch to review and the base to compare it with.'
  }
  if (head !== base) {
    return null
  }
  const branches = new Set([...refs.local, ...refs.remote.map((name) => name.slice(name.indexOf('/') + 1))])
  if (branches.size <= 1) {
    return `This repository only has ${head}. Review a branch with your changes, or type an earlier commit as the base, for example ${head}${EXAMPLE_ANCESTOR}.`
  }
  return 'The branch and the base are the same, so there is nothing to review.'
}
