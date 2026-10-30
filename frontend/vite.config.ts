import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

const BACKEND_URL = 'http://127.0.0.1:8765'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: { '/api': { target: BACKEND_URL, changeOrigin: true } },
  },
  build: {
    outDir: '../src/bussola/static',
    emptyOutDir: true,
    license: { fileName: 'THIRD_PARTY_LICENSES.md' },
  },
  test: {
    environment: 'jsdom',
    include: ['src/**/*.test.{ts,tsx}'],
    setupFiles: ['./src/test/setup.ts'],
  },
})
