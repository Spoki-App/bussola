import { defineConfig, devices } from '@playwright/test'

import { E2E_PORT } from './e2e/constants.ts'

export default defineConfig({
  testDir: './e2e',
  globalSetup: './e2e/global-setup.ts',
  timeout: 60_000,
  expect: { timeout: 10_000 },
  retries: 0,
  reporter: 'list',
  use: {
    baseURL: `http://127.0.0.1:${String(E2E_PORT)}`,
    trace: 'retain-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'], viewport: { width: 1500, height: 1000 } } }],
})
