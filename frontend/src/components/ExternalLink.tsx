import type { MouseEvent, ReactNode } from 'react'

import { openExternal } from '../api/browser'

interface Props {
  href: string
  className?: string
  title?: string
  children: ReactNode
}

export function ExternalLink({ href, className, title, children }: Props) {
  const onClick = (event: MouseEvent<HTMLAnchorElement>) => {
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || event.button !== 0) {
      return
    }
    event.preventDefault()
    openExternal(href)
  }
  return (
    <a href={href} className={className} title={title} target="_blank" rel="noreferrer" onClick={onClick}>
      {children}
    </a>
  )
}
