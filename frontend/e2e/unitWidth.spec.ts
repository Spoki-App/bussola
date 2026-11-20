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

function createRepository(name: string, file: string, base: string, head: string, lineLength = 60): string {
  const repo = join(root, name)
  mkdirSync(repo)
  git(repo, 'init', '-q', '-b', 'main')
  git(repo, 'config', 'user.email', 'e2e@example.com')
  git(repo, 'config', 'user.name', 'E2E Reviewer')
  git(repo, 'config', 'commit.gpgsign', 'false')
  writeFileSync(join(repo, 'pyproject.toml'), `[tool.ruff]\nline-length = ${String(lineLength)}\n`)
  writeFileSync(join(repo, file), base)
  git(repo, 'add', '-A')
  git(repo, 'commit', '-q', '-m', 'base')
  git(repo, 'checkout', '-q', '-b', 'wide')
  writeFileSync(join(repo, file), head)
  git(repo, 'commit', '-q', '-am', 'wide')
  return repo
}

async function openReview(page: Page, path: string): Promise<number> {
  await page.goto(`/?token=${E2E_TOKEN}`)
  const repo = await page.request.post('/api/repos', { data: { path } })
  const { id: repoId } = (await repo.json()) as { id: number }
  const review = await page.request.post(`/api/repos/${String(repoId)}/reviews`, { data: { head_ref: 'wide', base_ref: 'main' } })
  const { id: reviewId } = (await review.json()) as { id: number }
  await page.goto(`/reviews/${String(reviewId)}`)
  return reviewId
}

async function box(locator: Locator) {
  return (await locator.boundingBox()) ?? { x: 0, y: 0, width: 0, height: 0 }
}

async function stepTo(button: Locator, label: string) {
  for (let step = 0; step < 6 && (await button.textContent()) !== label; step++) {
    await button.click()
  }
  await expect(button).toHaveText(label)
}

async function fitsOnOneRow(card: Locator, text: string): Promise<boolean> {
  const long = card.locator('td.diff-code', { hasText: text })
  const short = card.locator('td.diff-code', { hasText: 'return value' })
  return (await box(long)).height <= (await box(short)).height + 1
}

async function fitsTheLimit(card: Locator): Promise<boolean> {
  return (await fitsOnOneRow(card, 'value = "')) && !(await fitsOnOneRow(card, 'other = "'))
}

test.beforeAll(() => {
  root = mkdtempSync(join(tmpdir(), 'bussola-e2e-width-'))
})

test.afterAll(() => {
  rmSync(root, { recursive: true, force: true })
})

test.use({ viewport: { width: 1800, height: 1000 } })

async function fillsTheColumn(card: Locator, units: Locator): Promise<boolean> {
  const padding = await units.evaluate((element) => parseFloat(getComputedStyle(element).paddingLeft) + parseFloat(getComputedStyle(element).paddingRight))
  return Math.abs((await box(card)).width - ((await box(units)).width - padding)) < 2
}

test('the column of units follows the repository line length, preset steps and full width', async ({ page }) => {
  await openReview(page, createRepository('widths', 'wide.py', 'def wide():\n    return 0\n', `def wide():\n${AT_LIMIT}\n${OVER_LIMIT}\n    return value\n`))
  const units = page.locator('main.units')
  const card = page.locator('article.unit-card', { hasText: 'wide' })
  const button = page.getByRole('button', { name: /^Width / })

  await expect(button).toHaveText('Width Auto 60')
  await expect(button).toHaveAttribute('title', /60, from pyproject\.toml ruff/)
  await expect(card.locator('table.diff-split')).toBeVisible()
  expect(await fitsTheLimit(card)).toBe(true)
  expect(await fillsTheColumn(card, units)).toBe(true)
  const splitAutoWidth = (await box(card)).width

  await page.getByRole('tab', { name: 'Unified' }).click()
  await expect(card.locator('table.diff-unified')).toBeVisible()
  expect(await fitsTheLimit(card)).toBe(true)
  expect(await fillsTheColumn(card, units)).toBe(true)
  const autoWidth = (await box(units)).width

  await stepTo(button, 'Width 80')
  expect(await fitsOnOneRow(card, 'other = "')).toBe(true)
  expect((await box(units)).width).toBeGreaterThan(autoWidth)

  await stepTo(button, 'Width Full')
  expect(await fillsTheColumn(card, units)).toBe(true)
  expect(splitAutoWidth).toBeLessThan((await box(units)).width - 100)

  await page.reload()
  await expect(button).toHaveText('Width Full')

  await stepTo(button, 'Width 160')
  await page.setViewportSize({ width: 3000, height: 1000 })
  await page.getByRole('tab', { name: 'Split' }).click()
  await expect(card.locator('table.diff-split')).toBeVisible()
  expect(await fitsOnOneRow(card, 'other = "')).toBe(true)
  expect(await fillsTheColumn(card, units)).toBe(true)
  expect((await box(page.locator('.review-page'))).width).toBeGreaterThan(1800)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true)

  await page.setViewportSize({ width: 700, height: 900 })
  const cardBox = await box(card)
  const unitsBox = await box(units)
  expect(cardBox.x + cardBox.width).toBeLessThanOrEqual(unitsBox.x + unitsBox.width)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true)
})

const LONG_NAME = 'synchronise_every_catalogue_item_with_the_remote_hub_and_report'

async function besideTheName(card: Locator, button: Locator): Promise<boolean> {
  const name = await box(card.locator('.qualified-name'))
  const target = await box(button)
  return target.x >= name.x + name.width && target.y < name.y + name.height && target.y + target.height > name.y
}

async function headerFits(card: Locator): Promise<boolean> {
  return card.locator('.unit-header').evaluate((header) => header.scrollWidth <= header.clientWidth && [...header.querySelectorAll('button')].every((button) => button.getBoundingClientRect().right <= header.getBoundingClientRect().right + 1))
}

test('the approve button stays next to the name of a narrow unit, which is cut instead, and the header never overflows', async ({ page }) => {
  const repo = createRepository('long-name', 'catalogue.py', `def ${LONG_NAME}():\n    return 0\n`, `def ${LONG_NAME}():\n    return 1\n`, 50)
  const reviewId = await openReview(page, repo)
  await page.getByRole('tab', { name: 'Unified' }).click()
  const card = page.locator('article.unit-card', { hasText: LONG_NAME })
  const approve = card.getByRole('button', { name: 'Approve', exact: true })
  await expect(approve).toBeVisible()
  expect(await besideTheName(card, approve)).toBe(true)
  expect(await card.locator('.qualified-name').evaluate((element) => element.scrollWidth > element.clientWidth)).toBe(true)

  await approve.click()
  await expect(card.getByText('Approved', { exact: true })).toBeVisible()
  writeFileSync(join(repo, 'catalogue.py'), `def ${LONG_NAME}():\n    return 2\n`)
  git(repo, 'commit', '-q', '-am', 'again')
  await page.request.post(`/api/reviews/${String(reviewId)}/refresh`, { data: { fetch: false } })
  await page.reload()
  await expect(card.getByRole('group', { name: 'Diff mode' })).toBeVisible()
  expect(await besideTheName(card, approve)).toBe(true)
  expect(await headerFits(card)).toBe(true)

  await page.setViewportSize({ width: 360, height: 900 })
  await expect(approve).toBeVisible()
  expect(await headerFits(card)).toBe(true)
})
