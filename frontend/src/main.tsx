import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import '@fontsource-variable/instrument-sans/wdth.css'

import App from './App'
import './index.css'
import { applyCodeFont, loadCodeFont } from './settings/codeFont'
import { syncDiffWrap } from './settings/diffWrap'

applyCodeFont(loadCodeFont())
syncDiffWrap()

const queryClient = new QueryClient()
const rootElement = document.getElementById('root')
if (!rootElement) {
  throw new Error('Missing #root element')
}

createRoot(rootElement).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </StrictMode>,
)
