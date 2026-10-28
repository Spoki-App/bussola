import { useEffect, useState } from 'react'

import { renderMermaid } from '../markdown/mermaid'

type Rendering = { status: 'pending' } | { status: 'done'; svg: string } | { status: 'failed' }

export function MermaidDiagram({ code }: { code: string }) {
  const [rendering, setRendering] = useState<Rendering>({ status: 'pending' })

  useEffect(() => {
    let current = true
    renderMermaid(code).then(
      (svg) => { if (current) setRendering({ status: 'done', svg }) },
      () => { if (current) setRendering({ status: 'failed' }) },
    )
    return () => {
      current = false
    }
  }, [code])

  if (rendering.status === 'done') {
    return <div className="mermaid-diagram" role="img" aria-label="Mermaid diagram" dangerouslySetInnerHTML={{ __html: rendering.svg }} />
  }
  return (
    <div className="mermaid-diagram">
      {rendering.status === 'failed' && <p className="muted">This mermaid diagram could not be drawn.</p>}
      <pre>
        <code>{code}</code>
      </pre>
    </div>
  )
}
