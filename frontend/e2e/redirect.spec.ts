import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

import { expect, test, type Page } from '@playwright/test'

const REDIRECT_DIR = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..', 'redirect')
const SITE = 'https://bussola.test'
const SCRIPTS = new Set(['/page.js', '/link.js'])

async function serveRedirectPage(page: Page) {
  const requested: string[] = []
  await page.route(`${SITE}/**`, (route) => {
    const path = new URL(route.request().url()).pathname
    requested.push(path)
    if (SCRIPTS.has(path)) {
      return route.fulfill({ contentType: 'text/javascript', body: readFileSync(resolve(REDIRECT_DIR, path.slice(1))) })
    }
    return route.fulfill({ status: path === '/' ? 200 : 404, contentType: 'text/html', body: readFileSync(resolve(REDIRECT_DIR, 'index.html')) })
  })
  return requested
}

test('the redirect page opens the bussola link of its path and offers GitHub and the install steps', async ({ page }) => {
  const requested = await serveRedirectPage(page)
  await page.goto(`${SITE}/github.com/acme/shop/pull/482/files#discussion_r123`, { waitUntil: 'commit' })

  await expect(page.getByText('Opening bussola://github.com/acme/shop/pull/482/files#discussion_r123 in bussola.')).toBeVisible()
  await expect(page.getByRole('link', { name: 'Open in bussola' })).toHaveAttribute('href', 'bussola://github.com/acme/shop/pull/482/files#discussion_r123')
  await expect(page.getByText('Nothing happened?')).toBeVisible()
  await expect(page.getByRole('link', { name: 'Open it on GitHub' })).toHaveAttribute('href', 'https://github.com/acme/shop/pull/482/files#discussion_r123')
  await expect(page.getByRole('link', { name: 'Install bussola' })).toBeVisible()
  expect(requested.filter((path) => !SCRIPTS.has(path) && path !== '/favicon.svg')).toEqual(['/github.com/acme/shop/pull/482/files'])
})

test('the redirect page explains itself at the root', async ({ page }) => {
  await serveRedirectPage(page)
  await page.goto(`${SITE}/`)

  await expect(page.getByText('This page opens links in bussola')).toBeVisible()
  await expect(page.getByText(/^Opening/)).toBeHidden()
})
