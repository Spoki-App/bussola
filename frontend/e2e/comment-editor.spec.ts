import { execFileSync } from 'node:child_process'
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

import { expect, test } from '@playwright/test'

import { E2E_TOKEN } from './constants.ts'

const PIXEL_PNG = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==', 'base64')

let root = ''

function git(repo: string, ...args: string[]) {
  execFileSync('git', args, { cwd: repo, stdio: 'ignore' })
}

function createRepository(): string {
  const repo = join(root, 'notes')
  mkdirSync(repo)
  git(repo, 'init', '-q', '-b', 'main')
  git(repo, 'config', 'user.email', 'e2e@example.com')
  git(repo, 'config', 'user.name', 'E2E Reviewer')
  git(repo, 'config', 'commit.gpgsign', 'false')
  writeFileSync(join(repo, 'notes.py'), 'def note():\n    return 0\n')
  git(repo, 'add', '-A')
  git(repo, 'commit', '-q', '-m', 'base')
  git(repo, 'checkout', '-q', '-b', 'notes')
  writeFileSync(join(repo, 'notes.py'), 'def note():\n    text = "hi"\n    return text\n')
  git(repo, 'commit', '-q', '-am', 'notes')
  return repo
}

test.beforeAll(() => {
  root = mkdtempSync(join(tmpdir(), 'bussola-e2e-editor-'))
})

test.afterAll(() => {
  rmSync(root, { recursive: true, force: true })
})

test('write a comment in rich text with an image and send it as Markdown', async ({ page }) => {
  await page.goto(`/?token=${E2E_TOKEN}`)
  const repo = await page.request.post('/api/repos', { data: { path: createRepository() } })
  const { id: repoId } = (await repo.json()) as { id: number }
  const review = await page.request.post(`/api/repos/${String(repoId)}/reviews`, { data: { head_ref: 'notes', base_ref: 'main' } })
  const { id: reviewId } = (await review.json()) as { id: number }
  await page.goto(`/reviews/${String(reviewId)}`)

  const card = page.locator('article.unit-card', { hasText: 'note' })
  await card.locator('td.diff-gutter', { hasText: /^2$/ }).first().click()
  await card.getByRole('tab', { name: 'Rich text' }).click()
  const editor = card.getByRole('textbox', { name: 'Leave a comment (Markdown)' })
  await editor.click()
  await page.keyboard.type('Hello ')
  await page.keyboard.press('ControlOrMeta+b')
  await page.keyboard.type('bold')
  await page.keyboard.press('ControlOrMeta+b')
  await page.keyboard.type(' jk ')
  await expect(editor.locator('b, strong')).toHaveText('bold')

  await card.getByLabel('Attach image').setInputFiles({ name: 'pixel.png', mimeType: 'image/png', buffer: PIXEL_PNG })
  await expect(editor.locator('img')).toHaveAttribute('src', /^\/api\/attachments\/[0-9a-f]{64}\.png$/)

  await card.getByRole('tab', { name: 'Write' }).click()
  const markdown = card.getByPlaceholder('Leave a comment (Markdown)')
  await expect(markdown).toHaveValue(/^Hello \*\*bold\*\* jk !\[pixel\.png\]\(\/api\/attachments\/[0-9a-f]{64}\.png\)$/)
  await card.getByRole('tab', { name: 'Rich text' }).click()
  await card.getByRole('button', { name: 'Start thread' }).click()

  const thread = card.getByTestId('thread')
  await expect(thread.locator('.markdown strong')).toHaveText('bold')
  await expect(thread.locator('.markdown img')).toHaveJSProperty('naturalWidth', 1)
})
