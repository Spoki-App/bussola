import ReactMarkdown, { type Components } from 'react-markdown'

import { ExternalLink } from './ExternalLink'

const components: Components = {
  a: ({ href, children }) => (href ? <ExternalLink href={href}>{children}</ExternalLink> : <span>{children}</span>),
}

export function Markdown({ text }: { text: string }) {
  return (
    <div className="markdown">
      <ReactMarkdown skipHtml components={components}>
        {text}
      </ReactMarkdown>
    </div>
  )
}
