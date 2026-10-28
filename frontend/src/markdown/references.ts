import type { Link, Root, Text } from 'mdast'
import { findAndReplace } from 'mdast-util-find-and-replace'

const REFERENCE = /\b([\w.-]+\/[\w.-]+)#(\d+)\b/g

function referenceLink(value: string, repository: string, number: string): Link {
  const text: Text = { type: 'text', value }
  return { type: 'link', url: `https://github.com/${repository}/issues/${number}`, children: [text] }
}

export function remarkGitHubReferences() {
  return (tree: Root) => {
    findAndReplace(tree, [REFERENCE, referenceLink])
  }
}
