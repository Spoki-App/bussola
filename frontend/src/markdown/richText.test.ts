import { describe, expect, it } from 'vitest'

import { richHtmlFor, richToMarkdown } from './richText'

function richElement(html: string): HTMLElement {
  const root = document.createElement('div')
  root.innerHTML = html
  return root
}

function richRoundTrip(markdown: string): string {
  const html = richHtmlFor(markdown)
  if (html === null) {
    throw new Error('not kept')
  }
  return richToMarkdown(richElement(html))
}

function markdownToRichHtml(markdown: string): string {
  return richHtmlFor(markdown) ?? ''
}

const KEPT_EXACTLY = {
  'code blocks': '```python\ndef f():\n    return 1\n```',
  mermaid: 'Look:\n\n```mermaid\ngraph TD\n  A --> B\n```',
  'task lists': '- [ ] todo\n- [x] done',
  alerts: '> [!NOTE]\n> Useful information.',
  brackets: 'Use a[0] or [x] here, not *this* \\*literal\\*',
  'code in lists': '- item\n\n  ```js\n  x()\n  ```',
  'reference links': 'See [x].\n\n[x]: https://example.com',
  footnotes: 'Hi[^1]\n\n[^1]: note',
  'formatting and line breaks': 'Some **bold**, *italic*, ~~gone~~ and `code`.\nNext line',
  images: '![screenshot.png](/api/attachments/x.png "t")',
  mentions: 'Hi @octocat, see #12',
}

const KEPT_AS_CONTENT = {
  tables: '| a | b |\n| :- | -: |\n| 1 | 2 |',
  'other markup': '# Title\n\n* a\n  * nested\n\n1. one\n2. two\n\n> quote\n\n***',
  'raw HTML': 'Text <sub>small</sub>\n\n<details>\n<summary>More</summary>\n\nBody\n</details>',
  'hard breaks': 'line  \nhard\\\nbreak',
}

describe('rich text round trip', () => {
  for (const [name, markdown] of Object.entries(KEPT_EXACTLY)) {
    it(`keeps ${name} unchanged`, () => {
      expect(richRoundTrip(markdown)).toBe(markdown)
    })
  }

  for (const [name, markdown] of Object.entries(KEPT_AS_CONTENT)) {
    it(`keeps the content of ${name}`, () => {
      const once = richRoundTrip(markdown)
      expect(richHtmlFor(once)).toBe(richHtmlFor(markdown))
    })
  }

  it('normalizes formatting the same way every time', () => {
    const once = richRoundTrip(KEPT_AS_CONTENT['other markup'])

    expect(once).toBe('# Title\n\n- a\n  - nested\n\n1. one\n2. two\n\n> quote\n\n---')
    expect(richRoundTrip(once)).toBe(once)
  })

  it('reports Markdown that rich text cannot keep', () => {
    expect(richHtmlFor('a&nbsp;b')).toBeNull()
  })
})

describe('rich text editing', () => {
  it('shows formatting and keeps code blocks as source', () => {
    const root = richElement(markdownToRichHtml('**bold**\n\n```mermaid\ngraph TD\n```'))

    expect(root.querySelector('strong')?.textContent).toBe('bold')
    const block = root.querySelector('pre')
    expect(block?.getAttribute('contenteditable')).toBe('false')
    expect(block?.dataset.markdown).toBe('```mermaid\ngraph TD\n```')
  })

  it('drops unsafe links', () => {
    expect(markdownToRichHtml('[x](javascript:alert(1))')).not.toContain('javascript')
  })

  it('turns typed formatting into Markdown and escapes look-alike syntax', () => {
    const root = richElement('<p>Make it <b>bold</b> and <i>italic</i><br>- not a list</p><ul><li>item</li></ul><blockquote><p>quoted</p></blockquote>')

    expect(richToMarkdown(root)).toBe('Make it **bold** and *italic*\n\\- not a list\n\n- item\n\n> quoted')
  })

  it('does not keep the no-break spaces browsers insert while typing', () => {
    expect(richToMarkdown(richElement('<p>@octocat </p><p>a b</p>'))).toBe('@octocat\n\na b')
  })
})
