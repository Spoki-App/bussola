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

test('the header of an open unit stays below the file header while its diff scrolls past', async ({ page }) => {
  await page.setViewportSize({ width: 1000, height: 260 })
  await page.goto(`/?token=${E2E_TOKEN}`)
  await page.getByRole('link', { name: /feature\s+into\s+main/ }).first().click()
  const card = page.locator('article.unit-card', { hasText: 'total' })
  await card.getByRole('button', { name: 'Expand unit' }).click()
  await expect(card.getByTestId('thread')).toBeVisible()
  const fileHeader = page.locator('.file-header').first()

  await card.evaluate((element) => { window.scrollBy(0, element.getBoundingClientRect().top - 20) })

  const fileHeaderBox = await fileHeader.boundingBox()
  const unitHeaderBox = await card.locator('.unit-header').boundingBox()
  const cardBox = await card.boundingBox()
  expect(cardBox && fileHeaderBox && cardBox.y < fileHeaderBox.y + fileHeaderBox.height).toBe(true)
  expect(unitHeaderBox?.y).toBeCloseTo((fileHeaderBox?.y ?? 0) + (fileHeaderBox?.height ?? 0), 0)
})

test('the unit filters sit in the files bar, and above the units while it is hidden', async ({ page }) => {
  await page.goto(`/?token=${E2E_TOKEN}`)
  await page.getByRole('link', { name: /feature\s+into\s+main/ }).first().click()
  const sidebar = page.getByRole('complementary', { name: 'Files' })
  const search = page.getByRole('searchbox', { name: 'Find units by module, name or path' })

  await expect(sidebar.getByRole('tablist', { name: 'Filter units' })).toBeVisible()
  await expect(sidebar.getByRole('tablist', { name: 'Diff layout' })).toBeVisible()
  await search.fill('total')

  await sidebar.getByRole('button', { name: 'Files' }).click()

  await expect(sidebar.getByRole('tablist', { name: 'Filter units' })).toHaveCount(0)
  await expect(page.locator('.review-summary').getByRole('tablist', { name: 'Filter units' })).toBeVisible()
  await expect(search).toHaveValue('total')
})

test('the unit filter and the diff layout are kept after a reload and in a new tab', async ({ page, context }) => {
  await page.goto(`/?token=${E2E_TOKEN}`)
  await page.getByRole('link', { name: /feature\s+into\s+main/ }).first().click()
  const sidebar = (on: typeof page) => on.getByRole('complementary', { name: 'Files' })
  await sidebar(page).getByRole('tablist', { name: 'Filter units' }).getByRole('tab', { name: 'To review' }).click()
  await sidebar(page).getByRole('tablist', { name: 'Diff layout' }).getByRole('tab', { name: 'Unified' }).click()

  for (const view of [page, await context.newPage()]) {
    await (view === page ? view.reload() : view.goto(page.url()))
    await expect(sidebar(view).getByRole('tablist', { name: 'Filter units' }).getByRole('tab', { name: 'To review' })).toHaveAttribute('aria-selected', 'true')
    await expect(sidebar(view).getByRole('tablist', { name: 'Diff layout' }).getByRole('tab', { name: 'Unified' })).toHaveAttribute('aria-selected', 'true')
  }
})

test('the wrap button of an open unit turns line wrap off and on, and split view then scrolls each side on its own', async ({ page }) => {
  await page.goto(`/?token=${E2E_TOKEN}`)
  await page.getByRole('link', { name: /feature\s+into\s+main/ }).first().click()
  const layout = page.getByRole('complementary', { name: 'Files' }).getByRole('tablist', { name: 'Diff layout' })
  const card = page.locator('article.unit-card', { hasText: 'total' })
  await card.getByRole('button', { name: 'Expand unit' }).click()
  const wrap = card.getByRole('button', { name: 'Wrap long lines' })

  await layout.getByRole('tab', { name: 'Unified' }).click()
  await card.hover()
  await expect(wrap).toHaveCSS('opacity', '1')
  await expect(wrap).toHaveAttribute('aria-pressed', 'true')

  await wrap.click()
  await expect(page.locator('html')).toHaveAttribute('data-diff-wrap', 'off')
  await expect(wrap).toHaveAttribute('aria-pressed', 'false')

  await layout.getByRole('tab', { name: 'Split' }).click()
  await expect(card.locator('.split-scroll table.diff-split')).toBeVisible()
  await expect(card.locator('table.diff-split td.diff-code').first()).toHaveCSS('white-space', 'pre')

  await card.hover()
  await wrap.click()
  await expect(page.locator('html')).toHaveAttribute('data-diff-wrap', 'on')
  await expect(card.locator('.split-scroll')).toHaveCount(0)
})

test('the window title names the open review and goes back to bussola elsewhere', async ({ page }) => {
  await page.goto(`/?token=${E2E_TOKEN}`)
  await expect(page).toHaveTitle('bussola')

  await page.getByRole('link', { name: /feature\s+into\s+main/ }).first().click()
  await expect(page).toHaveTitle('demo feature')

  await page.getByRole('link', { name: 'demo', exact: true }).click()
  await expect(page).toHaveTitle('bussola')
})

test('settings open with the search focused, move between categories with the arrow keys and close with Esc', async ({ page }) => {
  await page.goto(`/?token=${E2E_TOKEN}`)
  await page.getByRole('button', { name: 'Settings' }).click()

  const dialog = page.getByRole('dialog', { name: 'Settings' })
  await expect(dialog.getByRole('searchbox', { name: 'Search settings' })).toBeFocused()

  await dialog.getByRole('button', { name: 'Pull requests' }).focus()
  await page.keyboard.press('ArrowDown')
  await expect(dialog.getByRole('button', { name: 'Repositories' })).toBeFocused()
  await expect(dialog.getByRole('heading', { name: 'Add repository' })).toBeVisible()

  await dialog.getByRole('searchbox', { name: 'Search settings' }).fill('wrap')
  await expect(dialog.getByRole('heading', { name: 'Line wrap' })).toBeVisible()

  await page.keyboard.press('Escape')
  await expect(dialog).toBeHidden()
})
