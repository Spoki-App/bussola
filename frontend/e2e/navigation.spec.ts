/// <reference lib="dom" />
import { execFileSync } from 'node:child_process'
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join } from 'node:path'

import { expect, test, type Locator, type Page } from '@playwright/test'

import { E2E_TOKEN } from './constants.ts'

const HELPERS = 'def tidy(items):\n    return [item for item in items if item]\n'
const BASE_APP = 'def total(items):\n    return 0\n'
const FEATURE_APP = 'def total(items):\n    return sum(tidy(items))\n\n\ndef average(items):\n    return total(items) / len(items)\n'

let root = ''

function git(repo: string, ...args: string[]) {
  execFileSync('git', args, { cwd: repo, stdio: 'ignore' })
}

function commit(repo: string, files: Record<string, string>) {
  for (const [path, content] of Object.entries(files)) {
    mkdirSync(dirname(join(repo, path)), { recursive: true })
    writeFileSync(join(repo, path), content)
  }
  git(repo, 'add', '-A')
  git(repo, 'commit', '-q', '-m', 'change')
}

function createRepository(): string {
  const repo = join(root, 'shop')
  mkdirSync(repo)
  git(repo, 'init', '-q', '-b', 'main')
  git(repo, 'config', 'user.email', 'e2e@example.com')
  git(repo, 'config', 'user.name', 'E2E Reviewer')
  git(repo, 'config', 'commit.gpgsign', 'false')
  commit(repo, { 'helpers.py': HELPERS, 'app.py': BASE_APP })
  git(repo, 'checkout', '-q', '-b', 'pricing')
  commit(repo, { 'app.py': FEATURE_APP })
  return repo
}

function pointOn(container: Locator, word: string) {
  return container.evaluate((element, target) => {
    const walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT)
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
      const index = (node.textContent ?? '').indexOf(target)
      if (index >= 0) {
        const range = document.createRange()
        range.setStart(node, index + 1)
        range.setEnd(node, index + 2)
        const box = range.getBoundingClientRect()
        return { x: box.left + box.width / 2, y: box.top + box.height / 2 }
      }
    }
    throw new Error(`No ${target} in ${element.textContent}`)
  }, word)
}

function underlined(page: Page) {
  return page.evaluate(() => {
    const highlight = CSS.highlights.get('navigation-link')
    const range = highlight ? [...highlight][0] : undefined
    return range instanceof Range ? range.toString() : null
  })
}

async function navigateFrom(page: Page, container: Locator, word: string) {
  const point = await pointOn(container, word)
  await page.keyboard.down('ControlOrMeta')
  await page.mouse.click(point.x, point.y)
  await page.keyboard.up('ControlOrMeta')
}

test.beforeAll(() => {
  root = mkdtempSync(join(tmpdir(), 'bussola-e2e-navigation-'))
})

test.afterAll(() => {
  rmSync(root, { recursive: true, force: true })
})

test('Cmd/Ctrl underlines navigable names, and Cmd/Ctrl+click jumps to code in the review and opens the rest in a modal', async ({ page }) => {
  await page.goto(`/?token=${E2E_TOKEN}`)
  const repo = await page.request.post('/api/repos', { data: { path: createRepository() } })
  const { id: repoId } = (await repo.json()) as { id: number }
  const review = await page.request.post(`/api/repos/${String(repoId)}/reviews`, { data: { head_ref: 'pricing', base_ref: 'main' } })
  const { id: reviewId } = (await review.json()) as { id: number }
  await page.goto(`/reviews/${String(reviewId)}`)

  const unitCard = (name: string) => page.locator('article.unit-card').filter({ has: page.locator('.unit-header', { hasText: name }) })
  const average = unitCard('average')
  const total = unitCard('total')
  const averageLine = average.locator('td.diff-code', { hasText: 'total(items) /' })

  const symbol = await pointOn(averageLine, 'total')
  await page.mouse.move(symbol.x, symbol.y)
  await page.keyboard.down('ControlOrMeta')
  await expect(averageLine).toHaveClass(/navigation-link/)
  await expect.poll(() => underlined(page)).toBe('total')
  const keyword = await pointOn(averageLine, 'return')
  await page.mouse.move(keyword.x, keyword.y)
  await expect(averageLine).not.toHaveClass(/navigation-link/)
  expect(await underlined(page)).toBeNull()
  await page.mouse.move(symbol.x, symbol.y)
  await expect(averageLine).toHaveClass(/navigation-link/)
  await page.keyboard.up('ControlOrMeta')
  await expect(averageLine).not.toHaveClass(/navigation-link/)
  expect(await underlined(page)).toBeNull()

  await navigateFrom(page, averageLine, 'total')
  await expect(total.locator('tr[class*="row-target"]')).toContainText('def total(items):')

  await navigateFrom(page, total.locator('td.diff-code', { hasText: 'sum(tidy' }), 'tidy')
  const modal = page.getByRole('dialog', { name: 'helpers.py:1' })
  await expect(modal.locator('.source-line.target')).toContainText('def tidy(items):')
  await expect(page.getByRole('dialog', { name: 'Definitions of tidy' })).toHaveCount(0)
  await expect(modal.getByRole('button', { name: 'Back' })).toBeDisabled()

  const modalLine = modal.locator('.source-line.target code')
  const definition = await pointOn(modalLine, 'tidy')
  await page.mouse.move(definition.x, definition.y)
  await page.keyboard.down('ControlOrMeta')
  await expect(modalLine).toHaveClass(/navigation-link/)
  await expect.poll(() => underlined(page)).toBe('tidy')
  await page.keyboard.up('ControlOrMeta')
  await expect(modalLine).not.toHaveClass(/navigation-link/)

  await navigateFrom(page, modalLine, 'tidy')
  await expect(modal).toBeHidden()
  await expect(total.locator('tr[class*="row-target"]')).toContainText('return sum(tidy(items))')
})
