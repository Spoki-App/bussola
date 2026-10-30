import type { HunkTokens, TokenNode } from 'react-diff-view'

const LEADING_WHITESPACE = /^[ \t]*/

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
  const head: TokenNode[] = []
  const tail: TokenNode[] = []
  let remaining = offset
  for (const token of tokens) {
    const length = textOf(token).length
    if (remaining <= 0) {
      tail.push(token)
    } else if (length <= remaining) {
      head.push(token)
    } else {
      const [left, right] = splitToken(token, remaining)
      head.push(left)
      tail.push(right)
    }
    remaining -= length
  }
  return [head, tail]
}

export function hangingIndent(line: TokenNode[]): TokenNode[] {
  const text = line.map(textOf).join('')
  const indent = LEADING_WHITESPACE.exec(text)?.[0].length ?? 0
  if (indent === 0 || indent === text.length) {
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
