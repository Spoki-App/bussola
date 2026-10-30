import type { ReactNode } from 'react'

import type { Unit } from '../api/types'
import type { UnitNode } from '../review/unitTree'
import { KindBadge } from './Badges'
import { QualifiedName } from './QualifiedName'

interface Props {
  nodes: UnitNode[]
  renderUnit: (unit: Unit, nested: boolean) => ReactNode
  module: string | null
  nested?: boolean
}

export function UnitTree({ nodes, renderUnit, module, nested = false }: Props) {
  return (
    <>
      {nodes.map((node) => {
        if (node.kind === 'unit') {
          return renderUnit(node.unit, nested)
        }
        return (
          <div key={`class-${node.name}`} className="class-group">
            {node.unit ? renderUnit(node.unit, nested) : <ClassStandIn name={node.name} module={module} kind={node.standIn} nested={nested} />}
            <div className="unit-children">
              <UnitTree nodes={node.children} renderUnit={renderUnit} module={module} nested />
            </div>
          </div>
        )
      })}
    </>
  )
}

function ClassStandIn({ name, module, kind, nested }: { name: string; module: string | null; kind: string; nested: boolean }) {
  return (
    <article className="unit-card class-stand-in">
      <header className="unit-header">
        <KindBadge kind={kind} />
        <QualifiedName module={module} name={name} nested={nested} />
        <span className="label">{kind === 'type' ? 'only its methods changed here' : 'no changes outside its methods'}</span>
      </header>
    </article>
  )
}
