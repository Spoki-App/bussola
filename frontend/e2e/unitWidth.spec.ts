import { execFileSync } from 'node:child_process'
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

import { expect, test, type Locator, type Page } from '@playwright/test'

import { E2E_TOKEN } from './constants.ts'

const AT_LIMIT = `    value = "${'x'.repeat(46)}"`
const OVER_LIMIT = `    other = "${'y'.repeat(48)}"`

let root = ''

function git(repo: string, ...args: string[]) {
  execFileSync('git', args, { cwd: repo, stdio: 'ignore' })
}

function createRepository(): string {
  const repo = join(root, 'widths')
  mkdirSync(repo)
  git(repo, 'init', '-q', '-b', 'main')
  git(repo, 'config', 'user.email', 'e2e@example.com')
  git(repo, 'config', 'user.name', 'E2E Reviewer')
  git(repo, 'config', 'commit.gpgsign', 'false')
  writeFileSync(join(repo, 'pyproject.toml'), '[tool.ruff]\nline-length = 60\n')
  writeFileSync(join(repo, 'wide.py'), 'def wide():\n    return 0\n')
  git(repo, 'add', '-A')
  git(repo, 'commit', '-q', '-m', 'base')
  git(repo, 'checkout', '-q', '-b', 'wide')
  writeFileSync(join(repo, 'wide.py'), `def wide():\n${AT_LIMIT}\n${OVER_LIMIT}\n    return value\n`)
  git(repo, 'commit', '-q', '-am', 'wide')
  return repo
}

async function openReview(page: Page) {
  await page.goto(`/?token=${E2E_TOKEN}`)
  const repo = await page.request.post('/api/repos', { data: { path: createRepository() } })
  const { id: repoId } = (await repo.json()) as { id: number }
  const review = await page.request.post(`/api/repos/${String(repoId)}/reviews`, { data: { head_ref: 'wide', base_ref: 'main' } })
  const { id: reviewId } = (await review.json()) as { id: number }
  await page.goto(`/reviews/${String(reviewId)}`)
}

async function height(cell: Locator): Promise<number> {
  return (await cell.boundingBox())?.height ?? 0
}

async function fitsOnOneRow(card: Locator, text: string): Promise<boolean> {
  const long = card.locator('td.diff-code', { hasText: text })
  const short = card.locator('td.diff-code', { hasText: 'return value' })
  return (await height(long)) <= (await height(short)) + 1
}

async function fitsTheLimit(card: Locator): Promise<boolean> {
  return (await fitsOnOneRow(card, 'value = "')) && !(await fitsOnOneRow(card, 'other = "'))
}

async function width(locator: Locator): Promise<number> {
  return (await locator.boundingBox())?.width ?? 0
}

test.beforeAll(() => {
  root = mkdtempSync(join(tmpdir(), 'bussola-e2e-width-'))
})

test.afterAll(() => {
  rmSync(root, { recursive: true, force: true })
})

test.use({ viewport: { width: 1800, height: 1000 } })

test('the unit box follows the repository line length, preset steps and full width', async ({ page }) => {
  await openReview(page)
  const units = page.locator('main.units')
  const card = page.locator('article.unit-card', { hasText: 'wide' })
  const button = page.getByRole('button', { name: /^Width / })

  await expect(button).toHaveText('Width Auto 60')
  await expect(button).toHaveAttribute('title', /60, from pyproject\.toml ruff/)
  await expect(card.locator('table.diff-split')).toBeVisible()
  expect(await fitsTheLimit(card)).toBe(true)
  expect(await width(card)).toBeLessThan((await width(units)) - 100)

  await page.getByRole('tab', { name: 'Unified' }).click()
  await expect(card.locator('table.diff-unified')).toBeVisible()
  expect(await fitsTheLimit(card)).toBe(true)
  const autoWidth = await width(card)

  await button.click()
  await expect(button).toHaveText('Width 80')
  expect(await fitsOnOneRow(card, 'other = "')).toBe(true)
  expect(await width(card)).toBeGreaterThan(autoWidth)

  await button.click()
  await button.click()
  await button.click()
  await button.click()
  await expect(button).toHaveText('Width Full')
  const padding = await units.evaluate((element) => parseFloat(getComputedStyle(element).paddingLeft) + parseFloat(getComputedStyle(element).paddingRight))
  expect(Math.abs((await width(card)) - ((await width(units)) - padding))).toBeLessThan(2)

  await page.reload()
  await expect(button).toHaveText('Width Full')

  await button.click()
  await expect(button).toHaveText('Width Auto 60')
  await button.click()
  await button.click()
  await button.click()
  await button.click()
  await expect(button).toHaveText('Width 160')
  await page.setViewportSize({ width: 700, height: 900 })
  const cardBox = await card.boundingBox()
  const unitsBox = await units.boundingBox()
  expect((cardBox?.x ?? 0) + (cardBox?.width ?? 0)).toBeLessThanOrEqual((unitsBox?.x ?? 0) + (unitsBox?.width ?? 0))
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true)
})
