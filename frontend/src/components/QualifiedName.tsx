import { fullName } from '../review/unitSearch'
import { lastSegment, parentName } from '../review/unitTree'

interface Props {
  module: string | null
  name: string
}

export function QualifiedName({ module, name }: Props) {
  const parent = parentName(name)
  return (
    <span className="qualified-name" title={fullName(module, name)}>
      {module && <span className="unit-module muted">{`${module}.`}</span>}
      {parent && <span className="unit-parent">{`${parent}.`}</span>}
      <span className="unit-name">{lastSegment(name)}</span>
    </span>
  )
}
