import type { ComparisonRequest } from '../api/types'
import { moveTitle, rangeName, type MoveLink } from '../review/moves'

interface Props {
  links: MoveLink[]
  onCompare: (request: ComparisonRequest) => void
}

export function MoveLinks({ links, onCompare }: Props) {
  return links.map((link) => (
    <button
      key={`${link.direction}:${String(link.other.unit_id)}:${String(link.other.line_offset)}`}
      type="button"
      className="move-link"
      title={moveTitle(link)}
      onClick={(event) => {
        event.stopPropagation()
        onCompare(link.comparison)
      }}
    >
      {`moved ${link.direction} `}
      <code>{rangeName(link.other)}</code>
      {link.identical && <span className="move-identical">identical</span>}
    </button>
  ))
}
