/// <reference lib="dom" />
import { execFileSync } from 'node:child_process'
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

import { expect, test } from '@playwright/test'

import { E2E_TOKEN } from './constants.ts'

const BASE = 'def total(items):\n    return 0\n'
const FEATURE = 'def total(items):\n    subtotal = sum(items)\n    return subtotal * 2\n'

let root = ''

function git(repo: string, ...args: string[]) {
  execFileSync('git', args, { cwd: repo, stdio: 'ignore' })
}

function createRepository(): string {
  const repo = join(root, 'clipboard')
  mkdirSync(repo)
  git(repo, 'init', '-q', '-b', 'main')
  git(repo, 'config', 'user.email', 'e2e@example.com')
  git(repo, 'config', 'user.name', 'E2E Reviewer')
  git(repo, 'config', 'commit.gpgsign', 'false')
  writeFileSync(join(repo, 'billing.py'), BASE)
  git(repo, 'add', '-A')
  git(repo, 'commit', '-q', '-m', 'base')
  git(repo, 'checkout', '-q', '-b', 'feature')
  writeFileSync(join(repo, 'billing.py'), FEATURE)
  git(repo, 'commit', '-q', '-am', 'feature')
  return repo
}

test.beforeAll(() => {
  root = mkdtempSync(join(tmpdir(), 'bussola-e2e-clipboard-'))
})

test.afterAll(() => {
  rmSync(root, { recursive: true, force: true })
})

test('selected lines are compared with the code copied to the clipboard', async ({ page, context }) => {
  await context.grantPermissions(['clipboard-read', 'clipboard-write'])
  await page.goto(`/?token=${E2E_TOKEN}`)
  const repo = await page.request.post('/api/repos', { data: { path: createRepository() } })
  const { id: repoId } = (await repo.json()) as { id: number }
  const review = await page.request.post(`/api/repos/${String(repoId)}/reviews`, { data: { head_ref: 'feature', base_ref: 'main' } })
  const { id: reviewId } = (await review.json()) as { id: number }
  await page.goto(`/reviews/${String(reviewId)}`)
  const card = page.locator('article.unit-card', { hasText: 'total' })
  await page.evaluate(() => navigator.clipboard.writeText('subtotal = sum(items)\nreturn subtotal * 3\n'))

  await card.locator('td.diff-gutter-insert', { hasText: /^2$/ }).click()
  await card.locator('td.diff-gutter-insert', { hasText: /^3$/ }).click({ modifiers: ['Shift'] })
  await card.getByRole('button', { name: 'Compare with clipboard' }).click()

  const dialog = page.getByRole('dialog', { name: 'Compare' })
  await expect(dialog.getByText('Clipboard')).toBeVisible()
  await expect(dialog.getByText('changed')).toBeVisible()
  await expect(dialog.locator('td.diff-code-delete', { hasText: 'return subtotal * 3' })).toBeVisible()
  await expect(dialog.locator('td.diff-code-insert', { hasText: 'return subtotal * 2' })).toBeVisible()
  await expect(dialog.locator('td.diff-code-normal', { hasText: 'subtotal = sum(items)' }).first()).toBeVisible()
})
