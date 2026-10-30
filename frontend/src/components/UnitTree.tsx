import type { ReactNode } from 'react'

import type { Unit } from '../api/types'
import type { UnitNode } from '../review/unitTree'
import { KindBadge } from './Badges'
import { QualifiedName } from './QualifiedName'

interface Props {
  nodes: UnitNode[]
  renderUnit: (unit: Unit) => ReactNode
  module: string | null
}

export function UnitTree({ nodes, renderUnit, module }: Props) {
  return (
    <>
      {nodes.map((node) => {
        if (node.kind === 'unit') {
          return renderUnit(node.unit)
        }
        return (
          <div key={`class-${node.name}`} className="class-group">
            {node.unit ? renderUnit(node.unit) : <ClassStandIn name={node.name} module={module} kind={node.standIn} />}
            <div className="unit-children">
              <UnitTree nodes={node.children} renderUnit={renderUnit} module={module} />
            </div>
          </div>
        )
      })}
    </>
  )
}

function ClassStandIn({ name, module, kind }: { name: string; module: string | null; kind: string }) {
  return (
    <article className="unit-card class-stand-in">
      <header className="unit-header">
        <KindBadge kind={kind} />
        <QualifiedName module={module} name={name} />
        <span className="label">{kind === 'type' ? 'only its methods changed here' : 'no changes outside its methods'}</span>
      </header>
    </article>
  )
}
