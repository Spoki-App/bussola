import type { HunkTokens, TokenNode } from 'react-diff-view'

const NOT_INDENT = /[^ \t]/

function textOf(token: TokenNode): string {
  if (typeof token.value === 'string') {
    return token.value
  }
  return (token.children ?? []).map(textOf).join('')
}

function splitToken(token: TokenNode, offset: number): [TokenNode, TokenNode] {
  if (typeof token.value === 'string') {
    return [
      { ...token, value: token.value.slice(0, offset) },
      { ...token, value: token.value.slice(offset) },
    ]
  }
  const [head, tail] = splitTokens(token.children ?? [], offset)
  return [
    { ...token, children: head },
    { ...token, children: tail },
  ]
}

function splitTokens(tokens: TokenNode[], offset: number): [TokenNode[], TokenNode[]] {
  let remaining = offset
  for (const [index, token] of tokens.entries()) {
    const length = textOf(token).length
    if (length === remaining) {
      return [tokens.slice(0, index + 1), tokens.slice(index + 1)]
    }
    if (length > remaining) {
      const [head, tail] = splitToken(token, remaining)
      return [
        [...tokens.slice(0, index), head],
        [tail, ...tokens.slice(index + 1)],
      ]
    }
    remaining -= length
  }
  return [tokens, []]
}

export function hangingIndent(line: TokenNode[]): TokenNode[] {
  const indent = line.map(textOf).join('').search(NOT_INDENT)
  if (indent <= 0) {
    return line
  }
  const [head, tail] = splitTokens(line, indent)
  return [
    { type: 'indent', className: 'line-indent', children: head },
    { type: 'body', className: 'line-body', children: tail },
  ]
}

export function withHangingIndent(tokens: HunkTokens): HunkTokens {
  return { old: tokens.old.map(hangingIndent), new: tokens.new.map(hangingIndent) }
}
