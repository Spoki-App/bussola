import { expect, test } from '@playwright/test'

import { E2E_TOKEN } from './constants.ts'

test('review a branch: open it, approve a unit and comment on a line', async ({ page }) => {
  await page.goto(`/?token=${E2E_TOKEN}`)
  await expect(page.getByRole('heading', { name: 'demo' })).toBeVisible()

  await page.getByRole('button', { name: 'New review' }).click()
  await page.getByRole('button', { name: 'Start review' }).click()
  await expect(page.getByRole('heading', { name: /feature\s+into\s+main/ })).toBeVisible()

  const card = page.locator('article.unit-card', { hasText: 'total' })
  await card.getByRole('button', { name: 'Approve', exact: true }).click()
  await expect(card.getByText('Approved', { exact: true })).toBeVisible()
  await expect(page.getByRole('progressbar', { name: 'Review progress' })).toHaveAttribute('aria-valuenow', '100')
  await expect(card.getByRole('button', { name: 'Expand unit' })).toBeVisible()

  await card.getByRole('button', { name: 'Expand unit' }).click()
  await card.locator('td.diff-gutter', { hasText: /^2$/ }).first().click()
  await card.getByPlaceholder('Leave a comment (Markdown)').fill('Is `len` needed here?')
  await card.getByRole('button', { name: 'Start thread' }).click()

  await expect(card.getByTestId('thread')).toContainText('Is len needed here?')
  await expect(card.getByText('1 open thread')).toBeVisible()
})

test('narrow screens show the files above the units, which stay visible and hoverable', async ({ page }) => {
  await page.setViewportSize({ width: 600, height: 800 })
  await page.goto(`/?token=${E2E_TOKEN}`)
  await page.getByRole('link', { name: /feature\s+into\s+main/ }).first().click()

  const sidebar = page.getByRole('complementary', { name: 'Files' })
  const card = page.locator('article.unit-card', { hasText: 'total' })
  await expect(card).toBeVisible()
  await card.locator('.unit-header').hover({ timeout: 5000 })

  const sidebarBox = await sidebar.boundingBox()
  const cardBox = await card.boundingBox()
  expect(sidebarBox && cardBox && sidebarBox.y + sidebarBox.height <= cardBox.y).toBe(true)
  expect(sidebarBox?.height).toBeLessThan(800)
})

test('a review link with a path and line expands and focuses the unit containing that line', async ({ page }) => {
  await page.goto(`/?token=${E2E_TOKEN}`)
  const href = await page.getByRole('link', { name: /feature\s+into\s+main/ }).first().getAttribute('href')

  await page.goto(`${href ?? ''}?path=app.py&line=2`)

  const card = page.locator('article.unit-card', { hasText: 'total' })
  await expect(card).toHaveClass(/focused/)
  await expect(card.getByRole('button', { name: 'Collapse unit' })).toBeVisible()
})

test('a review link with a thread opens its collapsed unit and shows the thread', async ({ page }) => {
  await page.goto(`/?token=${E2E_TOKEN}`)
  const href = (await page.getByRole('link', { name: /feature\s+into\s+main/ }).first().getAttribute('href')) ?? ''
  await page.goto(href)
  const card = page.locator('article.unit-card', { hasText: 'total' })
  await card.getByRole('button', { name: 'Expand unit' }).click()
  const threadId = (await card.getByTestId('thread').getAttribute('id')) ?? ''

  await page.goto(`${href}?thread=${threadId.replace(/^thread-/, '')}`)

  await expect(card.getByRole('button', { name: 'Collapse unit' })).toBeVisible()
  await expect(page.locator(`#${threadId}`)).toBeInViewport()
})

test('a link to the review already open is applied too', async ({ page }) => {
  await page.goto(`/?token=${E2E_TOKEN}`)
  await page.getByRole('link', { name: /feature\s+into\s+main/ }).first().click()
  const card = page.locator('article.unit-card', { hasText: 'total' })
  await expect(card.getByRole('button', { name: 'Expand unit' })).toBeVisible()

  await page.evaluate("history.pushState(null, '', location.pathname + '?path=app.py&line=2'); dispatchEvent(new Event('bussola:navigate'))")

  await expect(card).toHaveClass(/focused/)
  await expect(card.getByRole('button', { name: 'Collapse unit' })).toBeVisible()
  await expect(page).toHaveURL(/\/reviews\/\d+$/)

  for (const query of ['?path=missing.py', '?path=missing.py', '?path=app.py&line=2']) {
    await page.evaluate(`history.pushState(null, '', location.pathname + '${query}'); dispatchEvent(new Event('bussola:navigate'))`)
    await expect(page).toHaveURL(/\/reviews\/\d+$/)
  }
})

test('a pull request link of an unknown repository opens the add repository flow prefilled', async ({ page }) => {
  await page.goto(`/?token=${E2E_TOKEN}`)

  await page.goto('/github.com/acme/no-such-repository/pull/7?path=app.py&line=2')

  await expect(page.getByRole('heading', { name: 'Add acme/no-such-repository' })).toBeVisible()
  await expect(page.getByText('git clone https://github.com/acme/no-such-repository.git')).toBeVisible()
  expect(new URL(page.url()).searchParams.get('add_repo')).toBe('/github.com/acme/no-such-repository/pull/7?path=app.py&line=2')

  await page.getByRole('button', { name: 'Browse...' }).first().click()

  await expect(page.getByRole('dialog', { name: 'Add a repository' })).toBeVisible()
  await expect(page.getByLabel('Filter repositories')).toHaveValue('no-such-repository')
})
