import type { ReactNode } from 'react'

import type { Unit } from '../api/types'
import type { UnitNode } from '../review/unitTree'
import { firstUnit, lastSegment } from '../review/unitTree'
import { KindBadge } from './Badges'
import { QualifiedName } from './QualifiedName'

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
            {node.unit ? renderUnit(node.unit, nested) : <ClassStandIn name={node.name} module={firstUnit(node.children)?.module ?? null} kind={node.standIn} nested={nested} />}
            <div className="unit-children">
              <UnitTree nodes={node.children} renderUnit={renderUnit} nested />
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
        {nested ? (
          <span className="unit-name" title={name}>
            {lastSegment(name)}
          </span>
        ) : (
          <QualifiedName module={module} name={name} />
        )}
        <span className="label">{kind === 'type' ? 'only its methods changed here' : 'no changes outside its methods'}</span>
      </header>
    </article>
  )
}
