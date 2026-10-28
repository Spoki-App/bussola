import type { ReactNode } from 'react'

import type { Unit } from '../api/types'
import type { UnitNode } from '../review/unitTree'
import { lastSegment } from '../review/unitTree'
import { KindBadge } from './Badges'

interface Props {
  nodes: UnitNode[]
  renderUnit: (unit: Unit, nested: boolean) => ReactNode
  nested?: boolean
}

export function UnitTree({ nodes, renderUnit, nested = false }: Props) {
  return (
    <>
      {nodes.map((node) => {
        if (node.kind === 'unit') {
          return renderUnit(node.unit, nested)
        }
        return (
          <div key={`class-${node.name}`} className="class-group">
            {node.unit ? renderUnit(node.unit, nested) : <ClassStandIn name={node.name} nested={nested} />}
            <div className="unit-children">
              <UnitTree nodes={node.children} renderUnit={renderUnit} nested />
            </div>
          </div>
        )
      })}
    </>
  )
}

function ClassStandIn({ name, nested }: { name: string; nested: boolean }) {
  return (
    <article className="unit-card class-stand-in">
      <header className="unit-header">
        <KindBadge kind="class" />
        <span className="unit-name" title={name}>
          {nested ? lastSegment(name) : name}
        </span>
        <span className="label">no changes outside its methods</span>
      </header>
    </article>
  )
}
