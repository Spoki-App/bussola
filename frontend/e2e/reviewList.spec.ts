import { expect, test, type Page } from '@playwright/test'

import type { Repo, Review, ReviewPullRequest } from '../src/api/types.ts'
import { E2E_TOKEN } from './constants.ts'

const REPOS: Repo[] = [
  { id: 901, path: '/work/alpha', name: 'alpha', missing: false },
  { id: 902, path: '/work/beta-service-with-a-long-name', name: 'beta-service-with-a-long-name', missing: false },
]

function pull(number: number, title: string): ReviewPullRequest {
  return { number, title, url: null, author: 'someone', state: 'OPEN', description: null }
}

function review(id: number, repoId: number, fields: Partial<Review>): Review {
  return {
    id,
    repo_id: repoId,
    repo_name: 'repo',
    head_ref: `feature-${String(id)}`,
    base_ref: 'main',
    latest_revision: null,
    counts: { approved: 2, approved_moved: 0, changed: 1, partial: 0, removed: 0, new: 3 },
    total: 6,
    approved: 2,
    open_threads: 0,
    total_threads: 0,
    last_session_at: null,
    pull_request: null,
    pull_request_review: false,
    ...fields,
  }
}

const REVIEWS: Record<number, Review[]> = {
  901: [
    review(1, 901, { pull_request: pull(7, 'Short'), total_threads: 3 }),
    review(2, 901, { pull_request: pull(1234, `A very long pull request title ${'that keeps going '.repeat(12)}`), total_threads: 999, open_threads: 999, total: 1234, approved: 999 }),
    review(3, 901, { head_ref: `branch-${'x'.repeat(120)}`, total: 4, approved: 4, counts: { approved: 4, approved_moved: 0, changed: 0, partial: 0, removed: 0, new: 0 } }),
  ],
  902: [
    review(4, 902, { pull_request: pull(42, 'Medium sized title for a change'), total_threads: 12, open_threads: 1 }),
    review(5, 902, { total: 0, approved: 0, counts: { approved: 0, approved_moved: 0, changed: 0, partial: 0, removed: 0, new: 0 } }),
  ],
}

async function openHome(page: Page) {
  await page.route('**/api/repos', (route) => route.fulfill({ json: REPOS }))
  await page.route('**/api/repos/*/reviews', (route) => {
    const repoId = Number(new URL(route.request().url()).pathname.split('/')[3])
    return route.fulfill({ json: REVIEWS[repoId] ?? [] })
  })
  await page.goto(`/?token=${E2E_TOKEN}`)
  await expect(page.locator('.review-list li')).toHaveCount(5)
}

function columnEdges(page: Page, selector: string) {
  return page.locator(`.review-list li > ${selector}`).evaluateAll((cells) =>
    cells.map((cell) => {
      const box = cell.getBoundingClientRect()
      return { left: Math.round(box.left), right: Math.round(box.right), visible: box.width > 0 }
    }),
  )
}

async function expectColumnsAligned(page: Page, selectors: string[]) {
  for (const selector of selectors) {
    const edges = await columnEdges(page, selector)
    expect(edges, selector).toHaveLength(5)
    expect(edges.every((edge) => edge.visible), selector).toBe(true)
    expect(new Set(edges.map((edge) => edge.left)).size, `${selector} left edges`).toBe(1)
    expect(new Set(edges.map((edge) => edge.right)).size, `${selector} right edges`).toBe(1)
  }
}

async function expectBadgesFit(page: Page) {
  const overflows = await page.locator('.review-list .comment-count').evaluateAll((counts) => counts.map((count) => count.scrollWidth > count.clientWidth))
  expect(overflows.some(Boolean)).toBe(false)
}

test('review rows line up across rows and repositories, with or without the unresolved badge', async ({ page }) => {
  await openHome(page)

  await expectColumnsAligned(page, ['.review-link', '.course', '.review-count', '.review-todo', '.comment-count'])
  await expectBadgesFit(page)
})

test('review rows stay aligned on a narrower screen without the to review column', async ({ page }) => {
  await page.setViewportSize({ width: 1000, height: 900 })
  await openHome(page)

  await expect(page.locator('.review-todo').first()).toBeHidden()
  await expectColumnsAligned(page, ['.review-link', '.course', '.review-count', '.comment-count'])
  await expectBadgesFit(page)
})
