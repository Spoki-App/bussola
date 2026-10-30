import type { HunkTokens, TokenNode } from 'react-diff-view'

const NOT_INDENT = /[^ \t]/

interface IndentSplit {
  head: TokenNode[]
  tail: TokenNode[]
  found: boolean
}

function splitText(token: TokenNode, value: string): IndentSplit {
  const indent = value.search(NOT_INDENT)
  if (indent < 0) {
    return { head: [token], tail: [], found: false }
  }
  return {
    head: indent > 0 ? [{ ...token, value: value.slice(0, indent) }] : [],
    tail: [{ ...token, value: value.slice(indent) }],
    found: true,
  }
}

function splitTokenIndent(token: TokenNode): IndentSplit {
  if (typeof token.value === 'string') {
    return splitText(token, token.value)
  }
  const inner = splitIndent(token.children ?? [])
  if (!inner.found) {
    return { head: [token], tail: [], found: false }
  }
  return {
    head: inner.head.length > 0 ? [{ ...token, children: inner.head }] : [],
    tail: [{ ...token, children: inner.tail }],
    found: true,
  }
}

function splitIndent(tokens: TokenNode[]): IndentSplit {
  for (const [index, token] of tokens.entries()) {
    const split = splitTokenIndent(token)
    if (split.found) {
      return { head: [...tokens.slice(0, index), ...split.head], tail: [...split.tail, ...tokens.slice(index + 1)], found: true }
    }
  }
  return { head: tokens, tail: [], found: false }
}

export function hangingIndent(line: TokenNode[]): TokenNode[] {
  const { head, tail, found } = splitIndent(line)
  if (!found || head.length === 0) {
    return line
  }
  return [
    { type: 'indent', className: 'line-indent', children: head },
    { type: 'body', className: 'line-body', children: tail },
  ]
}

export function withHangingIndent(tokens: HunkTokens): HunkTokens {
  return { old: tokens.old.map(hangingIndent), new: tokens.new.map(hangingIndent) }
}
