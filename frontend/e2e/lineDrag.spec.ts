/// <reference lib="dom" />
import { execFileSync } from 'node:child_process'
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

import { expect, test, type Locator, type Page } from '@playwright/test'

import { E2E_TOKEN } from './constants.ts'

const BASE = 'ROWS = []\nprint(ROWS)\n'
const FEATURE = `ROWS = []\nROWS.clear()\n${Array.from({ length: 60 }, (_, index) => `ROWS.append(${String(index)})\n`).join('')}print(ROWS)\n`

let root = ''

function git(repo: string, ...args: string[]) {
  execFileSync('git', args, { cwd: repo, stdio: 'ignore' })
}

function createRepository(name: string): string {
  const repo = join(root, name)
  mkdirSync(repo)
  git(repo, 'init', '-q', '-b', 'main')
  git(repo, 'config', 'user.email', 'e2e@example.com')
  git(repo, 'config', 'user.name', 'E2E Reviewer')
  git(repo, 'config', 'commit.gpgsign', 'false')
  writeFileSync(join(repo, 'ledger.py'), BASE)
  git(repo, 'add', '-A')
  git(repo, 'commit', '-q', '-m', 'base')
  git(repo, 'checkout', '-q', '-b', 'ledger')
  writeFileSync(join(repo, 'ledger.py'), FEATURE)
  git(repo, 'commit', '-q', '-am', 'feature')
  return repo
}

async function openReview(page: Page, name: string): Promise<Locator> {
  await page.goto(`/?token=${E2E_TOKEN}`)
  const repo = await page.request.post('/api/repos', { data: { path: createRepository(name) } })
  const { id: repoId } = (await repo.json()) as { id: number }
  const review = await page.request.post(`/api/repos/${String(repoId)}/reviews`, { data: { head_ref: 'ledger', base_ref: 'main' } })
  const { id: reviewId } = (await review.json()) as { id: number }
  await page.goto(`/reviews/${String(reviewId)}`)
  const card = page.locator('article.unit-card', { hasText: 'Module code' })
  await expect(card.locator('td.diff-gutter-insert').first()).toBeVisible()
  return card
}

function gutter(card: Locator, line: number): Locator {
  return card.locator('td.diff-gutter-insert', { hasText: new RegExp(`^${String(line)}$`) })
}

async function center(locator: Locator) {
  const box = await locator.boundingBox()
  if (!box) {
    throw new Error('Not visible')
  }
  return { x: box.x + box.width / 2, y: box.y + box.height / 2 }
}

test.beforeAll(() => {
  root = mkdtempSync(join(tmpdir(), 'bussola-e2e-line-drag-'))
})

test.afterAll(() => {
  rmSync(root, { recursive: true, force: true })
})

test('dragging over line numbers selects the lines covered, to approve them and comment on exactly those lines', async ({ page }) => {
  const card = await openReview(page, 'drag')
  const from = await center(gutter(card, 2))
  const to = await center(gutter(card, 4))

  await page.mouse.move(from.x, from.y)
  await page.mouse.down()
  await page.mouse.move(to.x, to.y, { steps: 5 })
  await expect(card.getByRole('button', { name: 'Approve selection (3)' })).toBeVisible()
  await page.mouse.move(from.x, from.y, { steps: 5 })
  await expect(card.getByRole('button', { name: 'Approve selection (1)' })).toBeVisible()
  await page.mouse.move(to.x, to.y, { steps: 5 })
  await page.mouse.up()

  await expect(card.getByText('Commenting on 3 lines')).toBeVisible()
  await card.getByPlaceholder('Leave a comment (Markdown)').fill('Why three appends?')
  await card.getByRole('button', { name: 'Start thread' }).click()
  await expect(card.getByTestId('thread')).toContainText('lines 2-4')

  await card.getByRole('button', { name: 'Approve selection (3)' }).click()
  await expect(card.getByText(/^3\/\d+ lines approved$/)).toBeVisible()
})

test('dragging to the bottom edge scrolls and keeps extending the selection', async ({ page }) => {
  await page.setViewportSize({ width: 1500, height: 500 })
  const card = await openReview(page, 'scroll')
  await gutter(card, 3).scrollIntoViewIfNeeded()
  const from = await center(gutter(card, 3))

  await page.mouse.move(from.x, from.y)
  await page.mouse.down()
  await page.mouse.move(from.x, 498, { steps: 5 })
  await expect.poll(() => page.evaluate(() => window.scrollY)).toBeGreaterThan(300)
  await page.mouse.up()

  const approve = card.getByRole('button', { name: /^Approve selection \(\d+\)$/ })
  const count = Number((await approve.textContent())?.match(/\d+/)?.[0])
  expect(count).toBeGreaterThan(15)
})

test('dragging over the code text selects text to copy and leaves the line selection alone', async ({ page }) => {
  const card = await openReview(page, 'copy')
  const first = card.locator('td.diff-code-insert', { hasText: 'ROWS.append(0)' })
  const last = card.locator('td.diff-code-insert', { hasText: 'ROWS.append(2)' })
  const from = await center(first)
  const to = await center(last)

  await page.mouse.move(from.x, from.y)
  await page.mouse.down()
  await page.mouse.move(to.x, to.y, { steps: 5 })
  await page.mouse.up()

  expect(await page.evaluate(() => window.getSelection()?.toString() ?? '')).toContain('ROWS.append(1)')
  await expect(card.getByRole('button', { name: /^Approve selection/ })).toHaveCount(0)
})

test('clicking a line number to comment leaves the lines to approve unselected', async ({ page }) => {
  const card = await openReview(page, 'comment')

  await gutter(card, 3).click()

  await expect(card.getByPlaceholder('Leave a comment (Markdown)')).toBeVisible()
  await expect(card.getByRole('button', { name: /^Approve selection/ })).toHaveCount(0)
})
