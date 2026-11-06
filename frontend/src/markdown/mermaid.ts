import { isDarkTheme } from '../settings/theme'

let diagrams = 0

export async function renderMermaid(code: string): Promise<string> {
  const { default: mermaid } = await import('mermaid')
  mermaid.initialize({ startOnLoad: false, securityLevel: 'strict', theme: isDarkTheme() ? 'dark' : 'default' })
  diagrams += 1
  const { svg } = await mermaid.render(`bussola-mermaid-${String(diagrams)}`, code)
  return svg
}
