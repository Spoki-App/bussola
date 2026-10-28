import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { Markdown } from './Markdown'

vi.mock('../markdown/mermaid', () => ({
  renderMermaid: (code: string) => Promise.resolve(`<svg data-code="${code.split('\n')[0]}"></svg>`),
}))

const FENCE = '```'

function renderMarkdown(text: string) {
  return render(<Markdown text={text} />).container
}

describe('Markdown', () => {
  it('renders GitHub tables', () => {
    const container = renderMarkdown('| | events |\n|---|---|\n| today | ~2.3M |')

    expect(container.querySelector('table td')?.textContent).toBe('today')
  })

  it('renders GitHub alerts', () => {
    const container = renderMarkdown('> [!NOTE]\n> **Medium Risk**\n> Changes when updates arrive.')

    const alert = container.querySelector('.markdown-alert.markdown-alert-note')
    expect(alert?.querySelector('.markdown-alert-title')?.textContent).toBe('Note')
    expect(alert?.querySelector('strong')?.textContent).toBe('Medium Risk')
    expect(alert?.textContent).not.toContain('[!NOTE]')
    expect(alert?.querySelector('.markdown-alert-title + p')?.firstChild?.nodeName).toBe('STRONG')
  })

  it('keeps safe HTML and drops comments and scripts', () => {
    const container = renderMarkdown('<!-- hidden -->\n<sup>Reviewed by bot</sup>\n\n<script>alert(1)</script>')

    expect(container.querySelector('sup')?.textContent).toBe('Reviewed by bot')
    expect(container.innerHTML).not.toContain('hidden')
    expect(container.querySelector('script')).toBeNull()
  })

  it('loads GitHub attachments through rtool', () => {
    renderMarkdown('![Where the marker sits](https://github.com/user-attachments/assets/ad4619dd-3cdd-4568-a5e3-2fad4b1db525)')

    expect(screen.getByAltText('Where the marker sits').getAttribute('src')).toBe(
      '/api/forge/asset?url=https%3A%2F%2Fgithub.com%2Fuser-attachments%2Fassets%2Fad4619dd-3cdd-4568-a5e3-2fad4b1db525',
    )
  })

  it('highlights code blocks', () => {
    const container = renderMarkdown(`${FENCE}python\ndef send_if_held() -> None:\n    pass\n${FENCE}`)

    expect(container.querySelector('pre code .hljs-keyword')?.textContent).toBe('def')
  })

  it('keeps line breaks and links cross-repository references like GitHub', () => {
    const container = renderMarkdown('**Overview**\nPairs with Spoki-App/spoki-ai#517.')

    expect(container.querySelector('br')).not.toBeNull()
    expect(screen.getByRole('link', { name: 'Spoki-App/spoki-ai#517' }).getAttribute('href')).toBe('https://github.com/Spoki-App/spoki-ai/issues/517')
  })

  it('draws mermaid diagrams', async () => {
    renderMarkdown(`${FENCE}mermaid\nsequenceDiagram\n  A->>B: hello\n${FENCE}`)

    const diagram = await screen.findByRole('img', { name: 'Mermaid diagram' })
    expect(diagram.querySelector('svg')?.getAttribute('data-code')).toBe('sequenceDiagram')
  })
})
