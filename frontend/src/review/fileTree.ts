import type { FileGroup } from './logic'

export type FileNode = DirectoryNode | { kind: 'file'; name: string; group: FileGroup }

export interface DirectoryNode {
  kind: 'directory'
  name: string
  path: string
  children: FileNode[]
  todo: number
  complete: boolean
}

export function buildFileTree(groups: FileGroup[]): FileNode[] {
  const root = directory('', '')
  for (const group of groups) {
    const parts = group.path.split('/')
    let current = root
    parts.slice(0, -1).forEach((part, index) => {
      const path = parts.slice(0, index + 1).join('/')
      const existing = current.children.find((child): child is DirectoryNode => child.kind === 'directory' && child.path === path)
      if (existing) {
        current = existing
      } else {
        const created = directory(part, path)
        current.children.push(created)
        current = created
      }
    })
    current.children.push({ kind: 'file', name: parts.at(-1) ?? group.path, group })
  }
  return finish(root).children
}

export function filesInOrder(nodes: FileNode[]): FileGroup[] {
  return nodes.flatMap((node) => (node.kind === 'file' ? [node.group] : filesInOrder(node.children)))
}

export function directoryPaths(nodes: FileNode[]): string[] {
  return nodes.flatMap((node) => (node.kind === 'directory' ? [node.path, ...directoryPaths(node.children)] : []))
}

function directory(name: string, path: string): DirectoryNode {
  return { kind: 'directory', name, path, children: [], todo: 0, complete: true }
}

function finish(node: DirectoryNode): DirectoryNode {
  const children = node.children.map((child) => (child.kind === 'directory' ? compact(finish(child)) : child)).sort(byKindThenName)
  const files = filesInOrder(children)
  return { ...node, children, todo: files.reduce((sum, group) => sum + group.todo, 0), complete: files.every((group) => group.complete) }
}

function compact(node: DirectoryNode): DirectoryNode {
  const only = node.children.length === 1 ? node.children[0] : null
  return only?.kind === 'directory' ? { ...only, name: `${node.name}/${only.name}` } : node
}

function byKindThenName(first: FileNode, second: FileNode): number {
  if (first.kind !== second.kind) {
    return first.kind === 'directory' ? -1 : 1
  }
  return first.name.localeCompare(second.name)
}
