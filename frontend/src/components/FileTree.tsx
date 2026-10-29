import { useState, type CSSProperties } from 'react'

import type { FileNode } from '../review/fileTree'

interface Props {
  nodes: FileNode[]
  activePath?: string
  onSelect: (path: string) => void
}

export function FileTree({ nodes, activePath, onSelect }: Props) {
  const [closed, setClosed] = useState<ReadonlySet<string>>(new Set())
  if (nodes.length === 0) {
    return <p className="muted">No files.</p>
  }
  const toggle = (path: string) => {
    const next = new Set(closed)
    if (!next.delete(path)) {
      next.add(path)
    }
    setClosed(next)
  }
  return (
    <nav aria-label="Changed files">
      <ul className="file-tree" role="tree">
        <FileNodes nodes={nodes} depth={0} closed={closed} activePath={activePath} onToggle={toggle} onSelect={onSelect} />
      </ul>
    </nav>
  )
}

interface NodesProps {
  nodes: FileNode[]
  depth: number
  closed: ReadonlySet<string>
  activePath?: string
  onToggle: (path: string) => void
  onSelect: (path: string) => void
}

function FileNodes({ nodes, depth, closed, activePath, onToggle, onSelect }: NodesProps) {
  const indent = { '--depth': depth } as CSSProperties
  return nodes.map((node) => {
    if (node.kind === 'file') {
      const { group } = node
      return (
        <li key={group.path} role="treeitem" aria-selected={group.path === activePath} className={`${group.complete ? 'complete' : ''}${group.path === activePath ? ' active' : ''}`}>
          <button type="button" style={indent} onClick={() => { onSelect(group.path) }} title={group.path}>
            <FileIcon />
            <span className="file-name">{node.name}</span>
            <Progress todo={group.todo} complete={group.complete} />
          </button>
        </li>
      )
    }
    const open = !closed.has(node.path)
    return (
      <li key={node.path} role="treeitem" aria-expanded={open} className={node.complete ? 'complete' : ''}>
        <button type="button" style={indent} onClick={() => { onToggle(node.path) }} title={node.path}>
          <span className="tree-chevron" aria-hidden="true">{open ? '▾' : '▸'}</span>
          <FolderIcon />
          <span className="file-name">{node.name}</span>
          {!open && <Progress todo={node.todo} complete={node.complete} />}
        </button>
        {open && (
          <ul role="group">
            <FileNodes nodes={node.children} depth={depth + 1} closed={closed} activePath={activePath} onToggle={onToggle} onSelect={onSelect} />
          </ul>
        )}
      </li>
    )
  })
}

function Progress({ todo, complete }: { todo: number; complete: boolean }) {
  return complete ? <span className="check" aria-label="All approved">{'✓'}</span> : <span className="count" aria-label={`${String(todo)} to review`}>{todo}</span>
}

function FolderIcon() {
  return (
    <svg className="tree-icon" viewBox="0 0 16 16" aria-hidden="true">
      <path d="M1.75 2.5h4.1c.4 0 .78.18 1.03.5l.9 1.1h6.47c.41 0 .75.34.75.75v8.4c0 .41-.34.75-.75.75H1.75A.75.75 0 0 1 1 13.25V3.25c0-.41.34-.75.75-.75Z" />
    </svg>
  )
}

function FileIcon() {
  return (
    <svg className="tree-icon" viewBox="0 0 16 16" aria-hidden="true">
      <path d="M3.75 1.5h5.6l3.9 3.9v8.85c0 .41-.34.75-.75.75h-8.75a.75.75 0 0 1-.75-.75V2.25c0-.41.34-.75.75-.75ZM9 2v3.5c0 .28.22.5.5.5H13" />
    </svg>
  )
}
