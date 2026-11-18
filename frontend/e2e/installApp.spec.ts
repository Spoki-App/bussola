import { expect, test } from '@playwright/test'

import { E2E_PORT, E2E_TOKEN } from './constants.ts'

test('Chromium can install bussola as an app', async ({ page, context }) => {
  await page.goto(`/?token=${E2E_TOKEN}`)
  await expect(page.getByRole('heading', { name: 'demo' })).toBeVisible()

  const devtools = await context.newCDPSession(page)
  const { errors } = await devtools.send('Page.getAppManifest')
  const { installabilityErrors } = await devtools.send('Page.getInstallabilityErrors')

  expect(errors).toEqual([])
  expect(installabilityErrors.filter((error) => error.errorId !== 'in-incognito')).toEqual([])
})

test('the app explains how to start bussola while the server is down, then reloads', async ({ page, context }) => {
  await page.goto(`/?token=${E2E_TOKEN}`)
  await page.evaluate(() => navigator.serviceWorker.ready)

  await context.setOffline(true)
  await page.reload()

  await expect(page.getByRole('heading', { name: 'bussola is not running' })).toBeVisible()
  await expect(page.getByText(`bussola serve --port ${String(E2E_PORT)}`)).toBeVisible()
  await expect(page.getByRole('link', { name: 'bussola:// link' })).toHaveCount(0)

  let otherServerAnswers = 0
  await page.evaluate(() => Object.assign(window, { notReloaded: true }))
  await page.route('**/api/health', (route) => {
    otherServerAnswers += 1
    return route.fulfill({ json: { status: 'ok' } })
  })
  await expect.poll(() => otherServerAnswers, { timeout: 5000 }).toBeGreaterThan(1)
  expect(await page.evaluate(() => 'notReloaded' in window)).toBe(true)
  await page.unroute('**/api/health')

  await context.setOffline(false)

  await expect(page.getByRole('heading', { name: 'demo' })).toBeVisible()
})
