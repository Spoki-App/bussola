import ReactMarkdown from 'react-markdown'

export function Markdown({ text }: { text: string }) {
  return (
    <div className="markdown">
      <ReactMarkdown skipHtml>{text}</ReactMarkdown>
    </div>
  )
}
