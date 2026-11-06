import { describeError } from '../api/client'
import { useComparison } from '../api/compare'
import type { CodeRange, ComparisonRequest } from '../api/types'
import { useModalDialog } from '../hooks/useModalDialog'
import { rangeLines, rangeName } from '../review/moves'
import { ErrorNote } from './Badges'
import { UnitDiffView } from './UnitDiffView'

interface Props {
  reviewId: number
  request: ComparisonRequest
  onClose: () => void
}

const NOTHING_SELECTED: ReadonlySet<string> = new Set()
const IDENTICAL_TITLE = 'Same code, ignoring indentation and blank lines'

function ignore() {}

function RangeHeading({ range }: { range: CodeRange }) {
  return (
    <p className="compare-range">
      <code>{rangeName(range)}</code>
      <span className="muted">{[range.path, rangeLines(range), range.side === 'base' ? '(base)' : ''].filter(Boolean).join(' ')}</span>
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
          {data && (
            <span className={data.identical ? 'label move-identical' : 'label'} title={data.identical ? IDENTICAL_TITLE : undefined}>
              {data.identical ? 'identical' : 'changed'}
            </span>
          )}
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
            <UnitDiffView diff={{ ...data, binary: false }} path={data.right.path} viewType="split" selectable={false} selected={NOTHING_SELECTED} onRowClick={ignore} />
          </div>
        </>
      )}
    </dialog>
  )
}
