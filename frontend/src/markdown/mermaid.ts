let diagrams = 0

function prefersDark(): boolean {
  return window.matchMedia('(prefers-color-scheme: dark)').matches
}

export async function renderMermaid(code: string): Promise<string> {
  const { default: mermaid } = await import('mermaid')
  mermaid.initialize({ startOnLoad: false, securityLevel: 'strict', theme: prefersDark() ? 'dark' : 'default' })
  diagrams += 1
  const { svg } = await mermaid.render(`rtool-mermaid-${String(diagrams)}`, code)
  return svg
}
