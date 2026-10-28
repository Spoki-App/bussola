import type { Review } from '../api/types'

export function ReviewTitle({ review }: { review: Review }) {
  const pull = review.pull_request
  if (!pull) {
    return (
      <>
        <code>{review.head_ref}</code> <span className="muted">into</span> <code>{review.base_ref}</code>
      </>
    )
  }
  return (
    <>
      <span className="pr-number">{`#${String(pull.number)}`}</span> {pull.title ?? 'Pull request'} <span className="muted">into</span> <code>{review.base_ref}</code>
      {pull.state && pull.state !== 'OPEN' && <span className="badge state-removed pr-state">{pull.state.toLowerCase()}</span>}
    </>
  )
}
