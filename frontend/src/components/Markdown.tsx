import type { Element, ElementContent } from 'hast'
import ReactMarkdown, { type Components } from 'react-markdown'
import rehypeHighlight from 'rehype-highlight'
import rehypeRaw from 'rehype-raw'
import rehypeSanitize, { defaultSchema, type Options as SanitizeSchema } from 'rehype-sanitize'
import remarkBreaks from 'remark-breaks'
import remarkGfm from 'remark-gfm'

import { remarkAlerts } from '../markdown/alerts'
import { imageSource } from '../markdown/assets'
import { remarkGitHubReferences } from '../markdown/references'
import { ExternalLink } from './ExternalLink'
import { MermaidDiagram } from './MermaidDiagram'

const schema: SanitizeSchema = {
  ...defaultSchema,
  attributes: {
    ...defaultSchema.attributes,
    div: [...(defaultSchema.attributes?.div ?? []), ['className', 'markdown-alert', /^markdown-alert-[a-z]+$/]],
    p: [...(defaultSchema.attributes?.p ?? []), ['className', 'markdown-alert-title']],
  },
}

function textOf(node: ElementContent): string {
  if (node.type === 'text') {
    return node.value
  }
  return node.type === 'element' ? node.children.map(textOf).join('') : ''
}

function mermaidSource(pre: Element | undefined): string | null {
  const code = pre?.children[0]
  if (code?.type !== 'element' || code.tagName !== 'code') {
    return null
  }
  const classes = code.properties.className
  return Array.isArray(classes) && classes.includes('language-mermaid') ? textOf(code) : null
}

const components: Components = {
  a: ({ href, children }) => (href ? <ExternalLink href={href}>{children}</ExternalLink> : <span>{children}</span>),
  img: ({ src, alt, title, width, height }) => (typeof src === 'string' ? <img src={imageSource(src)} alt={alt} title={title} width={width} height={height} loading="lazy" /> : null),
  pre: ({ node, children }) => {
    const mermaid = mermaidSource(node)
    return mermaid === null ? <pre>{children}</pre> : <MermaidDiagram code={mermaid} />
  },
}

export function Markdown({ text }: { text: string }) {
  return (
    <div className="markdown">
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkBreaks, remarkAlerts, remarkGitHubReferences]}
        rehypePlugins={[rehypeRaw, [rehypeSanitize, schema], [rehypeHighlight, { plainText: ['mermaid'] }]]}
        components={components}
      >
        {text}
      </ReactMarkdown>
    </div>
  )
}
