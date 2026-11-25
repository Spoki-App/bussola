import { execFileSync } from 'node:child_process'
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

import { expect, test } from '@playwright/test'

import { E2E_TOKEN } from './constants.ts'

let root = ''

function git(repo: string, ...args: string[]) {
  execFileSync('git', args, { cwd: repo, stdio: 'ignore' })
}

function createRepository(): string {
  const repo = join(root, 'resolved')
  mkdirSync(repo)
  git(repo, 'init', '-q', '-b', 'main')
  git(repo, 'config', 'user.email', 'e2e@example.com')
  git(repo, 'config', 'user.name', 'E2E Reviewer')
  git(repo, 'config', 'commit.gpgsign', 'false')
  writeFileSync(join(repo, 'price.py'), 'def price():\n    return 0\n')
  git(repo, 'add', '-A')
  git(repo, 'commit', '-q', '-m', 'base')
  git(repo, 'checkout', '-q', '-b', 'price')
  writeFileSync(join(repo, 'price.py'), 'def price():\n    amount = 10\n    return amount\n')
  git(repo, 'commit', '-q', '-am', 'price')
  return repo
}

test.beforeAll(() => {
  root = mkdtempSync(join(tmpdir(), 'bussola-e2e-resolved-'))
})

test.afterAll(() => {
  rmSync(root, { recursive: true, force: true })
})

test('a resolved thread folds into an icon next to its line number, which opens it again', async ({ page }) => {
  await page.goto(`/?token=${E2E_TOKEN}`)
  const repo = await page.request.post('/api/repos', { data: { path: createRepository() } })
  const { id: repoId } = (await repo.json()) as { id: number }
  const review = await page.request.post(`/api/repos/${String(repoId)}/reviews`, { data: { head_ref: 'price', base_ref: 'main' } })
  const { id: reviewId } = (await review.json()) as { id: number }
  await page.goto(`/reviews/${String(reviewId)}`)

  const card = page.locator('article.unit-card', { hasText: 'price' })
  const line = card.locator('td.diff-gutter-insert', { hasText: /^2$/ })
  await line.click()
  await card.getByPlaceholder('Leave a comment (Markdown)').fill('Name the constant')
  await card.getByRole('button', { name: 'Start thread' }).click()
  const thread = card.getByTestId('thread')
  await expect(thread).toContainText('Name the constant')
  const threadId = (await thread.getAttribute('id')) ?? ''

  await thread.getByRole('button', { name: 'Resolve' }).click()
  await expect(thread).toHaveCount(0)
  const marker = line.getByRole('button', { name: '1 resolved thread' })
  await expect(marker).toHaveAttribute('aria-expanded', 'false')

  await marker.click()
  await expect(thread).toContainText('Name the constant')
  await expect(thread.getByRole('button', { name: 'Reopen' })).toBeVisible()
  await expect(marker).toHaveAttribute('aria-expanded', 'true')
  await expect(card.getByPlaceholder('Leave a comment (Markdown)')).toHaveCount(0)

  await marker.click()
  await expect(thread).toHaveCount(0)

  await page.goto(`/reviews/${String(reviewId)}?thread=${threadId.replace(/^thread-/, '')}`)
  await expect(page.locator(`#${threadId}`)).toContainText('Name the constant')
  await expect(page.locator(`#${threadId}`)).toBeInViewport()
})
