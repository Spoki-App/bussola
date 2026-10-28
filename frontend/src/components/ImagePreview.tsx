import { useState } from 'react'

import type { Unit } from '../api/types'
import { imageUrl } from '../review/images'

type Side = 'base' | 'head'

const SIDE_LABELS: Record<Side, string> = { base: 'Before', head: 'After' }

function ImageSide({ reviewId, unit, side }: { reviewId: number; unit: Unit; side: Side }) {
  const [size, setSize] = useState<string | null>(null)
  const [failed, setFailed] = useState(false)
  return (
    <figure className={`image-side image-${side}`}>
      <figcaption>
        {SIDE_LABELS[side]}
        {size && <span className="muted">{` · ${size}`}</span>}
      </figcaption>
      {failed ? (
        <p className="muted">This image could not be shown.</p>
      ) : (
        <img
          src={imageUrl(reviewId, unit.id, side)}
          alt={`${unit.path} ${SIDE_LABELS[side].toLowerCase()}`}
          onLoad={(event) => { setSize(`${String(event.currentTarget.naturalWidth)} × ${String(event.currentTarget.naturalHeight)}`) }}
          onError={() => { setFailed(true) }}
        />
      )}
    </figure>
  )
}

export function ImagePreview({ reviewId, unit }: { reviewId: number; unit: Unit }) {
  const sides: Side[] = unit.change_type === 'added' ? ['head'] : unit.change_type === 'removed' ? ['base'] : ['base', 'head']
  return (
    <div className="image-preview">
      {sides.map((side) => (
        <ImageSide key={side} reviewId={reviewId} unit={unit} side={side} />
      ))}
    </div>
  )
}
