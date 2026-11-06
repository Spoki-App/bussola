import { describeError } from '../api/client'
import { useComparison } from '../api/compare'
import type { CodeRange, ComparisonRequest } from '../api/types'
import { useModalDialog } from '../hooks/useModalDialog'
import { unitTitle } from '../review/logic'
import { rangeLocation } from '../review/moves'
import { ErrorNote } from './Badges'
import { UnitDiffView } from './UnitDiffView'

interface Props {
  reviewId: number
  request: ComparisonRequest
  onClose: () => void
}

const IDENTICAL_TITLE = 'Same code, ignoring indentation and blank lines'

function RangeHeading({ range }: { range: CodeRange }) {
  return (
    <p className="compare-range">
      <code>{unitTitle(range)}</code>
      <span className="muted">{range.side === 'base' ? `${rangeLocation(range)} (base)` : rangeLocation(range)}</span>
    </p>
  )
}

export function CompareDialog({ reviewId, request, onClose }: Props) {
  const { ref, close } = useModalDialog()
  const comparison = useComparison(reviewId, request)
  const data = comparison.data
  return (
    <dialog ref={ref} className="picker compare-dialog" aria-labelledby="compare-dialog-title" onClose={onClose}>
      <header className="picker-header">
        <div className="compare-title">
          <h2 id="compare-dialog-title">Compare</h2>
          {data?.identical === true && (
            <span className="label move-identical" title={IDENTICAL_TITLE}>
              identical
            </span>
          )}
          {data?.identical === false && <span className="label">changed</span>}
        </div>
        <button type="button" className="link" data-autofocus onClick={close}>
          Close
        </button>
      </header>
      {comparison.isPending && <p className="muted">Loading comparison...</p>}
      {comparison.error && <ErrorNote message={describeError(comparison.error)} />}
      {data && (
        <>
          <div className="compare-sides">
            <RangeHeading range={data.left} />
            <RangeHeading range={data.right} />
          </div>
          <div className="compare-view">
            <UnitDiffView diff={data} path={data.right.path} viewType="split" selectable={false} />
          </div>
        </>
      )}
    </dialog>
  )
}
