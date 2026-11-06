import type { SourceLine } from '../review/sourceLines'

export function LineCode({ tokens }: { tokens: SourceLine }) {
  return tokens.map((token, index) =>
    token.className ? (
      <span key={index} className={token.className}>
        {token.text}
      </span>
    ) : (
      token.text
    ),
  )
}
